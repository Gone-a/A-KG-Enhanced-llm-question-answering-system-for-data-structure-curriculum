import os
import json
import sys
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from tqdm import tqdm
import warnings
import torch
import re
import yaml
import pickle
import gc
import signal
import time
from transformers import AutoTokenizer, AutoModel, AutoConfig
from torch.utils.data import DataLoader, Dataset
from collections import defaultdict
os.environ["HF_ENDPOINT"] = "https://huggingface.co"  # 强制走官方源
# 添加DeepKE路径
sys.path.append('/root/KG_inde/DeepKE/src')
sys.path.append('/root/KG_inde/DeepKE/example/re/standard')
warnings.filterwarnings("ignore")

# 导入DeepKE相关模块
from transformers import AutoTokenizer
from deepke.name_entity_re.standard.w2ner.model import Model

class TimeoutError(Exception):
    """自定义超时异常"""
    pass

def timeout_handler(signum, frame):
    """超时处理函数"""
    raise TimeoutError("操作超时")

class NERProcessor:
    def __init__(self, txt_file_path: str, output_dir: str = "data/optimized_output"):
        self.txt_file_path = txt_file_path
        self.output_dir = output_dir
        self.ner_model_path = "/root/KG_inde/DeepKE/example/ner/standard/w2ner"
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化模型
        self.ner_model = None
        self.load_ner_model()
    
    def load_ner_model(self):
        """加载W2NER模型"""
        print("正在加载W2NER模型...")
        
        # 切换到NER模型目录
        original_cwd = os.getcwd()
        os.chdir(self.ner_model_path)
        
        try:
            # 加载所有配置文件
            config_files = ['conf/config.yaml', 'conf/model.yaml', 'conf/train.yaml']
            cfg = {}
            
            for config_file in config_files:
                config_path = os.path.join(self.ner_model_path, config_file)
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        file_cfg = yaml.safe_load(f)
                        if file_cfg:
                            cfg.update(file_cfg)
            
            # 创建配置对象
            config = type('Config', (), {})()
            
            # 从配置文件中读取的关键参数
            config.bert_name = cfg.get('bert_name', 'bert-base-chinese')
            config.do_lower_case = cfg.get('do_lower_case', True)
            config.dist_emb_size = cfg.get('dist_emb_size', 20)
            config.type_emb_size = cfg.get('type_emb_size', 20)
            config.lstm_hid_size = cfg.get('lstm_hid_size', 512)
            config.conv_hid_size = cfg.get('conv_hid_size', 96)
            config.bert_hid_size = cfg.get('bert_hid_size', 768)
            config.biaffine_size = cfg.get('biaffine_size', 512)
            config.ffnn_hid_size = cfg.get('ffnn_hid_size', 288)
            config.dilation = cfg.get('dilation', [1, 2, 3])
            config.emb_dropout = cfg.get('emb_dropout', 0.5)
            config.conv_dropout = cfg.get('conv_dropout', 0.5)
            config.out_dropout = cfg.get('out_dropout', 0.33)
            config.use_bert_last_4_layers = cfg.get('use_bert_last_4_layers', True)
            
            # 设置标签数量 - 根据W2NER的实际标签设置
            config.label_num = 8
            
            # 设置设备
            device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
            print(f"使用设备: {device}")
            
            # 加载tokenizer
            print(f"加载tokenizer: {config.bert_name}")
            bert_model_path = os.path.join(os.path.dirname(__file__), "bert-base-chinese")
            tokenizer = AutoTokenizer.from_pretrained(bert_model_path)
            
            # 设置本地BERT模型路径到config中
            config.bert_model_path = bert_model_path
            
            # 加载模型
            print("初始化W2NER模型...")
            model = Model(config)
            
            # 加载预训练权重
            weights_path = os.path.join(self.ner_model_path, 'output', 'pytorch_model.bin')
            if os.path.exists(weights_path):
                print(f"加载预训练权重: {weights_path}")
                state_dict = torch.load(weights_path, map_location=device)
                model.load_state_dict(state_dict)
                print("权重加载成功")
            else:
                print(f"警告: 未找到预训练权重文件 {weights_path}")
            
            model.to(device)
            model.eval()
            
            # 加载词汇表
            vocab_path = os.path.join(self.ner_model_path, 'output', 'vocab.pkl')
            vocab = None
            if os.path.exists(vocab_path):
                with open(vocab_path, 'rb') as f:
                    vocab = pickle.load(f)
                print("词汇表加载成功")
            
            self.ner_model = model
            self.ner_tokenizer = tokenizer
            self.ner_config = config
            self.device = device
            self.vocab = vocab
            
            print("W2NER模型加载完成")
            
        except Exception as e:
            print(f"模型加载失败: {e}")
            raise e
        finally:
            # 恢复原始工作目录
            os.chdir(original_cwd)
    
    def run_ner_prediction(self, sentences: List[str]) -> List[Dict]:
        """运行NER预测"""
        results = []
        
        # 构建距离映射（W2NER模型需要）
        dis2idx = np.zeros((1000), dtype='int64')
        dis2idx[1] = 1
        dis2idx[2:] = 2
        dis2idx[4:] = 3
        dis2idx[8:] = 4
        dis2idx[16:] = 5
        dis2idx[32:] = 6
        dis2idx[64:] = 7
        dis2idx[128:] = 8
        dis2idx[256:] = 9
        
        with torch.no_grad():
            for i, sentence in enumerate(tqdm(sentences, desc="NER预测进度")):
                if i % 100 == 0:
                    print(f"已处理 {i} / {len(sentences)} 个句子")
                
                try:
                    # 预处理句子
                    entity_text = list(sentence.strip())
                    length = len(entity_text)
                    
                    if length == 0:
                        results.append({'sentence': sentence, 'entities': []})
                        continue
                    
                    # 分词 - 修复tokenize方法调用
                    tokens = []
                    for word in entity_text:
                        if word.strip():  # 只处理非空字符
                            word_tokens = self.ner_tokenizer.tokenize(word)
                            tokens.append(word_tokens if word_tokens else [word])
                        else:
                            tokens.append([word])
                    
                    pieces = [piece for pieces in tokens for piece in pieces]
                    bert_inputs = self.ner_tokenizer.convert_tokens_to_ids(pieces)
                    bert_inputs = np.array([self.ner_tokenizer.cls_token_id] + bert_inputs + [self.ner_tokenizer.sep_token_id])
                    
                    # 构建pieces2word映射
                    pieces2word = np.zeros((length, len(bert_inputs)), dtype=np.bool_)
                    if self.ner_tokenizer is not None:
                        start = 0
                        for j, pieces_tokens in enumerate(tokens):
                            if len(pieces_tokens) == 0:
                                continue
                            pieces_range = list(range(start, start + len(pieces_tokens)))
                            if pieces_range and pieces_range[-1] + 1 < len(bert_inputs):
                                pieces2word[j, pieces_range[0] + 1:pieces_range[-1] + 2] = 1
                            start += len(pieces_tokens)
                    
                    # 构建距离输入
                    dist_inputs = np.zeros((length, length), dtype=np.int32)
                    for k in range(length):
                        dist_inputs[k, :] += k
                        dist_inputs[:, k] -= k
                    
                    for j in range(length):
                        for k in range(length):
                            if dist_inputs[j, k] < 0:
                                dist_inputs[j, k] = dis2idx[-dist_inputs[j, k]] + 9
                            else:
                                dist_inputs[j, k] = dis2idx[dist_inputs[j, k]]
                    dist_inputs[dist_inputs == 0] = 19
                    
                    # 构建grid_mask2d
                    grid_mask2d = np.ones((length, length), dtype=np.bool_)
                    sent_length = length
                    
                    # 转换为tensor
                    bert_inputs_tensor = torch.tensor([bert_inputs], dtype=torch.long).to(self.device)
                    grid_mask2d_tensor = torch.tensor([grid_mask2d], dtype=torch.bool).to(self.device)
                    dist_inputs_tensor = torch.tensor([dist_inputs], dtype=torch.long).to(self.device)
                    pieces2word_tensor = torch.tensor([pieces2word], dtype=torch.bool).to(self.device)
                    sent_length_tensor = torch.tensor([sent_length], dtype=torch.long).to(self.device)
                    
                    # 预测
                    outputs = self.ner_model(bert_inputs_tensor, grid_mask2d_tensor, dist_inputs_tensor, pieces2word_tensor, sent_length_tensor)
                    
                    # 解析实体
                    entities = self._parse_entities(outputs, entity_text, sentence)
                    
                    results.append({
                        'sentence': sentence,
                        'entities': entities
                    })
                    
                except Exception as e:
                    print(f"NER预测错误: {e}")
                    results.append({
                        'sentence': sentence,
                        'entities': []
                    })
        
        return results
    
    def _parse_entities(self, outputs, tokens, original_sentence):
        """解析实体 - 基于W2NER的输出格式"""
        entities = []
        
        try:
            # W2NER的输出是关系分类结果，需要根据关系矩阵解析实体
            predictions = torch.argmax(outputs, -1).cpu().numpy()[0]  # [seq_len, seq_len]
            seq_len = len(tokens)
            
            # W2NER的标签映射：0:<pad>, 1:<suc>, 2:con, 3:ari
            # 其中con表示连续关系，ari表示实体关系
            
            # 查找实体
            visited = set()
            
            for i in range(seq_len):
                for j in range(i, seq_len):
                    if (i, j) in visited:
                        continue
                        
                    # 检查是否为实体关系
                    if predictions[i][j] in [2, 3]:  # con或ari关系
                        # 找到实体的边界
                        entity_start = i
                        entity_end = j
                        
                        # 扩展实体边界（查找连续的con关系）
                        while entity_end + 1 < seq_len and predictions[entity_start][entity_end + 1] == 2:
                            entity_end += 1
                        
                        # 标记已访问
                        for k in range(entity_start, entity_end + 1):
                            for l in range(k, entity_end + 1):
                                visited.add((k, l))
                        
                        # 提取实体文本
                        entity_text = ''.join(tokens[entity_start:entity_end + 1])
                        
                        if len(entity_text.strip()) > 0:
                            # 在原句中查找位置
                            start_pos = original_sentence.find(entity_text)
                            if start_pos == -1:
                                # 如果直接查找失败，尝试逐字符匹配
                                start_pos = 0
                                for idx, char in enumerate(original_sentence):
                                    if char == tokens[entity_start]:
                                        temp_text = ''.join(tokens[entity_start:entity_end + 1])
                                        if original_sentence[idx:idx + len(temp_text)] == temp_text:
                                            start_pos = idx
                                            break
                            
                            end_pos = start_pos + len(entity_text)
                            
                            # 确定实体类型
                            entity_type = "ENTITY"
                            if predictions[entity_start][entity_end] == 3:  # ari关系
                                entity_type = "NAMED_ENTITY"
                            elif predictions[entity_start][entity_end] == 2:  # con关系
                                entity_type = "CONCEPT"
                            
                            entities.append({
                                'text': entity_text,
                                'start': start_pos,
                                'end': end_pos,
                                'label': entity_type,
                                'confidence': 1.0  # W2NER不提供置信度，设为1.0
                            })
        
        except Exception as e:
            print(f"实体解析错误: {e}")
            # 如果解析失败，使用简单的规则提取
            for i, token in enumerate(tokens):
                if len(token) > 1 and not token.isspace():
                    start_pos = original_sentence.find(token)
                    if start_pos != -1:
                        entities.append({
                            'text': token,
                            'start': start_pos,
                            'end': start_pos + len(token),
                            'label': 'ENTITY',
                            'confidence': 0.5
                        })
        
        return entities
    
    def process_txt_file(self) -> str:
        """处理文本文件，只进行NER预测"""
        print(f"开始处理文件: {self.txt_file_path}")
        
        # 读取文件
        with open(self.txt_file_path, 'r', encoding='utf-8') as f:
            sentences = [line.strip() for line in f if line.strip()]
        
        print(f"共读取到 {len(sentences)} 个句子")
        
        # 批量处理
        batch_size = 500
        all_ner_results = []
        
        for i in tqdm(range(0, len(sentences), batch_size), desc="处理进度"):
            batch_sentences = sentences[i:i+batch_size]
            print(f"处理第 {i//batch_size + 1} 批，共 {len(batch_sentences)} 个句子")
            
            # NER预测
            print("正在使用W2NER模型进行NER预测...")
            ner_results = self.run_ner_prediction(batch_sentences)
            all_ner_results.extend(ner_results)
            
            # 清理内存
            gc.collect()
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
        
        # 保存NER结果
        ner_output_file = os.path.join(self.output_dir, "ner_results.json")
        with open(ner_output_file, 'w', encoding='utf-8') as f:
            json.dump(all_ner_results, f, ensure_ascii=False, indent=2)
        
        print(f"NER结果已保存到: {ner_output_file}")
        return ner_output_file

def main():
    # 输入文件路径
    txt_file = "/root/KG_inde/generate_data/data_backups/knowledge_graph_sentences_2.txt"
    
    # 检查输入文件是否存在
    if not os.path.exists(txt_file):
        print(f"错误: 输入文件不存在: {txt_file}")
        return
    
    # 创建NER处理器
    processor = NERProcessor(txt_file)
    
    # 处理文本文件
    output_file = processor.process_txt_file()
    print(f"NER处理完成，结果保存在: {output_file}")

if __name__ == "__main__":
    main()
