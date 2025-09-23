#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据结构课程知识图谱数据生成器 - 关系均等分布版
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
    DELAY_BETWEEN_REQUESTS = 0
    CONCURRENCY = 30
    
    # 数据生成配置
    NUM_RECORDS = 30000
    MAX_PROMPTS = 1000
    MIN_PROMPTS_PER_RELATION = 5
    
    # 文件路径配置
    OUTPUT_FILE = "/root/KG_inde/generate_data/data_backups/knowledge_graph_sentences_2.txt"
    PROMPTS_FILE = "kg_prompts.txt"
    VOCAB_DICT_FILE = "../DeepKE/example/ner/prepare-data/vocab_dict.csv"
    
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

# ========================= 关系模板 =============================
RELATION_TEMPLATES = {
    "rely": [
        "{entity1}的实现需要依赖{entity2}",
        "{entity1}算法依赖于{entity2}的支持",
        "{entity1}的执行依赖{entity2}提供的功能",
        "{entity1}操作需要{entity2}作为基础",
        "{entity1}的性能依赖于{entity2}的效率"
    ],
    "b-rely": [
        "{entity1}被{entity2}算法所依赖",
        "{entity1}为{entity2}提供基础支持",
        "{entity1}是{entity2}实现的前提条件",
        "{entity1}支撑着{entity2}的运行",
        "{entity1}是{entity2}不可缺少的组成部分"
    ],
    "belg": [
        "{entity1}属于{entity2}的范畴",
        "{entity1}是{entity2}的一种类型",
        "{entity1}归类为{entity2}",
        "{entity1}是{entity2}中的一员",
        "{entity1}被划分到{entity2}类别中"
    ],
    "b-belg": [
        "{entity1}包含{entity2}这种类型",
        "{entity1}涵盖了{entity2}",
        "{entity1}的范围包括{entity2}",
        "{entity1}囊括{entity2}在内",
        "{entity1}是{entity2}的上级分类"
    ],
    "syno": [
        "{entity1}与{entity2}是同义概念",
        "{entity1}和{entity2}表示相同含义",
        "{entity1}等同于{entity2}",
        "{entity1}就是{entity2}的另一种说法",
        "{entity1}与{entity2}在本质上相同"
    ],
    "anto": [
        "{entity1}与{entity2}形成对比关系",
        "{entity1}和{entity2}是相对的概念",
        "{entity1}与{entity2}互为对立",
        "{entity1}和{entity2}呈现相反特性",
        "{entity1}与{entity2}构成对偶关系"
    ],
    "attr": [
        "{entity1}是{entity2}的重要属性",
        "{entity1}表征了{entity2}的特性",
        "{entity1}描述{entity2}的性质",
        "{entity1}是衡量{entity2}的指标",
        "{entity1}反映了{entity2}的特征"
    ],
    "b-attr": [
        "{entity1}具有{entity2}这一属性",
        "{entity1}的特征包括{entity2}",
        "{entity1}表现出{entity2}的性质",
        "{entity1}拥有{entity2}特性",
        "{entity1}展现了{entity2}的特点"
    ]
}

# ========================= 核心函数 =============================
def create_client():
    """创建OpenAI客户端"""
    openai.api_key = Config.API_KEY
    openai.api_base = Config.BASE_URL
    return openai

def get_all_entities():
    """获取所有实体列表"""
    all_entities = []
    for category, entities in KNOWLEDGE_GRAPH_BASE.items():
        all_entities.extend(entities)
    return list(set(all_entities))  # 去重

def generate_relation_prompts(num_records):
    """生成8种关系类型均等分布的提示词"""
    prompts = []
    all_entities = get_all_entities()
    
    # 每种关系类型分配相等数量
    records_per_relation = num_records // len(RELATION_TYPES)
    remaining_records = num_records % len(RELATION_TYPES)
    
    relation_counts = {}
    for relation in RELATION_TYPES.keys():
        count = records_per_relation
        if remaining_records > 0:
            count += 1
            remaining_records -= 1
        relation_counts[relation] = count
    
    print(f"📊 关系分布计划: {relation_counts}")
    
    # 为每种关系生成提示词
    for relation_type, count in relation_counts.items():
        templates = RELATION_TEMPLATES[relation_type]
        
        for _ in range(count):
            # 随机选择两个不同的实体
            entity1, entity2 = random.sample(all_entities, 2)
            template = random.choice(templates)
            
            # 生成提示词
            prompt = template.format(entity1=entity1, entity2=entity2)
            prompts.append((prompt, relation_type, entity1, entity2))
    
    random.shuffle(prompts)
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
    print("\n🔧 正在进行数据后处理优化...")
    
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
    print(f"📊 关系分布统计: {dict(relation_stats)}")
    return processed

def process_large_batch(prompt_data_list):
    """批量处理提示词"""
    print(f"\n🚀 开始批量生成 {len(prompt_data_list)} 条数据...")
    
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
        
        print(f"💾 数据已保存到: {filename}")
        print(f"💾 关系数据已保存到: {relation_filename}")
        
        return analyze_data_quality(results)
        
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return None

def analyze_data_quality(results):
    """分析生成数据的质量"""
    print("\n📊 数据质量分析:")
    
    all_entities = get_all_entities()
    
    # 统计关系分布
    relation_counts = Counter(result['relation'] for result in results)
    print(f"🔗 关系分布: {dict(relation_counts)}")
    
    # 统计实体覆盖率
    used_entities = set()
    for result in results:
        used_entities.add(result['entity1'])
        used_entities.add(result['entity2'])
    
    coverage_rate = (len(used_entities) / len(all_entities)) * 100
    print(f"🎯 实体覆盖率: {len(used_entities)}/{len(all_entities)} ({coverage_rate:.1f}%)")
    
    # 统计句子长度
    lengths = [len(result['text']) for result in results]
    avg_length = sum(lengths) / len(lengths)
    print(f"📏 平均句子长度: {avg_length:.1f}字")
    
    return {
        'relation_distribution': dict(relation_counts),
        'entity_coverage': coverage_rate,
        'used_entities': len(used_entities),
        'total_entities': len(all_entities),
        'avg_length': avg_length
    }

def update_vocab_dict():
    """更新词典文件"""
    vocab_file = "/root/KG_inde/DeepKE/example/ner/prepare-data/vocab_dict.csv"
    
    # 读取现有词典
    existing_entities = set()
    if os.path.exists(vocab_file):
        with open(vocab_file, 'r', encoding='utf-8') as f:
            for line in f:
                if ',' in line:
                    entity = line.strip().split(',')[0]
                    existing_entities.add(entity)
    
    # 获取所有新实体
    all_entities = get_all_entities()
    new_entities = []
    
    for entity in all_entities:
        if entity not in existing_entities:
            # 根据实体类型分配标签
            if any(entity in KNOWLEDGE_GRAPH_BASE[cat] for cat in ["排序算法", "查找算法", "图算法", "算法设计"]):
                label = "ARI"  # 算法
            else:
                label = "CON"  # 概念
            new_entities.append(f"{entity},{label}")
    
    # 追加新实体到文件
    if new_entities:
        with open(vocab_file, 'a', encoding='utf-8') as f:
            for entity_line in new_entities:
                f.write(entity_line + '\n')
        print(f"📝 已向词典添加 {len(new_entities)} 个新实体")
    else:
        print("📝 词典已包含所有实体，无需更新")

# DataStructureKGConfig类已合并到Config类中

def generate_sentence_for_relation(relation: str, head_entity: str, tail_entity: str) -> str:
    """
    根据关系类型和实体生成句子
    
    Args:
        relation: 关系类型
        head_entity: 头实体
        tail_entity: 尾实体
    
    Returns:
        生成的句子
    """
    templates = {
        'syno': [
            f"{head_entity}和{tail_entity}是同义概念",
            f"{head_entity}与{tail_entity}具有相同的含义",
            f"{head_entity}等同于{tail_entity}",
            f"在数据结构中，{head_entity}和{tail_entity}表示相同的概念"
        ],
        'anto': [
            f"{head_entity}和{tail_entity}是相反的操作",
            f"{head_entity}与{tail_entity}具有相反的作用",
            f"{head_entity}和{tail_entity}是对立的概念",
            f"在算法中，{head_entity}和{tail_entity}执行相反的功能"
        ],
        'belg': [
            f"{head_entity}包含{tail_entity}",
            f"{tail_entity}是{head_entity}的组成部分",
            f"{head_entity}由{tail_entity}等部分构成",
            f"在{head_entity}中包含了{tail_entity}"
        ],
        'b-belg': [
            f"{tail_entity}包含{head_entity}",
            f"{head_entity}是{tail_entity}的组成部分",
            f"{tail_entity}由{head_entity}等部分构成",
            f"在{tail_entity}中包含了{head_entity}"
        ],
        'rely': [
            f"{head_entity}依赖于{tail_entity}",
            f"{head_entity}需要使用{tail_entity}",
            f"{head_entity}的实现基于{tail_entity}",
            f"实现{head_entity}时需要依赖{tail_entity}"
        ],
        'b-rely': [
            f"{tail_entity}依赖于{head_entity}",
            f"{tail_entity}需要使用{head_entity}",
            f"{tail_entity}的实现基于{head_entity}",
            f"实现{tail_entity}时需要依赖{head_entity}"
        ],
        'attr': [
            f"{head_entity}具有{tail_entity}属性",
            f"{head_entity}的特征是{tail_entity}",
            f"{head_entity}表现出{tail_entity}的特性",
            f"{tail_entity}是{head_entity}的重要属性"
        ],
        'b-attr': [
            f"{tail_entity}具有{head_entity}属性",
            f"{tail_entity}的特征是{head_entity}",
            f"{tail_entity}表现出{head_entity}的特性",
            f"{head_entity}是{tail_entity}的重要属性"
        ],
        'none': [
            f"{head_entity}和{tail_entity}没有直接关系",
            f"{head_entity}与{tail_entity}相互独立",
            f"在数据结构中，{head_entity}和{tail_entity}是不同的概念",
            f"{head_entity}和{tail_entity}分别用于不同的场景"
        ]
    }
    
    if relation in templates:
        return random.choice(templates[relation])
    else:
        return f"{head_entity}和{tail_entity}存在{relation}关系"

def main():
    """主函数 - 集成文本数据生成和标注数据生成"""
    
    print("=== 数据结构知识图谱构建系统 ===")
    print(f"目标生成数量: {Config.NUM_RECORDS}")
    print(f"每种关系最少: {Config.MIN_PROMPTS_PER_RELATION}")
    
    # 第一步：生成关系提示词（用于LLM文本生成）
    print("\n第一步：生成关系提示词...")
    prompt_tuples = generate_relation_prompts(Config.NUM_RECORDS)
    
    # 第二步：调用LLM生成文本数据（如果需要）
    print("\n第二步：准备LLM文本生成...")
    llm_prompts = []
    for prompt_tuple in prompt_tuples:
        if len(prompt_tuple) >= 4:
            prompt, relation_type, entity1, entity2 = prompt_tuple
            llm_prompts.append(prompt)
    
    # 保存LLM提示词到文件
    with open(Config.PROMPTS_FILE, 'w', encoding='utf-8') as f:
        for prompt in llm_prompts:
            f.write(prompt + '\n')
    
    print(f"LLM提示词已保存到: {Config.PROMPTS_FILE}")
    print(f"可使用这些提示词调用LLM生成自然语言文本")
    
    # 第三步：生成关系抽取标注文件
    print("\n第三步：生成关系抽取标注文件...")
    
    # 转换为标注数据格式
    annotation_data = []
    for prompt_tuple in prompt_tuples:
        if len(prompt_tuple) >= 4:
            _, relation_type, entity1, entity2 = prompt_tuple
            # 生成句子
            sentence = generate_sentence_for_relation(relation_type, entity1, entity2)
            annotation_data.append({
                'sentence': sentence,
                'relation': relation_type,
                'head': entity1,
                'tail': entity2
            })
    
    # 生成标注文件
    generate_annotation_files_from_data(annotation_data, Config.ANNOTATION_OUTPUT_DIR)
    
    # 第四步：统计和验证
    print("\n第四步：数据统计和验证...")
    
    # 统计关系分布
    relation_stats = Counter()
    for data in annotation_data:
        relation_stats[data['relation']] += 1
    
    print(f"\n=== 生成完成 ===")
    print(f"LLM提示词数量: {len(llm_prompts)}")
    print(f"标注数据数量: {len(annotation_data)}")
    print(f"LLM提示词文件: {Config.PROMPTS_FILE}")
    print(f"标注文件目录: {Config.ANNOTATION_OUTPUT_DIR}")
    
    print("\n关系分布:")
    for relation, count in sorted(relation_stats.items()):
        print(f"  {relation}: {count}")
    
    # 验证实体一致性
    all_entities = get_all_entities()
    print(f"\n实体统计:")
    print(f"  总实体数: {len(all_entities)}")
    
    # 按类别统计
    category_stats = Counter()
    for category, entities in KNOWLEDGE_GRAPH_BASE.items():
        category_stats[category] = len(entities)
    
    print("  类别分布:")
    for category, count in sorted(category_stats.items()):
        print(f"    {category}: {count}")
    
    print(f"\n=== 使用说明 ===")
    print(f"1. LLM文本生成: 使用 {Config.PROMPTS_FILE} 中的提示词调用LLM生成自然语言文本")
    print(f"2. 关系抽取训练: 使用 {Config.ANNOTATION_OUTPUT_DIR} 中的标注文件训练关系抽取模型")
    print(f"3. 两个任务可以独立进行，也可以结合使用")

def generate_annotation_files_from_data(annotation_data: List[Dict], output_dir: str) -> None:
    """
    从标注数据生成DeepKE关系抽取标注文件
    
    Args:
        annotation_data: 标注数据列表，每个元素包含sentence, relation, head, tail
        output_dir: 输出目录路径
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 生成关系映射文件
    relation_mapping = {}
    relation_index = 0
    
    # 为每种关系分配索引，但跳过none关系
    for relation in RELATION_TYPES.keys():
        if relation != "none":
            relation_mapping[relation] = relation_index
            relation_index += 1
    
    # 添加none关系作为最后一个
    relation_mapping["none"] = relation_index
    
    # 写入关系映射文件
    relation_file = os.path.join(output_dir, "relation.csv")
    with open(relation_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['head_type', 'tail_type', 'relation', 'index'])
        
        for relation, index in relation_mapping.items():
            if relation == "none":
                writer.writerow(['CON', 'CON', relation, index])
            else:
                # 根据关系类型确定头尾实体类型
                writer.writerow(['CON', 'CON', relation, index])
                writer.writerow(['ARI', 'ARI', relation, index])
                writer.writerow(['CON', 'ARI', relation, index])
                writer.writerow(['ARI', 'CON', relation, index])
    
    # 重新生成关系映射文件（简化版本）
    with open(relation_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['head_type', 'tail_type', 'relation', 'index'])
        
        index = 0
        for relation in RELATION_TYPES.keys():
            writer.writerow(['CON', 'ARI', relation, index])
            index += 1
        writer.writerow(['CON', 'CON', 'none', index])
    
    # 2. 准备训练数据
    training_data = []
    for data in annotation_data:
        sentence = data['sentence']
        relation = data['relation']
        head = data['head']
        tail = data['tail']
        
        # 计算实体在句子中的位置
        head_offset = sentence.find(head)
        tail_offset = sentence.find(tail)
        
        # 如果找不到实体位置，跳过这条数据
        if head_offset == -1 or tail_offset == -1:
            continue
            
        training_data.append({
            'sentence': sentence,
            'relation': relation,
            'head': head,
            'tail': tail,
            'head_offset': head_offset,
            'tail_offset': tail_offset
        })
    
    # 3. 随机打乱数据
    random.shuffle(training_data)
    
    # 4. 按8:1:1分割数据
    total_size = len(training_data)
    train_size = int(total_size * 0.8)
    valid_size = int(total_size * 0.1)
    
    train_data = training_data[:train_size]
    valid_data = training_data[train_size:train_size + valid_size]
    test_data = training_data[train_size + valid_size:]
    
    # 5. 写入训练、验证、测试文件
    datasets = [
        (train_data, "train.csv"),
        (valid_data, "valid.csv"),
        (test_data, "test.csv")
    ]
    
    for dataset, filename in datasets:
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['sentence', 'relation', 'head', 'tail', 'head_offset', 'tail_offset'])
            
            for item in dataset:
                writer.writerow([
                    item['sentence'],
                    item['relation'],
                    item['head'],
                    item['tail'],
                    item['head_offset'],
                    item['tail_offset']
                ])
    
    print(f"标注文件生成完成:")
    print(f"  关系映射: {relation_file}")
    print(f"  训练数据: {len(train_data)} 条")
    print(f"  验证数据: {len(valid_data)} 条") 
    print(f"  测试数据: {len(test_data)} 条")

if __name__ == "__main__":
    main()