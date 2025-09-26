import pandas as pd
from sklearn.utils.class_weight import compute_class_weight
import numpy as np

# 读取训练数据 - 使用标准CSV格式
train_df = pd.read_csv('data/origin/train.csv')

# 获取关系列
relations = train_df['relation'].values

# 计算类别权重
unique_relations = np.unique(relations)
class_weights = compute_class_weight('balanced', classes=unique_relations, y=relations)

# 创建权重字典
weight_dict = dict(zip(unique_relations, class_weights))

print("类别权重:")
for relation, weight in weight_dict.items():
    print(f"{relation}: {weight:.4f}")

# 保存权重到文件
with open('class_weights.txt', 'w', encoding='utf-8') as f:
    for relation, weight in weight_dict.items():
        f.write(f"{relation}: {weight:.4f}\n")

print("\n权重已保存到 class_weights.txt")