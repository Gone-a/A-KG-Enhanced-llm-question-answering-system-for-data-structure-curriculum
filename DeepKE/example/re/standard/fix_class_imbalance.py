#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解决关系抽取模型类别不平衡问题的脚本
"""

import pandas as pd
import numpy as np
from sklearn.utils.class_weight import compute_class_weight
import torch
import torch.nn as nn
from collections import Counter
import os
import yaml

def analyze_class_distribution(data_path):
    """分析类别分布"""
    df = pd.read_csv(data_path)
    print(f"训练数据总数: {len(df)}")
    
    relation_counts = df['relation'].value_counts()
    print("\n关系分布:")
    print(relation_counts)
    
    print("\n关系比例:")
    for rel, count in relation_counts.items():
        ratio = count / len(df)
        print(f"{rel}: {count} ({ratio:.3f}, {ratio*100:.1f}%)")
    
    return df, relation_counts

def compute_balanced_weights(df):
    """计算平衡权重"""
    relations = df['relation'].values
    unique_relations = np.unique(relations)
    
    # 使用sklearn计算类别权重
    class_weights = compute_class_weight(
        'balanced',
        classes=unique_relations,
        y=relations
    )
    
    weight_dict = dict(zip(unique_relations, class_weights))
    print("\n计算的类别权重:")
    for rel, weight in weight_dict.items():
        print(f"{rel}: {weight:.3f}")
    
    return weight_dict, unique_relations

def create_balanced_dataset(df, target_samples_per_class=500):
    """创建平衡的数据集"""
    balanced_dfs = []
    
    for relation in df['relation'].unique():
        relation_df = df[df['relation'] == relation]
        current_count = len(relation_df)
        
        if current_count >= target_samples_per_class:
            # 如果样本足够，随机采样
            sampled_df = relation_df.sample(n=target_samples_per_class, random_state=42)
        else:
            # 如果样本不足，进行过采样
            n_repeats = target_samples_per_class // current_count
            remainder = target_samples_per_class % current_count
            
            # 重复数据
            repeated_df = pd.concat([relation_df] * n_repeats, ignore_index=True)
            
            # 添加剩余样本
            if remainder > 0:
                extra_df = relation_df.sample(n=remainder, random_state=42)
                repeated_df = pd.concat([repeated_df, extra_df], ignore_index=True)
            
            sampled_df = repeated_df
        
        balanced_dfs.append(sampled_df)
        print(f"{relation}: {current_count} -> {len(sampled_df)}")
    
    balanced_df = pd.concat(balanced_dfs, ignore_index=True)
    balanced_df = balanced_df.sample(frac=1, random_state=42).reset_index(drop=True)  # 打乱顺序
    
    return balanced_df

def update_train_config_with_weights(config_path, weight_dict, relation_to_idx):
    """更新训练配置文件，添加类别权重"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 按索引顺序排列权重
    weights = [weight_dict[rel] for rel in sorted(relation_to_idx.keys(), key=lambda x: relation_to_idx[x])]
    
    # 添加类别权重配置
    config['class_weights'] = weights
    config['use_class_weights'] = True
    
    # 保存更新的配置
    backup_path = config_path + '.backup'
    if not os.path.exists(backup_path):
        os.rename(config_path, backup_path)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print(f"\n配置文件已更新: {config_path}")
    print(f"备份文件: {backup_path}")
    print(f"类别权重: {weights}")

def main():
    # 数据路径
    train_data_path = "data/origin/train.csv"
    relation_data_path = "data/origin/relation.csv"
    config_path = "conf/train.yaml"
    
    print("=== 分析原始数据分布 ===")
    df, relation_counts = analyze_class_distribution(train_data_path)
    
    print("\n=== 计算类别权重 ===")
    weight_dict, unique_relations = compute_balanced_weights(df)
    
    # 读取关系映射
    relation_df = pd.read_csv(relation_data_path)
    relation_to_idx = dict(zip(relation_df['relation'], relation_df['index']))
    
    print("\n=== 创建平衡数据集 ===")
    balanced_df = create_balanced_dataset(df, target_samples_per_class=300)
    
    # 保存平衡数据集
    balanced_train_path = "data/origin/train_balanced.csv"
    balanced_df.to_csv(balanced_train_path, index=False)
    print(f"\n平衡数据集已保存: {balanced_train_path}")
    
    print("\n=== 平衡后的数据分布 ===")
    analyze_class_distribution(balanced_train_path)
    
    print("\n=== 更新训练配置 ===")
    update_train_config_with_weights(config_path, weight_dict, relation_to_idx)
    
    print("\n=== 解决方案总结 ===")
    print("1. 创建了平衡的训练数据集")
    print("2. 计算了类别权重用于损失函数")
    print("3. 更新了训练配置文件")
    print("\n建议:")
    print("1. 使用平衡数据集重新训练模型")
    print("2. 在训练时使用类别权重")
    print("3. 调整预测时的置信度阈值")
    print("4. 考虑使用Focal Loss等专门处理不平衡数据的损失函数")

if __name__ == "__main__":
    main()