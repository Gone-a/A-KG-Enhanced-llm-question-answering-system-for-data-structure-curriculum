#处理多条输入的情况
import os
import sys
import torch
import logging
import hydra
import csv
import pandas as pd
from hydra import utils
from deepke.relation_extraction.standard.tools import Serializer
from deepke.relation_extraction.standard.tools import _serialize_sentence, _convert_tokens_into_index, _add_pos_seq, _handle_relation_data , _lm_serialize
import matplotlib.pyplot as plt
from tqdm import tqdm
import numpy as np
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from deepke.relation_extraction.standard.utils import load_pkl, load_csv
import deepke.relation_extraction.standard.models as models


logger = logging.getLogger(__name__)


def _preprocess_data(data, cfg):
    
    relation_data = load_csv(os.path.join(cfg.cwd, cfg.data_path, 'relation.csv'), verbose=False)
    rels = _handle_relation_data(relation_data)

    if cfg.model.model_name != 'lm':
        vocab = load_pkl(os.path.join(cfg.cwd, cfg.out_path, 'vocab.pkl'), verbose=False)
        cfg.vocab_size = vocab.count
        serializer = Serializer(do_chinese_split=cfg.chinese_split)
        serial = serializer.serialize

        # 修改的序列化处理，确保实体在句子中存在
        for d in data:
            sent = d['sentence'].strip()
            # 检查实体是否在句子中
            if d['head'] not in sent or d['tail'] not in sent:
                # 如果实体不在句子中，直接使用句子进行分词
                d['tokens'] = serial(sent)
                # 设置默认的头尾位置
                d['head_idx'], d['tail_idx'] = 0, min(1, len(d['tokens'])-1)
            else:
                # 原有的处理逻辑
                if d['head'] in d['tail']:
                    sent = sent.replace(d['tail'], ' tail ', 1).replace(d['head'], ' head ', 1)
                else:
                    sent = sent.replace(d['head'], ' head ', 1).replace(d['tail'], ' tail ', 1)
                d['tokens'] = serial(sent, never_split=['head', 'tail'])
                try:
                    head_idx, tail_idx = d['tokens'].index('head'), d['tokens'].index('tail')
                    d['head_idx'], d['tail_idx'] = head_idx, tail_idx
                except ValueError:
                    # 如果找不到head或tail标记，设置默认位置
                    d['head_idx'], d['tail_idx'] = 0, min(1, len(d['tokens'])-1)

                if cfg.replace_entity_with_type:
                    if cfg.replace_entity_with_scope:
                        d['tokens'][d['head_idx']], d['tokens'][d['tail_idx']] = 'HEAD_' + d['head_type'], 'TAIL_' + d['tail_type']
                    else:
                        d['tokens'][d['head_idx']], d['tokens'][d['tail_idx']] = d['head_type'], d['tail_type']
                else:
                    if cfg.replace_entity_with_scope:
                        d['tokens'][d['head_idx']], d['tokens'][d['tail_idx']] = 'HEAD', 'TAIL'
                    else:
                        d['tokens'][d['head_idx']], d['tokens'][d['tail_idx']] = d['head'], d['tail']
        
        _convert_tokens_into_index(data, vocab)
        _add_pos_seq(data, cfg)
        logger.info('start sentence preprocess...')
    else:
        _lm_serialize(data,cfg)

    return data, rels


def _load_csv_data(csv_path):
    """批量加载CSV文件中的预测数据"""
    data = []
    try:
        df = pd.read_csv(csv_path)
        required_columns = ['sentence', 'head', 'tail', 'head_type', 'tail_type']
        
        # 检查CSV是否包含所有必需的列
        for col in required_columns:
            if col not in df.columns:
                logger.error(f"CSV文件缺少必要的列: {col}")
                sys.exit(1)
        
        # 使用向量化操作过滤数据
        mask = ~(df['head'].isna() | df['tail'].isna() | (df['head'] == df['tail']))
        filtered_df = df[mask]
        
        # 批量转换为字典列表
        data = filtered_df.apply(lambda row: {
            'sentence': str(row['sentence']).strip(),
            'head': str(row['head']).strip(),
            'tail': str(row['tail']).strip(),
            'head_type': str(row['head_type']).strip(),
            'tail_type': str(row['tail_type']).strip()
        }, axis=1).tolist()
        
        logger.info(f'成功从 {csv_path} 加载 {len(data)} 条预测数据')
    except Exception as e:
        logger.error(f'加载CSV文件失败: {e}')
        sys.exit(1)
    
    return data


def prepare_batch_data(data, cfg, batch_size=32):
    """准备批量处理的数据"""
    batches = []
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        batch_data = {}
        
        if cfg.model.model_name != 'lm':
            # 预分配张量
            max_len = 512
            batch_len = len(batch)
            
            # 使用numpy预分配，然后转换为tensor
            word_batch = np.zeros((batch_len, max_len), dtype=np.int64)
            lens_batch = np.zeros(batch_len, dtype=np.int64)
            head_pos_batch = np.zeros((batch_len, max_len), dtype=np.int64)
            tail_pos_batch = np.zeros((batch_len, max_len), dtype=np.int64)
            
            for j, instance in enumerate(batch):
                tokens = instance.get('token2idx', [])
                seq_len = min(len(tokens), max_len)
                
                word_batch[j, :seq_len] = tokens[:seq_len]
                lens_batch[j] = seq_len
                
                head_pos = instance.get('head_pos', [0]*seq_len)
                tail_pos = instance.get('tail_pos', [0]*seq_len)
                head_pos_batch[j, :seq_len] = head_pos[:seq_len]
                tail_pos_batch[j, :seq_len] = tail_pos[:seq_len]
            
            # 一次性转换为tensor
            batch_data['word'] = torch.from_numpy(word_batch)
            batch_data['lens'] = torch.from_numpy(lens_batch)
            batch_data['head_pos'] = torch.from_numpy(head_pos_batch)
            batch_data['tail_pos'] = torch.from_numpy(tail_pos_batch)
            
            # 处理特殊模型需求
            if cfg.model.model_name == 'cnn' and cfg.use_pcnn:
                pcnn_batch = np.zeros((batch_len, max_len), dtype=np.int64)
                for j, instance in enumerate(batch):
                    entities_pos = instance.get('entities_pos', [0]*seq_len)
                    pcnn_batch[j, :len(entities_pos)] = entities_pos[:max_len]
                batch_data['pcnn_mask'] = torch.from_numpy(pcnn_batch)
                
            if cfg.model.model_name == 'gcn':
                batch_data['adj'] = torch.randint(0, 2, (batch_len, max_len, max_len))
        else:
            # LM模型批量处理
            max_len = 512
            batch_len = len(batch)
            word_batch = np.zeros((batch_len, max_len), dtype=np.int64)
            lens_batch = np.zeros(batch_len, dtype=np.int64)
            
            for j, instance in enumerate(batch):
                tokens = instance.get('token2idx', [])
                seq_len = min(len(tokens), max_len)
                word_batch[j, :seq_len] = tokens[:seq_len]
                lens_batch[j] = seq_len
            
            batch_data['word'] = torch.from_numpy(word_batch)
            batch_data['lens'] = torch.from_numpy(lens_batch)
        
        batches.append((batch, batch_data))
    
    return batches


def process_batch(model, batch_data, device, rels, model_name, cfg):
    """批量处理数据进行预测"""
    with torch.no_grad():
        # 将数据移动到设备
        for key, value in batch_data.items():
            batch_data[key] = value.to(device)
        
        # 模型预测
        logits = model(batch_data)
        
        # 添加详细的调试输出
        logger.info(f"模型输出logits形状: {logits.shape}")
        logger.info(f"模型输出logits范围: min={logits.min().item():.3f}, max={logits.max().item():.3f}")
        
        # 应用softmax获取概率
        probs = torch.softmax(logits, dim=-1)
        logger.info(f"Softmax概率形状: {probs.shape}")
        logger.info(f"Softmax概率范围: min={probs.min().item():.3f}, max={probs.max().item():.3f}")
        
        # 获取最高概率的索引
        max_probs, indices = torch.max(probs, dim=-1)
        
        # 详细分析每个样本的预测结果
        logger.info(f"预测索引分布: {indices.cpu().numpy()}")
        logger.info(f"最高概率分布: min={max_probs.min().item():.3f}, max={max_probs.max().item():.3f}, mean={max_probs.mean().item():.3f}")
        
        # 分析所有类别的概率分布
        for i in range(probs.shape[1]):
            class_probs = probs[:, i]
            logger.info(f"类别{i}概率: min={class_probs.min().item():.3f}, max={class_probs.max().item():.3f}, mean={class_probs.mean().item():.3f}")
        
        # 检查关系映射
        logger.info(f"关系映射: {list(rels.keys())}")
        logger.info(f"关系数量: {len(rels)}")
        
        # 转换为结果
        results = []
        rels_keys = list(rels.keys())
        for prob, index in zip(max_probs.cpu().numpy(), indices.cpu().numpy()):
            if index < len(rels_keys):
                prob_rel = rels_keys[index]
                results.append((prob_rel, float(prob)))
                logger.debug(f"预测: 索引{index} -> 关系'{prob_rel}', 概率{prob:.3f}")
            else:
                results.append(("", 0.0))
                logger.warning(f"索引{index}超出关系范围，关系数量为{len(rels_keys)}")
        
        return results


@hydra.main(config_path="conf", config_name="config", version_base=None)
def main(cfg):
    cwd = utils.get_original_cwd()
    cfg.cwd = cwd
    cfg.pos_size = 2 * cfg.pos_limit + 2

    # 批量加载CSV文件
    batch_predict_file= cfg.predict_data_path
    
    csv_path = os.path.join(cfg.cwd, batch_predict_file)
    data = _load_csv_data(csv_path)

    # preprocess data
    data, rels = _preprocess_data(data, cfg)

    # model
    __Model__ = {
        'cnn': models.PCNN,
        'rnn': models.BiLSTM,
        'transformer': models.Transformer,
        'gcn': models.GCN,
        'capsule': models.Capsule,
        'lm': models.LM,
    }

    # GPU设置
    cfg.use_gpu = True
    if cfg.use_gpu and torch.cuda.is_available():
        device = torch.device('cuda', cfg.gpu_id)
    else:
        device = torch.device('cpu')
    logger.info(f'device: {device}')

    model = __Model__[cfg.model.model_name](cfg)
    logger.info(f'model name: {cfg.model.model_name}')
    model.load(cfg.fp, device=device)
    model.to(device)
    model.eval()

    # 准备批量数据
    batch_size = 64 if cfg.use_gpu else 32  # GPU使用更大的批次
    batches = prepare_batch_data(data, cfg, batch_size)
    
    # 存储所有预测结果
    all_results = []
    
    # 批量处理
    for batch_instances, batch_data in tqdm(batches, desc="批量处理预测数据", unit="批"):
        batch_results = process_batch(model, batch_data, device, rels, cfg.model.model_name, cfg)
        
        # 组合结果
        for instance, (prob_rel, prob) in zip(batch_instances, batch_results):
            all_results.append({
                'sentence': instance['sentence'],
                'head': instance['head'],
                'tail': instance['tail'],
                'relation': prob_rel,
                'confidence': prob
            })
    
    # 设置置信度阈值
    confidence_threshold = 0.8
    
    # 打印统计信息
    if all_results:
        confidences = [result['confidence'] for result in all_results]
        logger.info(f"置信度统计: 最大值={max(confidences):.3f}, 最小值={min(confidences):.3f}, 平均值={sum(confidences)/len(confidences):.3f}")
        logger.info(f"总共预测结果: {len(all_results)} 条")
    else:
        logger.warning("没有生成任何预测结果！")

    # 过滤低置信度结果
    filtered_results = [
        result for result in all_results 
        if result['confidence'] >= confidence_threshold
    ]

    # 保存过滤后的结果到CSV
    results_file = os.path.join(cfg.cwd, cfg.predict_out_path)
    results_file_2 = os.path.abspath(os.path.join(cfg.cwd,"../../../..","neo4j/data/predictions.csv"))
    logger.info(f"完整输出路径: {results_file}")
    logger.info(f"完整输出路径_2: {results_file_2}")
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    os.makedirs(os.path.dirname(results_file_2), exist_ok=True)

    try:
        if filtered_results:
            results_df = pd.DataFrame(filtered_results)
            results_df.to_csv(results_file, index=False, encoding='utf-8-sig')
            results_df.to_csv(results_file_2, index=False, encoding='utf-8-sig')
            logger.info(f"预测结果已保存到: {results_file}")
            logger.info(f"预测结果已保存到: {results_file_2}")
            logger.info(f"保存了 {len(filtered_results)} 条结果，过滤掉 {len(all_results) - len(filtered_results)} 条低置信度结果（置信度 < {confidence_threshold})")
        else:
            logger.warning(f"没有置信度 >= {confidence_threshold} 的结果，保存空文件")
            # 保存空的DataFrame以创建带表头的空文件
            empty_df = pd.DataFrame(columns=['sentence', 'head', 'tail', 'relation', 'confidence'])
            empty_df.to_csv(results_file, index=False, encoding='utf-8-sig')
    except Exception as e:
        logger.error(f"保存结果失败: {e}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")


if __name__ == '__main__':
    main()