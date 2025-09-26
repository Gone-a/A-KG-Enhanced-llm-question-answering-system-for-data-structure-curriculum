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
from deepke.relation_extraction.standard.tools import *
import deepke.relation_extraction.standard.models as models

class TimeoutError(Exception):
    """自定义超时异常"""
    pass

def timeout_handler(signum, frame):
    """超时处理函数"""
    raise TimeoutError("操作超时")

class REProcessor:
    def __init__(self, ner_results_file: str, output_dir: str = "data/optimized_output"):
        self.ner_results_file = ner_results_file
        self.output_dir = output_dir
        self.re_model_path = "/root/KG_inde/DeepKE/example/re/standard"
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化模型
        self.re_model = None
        self.load_re_model()
    
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
        
        print(f"共找到 {len(entity_pairs)} 个实体对需要进行关系抽取")
        
        # 批量处理实体对 - 减小批处理大小
        batch_size = 32  # 从64减小到32
        
        for i in tqdm(range(0, len(entity_pairs), batch_size), desc="RE预测进度"):
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
    
    def process_ner_results(self) -> str:
        """处理NER结果文件，进行关系抽取"""
        print(f"开始处理NER结果文件: {self.ner_results_file}")
        
        # 读取NER结果
        with open(self.ner_results_file, 'r', encoding='utf-8') as f:
            ner_results = json.load(f)
        
        print(f"共读取到 {len(ner_results)} 个NER结果")
        
        # 进行关系抽取
        start_time = time.time()
        relations = self.run_re_prediction(ner_results)
        end_time = time.time()
        
        print(f"RE预测完成，耗时: {end_time - start_time:.2f}秒，提取到 {len(relations)} 个关系")
        
        # 保存关系抽取结果
        relations_output_file = os.path.join(self.output_dir, "relations.json")
        with open(relations_output_file, 'w', encoding='utf-8') as f:
            json.dump(relations, f, ensure_ascii=False, indent=2)
        
        # 保存为CSV格式
        csv_output_file = os.path.join(self.output_dir, "relations.csv")
        self.save_to_csv(relations, csv_output_file)
        
        print(f"关系抽取结果已保存到: {relations_output_file}")
        print(f"CSV格式结果已保存到: {csv_output_file}")
        
        return relations_output_file
    
    def save_to_csv(self, relations: List[Dict], csv_file: str):
        """保存关系到CSV文件"""
        df = pd.DataFrame(relations)
        df.to_csv(csv_file, index=False, encoding='utf-8')

def main():
    # NER结果文件路径
    ner_results_file = "data/optimized_output/ner_results.json"
    
    # 检查NER结果文件是否存在
    if not os.path.exists(ner_results_file):
        print(f"错误: NER结果文件不存在: {ner_results_file}")
        print("请先运行 ner_only.py 生成NER结果")
        return
    
    # 创建RE处理器
    processor = REProcessor(ner_results_file)
    
    # 处理NER结果
    output_file = processor.process_ner_results()
    print(f"RE处理完成，结果保存在: {output_file}")

if __name__ == "__main__":
    main()