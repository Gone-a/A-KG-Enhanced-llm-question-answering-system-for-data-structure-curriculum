#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据结构课程知识图谱数据生成器 - 新版本
基于新的实体表和关系表生成高质量的关系抽取训练数据
关系类型: hasComplexity, uses, variantOf, appliesTo, provides, implementedAs, usedIn
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
import hashlib
from typing import List, Dict, Tuple, Set
from collections import defaultdict, Counter

# 初始化全局logger
logger = logging.getLogger(__name__)

# 禁用HTTP请求日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# 导入配置管理器
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.config_manager import get_config_manager

# 获取配置管理器实例
config_manager = get_config_manager()
api_config = config_manager.get_api_config()
gen_config = config_manager.get_generation_config()

# ============================= 统一配置 =============================
class Config:
    """统一配置类"""
    # API配置
    API_KEY = api_config.get('ark_api_key')
    BASE_URL = api_config.get('base_url')
    MODEL = api_config.get('doubao_model_id')
    TIMEOUT = gen_config.get('timeout', 15)  # 减少超时时间
    RETRY_COUNT = gen_config.get('retry_count', 3)  # 增加重试次数
    DELAY_BETWEEN_REQUESTS = gen_config.get('delay', 0.1)  # 增加延迟，从0.01秒增加到0.1秒
    CONCURRENCY = gen_config.get('concurrency', 20)  # 大幅减少并发数，从50减少到5
    BATCH_SIZE = gen_config.get('batch_size', 100)  # 减少批处理大小，从1000减少到100
    
    # 数据生成配置
    NUM_RECORDS = gen_config.get('num_records', 21000)  # 每个关系3000条，7个关系共21000条
    RECORDS_PER_RELATION = NUM_RECORDS // 7  # 每个关系的目标数据量
    MAX_PROMPTS = 1000
    MIN_PROMPTS_PER_RELATION = 5
    SENTENCES_PER_API_CALL = 3  # 新增：每次API调用生成多个句子
    
    # 缓存配置
    ENABLE_CACHE = True  # 启用缓存
    CACHE_SIZE = 10000  # 缓存大小
    
    # 文件路径配置
    OUTPUT_FILE = gen_config.get('output_file')
    PROMPTS_FILE = gen_config.get('prompts_file')
    VOCAB_DICT_FILE = gen_config.get('vocab_dict_file')
    RELATION_FILE = gen_config.get('relation_file')
    STATE_FILE = gen_config.get('state_file')
    CACHE_FILE = gen_config.get('cache_file')  # 缓存文件
    
    ANNOTATION_OUTPUT_DIR = gen_config.get('annotation_output_dir')
    TRAIN_FILE = "train_new.csv"
    TEST_FILE = "test_new.csv"
    VALID_FILE = "valid_new.csv"

# ========================= 基于新实体表的知识库 =============================
def load_entities_from_vocab():
    """从vocab_dict.csv加载实体和类型映射"""
    entities_by_type = defaultdict(list)
    entity_to_type = {}
    
    vocab_path = Config.VOCAB_DICT_FILE
    try:
        with open(vocab_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    entity, entity_type = row[0].strip(), row[1].strip()
                    entities_by_type[entity_type].append(entity)
                    entity_to_type[entity] = entity_type
    except Exception as e:
        print(f"❌ 加载实体词典失败: {e}")
        return {}, {}
    
    return dict(entities_by_type), entity_to_type

# 加载实体数据
ENTITIES_BY_TYPE, ENTITY_TO_TYPE = load_entities_from_vocab()

# ========================= 新关系定义 =============================
RELATION_TYPES = {
    "hasComplexity": "算法的复杂度属性",
    "uses": "算法使用的数据结构", 
    "variantOf": "数据结构的变体关系",
    "appliesTo": "数据结构的应用场景",
    "provides": "数据结构提供的操作",
    "implementedAs": "数据结构的实现方式",
    "usedIn": "操作的应用场景"
}

# ========================= 关系模板 =============================
RELATION_TEMPLATES = {
    "hasComplexity": [
        "{algorithm}算法的时间复杂度为{complexity}",
        "{algorithm}的平均时间复杂度是{complexity}",
        "{algorithm}算法在最坏情况下的复杂度为{complexity}",
        "{algorithm}的空间复杂度为{complexity}",
        "使用{algorithm}进行处理，其复杂度为{complexity}",
        "{algorithm}算法具有{complexity}的时间复杂度",
        "在分析{algorithm}时，发现其复杂度为{complexity}",
        "{algorithm}的计算复杂度达到{complexity}"
    ],
    "uses": [
        "{algorithm}算法需要使用{datastructure}来实现",
        "{algorithm}的实现依赖于{datastructure}数据结构",
        "在{algorithm}中，我们使用{datastructure}来存储数据",
        "{algorithm}算法采用{datastructure}作为核心数据结构",
        "实现{algorithm}时，{datastructure}是必不可少的",
        "{algorithm}算法基于{datastructure}进行操作",
        "为了执行{algorithm}，系统使用了{datastructure}",
        "{algorithm}的高效实现需要{datastructure}的支持"
    ],
    "variantOf": [
        "{variant}是{original}的一种变体",
        "{variant}属于{original}的特殊形式",
        "{variant}是基于{original}改进的数据结构",
        "作为{original}的变体，{variant}具有更好的性能",
        "{variant}是{original}的优化版本",
        "{variant}继承了{original}的基本特性",
        "从{original}发展而来的{variant}具有独特优势",
        "{variant}是{original}在特定场景下的变形"
    ],
    "appliesTo": [
        "{datastructure}广泛应用于{scenario}场景",
        "在{scenario}中，{datastructure}发挥重要作用",
        "{datastructure}特别适合用于{scenario}",
        "当需要处理{scenario}时，{datastructure}是理想选择",
        "{datastructure}在{scenario}方面表现出色",
        "解决{scenario}问题时，{datastructure}非常有效",
        "{datastructure}是{scenario}的核心数据结构",
        "在{scenario}的实现中，{datastructure}不可或缺"
    ],
    "provides": [
        "{datastructure}提供了{operation}功能",
        "{datastructure}支持{operation}操作",
        "通过{datastructure}可以实现{operation}",
        "{datastructure}具备{operation}的能力",
        "使用{datastructure}能够进行{operation}",
        "{datastructure}允许用户执行{operation}",
        "{datastructure}的核心功能包括{operation}",
        "在{datastructure}中，{operation}是基本操作"
    ],
    "implementedAs": [
        "{datastructure}可以通过{algorithm}来实现",
        "{datastructure}的实现采用了{algorithm}方法",
        "使用{algorithm}可以构建{datastructure}",
        "{datastructure}基于{algorithm}进行实现",
        "通过{algorithm}，我们可以实现{datastructure}",
        "{datastructure}的底层实现使用{algorithm}",
        "{algorithm}是实现{datastructure}的有效方式",
        "{datastructure}采用{algorithm}作为实现策略"
    ],
    "usedIn": [
        "{operation}操作常用于{scenario}",
        "在{scenario}中，{operation}是关键操作",
        "{operation}在{scenario}场景下非常重要",
        "处理{scenario}时需要使用{operation}",
        "{operation}是{scenario}的核心操作",
        "实现{scenario}功能需要{operation}支持",
        "{scenario}的实现离不开{operation}操作",
        "在{scenario}过程中，{operation}发挥重要作用"
    ]
}

# ========================= 数据生成器类 =============================

class KnowledgeGraphGenerator:
    """知识图谱数据生成器"""
    
    def __init__(self, api_key):
        """初始化知识图谱生成器"""
        self.api_key = api_key
        
        # 配置OpenAI客户端（旧版本方式）
        openai.api_key = api_key
        openai.api_base = "https://ark.cn-beijing.volces.com/api/v3"
        
        # 加载实体数据（优化版本）
        self.entities_by_type = self._load_entities_optimized()
        
        # 预计算关系对（优化版本）
        self.build_relation_pairs()
        
        # 初始化缓存
        self.api_cache = {}
        self.cache_file = Config.CACHE_FILE
        self.enable_cache = Config.ENABLE_CACHE
        self.cache_size = Config.CACHE_SIZE
        
        # 初始化关系计数器
        self.relation_counts = {relation: 0 for relation in RELATION_TYPES.keys()}
        
        # 初始化生成的句子列表
        self.generated_sentences = []
        
        # 初始化输出文件路径
        self.output_file = Config.OUTPUT_FILE
        
        # 实时缓存配置
        self.realtime_cache_file = Config.OUTPUT_FILE.replace('.txt', '_realtime.json')
        self.cache_save_interval = 50  # 每生成50条句子保存一次
        self.last_cache_save = 0
        
        if self.enable_cache:
            self.load_cache()
            self.load_realtime_cache()
        
        print(f"✅ 知识图谱生成器初始化完成")
        print(f"📊 实体统计: {sum(len(entities) for entities in self.entities_by_type.values())} 个实体")
        print(f"🔗 关系对统计: {sum(len(pairs) for pairs in self.relation_pairs.values())} 个关系对")
    
    def _load_entities_optimized(self):
        """优化的实体加载方法"""
        print("📚 加载实体数据...")
        
        # 直接使用预定义的实体数据，避免重复处理
        entities_by_type = {
            "Algorithm": ENTITIES_BY_TYPE.get("Algorithm", []),
            "DataStructure": ENTITIES_BY_TYPE.get("DataStructure", []),
            "Complexity": ENTITIES_BY_TYPE.get("Complexity", []),
            "Operation": ENTITIES_BY_TYPE.get("Operation", []),
            "Scenario": ENTITIES_BY_TYPE.get("ApplicationScenario", [])
        }
        
        print("✅ 实体数据加载完成")
        return entities_by_type

    def build_relation_pairs(self):
        """构建关系实体对（优化版本）"""
        print("🔗 构建关系实体对...")
        
        # 预计算所有可能的实体对，避免运行时重复计算
        self.relation_pairs = {
            "hasComplexity": self._build_complexity_pairs(),
            "uses": self._build_uses_pairs(),
            "variantOf": self._build_variant_pairs(),
            "appliesTo": self._build_applies_pairs(),
            "provides": self._build_provides_pairs(),
            "implementedAs": self._build_implemented_pairs(),
            "usedIn": self._build_used_in_pairs()
        }
        
        print("✅ 关系实体对构建完成")
    
    def _build_complexity_pairs(self):
        """构建算法-复杂度关系对"""
        pairs = []
        algorithms = self.entities_by_type.get("Algorithm", [])
        complexities = self.entities_by_type.get("Complexity", [])
        
        # 为每个算法分配合适的复杂度
        for algorithm in algorithms:
            # 随机选择1-2个复杂度
            selected_complexities = random.sample(complexities, min(2, len(complexities)))
            for complexity in selected_complexities:
                pairs.append((algorithm, complexity))
        
        return pairs[:Config.RECORDS_PER_RELATION]
    
    def _build_uses_pairs(self):
        """构建算法-数据结构关系对"""
        pairs = []
        algorithms = self.entities_by_type.get("Algorithm", [])
        data_structures = self.entities_by_type.get("DataStructure", [])
        
        for algorithm in algorithms:
            # 每个算法使用1-3个数据结构
            selected_ds = random.sample(data_structures, min(3, len(data_structures)))
            for ds in selected_ds:
                pairs.append((algorithm, ds))
        
        return pairs[:Config.RECORDS_PER_RELATION]
    
    def _build_variant_pairs(self):
        """构建数据结构变体关系对"""
        pairs = []
        data_structures = self.entities_by_type.get("DataStructure", [])
        
        # 创建变体关系（一些数据结构是其他的变体）
        for i, ds1 in enumerate(data_structures):
            for j, ds2 in enumerate(data_structures):
                if i != j and random.random() < 0.1:  # 10%的概率创建变体关系
                    pairs.append((ds1, ds2))
        
        return pairs[:Config.RECORDS_PER_RELATION]
    
    def _build_applies_pairs(self):
        """构建数据结构-应用场景关系对"""
        pairs = []
        data_structures = self.entities_by_type.get("DataStructure", [])
        scenarios = self.entities_by_type.get("Scenario", [])
        
        for ds in data_structures:
            # 每个数据结构应用于2-4个场景
            selected_scenarios = random.sample(scenarios, min(4, len(scenarios)))
            for scenario in selected_scenarios:
                pairs.append((ds, scenario))
        
        return pairs[:Config.RECORDS_PER_RELATION]
    
    def _build_provides_pairs(self):
        """构建数据结构-操作关系对"""
        pairs = []
        data_structures = self.entities_by_type.get("DataStructure", [])
        operations = self.entities_by_type.get("Operation", [])
        
        for ds in data_structures:
            # 每个数据结构提供3-5个操作
            selected_ops = random.sample(operations, min(5, len(operations)))
            for op in selected_ops:
                pairs.append((ds, op))
        
        return pairs[:Config.RECORDS_PER_RELATION]
    
    def _build_implemented_pairs(self):
        """构建数据结构-算法实现关系对"""
        pairs = []
        data_structures = self.entities_by_type.get("DataStructure", [])
        algorithms = self.entities_by_type.get("Algorithm", [])
        
        for ds in data_structures:
            # 每个数据结构可以通过1-2个算法实现
            selected_algs = random.sample(algorithms, min(2, len(algorithms)))
            for alg in selected_algs:
                pairs.append((ds, alg))
        
        return pairs[:Config.RECORDS_PER_RELATION]
    
    def _build_used_in_pairs(self):
        """构建操作-应用场景关系对"""
        pairs = []
        operations = self.entities_by_type.get("Operation", [])
        scenarios = self.entities_by_type.get("Scenario", [])
        
        for op in operations:
            # 每个操作用于2-3个场景
            selected_scenarios = random.sample(scenarios, min(3, len(scenarios)))
            for scenario in selected_scenarios:
                pairs.append((op, scenario))
        
        return pairs[:Config.RECORDS_PER_RELATION]
    
    def load_cache(self):
        """加载API缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.api_cache = json.load(f)
                print(f"📦 加载缓存: {len(self.api_cache)} 条记录")
            else:
                self.api_cache = {}
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")
            self.api_cache = {}
    
    def save_cache(self):
        """保存API缓存"""
        if not self.enable_cache:
            return
        
        try:
            # 限制缓存大小
            if len(self.api_cache) > self.cache_size:
                # 保留最新的缓存项
                items = list(self.api_cache.items())
                self.api_cache = dict(items[-self.cache_size:])
            
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.api_cache, f, ensure_ascii=False, indent=2)
            print(f"💾 保存缓存: {len(self.api_cache)} 条记录")
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")
    
    def load_realtime_cache(self):
        """加载实时缓存的生成结果"""
        try:
            if os.path.exists(self.realtime_cache_file):
                with open(self.realtime_cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.generated_sentences = data.get('sentences', [])
                    self.relation_counts = data.get('relation_counts', {relation: 0 for relation in RELATION_TYPES.keys()})
                print(f"📦 加载实时缓存: {len(self.generated_sentences)} 条句子")
            else:
                self.generated_sentences = []
                self.relation_counts = {relation: 0 for relation in RELATION_TYPES.keys()}
        except Exception as e:
            logger.warning(f"加载实时缓存失败: {e}")
            self.generated_sentences = []
            self.relation_counts = {relation: 0 for relation in RELATION_TYPES.keys()}
    
    def save_realtime_cache(self, force=False):
        """保存实时缓存"""
        if not self.enable_cache:
            return
        
        # 检查是否需要保存
        current_count = len(self.generated_sentences)
        if not force and current_count - self.last_cache_save < self.cache_save_interval:
            return
        
        try:
            os.makedirs(os.path.dirname(self.realtime_cache_file), exist_ok=True)
            data = {
                'sentences': self.generated_sentences,
                'relation_counts': self.relation_counts,
                'timestamp': time.time(),
                'total_count': current_count
            }
            with open(self.realtime_cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.last_cache_save = current_count
            print(f"💾 实时缓存已保存: {current_count} 条句子")
        except Exception as e:
            logger.warning(f"保存实时缓存失败: {e}")
    
    def get_cache_key(self, prompt):
        """生成缓存键"""
        return hashlib.md5(prompt.encode('utf-8')).hexdigest()
    
    def generate_prompt_for_relation(self, relation, entity1, entity2, num_sentences=1):
        """为特定关系生成提示词"""
        relation_desc = RELATION_TYPES[relation]
        
        # 根据关系类型选择合适的模板
        templates = RELATION_TEMPLATES.get(relation, [])
        if not templates:
            return f"请生成一个描述{entity1}和{entity2}之间{relation_desc}关系的句子。"
        
        # 随机选择模板
        template = random.choice(templates)
        
        # 根据关系类型填充模板
        if relation == "hasComplexity":
            example = template.format(algorithm=entity1, complexity=entity2)
        elif relation == "uses":
            example = template.format(algorithm=entity1, datastructure=entity2)
        elif relation == "variantOf":
            example = template.format(variant=entity1, original=entity2)
        elif relation == "appliesTo":
            example = template.format(datastructure=entity1, scenario=entity2)
        elif relation == "provides":
            example = template.format(datastructure=entity1, operation=entity2)
        elif relation == "implementedAs":
            example = template.format(datastructure=entity1, algorithm=entity2)
        elif relation == "usedIn":
            example = template.format(operation=entity1, scenario=entity2)
        else:
            example = f"{entity1}与{entity2}存在{relation_desc}关系"
        
        prompt = f"""你是一个专业的知识图谱数据生成专家。请根据以下信息生成{num_sentences}个高质量的中文句子：

关系类型：{relation} ({relation_desc})
实体1：{entity1}
实体2：{entity2}

参考示例：{example}

要求：
1. 生成{num_sentences}个不同的句子，每个句子一行
2. 句子要自然流畅，符合中文表达习惯
3. 准确体现{entity1}和{entity2}之间的{relation_desc}关系
4. 句子长度适中（10-30个字符）
5. 避免重复和冗余表达
6. 只输出句子内容，不要添加编号或其他标记

请直接输出{num_sentences}个句子："""
        
        return prompt

    def call_api_batch(self, prompts):
        """批量调用API"""
        if not prompts:
            return []
        
        responses = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=Config.CONCURRENCY) as executor:
            future_to_prompt = {executor.submit(self.call_api, prompt): prompt for prompt in prompts}
            
            for future in concurrent.futures.as_completed(future_to_prompt):
                try:
                    response = future.result()
                    responses.append(response)
                except Exception as e:
                    logger.error(f"API调用失败: {e}")
                    responses.append(None)
                
                # 控制请求频率
                time.sleep(Config.DELAY_BETWEEN_REQUESTS)
        
        return responses
    
    def call_api(self, prompt):
        """调用API生成文本（带缓存）"""
        # 检查缓存
        if self.enable_cache:
            cache_key = self.get_cache_key(prompt)
            if cache_key in self.api_cache:
                return self.api_cache[cache_key]
        
        for attempt in range(Config.RETRY_COUNT):
            try:
                response = openai.ChatCompletion.create(
                    model=Config.MODEL,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500,
                    timeout=Config.TIMEOUT
                )
                
                result = response.choices[0].message.content.strip()
                
                # 保存到缓存
                if self.enable_cache:
                    self.api_cache[cache_key] = result
                
                return result
                
            except Exception as e:
                logger.warning(f"API调用失败 (尝试 {attempt + 1}/{Config.RETRY_COUNT}): {e}")
                if attempt < Config.RETRY_COUNT - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error(f"API调用最终失败: {e}")
                    return None
    
    def process_api_response(self, response, relation, entity1, entity2):
        """处理API响应，提取有效句子"""
        if not response:
            return []
        
        sentences = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 清理句子格式
            line = re.sub(r'^\d+[\.\)]\s*', '', line)  # 移除序号
            line = re.sub(r'^[-\*]\s*', '', line)      # 移除列表符号
            line = line.strip('\"\'')                   # 移除引号
            
            # 检查句子质量
            if (len(line) >= 10 and len(line) <= 100 and 
                entity1 in line and entity2 in line):
                sentences.append({
                    'sentence': line,
                    'relation': relation,
                    'entity1': entity1,
                    'entity2': entity2
                })
        
        return sentences
    
    def generate_mock_sentences_for_relation(self, relation, target_count):
        """为特定关系生成模拟句子（用于测试，不调用API）"""
        print(f"\n🔄 生成 {relation} 关系的模拟句子 (目标: {target_count} 条)")
        
        pairs = self.relation_pairs[relation]
        if not pairs:
            print(f"⚠️ 没有找到 {relation} 关系的实体对")
            return []
        
        generated_sentences = []
        templates = RELATION_TEMPLATES.get(relation, [])
        
        if not templates:
            print(f"⚠️ 没有找到 {relation} 关系的模板")
            return []
        
        with tqdm(total=target_count, desc=f"生成{relation}") as pbar:
            while len(generated_sentences) < target_count:
                # 随机选择实体对和模板
                entity1, entity2 = random.choice(pairs)
                template = random.choice(templates)
                
                # 根据关系类型填充模板
                if relation == "hasComplexity":
                    sentence = template.format(algorithm=entity1, complexity=entity2)
                elif relation == "uses":
                    sentence = template.format(algorithm=entity1, datastructure=entity2)
                elif relation == "variantOf":
                    sentence = template.format(variant=entity1, original=entity2)
                elif relation == "appliesTo":
                    sentence = template.format(datastructure=entity1, scenario=entity2)
                elif relation == "provides":
                    sentence = template.format(datastructure=entity1, operation=entity2)
                elif relation == "implementedAs":
                    sentence = template.format(datastructure=entity1, algorithm=entity2)
                elif relation == "usedIn":
                    sentence = template.format(operation=entity1, scenario=entity2)
                else:
                    sentence = f"{entity1}与{entity2}存在{relation}关系"
                
                generated_sentences.append({
                    'sentence': sentence,
                    'relation': relation,
                    'entity1': entity1,
                    'entity2': entity2
                })
                pbar.update(1)
        
        print(f"✅ {relation} 关系生成完成: {len(generated_sentences)} 条")
        return generated_sentences

    def generate_sentences_for_relation_fast(self, relation, target_count):
        """高效生成特定关系的句子（并发+批量）"""
        print(f"\n🚀 高效生成 {relation} 关系的句子 (目标: {target_count} 条)")
        
        pairs = self.relation_pairs[relation]
        if not pairs:
            print(f"⚠️ 没有找到 {relation} 关系的实体对")
            return []
        
        generated_sentences = []
        sentences_per_call = Config.SENTENCES_PER_API_CALL
        
        # 计算需要的API调用次数
        calls_needed = (target_count + sentences_per_call - 1) // sentences_per_call
        
        # 准备批量提示词
        prompts = []
        for i in range(calls_needed):
            entity1, entity2 = random.choice(pairs)
            remaining = min(sentences_per_call, target_count - len(generated_sentences))
            if remaining <= 0:
                break
            prompt = self.generate_prompt_for_relation(relation, entity1, entity2, remaining)
            prompts.append((prompt, relation, entity1, entity2, remaining))
        
        print(f"📊 准备进行 {len(prompts)} 次API调用，每次生成 {sentences_per_call} 个句子")
        
        # 批量处理提示词
        batch_size = Config.BATCH_SIZE // sentences_per_call  # 调整批次大小
        
        with tqdm(total=target_count, desc=f"生成{relation}") as pbar:
            for i in range(0, len(prompts), batch_size):
                batch_prompts = prompts[i:i + batch_size]
                
                # 并发调用API
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(Config.CONCURRENCY, len(batch_prompts))) as executor:
                    future_to_data = {
                        executor.submit(self.call_api, prompt_data[0]): prompt_data 
                        for prompt_data in batch_prompts
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_data):
                        prompt_data = future_to_data[future]
                        _, relation, entity1, entity2, expected_count = prompt_data
                        
                        try:
                            response = future.result()
                            if response:
                                sentences = self.process_api_response(response, relation, entity1, entity2)
                                for sentence in sentences[:expected_count]:
                                    if len(generated_sentences) < target_count:
                                        generated_sentences.append(sentence)
                                        # 添加到实时缓存
                                        self.generated_sentences.append(sentence)
                                        pbar.update(1)
                        except Exception as e:
                            logger.error(f"处理API响应失败: {e}")
                        
                        # 控制请求频率
                        time.sleep(Config.DELAY_BETWEEN_REQUESTS)
                
                # 定期保存实时缓存
                self.save_realtime_cache()
                
                # 如果已经生成足够的句子，提前退出
                if len(generated_sentences) >= target_count:
                    break
        
        print(f"✅ {relation} 关系生成完成: {len(generated_sentences)} 条")
        return generated_sentences[:target_count]
    
    def generate_all_data_fast(self):
        """高效生成所有关系的数据（并发处理不同关系）"""
        print(f"\n🚀 开始高效生成知识图谱数据")
        print(f"目标: 每个关系 {Config.RECORDS_PER_RELATION} 条，共 {len(RELATION_TYPES)} 个关系")
        
        all_sentences = []
        
        # 使用线程池并发处理不同关系
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(RELATION_TYPES), 4)) as executor:
            future_to_relation = {
                executor.submit(self.generate_sentences_for_relation_fast, relation, Config.RECORDS_PER_RELATION): relation
                for relation in RELATION_TYPES.keys()
            }
            
            for future in concurrent.futures.as_completed(future_to_relation):
                relation = future_to_relation[future]
                try:
                    sentences = future.result()
                    all_sentences.extend(sentences)
                    self.relation_counts[relation] = len(sentences)
                    print(f"🎯 {relation} 关系完成，生成 {len(sentences)} 条句子")
                except Exception as e:
                    logger.error(f"生成 {relation} 关系数据失败: {e}")
                    self.relation_counts[relation] = 0
        
        self.generated_sentences = all_sentences
        
        # 最终保存实时缓存
        self.save_realtime_cache(force=True)
        
        print(f"\n✅ 高效数据生成完成! 总计: {len(all_sentences)} 条")
        return all_sentences
    
    def generate_all_data(self):
        """生成所有关系的数据"""
        print(f"\n🚀 开始生成知识图谱数据")
        print(f"目标: 每个关系 {self.records_per_relation} 条，共 {len(RELATION_TYPES)} 个关系")
        
        all_sentences = []
        
        for relation in RELATION_TYPES.keys():
            sentences = self.generate_sentences_for_relation(relation, self.records_per_relation)
            all_sentences.extend(sentences)
            self.relation_counts[relation] = len(sentences)
        
        self.generated_sentences = all_sentences
        
        print(f"\n✅ 数据生成完成!")
        print(f"总计生成: {len(all_sentences)} 条句子")
        
        # 显示各关系统计
        for relation, count in self.relation_counts.items():
            percentage = (count / len(all_sentences)) * 100 if all_sentences else 0
            print(f"  - {relation}: {count} 条 ({percentage:.1f}%)")
    
    def save_data(self):
        """保存生成的数据"""
        print(f"\n💾 保存数据到文件...")
        
        # 准备JSON数据结构
        json_data = {
            "sentences": self.generated_sentences,
            "statistics": {
                "total_sentences": len(self.generated_sentences),
                "relation_counts": dict(self.relation_counts),
                "generation_time": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        # 保存为JSON格式
        json_file = self.output_file.replace('.txt', '.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        # 保存为文本格式
        with open(self.output_file, 'w', encoding='utf-8') as f:
            for item in self.generated_sentences:
                f.write(f"{item['sentence']}\t{item['relation']}\t{item['entity1']}\t{item['entity2']}\n")
        
        print(f"✅ 数据已保存:")
        print(f"  - JSON格式: {json_file}")
        print(f"  - 文本格式: {self.output_file}")
    
    def export_to_deepke_format(self):
        """导出为DeepKE训练格式"""
        print(f"\n📤 导出DeepKE训练数据...")
        
        # 确保输出目录存在
        output_dir = Config.ANNOTATION_OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)
        
        # 随机打乱数据
        random.shuffle(self.generated_sentences)
        
        # 分割数据集 (70% 训练, 15% 验证, 15% 测试)
        total = len(self.generated_sentences)
        train_size = int(total * 0.7)
        valid_size = int(total * 0.15)
        
        train_data = self.generated_sentences[:train_size]
        valid_data = self.generated_sentences[train_size:train_size + valid_size]
        test_data = self.generated_sentences[train_size + valid_size:]
        
        # 保存训练集
        train_file = os.path.join(output_dir, Config.TRAIN_FILE)
        self.save_csv_data(train_data, train_file)
        
        # 保存验证集
        valid_file = os.path.join(output_dir, Config.VALID_FILE)
        self.save_csv_data(valid_data, valid_file)
        
        # 保存测试集
        test_file = os.path.join(output_dir, Config.TEST_FILE)
        self.save_csv_data(test_data, test_file)
        
        print(f"✅ DeepKE数据导出完成:")
        print(f"  - 训练集: {train_file} ({len(train_data)} 条)")
        print(f"  - 验证集: {valid_file} ({len(valid_data)} 条)")
        print(f"  - 测试集: {test_file} ({len(test_data)} 条)")
    
    def save_csv_data(self, data, filename):
        """保存CSV格式数据"""
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['sentence', 'relation', 'head', 'head_offset', 'tail', 'tail_offset'])
            
            for item in data:
                sentence = item['sentence']
                head = item['head']
                tail = item['tail']
                relation = item['relation']
                
                # 计算实体在句子中的位置
                head_offset = sentence.find(head)
                tail_offset = sentence.find(tail)
                
                # 如果找不到实体位置，跳过这条数据
                if head_offset == -1 or tail_offset == -1:
                    continue
                
                writer.writerow([
                    sentence, relation, head, 
                    f"{head_offset},{head_offset + len(head)}", 
                    tail, 
                    f"{tail_offset},{tail_offset + len(tail)}"
                ])
    
    def run(self, fast_mode=True):
        """运行数据生成流程"""
        try:
            if fast_mode:
                print("\n⚡ 使用高效模式生成数据...")
                self.generate_all_data_fast()
            else:
                print("\n🐌 使用标准模式生成数据...")
                self.generate_all_data()
            
            # 保存数据
            self.save_data()
            
            # 导出DeepKE格式
            self.export_to_deepke_format()
            
            # 保存缓存
            if self.enable_cache:
                self.save_cache()
            
            print(f"\n🎉 数据生成流程完成!")
            print(f"📊 生成统计:")
            for relation, count in self.relation_counts.items():
                print(f"   - {relation}: {count} 条")
            
        except Exception as e:
            logger.error(f"数据生成失败: {e}")
            # 即使失败也要保存缓存
            if self.enable_cache:
                self.save_cache()
            raise

# ========================= 主函数 =============================
def main():
    """主函数"""
    try:
        # 检查API密钥
        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            print("❌ 错误: 请设置环境变量 ARK_API_KEY")
            return
        
        print("🚀 启动知识图谱数据生成器...")
        
        # 初始化生成器（使用优化版本）
        generator = KnowledgeGraphGenerator(api_key)
        
        # 运行数据生成（默认使用快速模式）
        generator.run(fast_mode=True)
        
    except Exception as e:
        print(f"❌ 程序执行失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()