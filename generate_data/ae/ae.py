import os
import json
import time
import re
import requests
from dotenv import load_dotenv
import sys
from volcenginesdkarkruntime import Ark
import concurrent.futures
from threading import Lock
import hashlib

# 加载环境变量
load_dotenv()

class KGAttributeGenerator:
    """数据结构知识图谱属性生成器（调用火山引擎大模型API）"""
    
    def __init__(self):
        """初始化火山引擎API配置"""
        self.api_key = os.getenv("ARK_API_KEY")
        if not self.api_key:
            raise EnvironmentError(
                "请设置火山引擎API密钥\n"
               
            )
        # 去除API密钥中的空白字符（包括换行符、制表符等）
        self.api_key = self.api_key.strip()
        
        # 初始化火山方舟客户端
        self.client = Ark(api_key=self.api_key)
        self.model_id = "doubao-seed-1-6-thinking-250715"
        
        # API调用优化参数
        self.api_timeout = 120  # 增加请求超时时间到120秒
        self.retry_attempts = 2  # 增加重试次数到2次
        self.retry_delay = 2  # 增加重试延迟到2秒
        
        # 并发控制和缓存
        self.max_workers = 3  # 减少并发数以降低API压力
        self.cache = {}  # 响应缓存
        self.cache_lock = Lock()  # 缓存锁
        self.cache_file = "cache/api_cache.json"  # 缓存文件
        # 初始化缓存大小记录
        self._last_cache_size = 0
        # 加载现有缓存
        self.load_cache()
        
        # 从提供的文件内容中解析实体列表
        self.entities = self.parse_entities_file()
        
        # 优化后的属性设计（基于计算机科学标准）
        self.optimized_attrs = {
            "DataStructure": [
                "description", "storage_method", "properties", "time_complexity", 
                "space_complexity", "related_algorithms", "common_operations"
            ],
            "Algorithm": [
                "description", "principle", "applicable_conditions", "time_complexity",
                "space_complexity", "related_data_structures", "key_steps"
            ],
            "Operation": [
                "description", "complexity", "applied_to", "operation_type", 
                "side_effects", "typical_usage"
            ],
            "Complexity": [
                "notation", "description", "typical_cases", "explanation", 
                "best_case", "average_case", "worst_case", "example"
            ],
            "ApplicationScenario": [
                "description", "key_problem", "common_solutions", "related_data_structures",
                "related_algorithms", "real_world_examples"
            ],
            "PrincipleOrProperty": [
                "description", "key_characteristic", "implications", "related_concepts",
                "examples", "theoretical_basis"
            ]
        }
        
        # 保存结果的JSON文件
        self.output_file = "data_structure_kg_optimized.json"
        self.start_time = time.time()
        
        # 验证实体列表
        if not self.entities:
            raise ValueError("未找到任何实体，请检查输入文件格式")
        print(f"✅ 识别到 {len(self.entities)} 个实体，开始生成属性...")

    def parse_entities_file(self):
        """解析提供的实体文件内容"""
        # 从用户提供的文件内容中提取实体
        entities_str = """
栈,DataStructure
队列,DataStructure
链表,DataStructure
二叉树,DataStructure
图,DataStructure
哈希表,DataStructure
数组,DataStructure
树,DataStructure
二叉搜索树,DataStructure
平衡二叉树,DataStructure
堆,DataStructure
大根堆,DataStructure
小根堆,DataStructure
单链表,DataStructure
双向链表,DataStructure
循环链表,DataStructure
线性表,DataStructure
优先队列,DataStructure
B+树,DataStructure
B树,DataStructure
红黑树,DataStructure
线段树,DataStructure
树状数组,DataStructure
字典树,DataStructure
后缀树,DataStructure
前缀树,DataStructure
AC自动机,DataStructure
跳跃表,DataStructure
布隆过滤器,DataStructure
并查集,DataStructure
二项堆,DataStructure
斐波那契堆,DataStructure
双端队列,DataStructure
循环队列,DataStructure
二叉堆,DataStructure
可持久化数据结构,DataStructure
生成森林,DataStructure
LRU缓存,DataStructure
LFU缓存,DataStructure
不相交集合,DataStructure
入栈,Operation
出栈,Operation
入队,Operation
出队,Operation
插入,Operation
删除,Operation
查找,Operation
遍历,Operation
初始化,Operation
扩容,Operation
缩容,Operation
复制,Operation
合并,Operation
移动,Operation
销毁,Operation
路径压缩,Operation
旋转,Operation
顺序访问,Operation
随机访问,Operation
按秩合并,Operation
内存分配,Operation
垃圾回收,Operation
引用计数,Operation
快速排序,Algorithm
深度优先搜索,Algorithm
广度优先搜索,Algorithm
Dijkstra算法,Algorithm
KMP算法,Algorithm
冒泡排序,Algorithm
选择排序,Algorithm
插入排序,Algorithm
归并排序,Algorithm
堆排序,Algorithm
拓扑排序,Algorithm
最小生成树,Algorithm
直接插入排序,Algorithm
希尔排序,Algorithm
基数排序,Algorithm
克鲁斯卡尔算法,Algorithm
普里姆算法,Algorithm
迪杰斯特拉算法,Algorithm
弗洛伊德算法,Algorithm
分治,Algorithm
贪心策略,Algorithm
动态规划,Algorithm
回溯法,Algorithm
穷举法,Algorithm
插值查找,Algorithm
折半查找,Algorithm
计数排序,Algorithm
单源最短路径,Algorithm
外部排序,Algorithm
桶排序,Algorithm
哈希查找,Algorithm
分支限界,Algorithm
分块查找,Algorithm
记忆化搜索,Algorithm
Bellman-Ford算法,Algorithm
二路归并,Algorithm
线性查找,Algorithm
多路归并,Algorithm
状态转移,Algorithm
O(1),Complexity
O(log n),Complexity
O(n),Complexity
O(n log n),Complexity
O(n²),Complexity
最坏情况,Complexity
平均情况,Complexity
最好情况,Complexity
平均查找长度,Complexity
渐近复杂度,Complexity
摊还分析,Complexity
会计方法,Complexity
聚合分析,Complexity
势能方法,Complexity
Θ记号,Complexity
Ω记号,Complexity
大O记号,Complexity
时间复杂度,Complexity
空间复杂度,Complexity
表达式求值,ApplicationScenario
任务调度,ApplicationScenario
迷宫求解,ApplicationScenario
最短路径,ApplicationScenario
括号匹配,ApplicationScenario
LIFO,PrincipleOrProperty
FIFO,PrincipleOrProperty
稳定性,PrincipleOrProperty
原地排序,PrincipleOrProperty
有穷性,PrincipleOrProperty
确定性,PrincipleOrProperty
可行性,PrincipleOrProperty
最优子结构,PrincipleOrProperty
贪心选择性质,PrincipleOrProperty
局部最优,PrincipleOrProperty
全局最优,PrincipleOrProperty
重叠子问题,PrincipleOrProperty
顺序存储,PrincipleOrProperty
链式存储,PrincipleOrProperty
无序序列,PrincipleOrProperty
有序序列,PrincipleOrProperty
线性结构,PrincipleOrProperty
非线性结构,PrincipleOrProperty
        """
        
        # 解析实体列表
        entities = []
        for line in entities_str.strip().split('\n'):
            if ',' in line:
                name, entity_type = line.strip().split(',', 1)
                entities.append({"name": name, "type": entity_type})
        return entities

    def generate_prompt(self, entity):
        """为每个实体生成大模型提示词（优化后的提示词）"""
        # 获取该类型需要的优化属性
        attrs = self.optimized_attrs.get(entity["type"], [])
        
        # 创建属性要求字符串
        attrs_str = ", ".join(attrs)
        
        prompt = f"""
你是一个计算机科学专家，请为以下数据结构知识图谱实体生成详细属性。必须严格按JSON格式返回，只包含以下属性：
{attrs_str}

实体类型：{entity["type"]}
实体名称：{entity["name"]}

要求：
1. 所有属性必须填写（无则填"未定义"）
2. 时间复杂度属性必须用字典格式（如：{{"入栈": "O(1)"}})
3. 仅输出JSON，不要包含其他任何文本
4. 确保属性值基于标准计算机科学知识（参考《算法导论》）
5. 为Operation类型添加typical_usage（典型使用场景）
6. 为Complexity类型添加best_case/average_case/worst_case（最好/平均/最坏情况）
"""
        return prompt

    def get_cache_key(self, prompt):
        """生成缓存键"""
        return hashlib.md5(prompt.encode('utf-8')).hexdigest()
    
    def load_cache(self):
        """加载缓存文件"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                print(f"✅ 加载缓存: {len(self.cache)} 条记录")
                # 初始化缓存大小记录
                self._last_cache_size = len(self.cache)
            else:
                self.cache = {}
                self._last_cache_size = 0
        except Exception as e:
            print(f"⚠️ 缓存加载失败: {e}")
            self.cache = {}
            self._last_cache_size = 0
    
    def save_cache(self):
        """保存缓存到文件（优化版本，避免频繁IO）"""
        try:
            with self.cache_lock:
                # 检查是否有新的缓存内容需要保存
                if hasattr(self, '_last_cache_size') and len(self.cache) == self._last_cache_size:
                    return  # 没有新内容，跳过保存
                
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
                
                # 记录当前缓存大小
                self._last_cache_size = len(self.cache)
                
        except Exception as e:
            print(f"⚠️ 缓存保存失败: {e}")

    def call_model_api(self, prompt):
        """调用模型API（带缓存和重试机制）"""
        # 检查缓存
        cache_key = self.get_cache_key(prompt)
        with self.cache_lock:
            if cache_key in self.cache:
                print("  📋 使用缓存响应")
                return self.cache[cache_key]
        
        # 准备API调用参数
        messages = [{"role": "user", "content": prompt}]
        
        # 重试机制
        for attempt in range(self.retry_attempts):
            try:
                # 调用API
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    max_tokens=2048,  # 优化：减少token数量
                    temperature=0.5,  # 优化：降低随机性，提高一致性
                    top_p=0.9,       # 优化：提高响应质量
                    stream=False,     # 优化：非流式响应更快
                    timeout=self.api_timeout  # 设置超时
                )
                
                # 提取响应内容
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content
                    
                    # 缓存响应并立即保存到文件
                    with self.cache_lock:
                        self.cache[cache_key] = content
                    
                    # 立即保存缓存到文件
                    self.save_cache()
                    print("  💾 缓存已保存")
                    
                    return content
                else:
                    print(f"  ⚠️ API响应格式异常")
                    return None
                    
            except Exception as e:
                error_msg = str(e)
                print(f"  ❌ API调用失败 (尝试 {attempt + 1}/{self.retry_attempts}): {error_msg}")
                
                # 根据错误类型调整重试策略
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    # 超时错误，使用更长的等待时间
                    wait_time = self.retry_delay * (2 ** attempt)  # 指数退避
                    print(f"  ⏳ 检测到超时错误，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                elif "rate limit" in error_msg.lower() or "429" in error_msg:
                    # 速率限制错误，等待更长时间
                    wait_time = self.retry_delay * (3 ** attempt)
                    print(f"  ⏳ 检测到速率限制，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    # 其他错误，正常等待
                    wait_time = self.retry_delay * (attempt + 1)
                    if attempt < self.retry_attempts - 1:
                        time.sleep(wait_time)
                
                if attempt >= self.retry_attempts - 1:
                    print(f"  ❌ 所有重试均失败，跳过此实体")
                    return None

    def parse_model_response(self, response):
        """解析大模型返回的JSON字符串（优化解析）"""
        # 尝试提取JSON（处理可能的额外文本）
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        
        # 尝试直接解析（如果返回的是纯JSON）
        try:
            return json.loads(response)
        except:
            return {}

    def process_single_entity(self, entity_info):
        """处理单个实体（用于并发）"""
        i, entity, total = entity_info
        print(f"处理实体 {i}/{total}: {entity['name']} ({entity['type']})")
        
        # 生成提示词
        prompt = self.generate_prompt(entity)
        
        # 调用API
        response = self.call_model_api(prompt)
        
        # 解析响应
        if not response:
            print(f"  ⚠️ 未收到有效响应，跳过实体: {entity['name']}")
            parsed = {}
        else:
            parsed = self.parse_model_response(response)
        
        # 合并原始实体和生成属性
        full_entity = {
            "type": entity["type"],
            "name": entity["name"],
            **parsed  # 添加生成的属性
        }
        
        # 确保所有优化属性都存在（避免缺失）
        for attr in self.optimized_attrs.get(entity["type"], []):
            if attr not in full_entity:
                full_entity[attr] = "未定义"
        
        return full_entity

    def generate_attributes(self):
        """为主实体生成所有属性（并发优化版）"""
        results = []
        total = len(self.entities)
        
        # 准备实体信息
        entity_infos = [(i+1, entity, total) for i, entity in enumerate(self.entities)]
        
        # 使用线程池并发处理，添加批次处理以减少API压力
        batch_size = 5  # 每批处理5个实体
        
        for i in range(0, len(entity_infos), batch_size):
            batch = entity_infos[i:i+batch_size]
            print(f"🔄 处理批次 {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交当前批次的任务
                future_to_entity = {
                    executor.submit(self.process_single_entity, entity_info): entity_info 
                    for entity_info in batch
                }
                
                # 收集当前批次的结果
                batch_results = []
                for future in concurrent.futures.as_completed(future_to_entity):
                    try:
                        result = future.result()
                        batch_results.append(result)
                        
                    except Exception as e:
                        entity_info = future_to_entity[future]
                        print(f"  ❌ 处理实体失败: {entity_info[1]['name']} - {e}")
                
                results.extend(batch_results)
                
                # 批次间休息，避免API压力过大
                if i + batch_size < len(entity_infos):
                    print(f"  💤 批次完成，休息1秒...")
                    time.sleep(1)
            
            # 定期保存缓存（移除，因为现在每个实体处理完都会保存）
            # if len(results) % 10 == 0:
            #     self.save_cache()
            #     print(f"  💾 已处理 {len(results)}/{total} 个实体，缓存已保存")
        
        # 最终保存缓存
        self.save_cache()
        print(f"✅ 处理完成，共 {len(results)} 个实体")
        
        return results

    def save_to_json(self, data):
        """保存结果到JSON文件（优化格式）"""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已保存到: {self.output_file}")
        print(f"总实体数: {len(data)} | 生成时间: {time.time() - self.start_time:.2f}秒")

    def validate_kg(self, data):
        """验证生成的JSON是否符合知识图谱规范"""
        print("\n🔍 正在验证知识图谱数据规范...")
        valid_types = set(self.optimized_attrs.keys())
        
        for i, entity in enumerate(data, 1):
            # 验证类型
            if entity["type"] not in valid_types:
                raise ValueError(f"实体{entity['name']}类型无效: {entity['type']}")
            
            # 验证必需属性
            required_attrs = self.optimized_attrs.get(entity["type"], [])
            missing = [attr for attr in required_attrs if attr not in entity]
            if missing:
                print(f"  ⚠️ 实体 {entity['name']} 缺少属性: {missing}")
        
        print("✅ 知识图谱数据验证通过")
        return True

    def run(self):
        """执行完整流程"""
        try:
            # 1. 生成属性
            generated_data = self.generate_attributes()
            
            # 2. 保存结果
            self.save_to_json(generated_data)
            
            # 3. 验证数据
            self.validate_kg(generated_data)
            
            print("\n🎉 知识图谱属性生成完成！")
            print(f"✅ 生成文件: {self.output_file}")
            print("✅ 生成时间: {:.2f}秒".format(time.time() - self.start_time))
            
        except Exception as e:
            print(f"\n🚨 生成过程出错: {str(e)}")
        
            sys.exit(1)

if __name__ == "__main__":
    try:
        generator = KGAttributeGenerator()
        generator.run()
    except Exception as e:
        print(f"初始化失败: {str(e)}")
        sys.exit(1)