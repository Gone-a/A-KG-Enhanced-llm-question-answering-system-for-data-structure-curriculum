#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用w2ner模型处理JSON数据并转换为CSV格式
基于my_predict-1.py的w2ner模型调用方法
优化版本：减少内存使用和运行压力
"""

import os
import re
import json
import numpy as np
import torch
import pickle
import pandas as pd
import gc
import hashlib
from tqdm import tqdm
from multiprocessing import Pool
from functools import partial
from transformers import AutoTokenizer, logging as transformers_logging
import warnings

# 禁用不必要的警告
transformers_logging.set_verbosity_error()
warnings.filterwarnings("ignore")

# 添加DeepKE路径
import sys
sys.path.append('/root/KG_inde/DeepKE/src')
from deepke.name_entity_re.standard.w2ner import *

# 定义dis2idx（根据原始模型配置）
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

# 优化配置
OPTIMIZED_CONFIG = {
    'batch_size': 8,  # 进一步减小批处理大小
    'max_workers': os.cpu_count(),  # 进一步限制进程数
    'max_seq_len': 128,  # 在预处理时限制序列长度
    'chunk_size': 200,  # 减小分块大小
    'cache_dir': '/root/KG_inde/cache',  # 缓存目录
}

# 缓存相关函数
def get_data_hash(data):
    """计算数据的哈希值，用于缓存键"""
    data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(data_str.encode('utf-8')).hexdigest()

def get_cache_path(cache_dir, cache_key, cache_type='processed'):
    """获取缓存文件路径"""
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{cache_type}_{cache_key}.pkl")

def save_to_cache(data, cache_path):
    """保存数据到缓存"""
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
        print(f"缓存已保存: {cache_path}")
        return True
    except Exception as e:
        print(f"保存缓存失败: {e}")
        return False

def load_from_cache(cache_path):
    """从缓存加载数据"""
    try:
        if os.path.exists(cache_path):
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
            print(f"从缓存加载数据: {cache_path}")
            return data
        return None
    except Exception as e:
        print(f"加载缓存失败: {e}")
        return None

def is_cache_valid(cache_path, source_file_path):
    """检查缓存是否有效（比较修改时间和文件大小）"""
    if not os.path.exists(cache_path):
        return False
    
    if not os.path.exists(source_file_path):
        return False
    
    try:
        # 比较修改时间
        cache_mtime = os.path.getmtime(cache_path)
        source_mtime = os.path.getmtime(source_file_path)
        
        # 比较文件大小（作为额外验证）
        cache_size = os.path.getsize(cache_path)
        
        # 缓存文件必须比源文件新，且不能为空
        return cache_mtime > source_mtime and cache_size > 0
    except OSError:
        return False

def clear_cache(cache_dir=None):
    """清理缓存目录"""
    if cache_dir is None:
        cache_dir = OPTIMIZED_CONFIG['cache_dir']
    
    if os.path.exists(cache_dir):
        import shutil
        try:
            shutil.rmtree(cache_dir)
            print(f"缓存目录已清理: {cache_dir}")
            return True
        except Exception as e:
            print(f"清理缓存失败: {e}")
            return False
    return True

def get_cache_info(cache_dir=None):
    """获取缓存信息"""
    if cache_dir is None:
        cache_dir = OPTIMIZED_CONFIG['cache_dir']
    
    if not os.path.exists(cache_dir):
        return {"cache_files": 0, "total_size": 0}
    
    cache_files = 0
    total_size = 0
    
    try:
        for filename in os.listdir(cache_dir):
            if filename.endswith('.pkl'):
                filepath = os.path.join(cache_dir, filename)
                cache_files += 1
                total_size += os.path.getsize(filepath)
        
        return {
            "cache_files": cache_files,
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    except Exception as e:
        print(f"获取缓存信息失败: {e}")
        return {"cache_files": 0, "total_size": 0}

def load_vocab(vocab_path):
    """加载词汇表"""
    with open(vocab_path, 'rb') as f:
        vocab = pickle.load(f)
    return vocab

def process_sentence(sub_sent, tokenizer, max_seq_len):
    """处理单个句子并返回输入数据"""
    sub_sent = sub_sent.strip()
    if not sub_sent:
        return None
    
    try:
        # 限制句子长度以减少内存使用
        if len(sub_sent) > max_seq_len * 2:  # 粗略估计
            sub_sent = sub_sent[:max_seq_len * 2]
        
        # BERT分词
        bert_tokens = tokenizer.tokenize(sub_sent)
        if len(bert_tokens) > max_seq_len - 2:
            bert_tokens = bert_tokens[:max_seq_len - 2]
        
        bert_tokens = ['[CLS]'] + bert_tokens + ['[SEP]']
        bert_inputs = tokenizer.convert_tokens_to_ids(bert_tokens)
        
        # 构建pieces2word映射
        pieces2word = np.zeros((len(sub_sent), len(bert_inputs)), dtype=bool)
        
        # 简化的映射逻辑
        word_idx = 0
        for token_idx, token in enumerate(bert_tokens[1:-1], 1):  # 跳过[CLS]和[SEP]
            if token.startswith('##'):
                continue
            if word_idx < len(sub_sent):
                pieces2word[word_idx, token_idx] = True
                word_idx += 1
        
        return {
            'sentence': sub_sent,
            'bert_inputs': bert_inputs,
            'pieces2word': pieces2word,
            'length': len(sub_sent)
        }
    except Exception as e:
        print(f"处理句子时出错: {str(e)}")
        return None

def extract_entities_with_w2ner(sentences, model, tokenizer, max_seq_len=256, batch_size=4, cache_key=None):
    """使用w2ner模型批量提取实体（优化版本，支持缓存）"""
    
    # 检查缓存
    if cache_key:
        cache_path = get_cache_path(OPTIMIZED_CONFIG['cache_dir'], cache_key, 'w2ner_results')
        cached_results = load_from_cache(cache_path)
        if cached_results is not None:
            print(f"从缓存加载W2NER结果，跳过预处理和推理")
            return cached_results
    
    print(f"预处理句子... (批大小: {batch_size}, 最大序列长度: {max_seq_len})")
    
    # 分块处理以减少内存压力
    chunk_size = OPTIMIZED_CONFIG['chunk_size']
    all_processed_data = []
    
    # 创建总体进度条
    total_chunks = (len(sentences) + chunk_size - 1) // chunk_size
    chunk_progress = tqdm(total=total_chunks, desc="预处理进度", unit="块")
    
    for i in range(0, len(sentences), chunk_size):
        chunk_sentences = sentences[i:i+chunk_size]
        
        # 多进程预处理（限制进程数）- 不显示单独的进度条
        with Pool(OPTIMIZED_CONFIG['max_workers']) as pool:
            process_func = partial(process_sentence, tokenizer=tokenizer, max_seq_len=max_seq_len)
            processed_data = list(pool.imap(process_func, chunk_sentences))
        
        # 过滤无效结果
        valid_data = [d for d in processed_data if d is not None]
        all_processed_data.extend(valid_data)
        
        # 更新进度条
        chunk_progress.update(1)
        chunk_progress.set_postfix({
            '当前块': f"{i//chunk_size + 1}/{total_chunks}",
            '句子数': len(chunk_sentences),
            '有效': len(valid_data)
        })
        
        # 强制垃圾回收
        del processed_data
        gc.collect()
    
    chunk_progress.close()
    print(f"有效句子数量: {len(all_processed_data)}/{len(sentences)}")
    
    # 批量推理
    print("开始批量推理...")
    all_results = []
    
    # 按句子长度分组，使批内句子长度相近
    length_groups = {}
    for data in all_processed_data:
        # 确保length是标量
        length_val = data['length']
        if isinstance(length_val, (np.ndarray, list)):
            length_val = length_val[0] if len(length_val) > 0 else 0
        length = int(min(length_val, 128))  # 限制长度分组，确保length是整数标量
        if length not in length_groups:
            length_groups[length] = []
        length_groups[length].append(data)

    # 按长度排序
    sorted_lengths = sorted(length_groups.keys())
    sorted_data = []
    for length in sorted_lengths:
        sorted_data.extend(length_groups[length])

    # 批处理
    for i in tqdm(range(0, len(sorted_data), batch_size), desc="推理进度"):
        batch = sorted_data[i:i+batch_size]
        
        try:
            # 找到批内最大长度和最大序列长度
            batch_lengths = []
            batch_seq_lens = []
            for d in batch:
                # 确保length是标量
                length_val = d['length']
                if isinstance(length_val, (np.ndarray, list)):
                    length_val = length_val[0] if len(length_val) > 0 else 0
                batch_lengths.append(int(length_val))
                
                # 确保bert_inputs长度是标量
                seq_len = len(d['bert_inputs'])
                batch_seq_lens.append(int(seq_len))
            
            max_length = max(batch_lengths)
            max_seq_len_batch = max(batch_seq_lens)
            
            # 初始化批张量
            bert_inputs_batch = torch.full(
                (len(batch), max_seq_len_batch), 
                tokenizer.pad_token_id, 
                dtype=torch.long
            ).cuda()
            
            pieces2word_batch = torch.zeros(
                (len(batch), max_length, max_seq_len_batch), 
                dtype=torch.bool
            ).cuda()
            
            dist_inputs_batch = torch.zeros(
                (len(batch), max_length, max_length), 
                dtype=torch.long
            ).cuda()
            
            # 添加grid_mask2d和sent_length
            grid_mask2d_batch = torch.zeros(
                (len(batch), max_length, max_length), 
                dtype=torch.bool
            ).cuda()
            
            sent_length_batch = torch.zeros(len(batch), dtype=torch.long).cuda()
            
            # 填充批数据
            for j, data in enumerate(batch):
                bert_len = len(data['bert_inputs'])
                # 确保sent_len是整数标量
                length_val = data['length']
                if isinstance(length_val, (np.ndarray, list)):
                    length_val = length_val[0] if len(length_val) > 0 else 0
                sent_len = int(length_val)
                
                bert_inputs_batch[j, :bert_len] = torch.tensor(data['bert_inputs'])
                pieces2word_batch[j, :sent_len, :bert_len] = torch.from_numpy(data['pieces2word'][:sent_len, :bert_len])
                
                # 填充sent_length
                sent_length_batch[j] = sent_len
                
                # 填充grid_mask2d (句子长度内的位置为True)
                grid_mask2d_batch[j, :sent_len, :sent_len] = True
                
                # 距离矩阵
                for k in range(sent_len):
                    # 直接使用整数索引，避免数组转换问题
                    dist_row = [int(dis2idx[abs(k - l)]) for l in range(sent_len)]
                    dist_inputs_batch[j, k, :sent_len] = torch.tensor(dist_row, dtype=torch.long)
            
            # 模型推理 - 修正参数顺序
            with torch.no_grad():
                outputs = model(bert_inputs_batch, grid_mask2d_batch, dist_inputs_batch, pieces2word_batch, sent_length_batch)
                outputs = torch.nn.functional.sigmoid(outputs)
            
            # 解码结果
            for j, data in enumerate(batch):
                # 确保sent_len是整数标量
                length_val = data['length']
                if isinstance(length_val, (np.ndarray, list)):
                    length_val = length_val[0] if len(length_val) > 0 else 0
                sent_len = int(length_val)
                sentence = data['sentence']
                
                # 提取实体
                entities = []
                output_matrix = outputs[j, :sent_len, :sent_len].cpu().numpy()
                
                for start in range(sent_len):
                    for end in range(start, sent_len):
                        # 确保获取标量值而不是数组
                        score = float(output_matrix[start, end])
                        if score > 0.5:  # 阈值
                            entity = sentence[start:end+1]
                            if len(entity.strip()) > 0:
                                entities.append({
                                    'text': entity,
                                    'start': start,
                                    'end': end
                                })
                
                # 按起始位置排序
                entities.sort(key=lambda x: x['start'])
                
                all_results.append({
                    'sentence': sentence,
                    'entities': entities
                })
            
            # 清理GPU内存
            del bert_inputs_batch, pieces2word_batch, dist_inputs_batch, grid_mask2d_batch, sent_length_batch, outputs
            torch.cuda.empty_cache()
            
        except Exception as e:
            print(f"批处理 {i//batch_size + 1} 出错: {str(e)}")
            # 添加空结果以保持索引一致
            for data in batch:
                all_results.append({
                    'sentence': data['sentence'],
                    'entities': []
                })
        
        # 定期垃圾回收
        if i % (batch_size * 10) == 0:
            gc.collect()
    
    # 保存到缓存
    if cache_key:
        cache_path = get_cache_path(OPTIMIZED_CONFIG['cache_dir'], cache_key, 'w2ner_results')
        save_to_cache(all_results, cache_path)
    
    return all_results

def process_json_data(json_file_path, model_path, vocab_path, bert_name):
    """处理JSON数据并使用w2ner模型提取实体（优化版本，支持缓存）"""
    
    # 加载JSON数据
    print(f"加载JSON数据: {json_file_path}")
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取句子（处理完整数据集）
    sentences = [item['text'] for item in data['results']]
    original_relations = [(item['entity1'], item['relation'], item['entity2']) for item in data['results']]
    
    # 如果数据量太大，可以分批处理
    # 移除句子数量限制，处理完整数据集
    print(f"处理句子数: {len(sentences)}")
    
    # 生成缓存键（基于输入数据和配置）
    cache_data = {
        'sentences': sentences[:100],  # 只使用前100个句子生成哈希，避免过大
        'config': OPTIMIZED_CONFIG,
        'model_path': model_path,
        'vocab_path': vocab_path,
        'bert_name': bert_name
    }
    cache_key = get_data_hash(cache_data)
    
    # 检查是否有有效的缓存
    cache_path = get_cache_path(OPTIMIZED_CONFIG['cache_dir'], cache_key, 'final_results')
    if is_cache_valid(cache_path, json_file_path):
        cached_results = load_from_cache(cache_path)
        if cached_results is not None:
            print("从缓存加载最终结果，跳过所有预处理")
            return cached_results
    
    # 加载模型和分词器
    print("加载w2ner模型和分词器...")
    
    # 加载词汇表
    vocab = load_vocab(vocab_path)
    
    # 创建配置对象（使用原始参数以匹配预训练模型）
    config = type('Config', (), {})()
    config.label_num = len(vocab.label2id)
    config.bert_name = bert_name
    config.max_seq_len = 128  # 保持原始序列长度以匹配模型
    config.use_bert_last_4_layers = True
    config.do_lower_case = True
    config.dist_emb_size = 20
    config.type_emb_size = 20
    config.lstm_hid_size = 512  # 恢复原始大小
    config.conv_hid_size = 96   # 恢复原始大小
    config.bert_hid_size = 768
    config.biaffine_size = 512  # 恢复原始大小
    config.ffnn_hid_size = 288  # 恢复原始大小
    config.dilation = [1, 2, 3]
    config.emb_dropout = 0.5
    config.conv_dropout = 0.5
    config.out_dropout = 0.33
    
    # 加载模型
    model = Model(config).cuda()
    model.load_state_dict(torch.load(model_path, map_location='cuda'))
    model.eval()
    
    # 加载分词器
    tokenizer = AutoTokenizer.from_pretrained(bert_name)
    
    # 使用w2ner模型提取实体
    print("使用w2ner模型提取实体...")
    w2ner_results = extract_entities_with_w2ner(
        sentences, 
        model, 
        tokenizer, 
        max_seq_len=OPTIMIZED_CONFIG['max_seq_len'],
        batch_size=OPTIMIZED_CONFIG['batch_size'],
        cache_key=cache_key  # 传递缓存键
    )
    
    # 清理模型内存
    del model
    torch.cuda.empty_cache()
    gc.collect()
    
    # 转换为CSV格式
    print("转换为CSV格式...")
    csv_data = []
    
    for i, (sentence, original_relation, w2ner_result) in enumerate(zip(sentences, original_relations, w2ner_results)):
        entities = w2ner_result['entities']
        
        if len(entities) >= 2:
            # 使用w2ner提取的实体
            head_entity = entities[0]
            tail_entity = entities[1]
            
            # 尝试从原始数据中获取关系
            original_head, relation, original_tail = original_relation
            
            csv_data.append({
                'sentence': sentence,
                'relation': relation,
                'head': head_entity['text'],
                'head_offset': f"{head_entity['start']},{head_entity['end']}",
                'tail': tail_entity['text'],
                'tail_offset': f"{tail_entity['start']},{tail_entity['end']}"
            })
        else:
            # 如果w2ner没有提取到足够的实体，使用原始数据
            original_head, relation, original_tail = original_relation
            
            # 简单的实体位置查找
            head_start = sentence.find(original_head)
            tail_start = sentence.find(original_tail)
            
            if head_start != -1 and tail_start != -1:
                csv_data.append({
                    'sentence': sentence,
                    'relation': relation,
                    'head': original_head,
                    'head_offset': f"{head_start},{head_start + len(original_head) - 1}",
                    'tail': original_tail,
                    'tail_offset': f"{tail_start},{tail_start + len(original_tail) - 1}"
                })
        
        # 定期垃圾回收
        if i % 100 == 0:
            gc.collect()
    
    print(f"成功转换 {len(csv_data)} 条数据")
    
    # 保存最终结果到缓存
    cache_path = get_cache_path(OPTIMIZED_CONFIG['cache_dir'], cache_key, 'final_results')
    save_to_cache(csv_data, cache_path)
    
    return csv_data

def split_dataset(data, train_ratio=0.8, test_ratio=0.1, valid_ratio=0.1):
    """按8:1:1比例划分数据集"""
    total_size = len(data)
    train_size = int(total_size * train_ratio)
    test_size = int(total_size * test_ratio)
    valid_size = total_size - train_size - test_size
    
    # 随机打乱数据
    import random
    random.seed(42)  # 设置随机种子以确保可重现性
    shuffled_data = data.copy()
    random.shuffle(shuffled_data)
    
    train_data = shuffled_data[:train_size]
    test_data = shuffled_data[train_size:train_size + test_size]
    valid_data = shuffled_data[train_size + test_size:]
    
    print(f"数据集划分: 训练集({len(train_data)}), 测试集({len(test_data)}), 验证集({len(valid_data)})")
    
    return train_data, test_data, valid_data

def main():
    """主函数（优化版本，支持缓存）"""
    print("=" * 60)
    print("W2NER数据处理脚本 - 优化版本（支持缓存）")
    print("=" * 60)
    print(f"优化配置:")
    print(f"  批处理大小: {OPTIMIZED_CONFIG['batch_size']}")
    print(f"  最大进程数: {OPTIMIZED_CONFIG['max_workers']}")
    print(f"  最大序列长度: {OPTIMIZED_CONFIG['max_seq_len']}")
    print(f"  分块大小: {OPTIMIZED_CONFIG['chunk_size']}")
    print(f"  缓存目录: {OPTIMIZED_CONFIG['cache_dir']}")
    
    # 显示缓存信息
    cache_info = get_cache_info()
    print(f"  缓存文件数: {cache_info['cache_files']}")
    print(f"  缓存大小: {cache_info.get('total_size_mb', 0)} MB")
    print("=" * 60)
    
    # 配置路径
    json_file_path = "/root/KG_inde/generate_data/data_backups/processing_state.json"
    model_path = "/root/KG_inde/DeepKE/example/ner/standard/w2ner/output/pytorch_model.bin"
    vocab_path = "/root/KG_inde/DeepKE/example/ner/standard/w2ner/output/vocab.pkl"
    bert_name = "bert-base-chinese"
    output_dir = "/root/KG_inde/DeepKE/example/re/standard/data/origin"
    
    # 检查文件是否存在
    if not os.path.exists(json_file_path):
        print(f"错误: JSON文件不存在: {json_file_path}")
        return
    
    if not os.path.exists(model_path):
        print(f"错误: 模型文件不存在: {model_path}")
        return
    
    if not os.path.exists(vocab_path):
        print(f"错误: 词汇表文件不存在: {vocab_path}")
        return
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 检查GPU内存
    if torch.cuda.is_available():
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"GPU内存: {gpu_memory:.1f} GB")
        torch.cuda.empty_cache()
    
    try:
        import time
        start_time = time.time()
        
        # 处理JSON数据
        print("\n开始处理JSON数据...")
        csv_data = process_json_data(json_file_path, model_path, vocab_path, bert_name)
        
        if not csv_data:
            print("错误: 没有成功处理的数据")
            return
        
        processing_time = time.time() - start_time
        print(f"数据处理完成，耗时: {processing_time:.2f} 秒")
        
        # 划分数据集
        print("\n划分数据集...")
        train_data, test_data, valid_data = split_dataset(csv_data)
        
        # 保存为CSV文件
        print("\n保存CSV文件...")
        train_df = pd.DataFrame(train_data)
        test_df = pd.DataFrame(test_data)
        valid_df = pd.DataFrame(valid_data)
        
        train_path = os.path.join(output_dir, "train.csv")
        test_path = os.path.join(output_dir, "test.csv")
        valid_path = os.path.join(output_dir, "valid.csv")
        
        train_df.to_csv(train_path, index=False, encoding='utf-8')
        test_df.to_csv(test_path, index=False, encoding='utf-8')
        valid_df.to_csv(valid_path, index=False, encoding='utf-8')
        
        total_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("处理完成!")
        print("=" * 60)
        print(f"数据集已保存:")
        print(f"  训练集: {train_path} ({len(train_data)} 条)")
        print(f"  测试集: {test_path} ({len(test_data)} 条)")
        print(f"  验证集: {valid_path} ({len(valid_data)} 条)")
        print(f"总耗时: {total_time:.2f} 秒")
        print(f"平均处理速度: {len(csv_data)/total_time:.2f} 条/秒")
        
        # 最终内存清理
        del train_df, test_df, valid_df, csv_data
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # 错误时也要清理内存
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

if __name__ == "__main__":
    main()