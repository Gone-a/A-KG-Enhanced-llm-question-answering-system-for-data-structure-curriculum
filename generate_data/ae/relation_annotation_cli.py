#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版关系标注工具 - 命令行版本
只显示关键信息，用户只需选择是/否
没有适用的关系规则直接跳过，有适用的关系规则旁显示标注规则
"""

import json
import csv
import os
import sys
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import argparse

# 配置文件
vocab_file = "vocab_dict.csv"
relation_file = "relation.csv"
data_file = "part_2.json"
progress_file = "annotation_progress.json"
output_file = "annotations.json"

class SimpleRelationAnnotationCLI:
    def __init__(self):
        self.data = []
        self.annotations = []
        self.current_index = 0
        self.relations = {}
        self.entity_types = {}
        self.progress_data = {}
        
        # 加载所有必要数据
        self.load_entity_types()
        self.load_relations()
        self.load_data()
        self.load_progress()
    
    def load_entity_types(self):
        """从vocab_dict.csv加载实体类型映射"""
        try:
            with open(vocab_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        entity, entity_type = row[0].strip(), row[1].strip()
                        self.entity_types[entity] = entity_type
            print(f"✓ 已加载 {len(self.entity_types)} 个实体类型")
            return True
        except Exception as e:
            print(f"❌ 加载实体类型失败: {e}")
            return False
    
    def get_entity_type(self, entity):
        """获取实体的类型"""
        return self.entity_types.get(entity, "Unknown")
    
    def load_relations(self):
        """加载关系规则"""
        try:
            with open(relation_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # 过滤掉注释行和空行
            filtered_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    filtered_lines.append(line)
            
            # 重新构建CSV内容
            csv_content = '\n'.join(filtered_lines)
            
            # 解析CSV
            from io import StringIO
            reader = csv.DictReader(StringIO(csv_content))
            for row in reader:
                if (row.get('relation') and 
                    row.get('head_type') and 
                    row.get('tail_type') and
                    row.get('index')):
                    self.relations[row['relation']] = {
                        'head_type': row['head_type'],
                        'tail_type': row['tail_type'],
                        'index': int(row['index'])
                    }
            print(f"✓ 已加载 {len(self.relations)} 个关系规则")
            return True
        except Exception as e:
            print(f"❌ 加载关系规则失败: {e}")
            return False
    
    def load_data(self):
        """加载预测数据"""
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            # 去重处理
            seen = set()
            unique_data = []
            for item in self.data:
                key = (item['sentence'], item['head'], item['tail'], 
                      item['head_offset'], item['tail_offset'])
                if key not in seen:
                    seen.add(key)
                    unique_data.append(item)
            
            self.data = unique_data
            print(f"✓ 已加载 {len(self.data)} 条数据")
            return True
        except Exception as e:
            print(f"❌ 加载数据失败: {e}")
            return False
    
    def load_progress(self):
        """加载标注进度"""
        try:
            if os.path.exists(progress_file):
                with open(progress_file, 'r', encoding='utf-8') as f:
                    self.progress_data = json.load(f)
                    self.current_index = self.progress_data.get('current_index', 0)
                    self.annotations = self.progress_data.get('annotations', [])
                print(f"✓ 已恢复进度: 第 {self.current_index + 1} 条，已标注 {len(self.annotations)} 条")
            else:
                print("✓ 开始新的标注任务")
            return True
        except Exception as e:
            print(f"❌ 加载进度失败: {e}")
            return False
    
    def save_progress(self):
        """保存标注进度"""
        try:
            self.progress_data = {
                'current_index': self.current_index,
                'annotations': self.annotations,
                'timestamp': datetime.now().isoformat()
            }
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress_data, f, ensure_ascii=False, indent=2)
            
            # 同时保存到最终输出文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.annotations, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 已保存进度: 第 {self.current_index + 1} 条，共标注 {len(self.annotations)} 条")
            return True
        except Exception as e:
            print(f"❌ 保存进度失败: {e}")
            return False
    
    def get_suggested_relation(self, head_type, tail_type):
        """获取建议的关系（如果有多个，返回第一个）"""
        for relation, rule in self.relations.items():
            if rule['head_type'] == head_type and rule['tail_type'] == tail_type:
                return relation
        return None
    
    def get_relation_description(self, relation):
        """获取关系的详细说明"""
        relation_descriptions = {
            'hasComplexity': '算法的复杂度属性（时间/空间复杂度）',
            'uses': '算法依赖或使用的数据结构',
            'variantOf': '数据结构的变体/派生关系',
            'appliesTo': '数据结构的典型应用场景',
            'provides': '数据结构支持的操作',
            'implementedAs': '数据结构的实现方式',
            'usedIn': '操作的典型应用场景'
        }
        return relation_descriptions.get(relation, '未知关系')
    
    def display_current_item(self):
        """显示当前项目的关键信息"""
        if self.current_index >= len(self.data):
            print("\n🎉 所有数据标注完成！")
            return False
        
        item = self.data[self.current_index]
        head_type = self.get_entity_type(item['head'])
        tail_type = self.get_entity_type(item['tail'])
        
        # 获取建议关系
        suggested_relation = self.get_suggested_relation(head_type, tail_type)
        
        # 如果没有适用的关系规则，直接跳过
        if suggested_relation is None:
            return None
        
        # 清屏（可选）
        # os.system('clear' if os.name == 'posix' else 'cls')
        
        print("\n" + "="*60)
        print(f"进度: {self.current_index + 1}/{len(self.data)} | 已标注: {len(self.annotations)}")
        print("="*60)
        print(f"句子: {item['sentence']}")
        print(f"实体对: {item['head']} ({head_type}) → {item['tail']} ({tail_type})")
        print(f"建议关系: {suggested_relation}")
        print(f"标注规则: {self.get_relation_description(suggested_relation)}")
        print("="*60)
        return suggested_relation
    
    def get_yes_no_input(self, prompt):
        """获取是/否输入"""
        while True:
            try:
                response = input(f"{prompt} (y/n/q): ").strip().lower()
                if response in ['y', 'yes', '是']:
                    return True
                elif response in ['n', 'no', '否']:
                    return False
                elif response in ['q', 'quit', '退出']:
                    return 'quit'
                else:
                    print("请输入 y(是)/n(否)/q(退出)")
            except KeyboardInterrupt:
                return 'quit'
    
    def annotate_current_item(self):
        """标注当前项目"""
        suggested_relation = self.display_current_item()
        
        # 如果没有适用关系，直接跳过
        if suggested_relation is None:
            self.current_index += 1
            return True
        
        # 有建议关系，询问是否接受
        response = self.get_yes_no_input("接受此关系？")
        
        if response == 'quit':
            return False
        elif response:  # 接受
            item = self.data[self.current_index]
            head_type = self.get_entity_type(item['head'])
            tail_type = self.get_entity_type(item['tail'])
            
            annotation = {
                'sentence': item['sentence'],
                'relation': suggested_relation,
                'head': item['head'],
                'head_offset': item['head_offset'],
                'tail': item['tail'],
                'tail_offset': item['tail_offset'],
                'head_type': head_type,
                'tail_type': tail_type,
                'timestamp': datetime.now().isoformat()
            }
            
            self.annotations.append(annotation)
            print(f"✓ 已标注: {item['head']} --{suggested_relation}--> {item['tail']}")
        else:  # 拒绝
            print("✗ 已跳过此关系")
        
        self.current_index += 1
        
        # 每标注10条自动保存一次
        if len(self.annotations) % 10 == 0 or self.current_index % 10 == 0:
            self.save_progress()
        
        return True
    
    def run(self):
        """运行标注工具"""
        print("🚀 简化版关系标注工具")
        print("说明: 对于每个实体对，系统会建议一个关系，您只需选择接受(y)或拒绝(n)")
        print("输入 q 可随时退出并保存进度")
        print("没有适用关系规则的项目会自动跳过")
        
        try:
            while self.current_index < len(self.data):
                if not self.annotate_current_item():
                    break
            
            # 完成所有标注或用户退出
            if self.current_index >= len(self.data):
                print(f"\n🎉 标注完成！共标注 {len(self.annotations)} 条关系")
            else:
                print(f"\n👋 已退出，当前进度已保存")
            
            # 最终保存
            self.save_progress()
            
        except KeyboardInterrupt:
            print(f"\n\n👋 用户中断，正在保存进度...")
            self.save_progress()
    
    def show_statistics(self):
        """显示统计信息"""
        print(f"\n📊 标注统计:")
        print(f"总数据量: {len(self.data)}")
        print(f"已处理: {self.current_index}")
        print(f"已标注: {len(self.annotations)}")
        print(f"剩余: {len(self.data) - self.current_index}")
        
        if self.annotations:
            relation_counts = {}
            for ann in self.annotations:
                rel = ann['relation']
                relation_counts[rel] = relation_counts.get(rel, 0) + 1
            
            print("\n关系分布:")
            for rel, count in sorted(relation_counts.items()):
                print(f"  {rel}: {count}")

def main():
    parser = argparse.ArgumentParser(description='简化版关系标注命令行工具')
    parser.add_argument('--stats', action='store_true', help='显示统计信息后退出')
    
    args = parser.parse_args()
    
    tool = SimpleRelationAnnotationCLI()
    
    if args.stats:
        tool.show_statistics()
        return
    
    tool.run()

if __name__ == "__main__":
    main()