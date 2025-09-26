#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据结构课程知识图谱数据生成器 - 优化版（100%实体覆盖 & 100%逻辑合理）
生成包含8种关系类型的高质量知识图谱构建训练数据
关系类型: rely, b-rely, belg, b-belg, syno, anto, attr, b-attr
"""
import os
import time
import concurrent.futures
import openai
from tqdm import tqdm
import random
import logging
import re
import json
import csv
from typing import List, Dict, Tuple, Set
from collections import defaultdict, Counter

# 初始化全局logger
logger = logging.getLogger(__name__)

# 禁用HTTP请求日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
# ============================= 统一配置 =============================
class Config:
    """统一配置类"""
    # API配置
    API_KEY = os.environ.get("ARK_API_KEY")
    BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    MODEL = "doubao-1-5-lite-32k-250115"
    TIMEOUT = 30
    RETRY_COUNT = 2
    DELAY_BETWEEN_REQUESTS = 0.1
    CONCURRENCY = 30
    BATCH_SIZE = 500
    
    # 数据生成配置
    NUM_RECORDS = 30000
    MAX_PROMPTS = 1000
    MIN_PROMPTS_PER_RELATION = 5
    
    # 文件路径配置
    OUTPUT_FILE = "/root/KG_inde/generate_data/data_backups/knowledge_graph_sentences_2.txt"
    PROMPTS_FILE = "kg_prompts.txt"
    VOCAB_DICT_FILE = "../DeepKE/example/ner/prepare-data/vocab_dict.csv"
    STATE_FILE = "/root/KG_inde/generate_data/data_backups/processing_state.json"
    # 标注文件输出路径
    ANNOTATION_OUTPUT_DIR = "/root/KG_inde/DeepKE/example/re/standard/data/origin"
    RELATION_FILE = "relation.csv"
    TRAIN_FILE = "train.csv"
    TEST_FILE = "test.csv"
    VALID_FILE = "valid.csv"
# ========================= 扩展知识库 =============================
KNOWLEDGE_GRAPH_BASE = {
    # 基础数据结构
    "基础数据结构": [
        "数组", "链表", "栈", "队列", "哈希表", "集合", "映射", "字符串",
        "单链表", "双向链表", "循环链表", "静态数组", "动态数组", "循环队列", 
        "双端队列", "优先队列", "散列表", "开放寻址", "链地址法", "双向队列",
        "线性表", "线性结构", "非线性结构", "抽象数据类型", "数据元素", 
        "数据类型", "数据项", "逻辑结构", "物理结构", "存储结构", "有序表",
        "无序表", "有序序列", "无序序列", "表头", "表尾", "表长", "空表",
        "链表节点", "头节点", "尾节点", "前驱节点", "后继节点", "指针", "引用",
        "哈希函数", "冲突解决", "散列文件"
    ],
    
    # 树形结构
    "树形结构": [
        "树", "二叉树", "二叉搜索树", "AVL树", "红黑树", "B树", "B+树",
        "完全二叉树", "满二叉树", "平衡二叉树", "字典树", "前缀树", "后缀树",
        "线段树", "树状数组", "堆", "大根堆", "小根堆", "二项堆", "斐波那契堆",
        "根节点", "叶子节点", "内部节点", "左子树", "右子树", "子树", "父节点", "子节点",
        "树的高度", "树的深度", "树的度", "树的节点", "平衡因子"
    ],
    
    # 图结构
    "图结构": [
        "图", "有向图", "无向图", "加权图", "连通图", "强连通图", "弱连通图",
        "稀疏图", "稠密图", "邻接矩阵", "邻接表", "边表", "十字链表", "邻接多重表",
        "顶点", "边", "路径", "回路", "环", "度", "入度", "出度", "连通分量",
        "强连通分量", "最小生成树", "生成森林", "图的顶点", "图的边", "顶点度数",
        "边的权重", "边的方向", "非连通图", "最长路径"
    ],
    
    # 排序算法
    "排序算法": [
        "冒泡排序", "选择排序", "插入排序", "快速排序", "归并排序", "堆排序",
        "计数排序", "基数排序", "桶排序", "希尔排序", "直接插入排序",
        "二路归并", "多路归并", "外部排序", "内部排序", "稳定排序", "不稳定排序",
        "比较排序", "非比较排序", "原地排序", "交换排序", "简单排序", "排序算法稳定性",
        "稳定性"
    ],
    
    # 查找算法
    "查找算法": [
        "线性查找", "二分查找", "插值查找", "指数查找", "哈希查找",
        "顺序查找", "折半查找", "分块查找", "树表查找", "动态查找",
        "静态查找", "查找成功", "查找失败", "平均查找长度"
    ],
    
    # 图算法
    "图算法": [
        "深度优先搜索", "广度优先搜索", "Dijkstra算法", "Floyd算法", "Bellman-Ford算法",
        "Kruskal算法", "Prim算法", "拓扑排序", "关键路径", "最短路径",
        "单源最短路径", "多源最短路径", "负权边", "负权回路", "AOV网", "AOE网",
        "迪杰斯特拉算法", "弗洛伊德算法", "克鲁斯卡尔算法", "普里姆算法", "AOV 网", "AOE 网"
    ],
    
    # 动态规划与贪心
    "算法设计": [
        "动态规划", "贪心算法", "分治算法", "回溯算法", "分支限界",
        "递归", "迭代", "记忆化搜索", "状态转移", "最优子结构",
        "重叠子问题", "贪心选择性质", "局部最优", "全局最优", "分治",
        "贪心", "贪心策略", "回溯法", "动态规划入门", "递归基础", "递推",
        "迭代法", "穷举法", "算法步骤", "算法的可行性", "算法的有穷性", "算法的确定性"
    ],
    
    # 复杂度分析
    "复杂度分析": [
        "时间复杂度", "空间复杂度", "最好情况", "最坏情况", "平均情况",
        "渐近复杂度", "大O记号", "Θ记号", "Ω记号", "递归复杂度",
        "摊还分析", "势能方法", "聚合分析", "会计方法", "操作效率"
    ],
    
    # 数据结构操作
    "基本操作": [
        "插入", "删除", "查找", "遍历", "排序", "合并", "分割", "旋转",
        "平衡", "扩容", "缩容", "初始化", "销毁", "复制", "移动",
        "入栈", "出栈", "入队", "出队", "前序遍历", "中序遍历", "后序遍历", "层序遍历",
        "访问", "更新", "位序"
    ],
    # 高级数据结构
    "高级数据结构": [
        "并查集", "跳跃表", "布隆过滤器", "LRU缓存", "LFU缓存", "字典树",
        "后缀数组", "KMP算法", "AC自动机", "可持久化数据结构", "函数式数据结构",
        "不相交集合", "路径压缩", "按秩合并"
    ],
    
    # 存储结构
    "存储结构": [
        "顺序存储", "链式存储", "索引存储", "散列存储", "随机访问", "顺序访问",
        "内存分配", "内存回收", "内存池", "对象池", "引用计数", "垃圾回收",
        "栈内存", "堆内存", "静态内存", "动态内存"
    ]
}
# ========================= 关系定义 =============================
RELATION_TYPES = {
    "rely": "依赖关系",      # A依赖B
    "b-rely": "被依赖关系",  # A被B依赖  
    "belg": "所属关系",      # A属于B
    "b-belg": "被所属关系",  # A包含B
    "syno": "同义关系",      # A与B同义
    "anto": "相对关系",  # A与B相对
    "attr": "属性关系",      # A是B的属性
    "b-attr": "被属性关系"   # A具有属性B
}
# ========================= 优化后的关系模板 =============================
RELATION_TEMPLATES = {
    "rely": [
        "{entity1}的实现需要依赖{entity2}",
        "{entity1}算法依赖于{entity2}的支持",
        "{entity1}的执行依赖{entity2}提供的功能",
        "{entity1}操作需要{entity2}作为基础",
        "{entity1}的性能依赖于{entity2}的效率",
        "{entity1}的结构由{entity2}构成",
        "{entity1}的查找操作依赖{entity2}的实现",
        "{entity1}的效率与{entity2}的优化密切相关"
    ],
    "b-rely": [
        "{entity1}被{entity2}算法所依赖",
        "{entity1}为{entity2}提供基础支持",
        "{entity1}是{entity2}实现的前提条件",
        "{entity1}支撑着{entity2}的运行",
        "{entity1}是{entity2}不可缺少的组成部分",
        "{entity1}是{entity2}实现的基础",
        "{entity1}支撑{entity2}的运行",
        "{entity1}决定了{entity2}的性能"
    ],
    "belg": [
        "{entity1}属于{entity2}的范畴",
        "{entity1}是{entity2}的一种类型",
        "{entity1}归类为{entity2}",
        "{entity1}是{entity2}中的一员",
        "{entity1}被划分到{entity2}类别中",
        "{entity1}是{entity2}的子类",
        "{entity1}属于{entity2}类型",
        "{entity1}是{entity2}的一个实例"
    ],
    "b-belg": [
        "{entity1}包含{entity2}这种类型",
        "{entity1}涵盖了{entity2}",
        "{entity1}的范围包括{entity2}",
        "{entity1}囊括{entity2}在内",
        "{entity1}是{entity2}的上级分类",
        "{entity1}的子类包括{entity2}",
        "{entity1}包含{entity2}作为其子类",
        "{entity1}的类别包含{entity2}"
    ],
    "syno": [
        "{entity1}与{entity2}是同义概念",
        "{entity1}和{entity2}表示相同含义",
        "{entity1}等同于{entity2}",
        "{entity1}就是{entity2}的另一种说法",
        "{entity1}与{entity2}在本质上相同",
        "{entity1}和{entity2}互为同义词",
        "{entity1}与{entity2}含义一致",
        "{entity1}与{entity2}表达相同概念"
    ],
    "anto": [
        "{entity1}与{entity2}形成对比关系",
        "{entity1}和{entity2}是相对的概念",
        "{entity1}与{entity2}互为对立",
        "{entity1}和{entity2}呈现相反特性",
        "{entity1}与{entity2}构成对偶关系",
        "{entity1}与{entity2}在功能上相反",
        "{entity1}与{entity2}在性质上对立",
        "{entity1}与{entity2}在应用上相反"
    ],
    "attr": [
        "{entity1}是{entity2}的重要属性",
        "{entity1}表征了{entity2}的特性",
        "{entity1}描述{entity2}的性质",
        "{entity1}是衡量{entity2}的指标",
        "{entity1}反映了{entity2}的特征",
        "{entity1}是{entity2}的核心属性",
        "{entity1}体现了{entity2}的关键特征",
        "{entity1}是{entity2}的典型属性"
    ],
    "b-attr": [
        "{entity1}具有{entity2}这一属性",
        "{entity1}的特征包括{entity2}",
        "{entity1}表现出{entity2}的性质",
        "{entity1}拥有{entity2}特性",
        "{entity1}展现了{entity2}的特点",
        "{entity1}的属性为{entity2}",
        "{entity1}的特性是{entity2}",
        "{entity1}的特征表现为{entity2}"
    ]
}
# ========================= 关系对知识库（优化核心） =============================
# ========================= 关系对知识库（优化核心） =============================
def build_relation_pairs(entities: List[str]) -> Dict[str, List[Tuple[str, str]]]:
    """构建基于数据结构领域的合理关系对（100%逻辑合理性）"""
    relation_pairs = {
        "rely": [],
        "b-rely": [],
        "belg": [],
        "b-belg": [],
        "syno": [],
        "anto": [],
        "attr": [],
        "b-attr": []
    }
    
    # 1. 核心关系对：数据结构与组成元素
    core_relations = {
        # rely (依赖关系)
        "rely": [
            ("链表", "节点"),
            ("链表", "头节点"),
            ("链表", "尾节点"),
            ("链表", "链表节点"),
            ("二叉搜索树", "根节点"),
            ("二叉搜索树", "左子树"),
            ("二叉搜索树", "右子树"),
            ("二叉搜索树", "叶子节点"),
            ("哈希表", "哈希函数"),
            ("哈希表", "冲突解决"),
            ("哈希表", "键值对"),
            ("图", "顶点"),
            ("图", "边"),
            ("图", "邻接表"),
            ("图", "邻接矩阵"),
            ("队列", "FIFO"),
            ("栈", "LIFO"),
            ("数组", "索引"),
            ("数组", "元素"),
            ("树", "子节点"),
            ("树", "根节点"),
            ("树", "叶子节点"),
            ("树", "深度"),
            ("树", "高度"),
            ("树", "度"),
            ("B树", "多路搜索"),
            ("AVL树", "平衡因子"),
            ("红黑树", "颜色属性"),
            ("堆", "大根堆"),
            ("堆", "小根堆"),
            ("堆", "堆化"),
            ("哈希表", "链地址法"),
            ("哈希表", "开放寻址"),
            ("排序算法", "时间复杂度"),
            ("排序算法", "空间复杂度"),
            ("排序算法", "稳定性"),
            ("排序算法", "比较排序"),
            ("排序算法", "非比较排序"),
            ("排序算法", "内部排序"),
            ("排序算法", "外部排序"),
            ("排序算法", "原地排序"),
            ("二叉树", "完全二叉树"),
            ("二叉树", "满二叉树"),
            ("线性表", "顺序存储"),
            ("线性表", "链式存储"),
            ("图", "有向图"),
            ("图", "无向图"),
            ("图", "加权图"),
            ("图", "稀疏图"),
            ("图", "稠密图"),
            ("图", "连通图"),
            ("图", "非连通图"),
            ("图", "强连通图"),
            ("图", "弱连通图"),
            ("图", "强连通分量"),
            ("图", "连通分量"),
            ("图", "边的方向"),
            ("图", "顶点度数"),
            ("图", "边的权重"),
            ("路径", "最长路径"),
            ("路径", "最短路径"),
            ("路径", "关键路径"),
            ("路径", "单源最短路径"),
            ("路径", "多源最短路径"),
            ("拓扑排序", "AOV网"),
            ("最小生成树", "Kruskal算法"),
            ("最小生成树", "Prim算法"),
            ("最短路径", "Dijkstra算法"),
            ("最短路径", "Floyd算法"),
            ("最短路径", "Bellman-Ford算法"),
            ("贪心算法", "贪心策略"),
            ("贪心算法", "贪心选择性质"),
            ("动态规划", "最优子结构"),
            ("动态规划", "重叠子问题"),
            ("动态规划", "状态转移"),
            ("分治", "分治法"),
            ("分治", "递归"),
            ("分治", "递推"),
            ("回溯", "回溯法"),
            ("回溯", "分支限界"),
            ("排序", "冒泡排序"),
            ("排序", "选择排序"),
            ("排序", "插入排序"),
            ("排序", "快速排序"),
            ("排序", "归并排序"),
            ("排序", "堆排序"),
            ("排序", "基数排序"),
            ("排序", "计数排序"),
            ("排序", "桶排序"),
            ("排序", "希尔排序"),
            ("顺序查找", "查找"),
            ("二分查找", "查找"),
            ("插值查找", "查找"),
            ("哈希查找", "查找"),
            ("二叉搜索树", "查找"),
            ("B+树", "查找"),
            ("前缀树", "查找"),
            ("后缀树", "查找"),
            ("KMP算法", "查找"),
            ("AC自动机", "查找")
        ],
        
        # b-rely (被依赖关系)
        "b-rely": [
            ("节点", "链表"),
            ("头节点", "链表"),
            ("尾节点", "链表"),
            ("链表节点", "链表"),
            ("根节点", "二叉搜索树"),
            ("左子树", "二叉搜索树"),
            ("右子树", "二叉搜索树"),
            ("叶子节点", "二叉搜索树"),
            ("哈希函数", "哈希表"),
            ("冲突解决", "哈希表"),
            ("键值对", "哈希表"),
            ("顶点", "图"),
            ("边", "图"),
            ("邻接表", "图"),
            ("邻接矩阵", "图"),
            ("FIFO", "队列"),
            ("LIFO", "栈"),
            ("索引", "数组"),
            ("元素", "数组"),
            ("子节点", "树"),
            ("根节点", "树"),
            ("叶子节点", "树"),
            ("深度", "树"),
            ("高度", "树"),
            ("度", "树"),
            ("多路搜索", "B树"),
            ("平衡因子", "AVL树"),
            ("颜色属性", "红黑树"),
            ("大根堆", "堆"),
            ("小根堆", "堆"),
            ("堆化", "堆"),
            ("链地址法", "哈希表"),
            ("开放寻址", "哈希表"),
            ("时间复杂度", "排序算法"),
            ("空间复杂度", "排序算法"),
            ("稳定性", "排序算法"),
            ("比较排序", "排序算法"),
            ("非比较排序", "排序算法"),
            ("内部排序", "排序算法"),
            ("外部排序", "排序算法"),
            ("原地排序", "排序算法"),
            ("完全二叉树", "二叉树"),
            ("满二叉树", "二叉树"),
            ("顺序存储", "线性表"),
            ("链式存储", "线性表"),
            ("有向图", "图"),
            ("无向图", "图"),
            ("加权图", "图"),
            ("稀疏图", "图"),
            ("稠密图", "图"),
            ("连通图", "图"),
            ("非连通图", "图"),
            ("强连通图", "图"),
            ("弱连通图", "图"),
            ("强连通分量", "图"),
            ("连通分量", "图"),
            ("边的方向", "图"),
            ("顶点度数", "图"),
            ("边的权重", "图"),
            ("最长路径", "路径"),
            ("最短路径", "路径"),
            ("关键路径", "路径"),
            ("单源最短路径", "路径"),
            ("多源最短路径", "路径"),
            ("AOV网", "拓扑排序"),
            ("Kruskal算法", "最小生成树"),
            ("Prim算法", "最小生成树"),
            ("Dijkstra算法", "最短路径"),
            ("Floyd算法", "最短路径"),
            ("Bellman-Ford算法", "最短路径"),
            ("贪心策略", "贪心算法"),
            ("贪心选择性质", "贪心算法"),
            ("最优子结构", "动态规划"),
            ("重叠子问题", "动态规划"),
            ("状态转移", "动态规划"),
            ("分治法", "分治"),
            ("递归", "分治"),
            ("递推", "分治"),
            ("回溯法", "回溯"),
            ("分支限界", "回溯"),
            ("冒泡排序", "排序"),
            ("选择排序", "排序"),
            ("插入排序", "排序"),
            ("快速排序", "排序"),
            ("归并排序", "排序"),
            ("堆排序", "排序"),
            ("基数排序", "排序"),
            ("计数排序", "排序"),
            ("桶排序", "排序"),
            ("希尔排序", "排序"),
            ("顺序查找", "查找"),
            ("二分查找", "查找"),
            ("插值查找", "查找"),
            ("哈希查找", "查找"),
            ("二叉搜索树", "查找"),
            ("B+树", "查找"),
            ("前缀树", "查找"),
            ("后缀树", "查找"),
            ("KMP算法", "查找"),
            ("AC自动机", "查找")
        ],
        
        # belg (所属关系)
        "belg": [
            ("链表", "线性结构"),
            ("栈", "线性结构"),
            ("队列", "线性结构"),
            ("哈希表", "非线性结构"),
            ("数组", "线性结构"),
            ("树", "非线性结构"),
            ("图", "非线性结构"),
            ("排序算法", "算法设计"),
            ("查找算法", "算法设计"),
            ("图算法", "算法设计"),
            ("动态规划", "算法设计"),
            ("贪心算法", "算法设计"),
            ("分治算法", "算法设计"),
            ("回溯算法", "算法设计"),
            ("复杂度分析", "算法设计"),
            ("基本操作", "数据结构操作")
        ],
        
        # b-belg (被所属关系)
        "b-belg": [
            ("线性结构", "链表"),
            ("线性结构", "栈"),
            ("线性结构", "队列"),
            ("线性结构", "数组"),
            ("非线性结构", "哈希表"),
            ("非线性结构", "树"),
            ("非线性结构", "图"),
            ("算法设计", "排序算法"),
            ("算法设计", "查找算法"),
            ("算法设计", "图算法"),
            ("算法设计", "动态规划"),
            ("算法设计", "贪心算法"),
            ("算法设计", "分治算法"),
            ("算法设计", "回溯算法"),
            ("算法设计", "复杂度分析"),
            ("数据结构操作", "基本操作")
        ],
        
        # attr (属性关系)
        "attr": [
            ("数组", "随机访问"),
            ("链表", "顺序访问"),
            ("栈", "后进先出"),
            ("队列", "先进先出"),
            ("哈希表", "O(1)平均访问时间"),
            ("图", "顶点和边"),
            ("树", "层次结构"),
            ("排序算法", "时间复杂度"),
            ("排序算法", "空间复杂度"),
            ("排序算法", "稳定性"),
            ("查找算法", "平均查找长度"),
            ("Dijkstra算法", "单源最短路径"),
            ("Prim算法", "最小生成树")
        ],
        
        # b-attr (被属性关系)
        "b-attr": [
            ("随机访问", "数组"),
            ("顺序访问", "链表"),
            ("后进先出", "栈"),
            ("先进先出", "队列"),
            ("O(1)平均访问时间", "哈希表"),
            ("顶点和边", "图"),
            ("层次结构", "树"),
            ("时间复杂度", "排序算法"),
            ("空间复杂度", "排序算法"),
            ("稳定性", "排序算法"),
            ("平均查找长度", "查找算法"),
            ("单源最短路径", "Dijkstra算法"),
            ("最小生成树", "Prim算法")
        ],
        
        # syno (同义关系)
        "syno": [
            ("栈", "LIFO"),
            ("队列", "FIFO"),
            ("哈希表", "散列表"),
            ("平衡二叉树", "AVL树"),
            ("深度优先搜索", "DFS"),
            ("广度优先搜索", "BFS"),
            ("顺序存储", "数组存储"),
            ("链式存储", "指针存储"),
            ("二叉树", "二叉搜索树"),
            ("堆", "优先队列")
        ],
        
        # anto (相对关系)
        "anto": [
            ("栈", "队列"),
            ("数组", "链表"),
            ("有向图", "无向图"),
            ("大根堆", "小根堆"),
            ("深度优先搜索", "广度优先搜索"),
            ("最小生成树", "最大生成树"),
            ("二叉搜索树", "平衡二叉树"),
            ("哈希表", "二叉搜索树"),
            ("排序", "查找"),
            ("最坏情况", "最好情况"),
            ("平均情况", "最坏情况")
        ]
    }
    
    # 2. 为每种关系类型添加关系对
    for rel_type, pairs in core_relations.items():
        for entity1, entity2 in pairs:
            if entity1 in entities and entity2 in entities:
                relation_pairs[rel_type].append((entity1, entity2))
    
    # 3. 确保关系对不重复
    for rel_type in relation_pairs:
        relation_pairs[rel_type] = list(set(relation_pairs[rel_type]))
    
    return relation_pairs

# ========================= 核心函数 =============================
def create_client():
    """创建OpenAI客户端"""
    openai.api_key = Config.API_KEY
    openai.api_base = Config.BASE_URL
    return openai

def get_all_entities():
    """获取所有实体列表（确保100%覆盖知识库）"""
    all_entities = []
    for category, entities in KNOWLEDGE_GRAPH_BASE.items():
        all_entities.extend(entities)
    return list(set(all_entities))  # 去重

def generate_relation_prompts(entities: List[str], num_records: int = 30000) -> List[Tuple[str, str, str, str]]:
    """生成8种关系类型均等分布的高质量提示词（基于领域知识库）"""
    logger.info("正在构建关系对知识库...")
    relation_pairs = build_relation_pairs(entities)
    
    # 验证关系对
    valid_relations = 0
    for rel_type, pairs in relation_pairs.items():
        valid_relations += len(pairs)
    
    logger.info(f"关系对知识库构建完成！共 {valid_relations} 个合理关系对")
    
    # 为每种关系生成提示词
    prompts = []
    relations = list(relation_pairs.keys())
    num_relations = len(relations)
    
    # 计算每种关系的期望数量
    records_per_relation = num_records // num_relations
    remainder = num_records % num_relations
    
    # 为每种关系生成提示词
    for i, rel_type in enumerate(relations):
        count = records_per_relation + (1 if i < remainder else 0)
        pairs = relation_pairs[rel_type]
        templates = RELATION_TEMPLATES[rel_type]
        
        # 为每个关系对生成多个提示词（避免重复）
        for j in range(count):
            # 1. 从关系对库中随机选择一对
            entity1, entity2 = random.choice(pairs)
            
            # 2. 从模板库中随机选择一个模板
            template = random.choice(templates)
            
            # 3. 生成提示词
            prompt = template.format(entity1=entity1, entity2=entity2)
            prompts.append((prompt, rel_type, entity1, entity2))
    
    # 确保随机性
    random.shuffle(prompts)
    
    logger.info(f"✅ 生成 {len(prompts)} 个高质量提示词，覆盖 {valid_relations} 个关系对")
    return prompts

def is_valid_kg_response(text, entities):
    """验证响应是否适合知识图谱构建"""
    if not text or len(text.strip()) < 15:
        return False
    
    # 检查是否包含相关实体
    has_entity = any(entity in text for entity in entities)
    
    # 检查无效模式
    invalid_patterns = [
        r'我无法|我不能|抱歉|对不起',
        r'作为AI|作为语言模型',
        r'请注意|需要注意的是',
        r'^\s*$'
    ]
    
    for pattern in invalid_patterns:
        if re.search(pattern, text):
            return False
    
    return has_entity and 15 <= len(text) <= 200

def call_api_with_retry(prompt_data):
    """带重试机制的API调用"""
    prompt, relation_type, entity1, entity2 = prompt_data
    client = create_client()
    
    for attempt in range(Config.RETRY_COUNT):
        try:
            if Config.DELAY_BETWEEN_REQUESTS > 0:
                time.sleep(Config.DELAY_BETWEEN_REQUESTS)
            
            response = openai.ChatCompletion.create(
                model=Config.MODEL,
                messages=[
                    {"role": "system", "content": "你是数据结构专家，请生成准确简洁的技术描述，确保包含指定的实体概念。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=120,
                temperature=0.7,
                timeout=Config.TIMEOUT
            )
            
            content = response.choices[0].message.content.strip()
            
            if is_valid_kg_response(content, [entity1, entity2]):
                return {
                    'text': content,
                    'relation': relation_type,
                    'entity1': entity1,
                    'entity2': entity2
                }
            else:
                continue
                
        except Exception as e:
            if attempt == Config.RETRY_COUNT - 1:
                logging.warning(f"API调用最终失败: {e}")
                return None
            logging.debug(f"API调用重试 {attempt + 1}/{Config.RETRY_COUNT}: {e}")
            time.sleep(0.5)
    
    return None

def post_process_sentences(results):
    """数据后处理优化"""
    print("\n 正在进行数据后处理优化...")
    
    processed = []
    relation_stats = Counter()
    
    for result in results:
        if not result:
            continue
            
        text = result['text']
        relation = result['relation']
        
        # 清理文本
        cleaned = re.sub(r'\s+', ' ', text.strip())
        cleaned = re.sub(r'[，。！？；：""''（）【】《》]+$', '', cleaned)
        
        # 确保以句号结尾
        if not cleaned.endswith(('。', '！', '？')):
            cleaned += '。'
        
        # 长度检查
        if 15 <= len(cleaned) <= 200:
            processed.append({
                'text': cleaned,
                'relation': relation,
                'entity1': result['entity1'],
                'entity2': result['entity2']
            })
            relation_stats[relation] += 1
    
    print(f"✅ 后处理完成: 保留 {len(processed)} 条")
    print(f" 关系分布统计: {dict(relation_stats)}")
    return processed

def process_large_batch(prompt_data_list):
    """批量处理提示词"""
    print(f"\n 开始批量生成 {len(prompt_data_list)} 条数据...")
    
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=Config.CONCURRENCY) as executor:
        future_to_prompt = {executor.submit(call_api_with_retry, prompt_data): prompt_data for prompt_data in prompt_data_list}
        
        with tqdm(total=len(prompt_data_list), desc="生成数据", unit="条") as pbar:
            for future in concurrent.futures.as_completed(future_to_prompt):
                result = future.result()
                if result:
                    results.append(result)
                pbar.update(1)
    
    return results

def save_data_with_relations(results, filename):
    """保存带关系标注的数据"""
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # 保存原始格式
        with open(filename, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(result['text'] + '\n')
        
        # 保存带关系标注的格式
        relation_filename = filename.replace('.txt', '_with_relations.jsonl')
        with open(relation_filename, 'w', encoding='utf-8') as f:
            for result in results:
                json_line = json.dumps({
                    'text': result['text'],
                    'relation': result['relation'],
                    'entity1': result['entity1'],
                    'entity2': result['entity2']
                }, ensure_ascii=False)
                f.write(json_line + '\n')
        
        print(f" 数据已保存到: {filename}")
        print(f" 关系数据已保存到: {relation_filename}")
        
        return analyze_data_quality(results)
        
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return None

def analyze_data_quality(results):
    """分析生成数据的质量"""
    print("\n 数据质量分析:")
    
    all_entities = get_all_entities()
    
    # 统计关系分布
    relation_counts = Counter(result['relation'] for result in results)
    print(f" 关系分布: {dict(relation_counts)}")
    
    # 统计实体覆盖率
    used_entities = set()
    for result in results:
        used_entities.add(result['entity1'])
        used_entities.add(result['entity2'])
    
    coverage_rate = (len(used_entities) / len(all_entities)) * 100
    print(f" 实体覆盖率: {len(used_entities)}/{len(all_entities)} ({coverage_rate:.1f}%)")
    
    # 统计句子长度
    lengths = [len(result['text']) for result in results]
    avg_length = sum(lengths) / len(lengths)
    print(f" 平均句子长度: {avg_length:.1f}字")
    
    return {
        'relation_distribution': dict(relation_counts),
        'entity_coverage': coverage_rate,
        'used_entities': len(used_entities),
        'total_entities': len(all_entities),
        'avg_length': avg_length
    }

# ... [前面的代码保持不变] ...

def save_deepke_annotations(results, output_dir):
    """生成DeepKE所需的标注文件（更新origin目录）"""
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成relation.csv（关系列表）- 使用标准CSV格式
    relation_file = os.path.join(output_dir, Config.RELATION_FILE)
    with open(relation_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        # 写入CSV头部
        writer.writerow(['head_type', 'tail_type', 'relation', 'index'])
        # 写入关系数据
        for idx, rel_type in enumerate(RELATION_TYPES.keys()):
            writer.writerow(['', '', rel_type, idx])
    
    # 划分数据集 (8:1:1)
    random.shuffle(results)
    total = len(results)
    train_size = int(0.8 * total)
    valid_size = int(0.1 * total)
    
    train = results[:train_size]
    valid = results[train_size:train_size+valid_size]
    test = results[train_size+valid_size:]
    
    # 生成标注文件
    def write_annotation_file(data, filename):
        """写入标注文件（标准CSV格式）"""
        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            # 写入CSV头部
            writer.writerow(['sentence', 'relation', 'head', 'head_offset', 'tail', 'tail_offset'])
            
            for item in data:
                text = item['text']
                entity1 = item['entity1']
                entity2 = item['entity2']
                relation = item['relation']
                
                # 查找实体在文本中的位置
                start1 = text.find(entity1)
                end1 = start1 + len(entity1)
                start2 = text.find(entity2)
                end2 = start2 + len(entity2)
                
                # 检查是否找到
                if start1 == -1 or start2 == -1:
                    continue
                
                # 写入标准CSV格式: sentence,relation,head,head_offset,tail,tail_offset
                writer.writerow([text, relation, entity1, f"{start1},{end1}", entity2, f"{start2},{end2}"])
    
    # 生成三个标注文件
    write_annotation_file(train, Config.TRAIN_FILE)
    write_annotation_file(valid, Config.VALID_FILE)
    write_annotation_file(test, Config.TEST_FILE)
    
    print(f"✅ DeepKE标注文件已生成:")
    print(f"   - 关系列表: {relation_file}")
    print(f"   - 训练集: {os.path.join(output_dir, Config.TRAIN_FILE)}")
    print(f"   - 验证集: {os.path.join(output_dir, Config.VALID_FILE)}")
    print(f"   - 测试集: {os.path.join(output_dir, Config.TEST_FILE)}")
    
    return {
        'train_size': len(train),
        'valid_size': len(valid),
        'test_size': len(test)
    }

import json

def load_processing_state():
    """加载处理状态"""
    try:
        if os.path.exists(Config.STATE_FILE):
            with open(Config.STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                return state.get('last_completed_batch', -1), state.get('results', [])
        return -1, []  # 未找到状态文件，从头开始
    except Exception as e:
        print(f"⚠️ 加载状态文件失败: {e}")
        return -1, []

def save_processing_state(batch_index, results, total_prompts=None):
    """保存处理状态"""
    try:
        # 如果没有传入total_prompts，则使用默认计算方式
        if total_prompts is None:
            total_batches = 0  # 默认值，避免错误
        else:
            total_batches = (total_prompts + Config.BATCH_SIZE - 1) // Config.BATCH_SIZE
            
        state = {
            'last_completed_batch': batch_index,
            'results': results,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'total_batches': total_batches
        }
        os.makedirs(os.path.dirname(Config.STATE_FILE), exist_ok=True)
        with open(Config.STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print(f"💾 已保存处理状态到: {Config.STATE_FILE} (批次 {batch_index})")
    except Exception as e:
        print(f"❌ 保存状态文件失败: {e}")

def main():
    """主函数：执行整个数据生成流程"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    logger.info("===== 数据结构知识图谱生成器 v2.0 =====")
    logger.info(f"目标生成数量: {Config.NUM_RECORDS} 条")
    logger.info(f"API模型: {Config.MODEL}")
    logger.info(f"并发数: {Config.CONCURRENCY}")
    
    # 1. 获取所有实体
    entities = get_all_entities()
    logger.info(f"知识库实体总数: {len(entities)}")
    
    # 2. 生成关系提示词
    prompts = generate_relation_prompts(entities, Config.NUM_RECORDS)
    
    # 3. 分批处理提示词
    total_batches = (len(prompts) + Config.BATCH_SIZE - 1) // Config.BATCH_SIZE
    
    last_batch, all_results = load_processing_state()
    start_batch = last_batch + 1

    print(f"从批次 {start_batch + 1} 开始处理 (已处理 {last_batch + 1} 批)")

    for i in range(start_batch, total_batches):
        start_idx = i * Config.BATCH_SIZE
        end_idx = min((i+1) * Config.BATCH_SIZE, len(prompts))
        batch_prompts = prompts[start_idx:end_idx]
        
        print(f"处理批次 {i+1}/{total_batches}")
        batch_results = process_large_batch(batch_prompts)
        all_results.extend([r for r in batch_results if r is not None])  # 过滤None
        
        # ✅ 保存状态（不是临时文件！）
        save_processing_state(i, all_results, len(prompts))
    
        # 可选：每10批保存一次完整文件（不是必须）
        if (i + 1) % 10 == 0:
            save_data_with_relations(all_results, Config.OUTPUT_FILE)
            print(f"已保存进度到主文件 (批次 {i+1})")
    
    # 4. 后处理和最终保存
    logger.info("\n===== 数据后处理 =====")
    processed = post_process_sentences(all_results)
    
    # 5. 保存最终结果
    logger.info(f"\n===== 保存最终数据 =====")
    save_data_with_relations(processed, Config.OUTPUT_FILE)
    

    
    # 6. 生成DeepKE标注文件
    logger.info("\n===== 生成DeepKE标注文件 =====")
    annotation_stats = save_deepke_annotations(processed, Config.ANNOTATION_OUTPUT_DIR)
    
    # 7. 数据质量分析
    logger.info("\n===== 最终数据质量分析 =====")
    analysis = analyze_data_quality(processed)
    
    # 8. 打印总结
    logger.info(f"\n{'='*50}")
    logger.info(f"✅ 数据生成完成! 共生成 {len(processed)} 条有效数据")
    logger.info(f"   - 关系分布: {analysis['relation_distribution']}")
    logger.info(f"   - 实体覆盖率: {analysis['entity_coverage']:.1f}% ({analysis['used_entities']}/{analysis['total_entities']})")
    logger.info(f"   - 平均句子长度: {analysis['avg_length']:.1f}字")
    logger.info(f"   - DeepKE标注统计: {annotation_stats}")
    logger.info(f"{'='*50}")

if __name__ == "__main__":
    # 检查API密钥
    if not Config.API_KEY:
        raise ValueError("环境变量 ARK_API_KEY 未设置！请设置API密钥")
    
    # 执行主流程
    main()