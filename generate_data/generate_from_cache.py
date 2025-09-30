#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从缓存数据生成最终文件的脚本
"""

import json
import os
import re
from collections import defaultdict

def load_cache_data():
    """加载缓存数据"""
    cache_file = "/root/KG_inde/generate_data/data_backups/api_cache.json"
    
    if not os.path.exists(cache_file):
        print(f"❌ 缓存文件不存在: {cache_file}")
        return {}
    
    with open(cache_file, 'r', encoding='utf-8') as f:
        cache_data = json.load(f)
    
    print(f"📦 加载缓存数据: {len(cache_data)} 条记录")
    return cache_data

def parse_sentences_from_cache(cache_data):
    """从缓存数据中解析句子"""
    all_sentences = []
    relation_counts = defaultdict(int)
    
    # 关系类型映射
    relation_types = {
        "hasComplexity": "算法的复杂度属性",
        "uses": "算法使用的数据结构", 
        "variantOf": "数据结构的变体关系",
        "appliesTo": "数据结构的应用场景",
        "provides": "数据结构提供的操作",
        "implementedAs": "数据结构的实现方式",
        "usedIn": "操作的应用场景"
    }
    
    for cache_key, response_text in cache_data.items():
        # 按行分割响应文本
        lines = response_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 尝试识别关系类型和实体
            sentence_data = parse_sentence(line, relation_types)
            if sentence_data:
                all_sentences.append(sentence_data)
                relation_counts[sentence_data['relation']] += 1
    
    print(f"✅ 解析完成，共 {len(all_sentences)} 条句子")
    for relation, count in relation_counts.items():
        print(f"  - {relation}: {count} 条")
    
    return all_sentences, relation_counts

def parse_sentence(sentence, relation_types):
    """解析单个句子，识别关系和实体"""
    
    # 定义关系识别模式
    patterns = {
        "hasComplexity": [
            r"(.+?)算法.*?复杂度.*?([OΘΩ]\([^)]+\)|时间复杂度|空间复杂度|[OΘΩ]记号|平均查找长度|势能方法|摊还分析)",
            r"(.+?)的.*?复杂度.*?([OΘΩ]\([^)]+\)|时间复杂度|空间复杂度|[OΘΩ]记号|平均查找长度|势能方法|摊还分析)",
        ],
        "uses": [
            r"(.+?)算法.*?使用.*?([^。，,\n]+?)(?:来实现|数据结构|进行|作为)",
            r"(.+?).*?依赖.*?([^。，,\n]+?)数据结构",
            r"(.+?).*?采用.*?([^。，,\n]+?)(?:作为|进行)",
        ],
        "variantOf": [
            r"([^。，,\n]+?)是([^。，,\n]+?)的.*?变体",
            r"([^。，,\n]+?)属于([^。，,\n]+?)的.*?形式",
            r"([^。，,\n]+?).*?基于([^。，,\n]+?)改进",
        ],
        "appliesTo": [
            r"([^。，,\n]+?).*?应用于([^。，,\n]+?)场景",
            r"([^。，,\n]+?).*?适合.*?([^。，,\n]+?)(?:场景|问题)",
            r"([^。，,\n]+?).*?用于([^。，,\n]+?)(?:场景|问题|中)",
        ],
        "provides": [
            r"([^。，,\n]+?)提供.*?([^。，,\n]+?)(?:功能|操作)",
            r"([^。，,\n]+?)支持([^。，,\n]+?)操作",
            r"([^。，,\n]+?).*?实现([^。，,\n]+?)(?:功能|操作)",
        ],
        "implementedAs": [
            r"([^。，,\n]+?).*?通过([^。，,\n]+?)来实现",
            r"([^。，,\n]+?).*?采用.*?([^。，,\n]+?)方法",
            r"([^。，,\n]+?).*?基于([^。，,\n]+?)进行实现",
        ],
        "usedIn": [
            r"([^。，,\n]+?)操作.*?用于([^。，,\n]+?)(?:场景|中)",
            r"([^。，,\n]+?).*?常用于([^。，,\n]+?)(?:场景|问题)",
            r"([^。，,\n]+?).*?应用.*?([^。，,\n]+?)场景",
        ]
    }
    
    # 尝试匹配每种关系类型
    for relation, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, sentence)
            if match:
                head = match.group(1).strip()
                tail = match.group(2).strip()
                
                # 清理实体名称
                head = clean_entity(head)
                tail = clean_entity(tail)
                
                if head and tail and head != tail:
                    return {
                        'sentence': sentence,
                        'relation': relation,
                        'head': head,
                        'tail': tail
                    }
    
    return None

def clean_entity(entity):
    """清理实体名称"""
    # 移除常见的修饰词
    entity = re.sub(r'^(在|当|使用|通过|为了|实现|分析|构建)', '', entity)
    entity = re.sub(r'(算法|数据结构|问题|场景|操作|方法|过程|时|中)$', '', entity)
    entity = entity.strip('，,。、')
    return entity.strip()

def save_data(sentences, output_dir="/root/KG_inde/generate_data/data_backups"):
    """保存数据到文件"""
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存为JSON格式
    json_file = os.path.join(output_dir, "knowledge_graph_sentences_from_cache.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(sentences, f, ensure_ascii=False, indent=2)
    
    # 保存为文本格式
    txt_file = os.path.join(output_dir, "knowledge_graph_sentences_from_cache.txt")
    with open(txt_file, 'w', encoding='utf-8') as f:
        for item in sentences:
            f.write(f"{item['sentence']}\t{item['relation']}\t{item['head']}\t{item['tail']}\n")
    
    print(f"✅ 数据已保存:")
    print(f"  - JSON格式: {json_file}")
    print(f"  - 文本格式: {txt_file}")
    
    return json_file, txt_file

def main():
    """主函数"""
    print("🚀 开始从缓存生成知识图谱数据...")
    
    # 加载缓存数据
    cache_data = load_cache_data()
    if not cache_data:
        return
    
    # 解析句子
    sentences, relation_counts = parse_sentences_from_cache(cache_data)
    
    if not sentences:
        print("❌ 没有解析到有效的句子数据")
        return
    
    # 保存数据
    json_file, txt_file = save_data(sentences)
    
    print(f"\n📊 数据统计:")
    print(f"总句子数: {len(sentences)}")
    for relation, count in relation_counts.items():
        percentage = (count / len(sentences)) * 100 if sentences else 0
        print(f"  - {relation}: {count} 条 ({percentage:.1f}%)")
    
    print(f"\n✅ 从缓存生成数据完成!")

if __name__ == "__main__":
    main()