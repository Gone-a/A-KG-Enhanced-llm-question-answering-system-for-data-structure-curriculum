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

# 添加DeepKE路径
sys.path.append('/root/KG_inde/DeepKE/src')
sys.path.append('/root/KG_inde/DeepKE/example/re/standard')
warnings.filterwarnings("ignore")

# 导入DeepKE相关模块
from transformers import AutoTokenizer
from deepke.name_entity_re.standard.w2ner.model import Model
from deepke.relation_extraction.standard.tools import *
import deepke.relation_extraction.standard.models as models

class TimeoutError(Exception):
    """自定义超时异常"""
    pass

def timeout_handler(signum, frame):
    """超时处理函数"""
    raise TimeoutError("操作超时")

class OptimizedKnowledgeGraphBuilder:
    def __init__(self, txt_file_path: str, output_dir: str = "data/optimized_output"):
        self.txt_file_path = txt_file_path
        self.output_dir = output_dir
        self.ner_model_path = "/root/KG_inde/DeepKE/example/ner/standard/w2ner"
        self.re_model_path = "/root/KG_inde/DeepKE/example/re/standard"
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化模型
        self.ner_model = None
        self.re_model = None
        self.load_models()
    
    def load_models(self):
        """加载NER和RE模型"""
        print("正在加载NER模型...")
        self.load_ner_model()
        print("NER模型加载完成")
        
        print("正在加载RE模型...")
        self.load_re_model()
        print("RE模型加载完成")
    
    def load_ner_model(self):
        """加载W2NER模型"""
        # 切换到NER模型目录
        original_cwd = os.getcwd()
        os.chdir(self.ner_model_path)
        
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
        
        # 创建配置对象并设置默认值
        config = type('Config', (), {})()
        
        # 设置必需的配置参数
        default_config = {
            'bert_name': 'bert-base-chinese',
            'do_lower_case': True,
            'dist_emb_size': 20,
            'type_emb_size': 20,
            'lstm_hid_size': 512,
            'conv_hid_size': 96,
            'bert_hid_size': 768,
            'biaffine_size': 512,
            'ffnn_hid_size': 288,
            'dilation': [1, 2, 3],
            'emb_dropout': 0.5,
            'conv_dropout': 0.5,
            'out_dropout': 0.33,
            'max_seq_len': 128,
            'use_bert_last_4_layers': True,
            'device': 'cpu'
        }
        
        # 合并配置
        default_config.update(cfg)
        
        for key, value in default_config.items():
            config.__setattr__(key, value)
        
        # 修正词汇表路径 - 使用output目录下的文件
        vocab_path = os.path.join(self.ner_model_path, 'output/vocab.pkl')
        with open(vocab_path, 'rb') as f:
            vocab = pickle.load(f)
        
        config.label_num = len(vocab.label2id)
        
        # 加载模型
        model = Model(config)
        model_path = os.path.join(self.ner_model_path, 'output/pytorch_model.bin')
        model.load_state_dict(torch.load(model_path, map_location='cpu'))
        model.eval()
        
        # 加载tokenizer
        tokenizer = AutoTokenizer.from_pretrained(config.bert_name)
        
        self.ner_model = {
            'model': model,
            'config': config,
            'vocab': vocab,
            'tokenizer': tokenizer
        }
        
        # 恢复工作目录
        os.chdir(original_cwd)
    
    def load_re_model(self):
        """加载RE模型"""
        # 切换到RE模型目录
        original_cwd = os.getcwd()
        os.chdir(self.re_model_path)
        
        # 加载配置 - 需要合并多个配置文件
        config_path = os.path.join(self.re_model_path, 'conf/config.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        
        # 加载模型配置
        model_config_path = os.path.join(self.re_model_path, 'conf/model/transformer.yaml')
        with open(model_config_path, 'r', encoding='utf-8') as f:
            model_cfg = yaml.safe_load(f)
        
        # 加载embedding配置
        embedding_config_path = os.path.join(self.re_model_path, 'conf/embedding.yaml')
        with open(embedding_config_path, 'r', encoding='utf-8') as f:
            embedding_cfg = yaml.safe_load(f)
        
        # 加载train配置
        train_config_path = os.path.join(self.re_model_path, 'conf/train.yaml')
        with open(train_config_path, 'r', encoding='utf-8') as f:
            train_cfg = yaml.safe_load(f)
        
        # 加载preprocess配置
        preprocess_config_path = os.path.join(self.re_model_path, 'conf/preprocess.yaml')
        with open(preprocess_config_path, 'r', encoding='utf-8') as f:
            preprocess_cfg = yaml.safe_load(f)
        
        # 加载predict配置
        predict_config_path = os.path.join(self.re_model_path, 'conf/predict.yaml')
        with open(predict_config_path, 'r', encoding='utf-8') as f:
            predict_cfg = yaml.safe_load(f)
        
        # 合并配置
        cfg.update(model_cfg)
        cfg.update(embedding_cfg)
        cfg.update(train_cfg)
        cfg.update(preprocess_cfg)
        cfg.update(predict_cfg)
        
        # 确保数值类型参数正确转换
        if 'layer_norm_eps' in cfg:
            cfg['layer_norm_eps'] = float(cfg['layer_norm_eps'])
        if 'dropout' in cfg:
            cfg['dropout'] = float(cfg['dropout'])
        if 'hidden_size' in cfg:
            cfg['hidden_size'] = int(cfg['hidden_size'])
        if 'num_heads' in cfg:
            cfg['num_heads'] = int(cfg['num_heads'])
        if 'num_hidden_layers' in cfg:
            cfg['num_hidden_layers'] = int(cfg['num_hidden_layers'])
        if 'intermediate_size' in cfg:
            cfg['intermediate_size'] = int(cfg['intermediate_size'])
        
        # 加载关系映射 - 从relation.csv文件中读取
        relation_path = os.path.join(self.re_model_path, 'data/origin/relation.csv')
        relation_df = pd.read_csv(relation_path)
        
        # 构建关系映射
        rels = {}
        id2rel = {}
        for _, row in relation_df.iterrows():
            rel_name = row['relation']
            rel_id = row['index']
            rels[rel_name] = rel_id
            id2rel[rel_id] = rel_name
        
        # 加载词汇表
        vocab_path = os.path.join(self.re_model_path, 'data/out/vocab.pkl')
        with open(vocab_path, 'rb') as f:
            vocab_data = pickle.load(f)
        
        # 设置必要的配置参数 - 使用训练时的实际参数
        cfg['vocab_size'] = 3432  # 从错误信息中获取的实际vocab大小
        cfg['pos_size'] = 62  # 从错误信息中获取的实际pos大小
        
        # 加载模型
        __Model__ = {
            'cnn': models.PCNN,
            'rnn': models.BiLSTM,
            'transformer': models.Transformer,
            'gcn': models.GCN,
            'capsule': models.Capsule,
            'lm': models.LM,
        }
        
        # 将配置转换为对象形式，以便模型可以使用点号访问
        class Config:
            def __init__(self, config_dict):
                for key, value in config_dict.items():
                    setattr(self, key, value)
                # 创建model子对象，包含模型相关配置
                self.model = type('Model', (), {})()
                for key in ['hidden_size', 'num_heads', 'num_hidden_layers', 'intermediate_size', 
                           'dropout', 'layer_norm_eps', 'hidden_act', 'output_attentions', 'output_hidden_states']:
                    if key in config_dict:
                        setattr(self.model, key, config_dict[key])
        
        config_obj = Config(cfg)
        
        device = torch.device('cpu')
        model = __Model__[cfg['model_name']](config_obj)
        
        # 查找模型文件
        model_files = [f for f in os.listdir('.') if f.endswith('.pth') or f.endswith('.pt')]
        if model_files:
            model_path = model_files[0]
        else:
            model_path = cfg.get('fp', 'checkpoints/model.pth')
        
        if os.path.exists(model_path):
            model.load(model_path, device=device)
        
        model.to(device)
        model.eval()
        
        self.re_model = {
            'model': model,
            'config': cfg,
            'rels': rels,
            'id2rel': id2rel,
            'device': device,
            'vocab': vocab_data
        }
        
        # 恢复工作目录
        os.chdir(original_cwd)
    
    def run_ner_prediction(self, sentences: List[str]) -> List[Dict]:
        """使用W2NER模型进行命名实体识别"""
        print("正在使用W2NER模型进行NER预测...")
        
        results = []
        model = self.ner_model['model']
        config = self.ner_model['config']
        vocab = self.ner_model['vocab']
        tokenizer = self.ner_model['tokenizer']
        
        # 构建正确的距离映射（与W2NER模型一致）- 只构建一次
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
        
        # 预先导入decode函数，避免在循环中重复导入
        from deepke.name_entity_re.standard.w2ner.utils import decode
        
        # 批量处理优化 - 进一步减小批处理大小
        batch_size = 8  # 从16进一步减小到8
        
        for i in range(0, len(sentences), batch_size):
            batch_sentences = sentences[i:i+batch_size]
            batch_results = []
            
            for sentence in batch_sentences:
                try:
                    # 预处理句子
                    entity_text = list(sentence.strip())
                    length = len(entity_text)
                    
                    if length == 0:
                        batch_results.append({'sentence': sentence, 'entities': []})
                        continue
                    
                    # 限制最大长度以节省内存 - 进一步减小
                    max_length = 128  # 从256进一步减小到128
                    if length > max_length:
                        entity_text = entity_text[:max_length]
                        length = max_length
                    
                    # 分词 - 添加异常处理
                    try:
                        tokens = [tokenizer.tokenize(word) for word in entity_text]
                        pieces = [piece for pieces in tokens for piece in pieces]
                        
                        # 检查pieces长度，避免过长序列
                        if len(pieces) > 500:  # 限制BERT输入长度
                            pieces = pieces[:500]
                    except Exception as e:
                        print(f"分词错误: {e}")
                        batch_results.append({'sentence': sentence, 'entities': []})
                        continue
                    
                    # 转换为BERT输入
                    bert_inputs = tokenizer.convert_tokens_to_ids(pieces)
                    bert_inputs = np.array([tokenizer.cls_token_id] + bert_inputs + [tokenizer.sep_token_id])
                    
                    # 构建pieces2word映射
                    pieces2word = np.zeros((length, len(bert_inputs)), dtype=np.bool_)
                    if tokenizer is not None:
                        start = 0
                        for j, pieces_tokens in enumerate(tokens):
                            if len(pieces_tokens) == 0:
                                continue
                            pieces_range = list(range(start, start + len(pieces_tokens)))
                            if pieces_range and pieces_range[-1] + 1 < len(bert_inputs):
                                pieces2word[j, pieces_range[0] + 1:pieces_range[-1] + 2] = 1
                            start += len(pieces_tokens)
                    
                    # 构建距离输入 - 进一步优化，使用向量化操作
                    dist_inputs = np.zeros((length, length), dtype=np.int32)
                    
                    # 使用向量化操作计算距离矩阵
                    indices = np.arange(length)
                    distance_matrix = np.abs(indices[:, None] - indices[None, :])
                    
                    # 使用向量化的dis2idx查找
                    dist_inputs = np.where(distance_matrix < 1000, 
                                         dis2idx[distance_matrix], 
                                         9)
                    
                    # 构建grid_mask2d
                    grid_mask2d = np.ones((length, length), dtype=np.bool_)
                    
                    # 转换为tensor并进行预测
                    with torch.no_grad():
                        try:
                            bert_inputs_tensor = torch.tensor([bert_inputs], dtype=torch.long)
                            grid_mask2d_tensor = torch.tensor([grid_mask2d], dtype=torch.bool)
                            dist_inputs_tensor = torch.tensor([dist_inputs], dtype=torch.long)
                            pieces2word_tensor = torch.tensor([pieces2word], dtype=torch.bool)
                            sent_length_tensor = torch.tensor([length], dtype=torch.long)
                            
                            # 模型预测 - 添加超时保护
                            outputs = model(bert_inputs_tensor, grid_mask2d_tensor, dist_inputs_tensor, 
                                          pieces2word_tensor, sent_length_tensor)
                            
                            # 解码结果
                            outputs = torch.argmax(outputs, -1)
                            
                            # 创建空的entity_text集合用于decode函数
                            entity_text_set = set()
                            
                            # 调用decode函数
                            ent_c, ent_p, ent_r, decode_entities = decode(
                                outputs.cpu().numpy(), 
                                [entity_text_set], 
                                sent_length_tensor.cpu().numpy()
                            )
                            
                            # 解析decode结果
                            entities = []
                            if decode_entities and len(decode_entities) > 0:
                                for entity_info in decode_entities[0]:
                                    index_list, type_id = entity_info
                                    if type_id in vocab.id2label:
                                        entity_text_str = ''.join([entity_text[i] for i in index_list])
                                        entity_label = vocab.id2label[type_id]
                                        entities.append({
                                            'text': entity_text_str,
                                            'label': entity_label,
                                            'start': min(index_list),
                                            'end': max(index_list) + 1
                                        })
                            
                            batch_results.append({
                                'sentence': sentence,
                                'entities': entities
                            })
                            
                        except Exception as e:
                            print(f"模型预测错误: {e}")
                            batch_results.append({'sentence': sentence, 'entities': []})
                            continue
                            
                except Exception as e:
                    print(f"处理句子时出错: {e}")
                    batch_results.append({'sentence': sentence, 'entities': []})
                    continue
            
            results.extend(batch_results)
            
            # 强制清理内存
            del batch_results
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # 添加进度信息
            if i % (batch_size * 10) == 0:
                print(f"已处理 {i + len(batch_sentences)} / {len(sentences)} 个句子")
        
        return results
    
    def _preprocess_single_sample(self, sample, vocab, config):
        """单样本预处理函数"""
        from deepke.relation_extraction.standard.tools import Serializer
        from deepke.relation_extraction.standard.tools import _serialize_sentence, _convert_tokens_into_index, _add_pos_seq, _lm_serialize
        from transformers import BertTokenizer
        
        # 创建单个样本的数据列表
        data = [sample]
        
        # 创建配置对象，添加必要的属性
        class Config:
            def __init__(self, config_dict):
                for key, value in config_dict.items():
                    setattr(self, key, value)
                # 添加必要的默认属性
                if not hasattr(self, 'model'):
                    self.model = type('Model', (), {'model_name': config_dict.get('model_name', 'cnn')})()
                if not hasattr(self, 'pos_limit'):
                    self.pos_limit = 25
                if not hasattr(self, 'replace_entity_with_type'):
                    self.replace_entity_with_type = False
                if not hasattr(self, 'replace_entity_with_scope'):
                    self.replace_entity_with_scope = False
                if not hasattr(self, 'use_pcnn'):
                    self.use_pcnn = False
                if not hasattr(self, 'lm_file'):
                    self.lm_file = 'bert-base-chinese'
        
        cfg = Config(config)
        
        if config.get('model_name') == 'lm':
            # 使用BERT tokenizer处理
            _lm_serialize(data, cfg)
        else:
            # 使用传统方式处理
            serializer = Serializer(do_chinese_split=config.get('chinese_split', True), do_lower_case=True)
            serial = serializer.serialize
            _serialize_sentence(data, serial, cfg)
            _convert_tokens_into_index(data, vocab)
            _add_pos_seq(data, cfg)
        
        return data[0]
    
    def run_re_prediction(self, ner_results: List[Dict]) -> List[Dict]:
        """使用RE模型进行关系抽取"""
        print("正在使用RE模型进行关系抽取...")
        
        relations = []
        model = self.re_model['model']
        config = self.re_model['config']
        rels = self.re_model['rels']
        device = self.re_model['device']
        vocab = self.re_model['vocab']
        
        id2rel = self.re_model['id2rel']
        
        # 过滤出有实体的结果，提高效率
        valid_results = [result for result in ner_results if len(result['entities']) >= 2]
        
        if not valid_results:
            print("没有找到足够的实体对进行关系抽取")
            return relations
        
        # 批量处理实体对
        entity_pairs = []
        for ner_result in valid_results:
            sentence = ner_result['sentence']
            entities = ner_result['entities']
            
            # 为每对实体创建关系抽取任务
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    entity_pairs.append({
                        'sentence': sentence,
                        'head_entity': entities[i],
                        'tail_entity': entities[j]
                    })
        
        if not entity_pairs:
            print("没有找到有效的实体对")
            return relations
        
        # 批量处理实体对 - 减小批处理大小
        batch_size = 32  # 从64减小到32
        
        for i in range(0, len(entity_pairs), batch_size):
            batch_pairs = entity_pairs[i:i+batch_size]
            
            for pair in batch_pairs:
                try:
                    sentence = pair['sentence']
                    head_entity = pair['head_entity']
                    tail_entity = pair['tail_entity']
                    
                    # 构建输入数据
                    head_start = head_entity['start']
                    head_end = head_entity['end']
                    tail_start = tail_entity['start']
                    tail_end = tail_entity['end']
                    
                    # 创建输入样本
                    sample = {
                        'sentence': sentence,
                        'head': head_entity['text'],
                        'tail': tail_entity['text'],
                        'head_offset': [head_start, head_end],
                        'tail_offset': [tail_start, tail_end],
                        'relation': 'NA',  # 预测时使用默认值
                        'head_type': 'ENTITY',  # 添加默认实体类型
                        'tail_type': 'ENTITY'   # 添加默认实体类型
                    }
                    
                    # 使用RE模型进行预测
                    with torch.no_grad():
                        # 预处理输入 - 使用正确的单样本预处理方式
                        processed_sample = self._preprocess_single_sample(sample, vocab, config)
                        
                        # 确保序列长度不超过512，并进行填充
                        max_len = 512
                        seq_len = processed_sample['seq_len']
                        
                        # 截断或填充到固定长度
                        if len(processed_sample['token2idx']) > max_len:
                            processed_sample['token2idx'] = processed_sample['token2idx'][:max_len]
                            seq_len = max_len
                        elif len(processed_sample['token2idx']) < max_len:
                            processed_sample['token2idx'] = processed_sample['token2idx'] + [0] * (max_len - len(processed_sample['token2idx']))
                        
                        # 转换为tensor
                        input_ids = torch.tensor([processed_sample['token2idx']], dtype=torch.long).to(device)
                        
                        # 对于非LM模型，还需要位置信息
                        if config.get('model_name') != 'lm':
                            # 截断或填充head_pos和tail_pos
                            head_pos_list = processed_sample['head_pos']
                            tail_pos_list = processed_sample['tail_pos']
                            
                            if len(head_pos_list) > max_len:
                                head_pos_list = head_pos_list[:max_len]
                                tail_pos_list = tail_pos_list[:max_len]
                            elif len(head_pos_list) < max_len:
                                head_pos_list = head_pos_list + [0] * (max_len - len(head_pos_list))
                                tail_pos_list = tail_pos_list + [0] * (max_len - len(tail_pos_list))
                            
                            head_pos = torch.tensor([head_pos_list], dtype=torch.long).to(device)
                            tail_pos = torch.tensor([tail_pos_list], dtype=torch.long).to(device)
                        
                        # 模型预测
                        if config.get('model_name') == 'lm':
                            # LM模型只需要input_ids和lens
                            x = {
                                'word': input_ids,
                                'lens': torch.tensor([seq_len], dtype=torch.long).to(device)
                            }
                            outputs = model(x)
                        else:
                            # 其他模型需要word, lens, head_pos, tail_pos
                            x = {
                                'word': input_ids,
                                'lens': torch.tensor([seq_len], dtype=torch.long).to(device),
                                'head_pos': head_pos,
                                'tail_pos': tail_pos
                            }
                            # 如果是GCN模型，还需要adj矩阵
                            if config.get('model_name') == 'gcn':
                                B, L = 1, max_len
                                adj = torch.empty(B, L, L).random_(2).to(device)
                                x['adj'] = adj
                            # 如果是PCNN模型且使用pcnn，还需要pcnn_mask
                            elif config.get('model_name') == 'cnn' and config.get('use_pcnn', False):
                                # 处理pcnn_mask
                                if 'entities_pos' in processed_sample:
                                    entities_pos = processed_sample['entities_pos']
                                    if len(entities_pos) > max_len:
                                        entities_pos = entities_pos[:max_len]
                                    elif len(entities_pos) < max_len:
                                        entities_pos = entities_pos + [1] * (max_len - len(entities_pos))
                                else:
                                    entities_pos = [1] * max_len
                                pcnn_mask = torch.tensor([entities_pos], dtype=torch.long).to(device)
                                x['pcnn_mask'] = pcnn_mask
                            
                            outputs = model(x)
                        
                        predictions = torch.nn.functional.softmax(outputs, dim=-1)
                        predicted_class = torch.argmax(predictions, dim=-1).item()
                        confidence = predictions[0][predicted_class].item()
                        
                        # 过滤低置信度预测
                        if confidence > 0.5 and predicted_class in id2rel:
                            predicted_relation = id2rel[predicted_class]
                            
                            # 过滤掉"NA"关系
                            if predicted_relation != 'NA':
                                relations.append({
                                    'sentence': sentence,
                                    'head_entity': head_entity['text'],
                                    'tail_entity': tail_entity['text'],
                                    'relation': predicted_relation,
                                    'confidence': confidence,
                                    'head_label': head_entity['label'],
                                    'tail_label': tail_entity['label']
                                })
                                
                except Exception as e:
                    print(f"RE预测错误: {e}")
                    continue
            
            # 清理内存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # 添加进度信息
            if i % (batch_size * 20) == 0:
                print(f"已处理 {i + len(batch_pairs)} / {len(entity_pairs)} 个实体对")
        
        return relations
    
    def process_txt_file(self) -> str:
        """处理文本文件并生成知识图谱"""
        print(f"开始处理文件: {self.txt_file_path}")
        
        # 设置超时信号
        signal.signal(signal.SIGALRM, timeout_handler)
        
        try:
            # 读取文件
            with open(self.txt_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 过滤空行并清理文本
            sentences = [line.strip() for line in lines if line.strip()]
            print(f"共读取到 {len(sentences)} 个句子")
            
            if not sentences:
                print("文件中没有有效的句子")
                return "处理完成，但没有找到有效内容"
            
            # 减小批处理大小，防止内存溢出
            batch_size = 20  # 从30进一步减小到20
            all_relations = []
            
            for i in tqdm(range(0, len(sentences), batch_size), desc="处理进度"):
                batch_sentences = sentences[i:i+batch_size]
                print(f"处理第 {i//batch_size + 1} 批，共 {len(batch_sentences)} 个句子")
                
                try:
                    # 设置批处理超时 (5分钟)
                    signal.alarm(300)
                    
                    # NER预测
                    start_time = time.time()
                    ner_results = self.run_ner_prediction(batch_sentences)
                    ner_time = time.time() - start_time
                    print(f"NER预测完成，耗时: {ner_time:.2f}秒")
                    
                    # 清理内存
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    gc.collect()
                    
                    # RE预测
                    start_time = time.time()
                    relations = self.run_re_prediction(ner_results)
                    re_time = time.time() - start_time
                    print(f"RE预测完成，耗时: {re_time:.2f}秒，提取到 {len(relations)} 个关系")
                    
                    all_relations.extend(relations)
                    
                    # 强制清理内存
                    del ner_results
                    del relations
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    
                    # 手动垃圾回收
                    gc.collect()
                    
                    # 取消超时设置
                    signal.alarm(0)
                    
                    # 每处理几个批次后强制垃圾回收
                    if (i // batch_size + 1) % 5 == 0:
                        print("执行深度内存清理...")
                        gc.collect()
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    
                except TimeoutError:
                    print(f"批处理 {i//batch_size + 1} 超时，跳过该批次")
                    signal.alarm(0)
                    continue
                except Exception as e:
                    print(f"处理第 {i//batch_size + 1} 批时出错: {e}")
                    signal.alarm(0)
                    continue
            
            print(f"总共提取到 {len(all_relations)} 个关系")
            
            # 保存结果
            output_file = os.path.join(self.output_dir, "optimized_knowledge_graph_results.json")
            csv_file = os.path.join(self.output_dir, "optimized_predictions.csv")
            
            # 构建结果数据
            result_data = {
                'total_sentences': len(sentences),
                'total_relations': len(all_relations),
                'relations': all_relations,
                'processing_info': {
                    'ner_model_path': self.ner_model_path,
                    're_model_path': self.re_model_path,
                    'batch_processing': True,
                    'batch_size': batch_size
                }
            }
            
            # 保存JSON文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            # 保存CSV文件
            if all_relations:
                self.save_to_csv(all_relations, csv_file)
            
            return f"处理完成！共处理 {len(sentences)} 个句子，提取 {len(all_relations)} 个关系。结果已保存到 {output_file} 和 {csv_file}"
            
        except Exception as e:
            print(f"处理文件时出错: {e}")
            return f"处理失败: {e}"
        finally:
            # 确保清理超时设置
            signal.alarm(0)
    
    def save_to_csv(self, relations: List[Dict], csv_file: str):
        """保存关系到CSV文件"""
        df = pd.DataFrame(relations)
        df.to_csv(csv_file, index=False, encoding='utf-8')

def main():
    txt_file = "/root/KG_inde/generate_data/data_backups/knowledge_graph_sentences_2.txt"
    
    if not os.path.exists(txt_file):
        print(f"错误：文件 {txt_file} 不存在")
        return
    
    builder = OptimizedKnowledgeGraphBuilder(txt_file)
    result = builder.process_txt_file()
    print(result)

if __name__ == "__main__":
    main()