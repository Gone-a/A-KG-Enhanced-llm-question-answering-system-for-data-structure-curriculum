#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动关系标注工具
基于火山引擎大模型API，自动为实体对标注关系
结合ae.py的API调用模式和relation_annotation_cli.py的关系规则
"""

import os
import json
import csv
import time
import re
import hashlib
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from dotenv import load_dotenv
from volcenginesdkarkruntime import Ark
import concurrent.futures
from threading import Lock

# 加载环境变量
load_dotenv()


class AutoRelationAnnotator:
    """自动关系标注器"""
    
    def __init__(self):
        """初始化配置"""
        # API配置
        self.api_key = os.getenv("ARK_API_KEY")
        if not self.api_key:
            raise EnvironmentError("请设置火山引擎API密钥")
        
        self.api_key = self.api_key.strip()
        self.client = Ark(api_key=self.api_key)
        self.model_id = "doubao-seed-1-6-thinking-250715"
        
        # API调用优化参数
        self.api_timeout = 120
        self.retry_attempts = 2
        self.retry_delay = 2
        self.max_workers = 40
        
        # 缓存配置
        self.cache = {}
        self.cache_lock = Lock()
        self.cache_file = "cache/relation_api_cache.json"
        self._last_cache_size = 0
        
        # 进度跟踪配置
        self.progress_file = "annotation_progress.json"
        self.processed_indices = set()  # 已处理的数据索引
        
        # 文件路径
        self.vocab_file = "vocab_dict.csv"
        self.relation_file = "relation.csv"
        self.input_file = "filtered.json"
        self.output_file = "predict_with_relations.json"
        self.csv_output_file = "DeepKE/example/re/standard/data/example.csv"
        
        # 数据存储
        self.entity_types = {}  # 实体到类型的映射
        self.relations = {}     # 关系规则
        self.data = []          # 输入数据
        self.annotated_data = [] # 标注后的数据
        
        # 关系规则详细说明
        self.relation_rules_details = {
            'hasComplexity': {
                'definition': '算法的复杂度属性（统一处理时间/空间/最坏/平均等）',
                'type_constraint': 'Algorithm → Complexity',
                'annotation_condition': '文件明确提到"算法的复杂度"（如"时间复杂度为O(n log n)"、"平均情况复杂度为O(n)"）或基于算法特性可合理推断其复杂度',
                'key_points': '标注复杂度值（如O(n log n)），可基于算法类型和专业知识推断典型复杂度',
                'knowledge_inference': '可基于算法类型推断：如快速排序通常为O(n log n)，线性搜索为O(n)等'
            },
            'uses': {
                'definition': '算法依赖或使用的数据结构',
                'type_constraint': 'Algorithm → DataStructure',
                'annotation_condition': '文件明确提到"算法使用数据结构"（如"最短路径算法使用图"、"DFS使用栈"）或基于算法原理可推断其使用的数据结构',
                'key_points': '标注算法直接使用的数据结构，可基于算法实现原理进行合理推断',
                'knowledge_inference': '可基于算法特性推断：如图算法使用图结构，排序算法可能使用数组，搜索算法可能使用树等'
            },
            'variantOf': {
                'definition': '数据结构的变体/派生关系',
                'type_constraint': 'DataStructure → DataStructure',
                'annotation_condition': '文件明确提到"是...的变体"（如"B+树是B树的变体"、"平衡二叉树是二叉树的变体"）或基于数据结构理论可推断的变体关系',
                'key_points': '标注明确的变体关系，可基于数据结构分类学进行推理',
                'knowledge_inference': '可基于结构特性推断：如红黑树是平衡二叉搜索树的变体，堆是完全二叉树的变体等'
            },
            'appliesTo': {
                'definition': '数据结构的典型应用场景',
                'type_constraint': 'DataStructure → ApplicationScenario',
                'annotation_condition': '文件明确提到"数据结构用于场景"（如"栈用于表达式求值"、"队列常用于任务调度"）或基于数据结构特性可推断的典型应用',
                'key_points': '标注典型应用场景，可基于数据结构特性和计算机科学常识进行推理',
                'knowledge_inference': '可基于结构特性推断：如栈适用于后进先出场景，队列适用于先进先出场景，哈希表适用于快速查找等'
            },
            'provides': {
                'definition': '数据结构支持的操作',
                'type_constraint': 'DataStructure → Operation',
                'annotation_condition': '文件明确提到"数据结构提供操作"（如"栈提供入栈和出栈操作"）或基于数据结构定义可推断的基本操作',
                'key_points': '标注数据结构的基本操作，可基于数据结构理论推断标准操作集',
                'knowledge_inference': '可基于结构定义推断：如栈提供push/pop操作，队列提供enqueue/dequeue操作，树提供遍历操作等'
            },
            'implementedAs': {
                'definition': '数据结构的实现方式',
                'type_constraint': 'DataStructure → Algorithm',
                'annotation_condition': '文件明确提到"数据结构用某种方式实现"（如"队列可用数组实现"、"链表实现队列"）或基于实现理论可推断的实现方式',
                'key_points': '标注实现方式，可基于计算机科学理论和实践经验进行合理推断',
                'knowledge_inference': '可基于实现原理推断：如动态数组可用静态数组实现，图可用邻接表或邻接矩阵实现等'
            },
            'usedIn': {
                'definition': '操作的典型应用场景',
                'type_constraint': 'Operation → ApplicationScenario',
                'annotation_condition': '文件明确提到"操作用于场景"（如"入栈用于括号匹配"、"出栈用于表达式求值"）或基于操作特性可推断的应用场景',
                'key_points': '标注操作的典型应用场景，可基于操作语义和计算机科学应用进行推理',
                'knowledge_inference': '可基于操作特性推断：如递归操作用于分治算法，比较操作用于排序算法等'
            }
        }
        
        # 初始化
        self.load_cache()
        self.load_progress()  # 加载进度信息
        self.load_entity_types()
        self.load_relations()
        self.load_data()
        
        # 初始化CSV文件
        self.init_csv_file()
        
        print(f"✅ 初始化完成")
        print(f"   - 实体类型: {len(self.entity_types)} 个")
        print(f"   - 关系规则: {len(self.relations)} 个")
        print(f"   - 输入数据: {len(self.data)} 条")
        print(f"   - CSV输出文件: {self.csv_output_file}")
        
        # 显示断点续用状态
        if len(self.processed_indices) > 0:
            remaining = len(self.data) - len(self.processed_indices)
            print(f"   - 断点续用: 已处理 {len(self.processed_indices)} 条，剩余 {remaining} 条")
        else:
            print(f"   - 处理模式: 从头开始处理")
    
    def load_cache(self):
        """加载缓存文件"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                print(f"✅ 加载缓存: {len(self.cache)} 条记录")
                self._last_cache_size = len(self.cache)
            else:
                self.cache = {}
                self._last_cache_size = 0
        except Exception as e:
            print(f"⚠️ 缓存加载失败: {e}")
            self.cache = {}
            self._last_cache_size = 0
    
    def load_progress(self):
        """加载进度文件"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                    self.processed_indices = set(progress_data.get('processed_indices', []))
                print(f"✅ 加载进度: 已处理 {len(self.processed_indices)} 条数据")
            else:
                self.processed_indices = set()
                print(f"📝 未找到进度文件，从头开始处理")
        except Exception as e:
            print(f"⚠️ 进度加载失败: {e}")
            self.processed_indices = set()
    
    def save_progress(self):
        """保存进度到文件"""
        try:
            progress_data = {
                'processed_indices': list(self.processed_indices),
                'last_updated': datetime.now().isoformat(),
                'total_processed': len(self.processed_indices)
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 进度保存失败: {e}")
    
    def init_csv_file(self):
        """初始化CSV输出文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.csv_output_file), exist_ok=True)
            
            # 如果有进度记录且CSV文件存在，则不重新初始化
            if len(self.processed_indices) > 0 and os.path.exists(self.csv_output_file):
                print(f"✅ 检测到断点续用，保留现有CSV文件: {self.csv_output_file}")
                return True
            
            # 创建CSV文件并写入表头
            with open(self.csv_output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['sentence', 'relation', 'head', 'head_offset', 'tail', 'tail_offset'])
            
            print(f"✅ CSV文件初始化完成: {self.csv_output_file}")
            return True
        except Exception as e:
            print(f"❌ CSV文件初始化失败: {e}")
            return False
    
    def save_cache(self):
        """保存缓存到文件"""
        try:
            with self.cache_lock:
                if len(self.cache) == self._last_cache_size:
                    return
                
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
                
                self._last_cache_size = len(self.cache)
        except Exception as e:
            print(f"⚠️ 缓存保存失败: {e}")
    
    def load_entity_types(self):
        """从vocab_dict.csv加载实体类型映射"""
        try:
            with open(self.vocab_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        entity, entity_type = row[0].strip(), row[1].strip()
                        self.entity_types[entity] = entity_type
            return True
        except Exception as e:
            print(f"❌ 加载实体类型映射失败: {e}")
            return False
    
    def load_relations(self):
        """加载关系规则"""
        try:
            with open(self.relation_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
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
            return True
        except Exception as e:
            print(f"❌ 加载关系规则失败: {e}")
            return False
    
    def load_data(self):
        """加载预测数据"""
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
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
            return True
        except Exception as e:
            print(f"❌ 加载数据失败: {e}")
            return False
    
    def get_entity_type(self, entity):
        """获取实体的类型"""
        return self.entity_types.get(entity, "Unknown")
    
    def get_available_relations(self, head_type, tail_type):
        """获取可用的关系列表"""
        available = []
        for relation, rule in self.relations.items():
            if rule['head_type'] == head_type and rule['tail_type'] == tail_type:
                available.append(relation)
        return available
    
    def generate_prompt(self, item):
        """为实体对生成大模型提示词"""
        head_type = self.get_entity_type(item['head'])
        tail_type = self.get_entity_type(item['tail'])
        
        # 获取可用关系
        available_relations = self.get_available_relations(head_type, tail_type)
        
        if not available_relations:
            return None
        
        # 构建关系规则说明
        relation_descriptions = []
        for relation in available_relations:
            if relation in self.relation_rules_details:
                rule = self.relation_rules_details[relation]
                relation_descriptions.append(
                    f"- {relation}: {rule['definition']}\n"
                    f"  类型约束: {rule['type_constraint']}\n"
                    f"  标注条件: {rule['annotation_condition']}\n"
                    f"  关键点: {rule['key_points']}\n"
                    f"  知识推理: {rule['knowledge_inference']}"
                )
        
        relations_str = "\n\n".join(relation_descriptions)
        
        prompt = f"""
你是一个计算机科学专家，请分析以下句子中实体对的关系。

句子: "{item['sentence']}"
头实体: {item['head']} (类型: {head_type})
尾实体: {item['tail']} (类型: {tail_type})

可用关系规则:
{relations_str}

任务要求:
1. 首先仔细分析句子的语义，查看是否明确提到了实体间的关系
2. 如果句子中没有明确提到关系，请基于你的计算机科学知识库和专业理解，谨慎判断这两个实体之间是否存在合理的关系
3. 在进行知识推理时，请考虑：
   - 计算机科学领域的常见关系模式
   - 实体类型之间的典型关联
   - 上下文语境中的隐含关系
   - 专业领域的标准实践和惯例
4. 判断标准（按优先级排序）：
   - 句子明确表述的关系（最高优先级）
   - 基于专业知识的合理推理（中等优先级）
   - 实体类型间的典型关系（较低优先级）
5. 置信度设置指导：
   - 句子明确提到关系：0.8-1.0
   - 基于专业知识的强推理：0.6-0.8
   - 基于常见模式的推理：0.4-0.6
   - 不确定或无关系：0.0-0.4
6. 只有在完全无法建立合理关系时才返回"none"

请严格按照以下JSON格式返回结果，不要包含其他任何文本:
{{
    "relation": "关系名称或none",
    "confidence": 0.0-1.0之间的置信度
}}
"""
        return prompt
    
    def get_cache_key(self, prompt):
        """生成缓存键"""
        return hashlib.md5(prompt.encode('utf-8')).hexdigest()
    
    def call_model_api(self, prompt):
        """调用模型API（带缓存和重试机制）"""
        # 检查缓存
        cache_key = self.get_cache_key(prompt)
        with self.cache_lock:
            if cache_key in self.cache:
                return self.cache[cache_key]
        
        # 准备API调用参数
        messages = [{"role": "user", "content": prompt}]
        
        # 重试机制
        for attempt in range(self.retry_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    max_tokens=1024,
                    temperature=0.3,  # 降低随机性，提高一致性
                    top_p=0.9,
                    stream=False,
                    timeout=self.api_timeout
                )
                
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content
                    
                    # 缓存响应
                    with self.cache_lock:
                        self.cache[cache_key] = content
                    
                    self.save_cache()
                    return content
                else:
                    print(f"  ⚠️ API响应格式异常")
                    return None
                    
            except Exception as e:
                error_msg = str(e)
                print(f"  ❌ API调用失败 (尝试 {attempt + 1}/{self.retry_attempts}): {error_msg}")
                
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"  ⏳ 检测到超时错误，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                elif "rate limit" in error_msg.lower() or "429" in error_msg:
                    wait_time = self.retry_delay * (3 ** attempt)
                    print(f"  ⏳ 检测到速率限制，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    wait_time = self.retry_delay * (attempt + 1)
                    if attempt < self.retry_attempts - 1:
                        time.sleep(wait_time)
                
                if attempt >= self.retry_attempts - 1:
                    print(f"  ❌ 所有重试均失败")
                    return None
    
    def parse_model_response(self, response):
        """解析大模型返回的JSON字符串"""
        if not response:
            return None
        
        # 尝试提取JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        
        # 尝试直接解析
        try:
            return json.loads(response)
        except:
            return None
    
    def process_single_item(self, item_info):
        """处理单个实体对（用于并发）"""
        i, item, total = item_info
        data_index = i - 1  # 转换为0基索引
        
        print(f"处理实体对 {i}/{total}: {item['head']} -> {item['tail']}")
        
        # 检查实体类型
        head_type = self.get_entity_type(item['head'])
        tail_type = self.get_entity_type(item['tail'])
        
        if head_type == "Unknown" or tail_type == "Unknown":
            print(f"  ⚠️ 跳过未知实体类型: {item['head']}({head_type}) -> {item['tail']}({tail_type})")
            result = dict(item)
            result['relation'] = 'none'
            result['confidence'] = 0.0
            result['reasoning'] = '未知实体类型'
            result['data_index'] = data_index  # 添加数据索引
            return result
        
        # 生成提示词
        prompt = self.generate_prompt(item)
        if not prompt:
            print(f"  ⚠️ 没有可用关系规则: {head_type} -> {tail_type}")
            result = dict(item)
            result['relation'] = 'none'
            result['confidence'] = 0.0
            result['reasoning'] = '没有可用关系规则'
            result['data_index'] = data_index  # 添加数据索引
            return result
        
        # 调用API
        response = self.call_model_api(prompt)
        
        # 解析响应
        parsed = self.parse_model_response(response)
        
        # 构建结果
        result = dict(item)
        result['data_index'] = data_index  # 添加数据索引
        if parsed and isinstance(parsed, dict):
            result['relation'] = parsed.get('relation', 'none')
            result['confidence'] = parsed.get('confidence', 0.0)
            result['reasoning'] = parsed.get('reasoning', '无推理说明')
        else:
            print(f"  ⚠️ 解析响应失败")
            result['relation'] = 'none'
            result['confidence'] = 0.0
            result['reasoning'] = '解析响应失败'
        
        print(f"  ✓ 标注结果: {result['relation']} (置信度: {result['confidence']:.2f})")
        
        # 立即保存到CSV文件
        self.save_single_result_to_csv(result)
        
        return result
    
    def save_single_result_to_csv(self, result):
        """将单条结果立即保存到CSV文件"""
        try:
            # 只保存有关系的结果
            if result.get('relation', 'none') != 'none':
                with open(self.csv_output_file, 'a', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        result.get('sentence', ''),
                        result.get('relation', 'none'),
                        result.get('head', ''),
                        result.get('head_offset', ''),
                        result.get('tail', ''),
                        result.get('tail_offset', '')
                    ])
                print(f"  💾 已保存到CSV: {result['head']} -> {result['tail']} ({result['relation']})")
            
            # 更新进度（无论是否有关系都要记录已处理）
            if 'data_index' in result:
                self.processed_indices.add(result['data_index'])
                self.save_progress()
                
        except Exception as e:
            print(f"  ⚠️ CSV保存失败: {e}")
    
    def annotate_all(self):
        """标注所有实体对"""
        print(f"\n🔄 开始自动标注 {len(self.data)} 条数据...")
        
        # 显示断点续用信息
        if len(self.processed_indices) > 0:
            remaining_count = len(self.data) - len(self.processed_indices)
            print(f"📋 检测到断点续用:")
            print(f"   - 已处理: {len(self.processed_indices)} 条")
            print(f"   - 剩余待处理: {remaining_count} 条")
        
        results = []
        total = len(self.data)
        
        # 准备数据，过滤掉已处理的项目
        item_infos = []
        for i, item in enumerate(self.data):
            if i not in self.processed_indices:  # 只处理未处理的数据
                item_infos.append((i+1, item, total))
        
        if not item_infos:
            print(f"✅ 所有数据已处理完成！")
            self.show_statistics()
            self.show_csv_statistics()
            return []
        
        print(f"🔄 本次需要处理 {len(item_infos)} 条数据")
        
        # 批次处理以减少API压力
        batch_size = 40
        
        for i in range(0, len(item_infos), batch_size):
            batch = item_infos[i:i+batch_size]
            print(f"\n🔄 处理批次 {i//batch_size + 1}/{(len(item_infos) + batch_size - 1)//batch_size}")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_item = {
                    executor.submit(self.process_single_item, item_info): item_info 
                    for item_info in batch
                }
                
                batch_results = []
                for future in concurrent.futures.as_completed(future_to_item):
                    try:
                        result = future.result()
                        batch_results.append(result)
                    except Exception as e:
                        item_info = future_to_item[future]
                        print(f"  ❌ 处理失败: {item_info[1]['head']} -> {item_info[1]['tail']} - {e}")
                
                results.extend(batch_results)
                
                # 批次间休息
                if i + batch_size < len(item_infos):
                    print(f"  💤 批次完成，休息1秒...")
                    time.sleep(1)
        
        self.annotated_data = results
        print(f"\n✅ 标注完成，本次处理 {len(results)} 条数据")
        print(f"📊 总进度: {len(self.processed_indices)}/{total} 条数据已完成")
        
        # 统计结果
        self.show_statistics()
        
        # 显示CSV文件统计
        self.show_csv_statistics()
        
        return results
    
    def show_csv_statistics(self):
        """显示CSV文件统计"""
        try:
            with open(self.csv_output_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
            # 减去表头
            data_rows = len(rows) - 1 if len(rows) > 1 else 0
            
            print(f"\n📄 CSV文件统计:")
            print(f"   文件路径: {self.csv_output_file}")
            print(f"   保存的关系数据: {data_rows} 条")
            
            if data_rows > 0:
                # 统计关系类型
                relation_counts = {}
                for row in rows[1:]:  # 跳过表头
                    if len(row) >= 2:
                        relation = row[1]
                        relation_counts[relation] = relation_counts.get(relation, 0) + 1
                
                print(f"   关系类型分布:")
                for relation, count in sorted(relation_counts.items(), key=lambda x: x[1], reverse=True):
                    print(f"     • {relation}: {count} 条")
                    
        except Exception as e:
            print(f"⚠️ CSV统计失败: {e}")
    
    def show_statistics(self):
        """显示标注统计"""
        if not self.annotated_data:
            print("❌ 没有标注数据")
            return
        
        print(f"\n📊 标注统计:")
        
        # 关系分布
        relation_count = {}
        confidence_sum = {}
        for item in self.annotated_data:
            relation = item.get('relation', 'none')
            confidence = item.get('confidence', 0.0)
            
            relation_count[relation] = relation_count.get(relation, 0) + 1
            confidence_sum[relation] = confidence_sum.get(relation, 0) + confidence
        
        print(f"关系分布:")
        for relation, count in sorted(relation_count.items(), key=lambda x: x[1], reverse=True):
            avg_confidence = confidence_sum[relation] / count if count > 0 else 0
            print(f"  • {relation}: {count} 条 (平均置信度: {avg_confidence:.3f})")
        
        # 高置信度关系
        high_confidence_relations = [
            item for item in self.annotated_data 
            if item.get('confidence', 0) >= 0.8 and item.get('relation') != 'none'
        ]
        print(f"\n高置信度关系 (≥0.8): {len(high_confidence_relations)} 条")
        
        # 低置信度关系
        low_confidence_relations = [
            item for item in self.annotated_data 
            if 0 < item.get('confidence', 0) < 0.5 and item.get('relation') != 'none'
        ]
        print(f"低置信度关系 (<0.5): {len(low_confidence_relations)} 条")
    
    def save_results(self):
        """保存标注结果"""
        if not self.annotated_data:
            print("❌ 没有标注数据可保存")
            return False
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.annotated_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 标注结果已保存到: {self.output_file}")
            print(f"   总条数: {len(self.annotated_data)}")
            return True
        except Exception as e:
            print(f"❌ 保存失败: {e}")
            return False
    
    def export_csv(self):
        """导出CSV格式"""
        if not self.annotated_data:
            print("❌ 没有标注数据可导出")
            return False
        
        csv_file = self.output_file.replace('.json', '.csv')
        
        try:
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                fieldnames = ['sentence', 'head', 'tail', 'head_offset', 'tail_offset', 
                             'relation', 'confidence', 'reasoning']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for item in self.annotated_data:
                    writer.writerow({
                        'sentence': item.get('sentence', ''),
                        'head': item.get('head', ''),
                        'tail': item.get('tail', ''),
                        'head_offset': item.get('head_offset', ''),
                        'tail_offset': item.get('tail_offset', ''),
                        'relation': item.get('relation', 'none'),
                        'confidence': item.get('confidence', 0.0),
                        'reasoning': item.get('reasoning', '')
                    })
            
            print(f"✅ CSV文件已导出到: {csv_file}")
            return True
        except Exception as e:
            print(f"❌ CSV导出失败: {e}")
            return False
    
    def run(self):
        """执行完整流程"""
        try:
            print("🚀 开始自动关系标注...")
            
            # 1. 标注所有数据
            self.annotate_all()
            
            # 2. 保存结果
            self.save_results()
            
            # 3. 导出CSV
            self.export_csv()
            
            # 4. 最终保存缓存
            self.save_cache()
            
            print("\n🎉 自动关系标注完成！")
            print(f"✅ JSON结果: {self.output_file}")
            print(f"✅ CSV结果: {self.csv_output_file}")
            print(f"📝 CSV格式符合DeepKE标准，可直接用于关系抽取训练")
            
        except Exception as e:
            print(f"\n🚨 标注过程出错: {str(e)}")
            return False
        
        return True


def main():
    """主函数"""
    try:
        annotator = AutoRelationAnnotator()
        annotator.run()
    except Exception as e:
        print(f"初始化失败: {str(e)}")
        return False
    
    return True


if __name__ == "__main__":
    main()