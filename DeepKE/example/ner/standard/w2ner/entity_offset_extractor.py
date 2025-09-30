#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体偏移量和类型提取器
从knowledge_graph_sentences_new.json文件中提取实体的偏移量和类型信息
"""

import json
import os
import csv
from typing import List, Dict, Tuple, Optional
from tqdm import tqdm


class EntityOffsetExtractor:
    """实体偏移量提取器类"""
    
    def __init__(self, json_file_path: str, vocab_dict_path: str = "/root/KG_inde/vocab_dict.csv"):
        """
        初始化提取器
        
        Args:
            json_file_path: JSON文件路径
            vocab_dict_path: 词典文件路径
        """
        self.json_file_path = json_file_path
        self.vocab_dict_path = vocab_dict_path
        self.data = None
        self.entity_type_dict = {}
        self.load_vocab_dict()
        
    def load_vocab_dict(self) -> bool:
        """
        加载词典文件，建立实体到类型的映射
        
        Returns:
            bool: 加载是否成功
        """
        try:
            with open(self.vocab_dict_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.reader(f)
                for row in csv_reader:
                    if len(row) >= 2:
                        entity = row[0].strip()
                        entity_type = row[1].strip()
                        self.entity_type_dict[entity] = entity_type
            print(f"成功加载词典，共有 {len(self.entity_type_dict)} 个实体类型映射")
            return True
        except Exception as e:
            print(f"加载词典失败: {e}")
            return False
        
    def load_data(self) -> bool:
        """
        加载JSON数据
        
        Returns:
            bool: 加载是否成功
        """
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            print(f"成功加载数据，共有 {len(self.data['sentences'])} 条句子")
            return True
        except Exception as e:
            print(f"加载数据失败: {e}")
            return False
    
    def find_entity_offset(self, sentence: str, entity: str) -> List[int]:
        """
        查找实体在句子中的所有偏移位置
        
        Args:
            sentence: 句子文本
            entity: 实体文本
            
        Returns:
            List[int]: 所有匹配位置的起始偏移量列表
        """
        if not entity or not sentence:
            return []
        
        offsets = []
        start = 0
        while True:
            pos = sentence.find(entity, start)
            if pos == -1:
                break
            offsets.append(pos)
            start = pos + 1
        
        return offsets
    
    def get_entity_type(self, entity: str) -> str:
        """
        根据词典获取实体类型
        
        Args:
            entity: 实体文本
            
        Returns:
            str: 实体类型，如果未找到则返回"ENTITY"
        """
        return self.entity_type_dict.get(entity, "ENTITY")
    
    def extract_entity_info(self, sentence_item: Dict) -> Optional[Dict]:
        """
        从单个句子项中提取实体信息
        
        Args:
            sentence_item: 包含句子和实体信息的字典
            
        Returns:
            Dict: 提取的实体信息，包含偏移量和类型
        """
        sentence = sentence_item.get('sentence', '').strip()
        entity1 = sentence_item.get('entity1', '').strip()
        entity2 = sentence_item.get('entity2', '').strip()
        relation = sentence_item.get('relation', '').strip()
        
        if not sentence or not entity1 or not entity2:
            return None
        
        # 查找实体偏移量
        entity1_offsets = self.find_entity_offset(sentence, entity1)
        entity2_offsets = self.find_entity_offset(sentence, entity2)
        
        if not entity1_offsets or not entity2_offsets:
            return None
        
        # 选择第一个匹配的偏移量
        entity1_offset = entity1_offsets[0]
        entity2_offset = entity2_offsets[0]
        
        # 确保头实体在尾实体之前
        if entity1_offset <= entity2_offset:
            head_entity = entity1
            tail_entity = entity2
            head_offset = entity1_offset
            tail_offset = entity2_offset
        else:
            head_entity = entity2
            tail_entity = entity1
            head_offset = entity2_offset
            tail_offset = entity1_offset
        
        return {
            "sentence": sentence,
            "head": head_entity,
            "tail": tail_entity,
            "head_offset": head_offset,
            "tail_offset": tail_offset,
            "head_type": self.get_entity_type(head_entity),
            "tail_type": self.get_entity_type(tail_entity),
            "relation": relation,
            "head_end_offset": head_offset + len(head_entity),
            "tail_end_offset": tail_offset + len(tail_entity)
        }
    
    def extract_all_entities(self) -> List[Dict]:
        """
        提取所有实体的偏移量和类型信息
        
        Returns:
            List[Dict]: 包含所有实体信息的列表
        """
        if not self.data:
            print("数据未加载，请先调用load_data()")
            return []
        
        results = []
        failed_count = 0
        
        print("开始提取实体偏移量和类型信息...")
        for item in tqdm(self.data['sentences'], desc="处理进度"):
            entity_info = self.extract_entity_info(item)
            if entity_info:
                results.append(entity_info)
            else:
                failed_count += 1
        
        print(f"提取完成！成功: {len(results)}, 失败: {failed_count}")
        return results
    
    def save_results(self, results: List[Dict], output_path: str) -> bool:
        """
        保存提取结果到文件
        
        Args:
            results: 提取的结果列表
            output_path: 输出文件路径
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            print(f"结果已保存到: {output_path}")
            print(f"共保存 {len(results)} 条记录")
            return True
        except Exception as e:
            print(f"保存结果失败: {e}")
            return False
    
    def generate_statistics(self, results: List[Dict]) -> Dict:
        """
        生成统计信息
        
        Args:
            results: 提取的结果列表
            
        Returns:
            Dict: 统计信息
        """
        if not results:
            return {}
        
        relations = [item['relation'] for item in results]
        unique_relations = set(relations)
        
        head_entities = [item['head'] for item in results]
        tail_entities = [item['tail'] for item in results]
        all_entities = set(head_entities + tail_entities)
        
        stats = {
            "total_records": len(results),
            "unique_relations": len(unique_relations),
            "unique_entities": len(all_entities),
            "relation_distribution": {rel: relations.count(rel) for rel in unique_relations},
            "average_sentence_length": sum(len(item['sentence']) for item in results) / len(results)
        }
        
        return stats


def main():
    """主函数"""
    # 文件路径配置
    json_file_path = "/root/KG_inde/DeepKE/example/ner/standard/w2ner/data/knowledge_graph_sentences_new.json"
    output_dir = "/root/KG_inde/output_predict"
    output_file = os.path.join(output_dir, "entity_offsets.json")
    stats_file = os.path.join(output_dir, "extraction_statistics.json")
    
    # 创建提取器实例
    extractor = EntityOffsetExtractor(json_file_path)
    
    # 加载数据
    if not extractor.load_data():
        return
    
    # 提取实体信息
    results = extractor.extract_all_entities()
    
    if not results:
        print("没有提取到任何实体信息")
        return
    
    # 保存结果
    if extractor.save_results(results, output_file):
        print("✅ 实体偏移量提取完成")
    
    # 生成并保存统计信息
    stats = extractor.generate_statistics(results)
    if stats:
        try:
            os.makedirs(output_dir, exist_ok=True)
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            print(f"📊 统计信息已保存到: {stats_file}")
            
            # 打印关键统计信息
            print("\n=== 提取统计 ===")
            print(f"总记录数: {stats['total_records']}")
            print(f"唯一关系数: {stats['unique_relations']}")
            print(f"唯一实体数: {stats['unique_entities']}")
            print(f"平均句子长度: {stats['average_sentence_length']:.1f} 字符")
            
        except Exception as e:
            print(f"保存统计信息失败: {e}")


if __name__ == "__main__":
    main()