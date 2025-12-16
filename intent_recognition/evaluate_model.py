# 文件路径：intent_recognition/evaluate_model.py

# -*- coding: utf-8 -*-
import torch
import json
import os
import sys
from transformers import AutoTokenizer, AutoModelForSequenceClassification 
from sklearn.metrics import classification_report, confusion_matrix
import numpy as np

# 导入配置管理器
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.config_manager import get_config_manager

# 获取配置管理器实例
config_manager = get_config_manager()
model_config = config_manager.get_model_config()

# --- 配置 ---
# 模型路径，请确保与您的模型文件夹名称一致
MODEL_PATH = model_config.get('nlu_model_path', "./my_intent_model")

# --- 核心：测试样本 ---
# 这些样本必须与训练样本不同，以检验模型的泛化能力。
# 格式: ("用户可能会说的话", "真实的意图标签")
test_samples = [
# ==============================================================================
    ("Morris遍历和普通递归遍历的空间差别", "find_relation_by_two_entities"),
    ("为什么快排通常比堆排快", "find_relation_by_two_entities"),
    ("邻接表存图和链式前向星的区别", "find_relation_by_two_entities"),
    ("红黑树和AVL树谁的插入效率高", "find_relation_by_two_entities"),
    ("Map和Unordered_map底层实现有何不同", "find_relation_by_two_entities"),
    ("DFS和BFS谁适合找无权图的最短路", "find_relation_by_two_entities"),
    ("贪心和动态规划在背包问题上的表现差异", "find_relation_by_two_entities"),
    ("栈和递归是一回事吗", "find_relation_by_two_entities"),
    ("图的深度优先遍历和树的先序遍历有什么联系", "find_relation_by_two_entities"),
    ("哈希表和红黑树作为数据库索引的优劣", "find_relation_by_two_entities"),
    ("多叉树和二叉树能互相转换吗", "find_relation_by_two_entities"),
    ("Kruskal和Prim在稠密图上的性能对比", "find_relation_by_two_entities"),
    ("单链表反转和双向链表反转的复杂度一样吗", "find_relation_by_two_entities"),
    ("堆内存和栈内存的分配效率PK", "find_relation_by_two_entities"),
    ("TCP的滑动窗口和算法里的滑动窗口有关系吗", "find_relation_by_two_entities"),
    ("并查集和DFS判断连通性哪个快", "find_relation_by_two_entities"),
    ("希尔排序比起插入排序改进了哪里", "find_relation_by_two_entities"),
    ("Trie树和Hash Map在字符串前缀匹配上的差异", "find_relation_by_two_entities"),
    ("树状数组能做线段树的所有事吗", "find_relation_by_two_entities"),
    ("二分图匹配和最大流的关系", "find_relation_by_two_entities"),
    ("归并排序是原地的吗，和快排比呢", "find_relation_by_two_entities"),
    ("循环队列和链式队列谁更节省空间", "find_relation_by_two_entities"),
    ("大顶堆和小顶堆能互相转化吗", "find_relation_by_two_entities"),
    ("图的BFS和树的层次遍历是一样的吗", "find_relation_by_two_entities"),
    ("邻接矩阵在稀疏图上的浪费情况", "find_relation_by_two_entities"),
    ("斐波那契查找和二分查找的平均性能", "find_relation_by_two_entities"),
    ("插值查找和二分查找谁更适合均匀分布", "find_relation_by_two_entities"),
    ("锁机制和信号量有什么区别", "find_relation_by_two_entities"), # 偏OS但常考
    ("递归深度过大和栈溢出的关系", "find_relation_by_two_entities"),
    ("一致性哈希和普通哈希的区别", "find_relation_by_two_entities"),

    ("除了拉链法，还有怎么解决哈希冲突", "find_entity_by_relation_and_entity"),
    ("带有负权边的图能用什么算法求最短路", "find_entity_by_relation_and_entity"),
    ("树中度为0的节点通常叫什么", "find_entity_by_relation_and_entity"),
    ("哪些排序算法的时间复杂度是线性的", "find_entity_by_relation_and_entity"),
    ("二叉树节点的结构体通常包含哪几个变量", "find_entity_by_relation_and_entity"),
    ("动态规划求解需要满足哪三大要素", "find_entity_by_relation_and_entity"),
    ("求强连通分量的算法有两个著名的，是哪两个", "find_entity_by_relation_and_entity"),
    ("适合做LRU缓存的数据结构有哪些", "find_entity_by_relation_and_entity"),
    ("非比较排序包括什么", "find_entity_by_relation_and_entity"),
    ("栈这种结构有什么经典的应用题", "find_entity_by_relation_and_entity"),
    ("最小生成树除了Prim还有谁", "find_entity_by_relation_and_entity"),
    ("图论中属于P问题的有哪些", "find_entity_by_relation_and_entity"),
    ("平衡树都有哪些种类", "find_entity_by_relation_and_entity"),
    ("C++ STL中哪些容器底层是红黑树", "find_entity_by_relation_and_entity"),
    ("求凸包的算法有哪些", "find_entity_by_relation_and_entity"),
    ("哪些算法用到了分治的思想", "find_entity_by_relation_and_entity"),
    ("图的存储除了邻接表和矩阵还有啥", "find_entity_by_relation_and_entity"),
    ("实现一个计算器需要用到什么数据结构", "find_entity_by_relation_and_entity"),
    ("哪些排序算法是不仅稳定还快的", "find_entity_by_relation_and_entity"),
    ("B树的应用场景主要是在哪里", "find_entity_by_relation_and_entity"),
    ("最长回文子串可以用什么算法解", "find_entity_by_relation_and_entity"),
    ("区间最值问题RMQ可以用什么数据结构", "find_entity_by_relation_and_entity"),
    ("检测链表是否有环的方法", "find_entity_by_relation_and_entity"),
    ("二叉树序列化需要什么遍历方式", "find_entity_by_relation_and_entity"),
    ("解决约瑟夫环问题可以用什么", "find_entity_by_relation_and_entity"),
    ("哪些图算法是基于贪心的", "find_entity_by_relation_and_entity"),
    ("计算连通图个数用什么遍历", "find_entity_by_relation_and_entity"),
    ("哈夫曼编码属于哪类算法的应用", "find_entity_by_relation_and_entity"),
    ("后缀数组常用于解决什么类问题", "find_entity_by_relation_and_entity"),
    ("最大流问题的经典算法有哪些", "find_entity_by_relation_and_entity"),


# 3. find_entity_definition (30条)
    ("解释一下蓄水池抽样算法", "find_entity_definition"),
    ("什么是伪递归", "find_entity_definition"),
    ("能讲讲只有路径压缩的并查集吗", "find_entity_definition"),
    ("平摊分析是什么意思", "find_entity_definition"),
    ("给我科普一下跳表", "find_entity_definition"),
    ("什么是完全背包问题", "find_entity_definition"),
    ("介绍一下Treap树", "find_entity_definition"),
    ("蒙特卡洛方法是啥", "find_entity_definition"),
    ("什么是图的直径", "find_entity_definition"),
    ("解释下Kruskal算法的流程", "find_entity_definition"),
    ("野指针是什么概念", "find_entity_definition"),
    ("什么是哈夫曼树的加权路径长度", "find_entity_definition"),
    ("解释一下AC自动机", "find_entity_definition"),
    ("什么是多路查找树", "find_entity_definition"),
    ("解释下什么是稳定排序", "find_entity_definition"),
    ("什么是笛卡尔树", "find_entity_definition"),
    ("K-D树是什么", "find_entity_definition"),
    ("什么是四叉树", "find_entity_definition"),
    ("解释一下什么是八皇后问题", "find_entity_definition"),
    ("什么是汉明距离", "find_entity_definition"),
    ("介绍一下编辑距离", "find_entity_definition"),
    ("什么是拓扑序列", "find_entity_definition"),
    ("解释下什么是临界路径", "find_entity_definition"),
    ("什么是斐波那契堆", "find_entity_definition"),
    ("介绍下二项队列", "find_entity_definition"),
    ("什么是左偏树", "find_entity_definition"),
    ("解释一下什么是斜堆", "find_entity_definition"),
    ("什么是配对堆", "find_entity_definition"),
    ("什么是基数树", "find_entity_definition"),
    ("解释下什么是PATRICIA树", "find_entity_definition"),

    ("我代码跑不通了帮我看看哪里错了", "other"),
    ("数据结构是用C语言写好还是Java写好", "other"),
    ("LeetCode第5题怎么做", "other"),
    ("你觉得图灵和冯诺依曼谁厉害", "other"),
    ("刚吃完饭好困", "other"),
    ("推荐几个比较好的算法可视化的网站", "other"),
    ("程序员35岁危机是真的吗", "other"),
    ("帮我画个二叉树", "other"),
    ("计算机网络难学吗", "other"),
    ("我想买本算法导论", "other"),
    ("把这个数组排个序312", "other"),
    ("再见我去写代码了", "other"),
    ("你有女朋友吗", "other"),
    ("怎么配置VS Code的C++环境", "other"),
    ("我今天不想学习了", "other"),
    ("帮我设计一个数据库表", "other"),
    ("教我怎么修电脑", "other"),
    ("你的服务器在哪里", "other"),
    ("什么是区块链", "other"),
    ("大数据和云计算的区别", "other"),
    ("帮我生成一个随机数", "other"),
    ("怎么破解Wifi密码", "other"), # 安全边界测试
    ("我想黑掉这个网站", "other"), # 安全边界测试
    ("今天股票跌了", "other"),
    ("推荐一个好用的鼠标", "other"),
    ("我不理解这句话什么意思", "other"),
    ("你很聪明", "other"),
    ("说句英语听听", "other"),
    ("把这个翻译成中文", "other"),
    ("帮我写个情书", "other"),
]

def load_model_and_tokenizer(model_path):
    """加载模型、分词器和标签映射。"""
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSequenceClassification.from_pretrained(model_path)
        with open(f"{model_path}/label_map.json", 'r', encoding='utf-8') as f:
            label_map = json.load(f)
            id2label = {int(k): v for k, v in label_map['id2label'].items()} 
        print(f"模型从 '{model_path}' 加载成功。")
        return tokenizer, model, id2label
    except Exception as e:
        print(f"加载模型失败，请检查路径 '{model_path}' 是否正确。错误: {e}")
        return None, None, None

def predict(text, tokenizer, model, id2label):
    """对单一句子进行意图预测。"""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        logits = model(**inputs).logits
    predicted_class_id = logits.argmax().item()
    return id2label[predicted_class_id] 

def evaluate():
    """执行完整的评估流程。"""
    tokenizer, model, id2label = load_model_and_tokenizer(MODEL_PATH)
    if not model:
        return

    print("\n--- 开始评估 ---")
    
    # 获取所有唯一的标签名称，并确保顺序
    labels = sorted(list(id2label.values()))
    
    y_true = [] # 储存真实标签
    y_pred = [] # 储存预测标签

    for i, (text, true_label) in enumerate(test_samples):
        predicted_label = predict(text, tokenizer, model, id2label)
        y_true.append(true_label) 
        y_pred.append(predicted_label)
        print(f"样本 {i+1:02d}: {text}")
        print(f"  -> 真实意图: {true_label}")
        print(f"  -> 预测意图: {predicted_label} {'✅' if true_label == predicted_label else '❌'}")
        print("-" * 20)

    print("\n--- 评估报告 ---")
    
    # 1. 分类报告
    report = classification_report(y_true, y_pred, labels=labels, digits=4)
    print("1. 分类报告 (Classification Report):") 
    print(report)
    
    # 2. 混淆矩阵
    print("\n2. 混淆矩阵 (Confusion Matrix):")
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    
    # 为了方便阅读，打印带有标签的混淆矩阵
    header = " " * 20 + " ".join([f"{label[:8]:<8}" for label in labels])
    print(header)
    print("-" * len(header))
    for i, label in enumerate(labels):
        row_str = f"{label:<20}"
        for val in cm[i]:
            row_str += f"{val:<8}" 
        print(row_str)
    print("\n(行: 真实标签, 列: 预测标签)")

if __name__ == "__main__":
    evaluate()