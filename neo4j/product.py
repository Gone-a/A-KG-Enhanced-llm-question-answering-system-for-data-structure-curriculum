from py2neo import Graph, Node, Relationship
import os
import pandas as pd
import re
import json
from tqdm import tqdm
import csv

class Neo4jKnowledgeGraph:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="123456", confidence=0.7):
        """初始化Neo4j图数据库连接
        
        Args:
            uri (str): Neo4j数据库URI
            user (str): 用户名
            password (str): 密码
            confidence (float): 置信度阈值，默认0.7
        """
        self.confidence = confidence
        # 获取当前文件所在目录
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_path = os.path.join(cur_dir, "data")
        
        # Neo4j连接配置
        try:
            #从环境变量获取连接信息
            password = os.getenv("NEO4J_KEY", password)
            self.graph = Graph(uri, auth=(user, password))
            # 测试连接
            self.graph.run("RETURN 1")
            print("✅ Neo4j图数据库连接成功")
        except Exception as e:
            print(f"❌ Neo4j连接失败: {e}")
            raise e
        
        # 从CSV文件加载实体类型映射
        self.entity_type_dict = self.load_entity_types_from_csv()
        
        # 从CSV文件加载关系类型映射
        self.relation_dict = self.load_relations_from_csv()
        
        # 备用的实体类型映射（用于未在CSV中定义的实体）
        self.fallback_entity_type_dict = {
            "ApplicationScenario": "应用场景",
            "DataStructure": "数据结构", 
            "Algorithm": "算法",
            "Operation": "操作",
            "Complexity": "复杂度",
            "PrincipleOrProperty": "原理或属性"
        }
        
        # 备用的关系类型映射
        self.fallback_relation_dict = {
            "hasComplexity": "具有复杂度",
            "uses": "使用",
            "variantOf": "是变体",
            "appliesTo": "适用于",
            "provides": "提供",
            "implementedAs": "实现为",
            "usedIn": "用于"
        }

    def load_entity_types_from_csv(self):
        """从vocab_dict.csv文件加载实体类型映射"""
        entity_types = {}
        vocab_dict_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'vocab_dict.csv')
        
        try:
            with open(vocab_dict_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        entity_name = row[0].strip()
                        entity_type = row[1].strip()
                        entity_types[entity_name] = entity_type
            print(f"成功加载 {len(entity_types)} 个实体类型映射")
        except FileNotFoundError:
            print(f"警告：未找到vocab_dict.csv文件，使用默认实体类型映射")
            return {}
        except Exception as e:
            print(f"加载vocab_dict.csv时出错：{e}")
            return {}
            
        return entity_types

    def load_relations_from_csv(self):
        """从relation.csv文件加载关系类型映射"""
        relations = {}
        relation_csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'relation.csv')
        
        try:
            with open(relation_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    relation_name = row['relation'].strip()
                    head_type = row['head_type'].strip()
                    tail_type = row['tail_type'].strip()
                    index = int(row['index'])
                    
                    # 存储关系信息，包括头尾实体类型约束
                    relations[relation_name] = {
                        'name': relation_name,
                        'head_type': head_type,
                        'tail_type': tail_type,
                        'index': index
                    }
            print(f"成功加载 {len(relations)} 个关系类型映射")
        except FileNotFoundError:
            print(f"警告：未找到relation.csv文件，使用默认关系类型映射")
            return {}
        except Exception as e:
            print(f"加载relation.csv时出错：{e}")
            return {}
            
        return relations

    def clean_database(self):
        """彻底清理数据库：删除所有节点、关系、索引、约束和属性标签"""
        try:
            print("🧹 开始清理数据库...")
            
            # 1. 获取并删除所有约束
            constraints_result = self.graph.run("SHOW CONSTRAINTS").data()
            for constraint in constraints_result:
                constraint_name = constraint.get('name')
                if constraint_name:
                    try:
                        self.graph.run(f"DROP CONSTRAINT {constraint_name} IF EXISTS")
                        print(f"   ✓ 删除约束: {constraint_name}")
                    except Exception as e:
                        print(f"   ⚠️ 删除约束 {constraint_name} 失败: {e}")
            
            # 2. 获取并删除所有索引
            indexes_result = self.graph.run("SHOW INDEXES").data()
            for index in indexes_result:
                index_name = index.get('name')
                if index_name:
                    try:
                        self.graph.run(f"DROP INDEX {index_name} IF EXISTS")
                        print(f"   ✓ 删除索引: {index_name}")
                    except Exception as e:
                        print(f"   ⚠️ 删除索引 {index_name} 失败: {e}")
            
            # 3. 删除所有节点和关系
            self.graph.run("MATCH (n) DETACH DELETE n")
            print("   ✓ 删除所有节点和关系")
            
            # 4. 尝试清理属性标签元数据 - Neo4j特殊处理
            print("   🔄 尝试清理属性标签元数据...")
            
            # 策略1: 尝试使用APOC清理（如果可用）
            try:
                self.graph.run("CALL apoc.schema.assert({}, {})")
                print("   ✓ 使用APOC清理模式")
            except:
                pass
            
            # 策略2: 尝试清理系统缓存
            try:
                self.graph.run("CALL db.clearQueryCaches()")
                print("   ✓ 清理查询缓存")
            except:
                pass
            
            # 策略3: 多次删除操作
            for i in range(5):
                self.graph.run("MATCH (n) DETACH DELETE n")
            
            # 策略4: 尝试手动清理统计信息
            try:
                self.graph.run("CALL db.stats.clear()")
                print("   ✓ 清理统计信息")
            except:
                pass
            
            # 策略5: 重新建立连接（修复属性引用问题）
            try:
                # 保存连接参数
                uri = getattr(self, 'uri', "bolt://localhost:7687")
                user = getattr(self, 'user', "neo4j") 
                password = getattr(self, 'password', "123456")
                
                # 重新连接
                from py2neo import Graph
                self.graph = Graph(uri, auth=(user, password))
                print("   ✓ 重新连接数据库刷新元数据")
            except Exception as e:
                print(f"   ⚠️ 重新连接失败: {e}")
            
            # 5. 验证清理结果
            try:
                property_keys_result = self.graph.run("CALL db.propertyKeys()").data()
                labels_result = self.graph.run("CALL db.labels()").data()
                rel_types_result = self.graph.run("CALL db.relationshipTypes()").data()
                
                property_count = len(property_keys_result) if property_keys_result else 0
                label_count = len(labels_result) if labels_result else 0
                rel_type_count = len(rel_types_result) if rel_types_result else 0
                
                if property_count == 0 and label_count == 0 and rel_type_count == 0:
                    print("   ✅ 属性标签已完全清理")
                else:
                    print(f"   ⚠️ Neo4j元数据残留（这是正常的）：属性键{property_count}个，标签{label_count}个，关系类型{rel_type_count}个")
                    print("   ℹ️ 注意：Neo4j会保留属性键元数据直到数据库重启，这不影响新数据的创建")
                        
            except Exception as e:
                print(f"   ⚠️ 验证清理结果时出错: {e}")
            
            print("🧹🧹 数据库已彻底清理完成（包括属性标签）")
            
        except Exception as e:
            print(f"清理数据库时出错: {e}")
            # 备选方案：使用传统方式清理
            print("⚠️ 尝试备选清理方案...")
            try:
                # 删除已知的约束和索引
                known_constraints = ["entity_name_unique"]
                for constraint in known_constraints:
                    self.graph.run(f"DROP CONSTRAINT {constraint} IF EXISTS")
                
                # 删除已知的索引
                entity_types = ['DataStructure', 'Algorithm', 'Operation', 'Complexity', 
                              'ApplicationScenario', 'PrincipleOrProperty', 'Concept']
                known_indexes = ["entity_name_index", "entity_type_index"]
                for entity_type in entity_types:
                    known_indexes.append(f"{entity_type.lower()}_name_index")
                
                for index in known_indexes:
                    self.graph.run(f"DROP INDEX {index} IF EXISTS")
                
                # 删除所有节点和关系
                self.graph.run("MATCH (n) DETACH DELETE n")
                
                # 备选方案也检查属性标签清理情况
                try:
                    property_keys_result = self.graph.run("CALL db.propertyKeys()").data()
                    labels_result = self.graph.run("CALL db.labels()").data()
                    rel_types_result = self.graph.run("CALL db.relationshipTypes()").data()
                    
                    if not property_keys_result and not labels_result and not rel_types_result:
                        print("   ✓ 属性标签已完全清理")
                    else:
                        print(f"   ⚠️ 仍有残留：属性键{len(property_keys_result or [])}个，标签{len(labels_result or [])}个，关系类型{len(rel_types_result or [])}个")
                except:
                    pass
                
                print("🧹 备选清理方案执行完成")
                
            except Exception as backup_e:
                print(f"备选清理方案也失败: {backup_e}")
                # 最后的兜底方案：只删除节点和关系
                try:
                    self.graph.run("MATCH (n) DETACH DELETE n")
                    print("🧹 最小清理方案：仅删除节点和关系")
                except Exception as final_e:
                    print(f"❌ 所有清理方案都失败: {final_e}")
                    raise final_e

    def normalize_entity(self, entity):
        """标准化实体名称，提取核心术语"""
        if not entity:
            return ""
        
        # 去除多余的空格和特殊字符
        entity = re.sub(r'\s+', ' ', entity.strip())
        
        # 去除括号内容（如：快速排序(QuickSort) -> 快速排序）
        entity = re.sub(r'\([^)]*\)', '', entity)
        
        # 去除引号
        entity = entity.replace('"', '').replace("'", '')
        
        return entity.strip()

    def get_entity_type_from_data(self, entity_name, data_type=None):
        """根据实体名称和数据中的类型信息获取实体类型"""
        # 优先使用数据中提供的类型
        if data_type and data_type in self.fallback_entity_type_dict:
            return data_type
        
        # 从CSV加载的实体类型映射中查找
        if entity_name in self.entity_type_dict:
            return self.entity_type_dict[entity_name]
        
        # 基于实体名称的启发式判断
        entity_lower = entity_name.lower()
        
        # 算法相关
        if any(keyword in entity_lower for keyword in ['排序', '搜索', '查找', '算法', 'sort', 'search', 'algorithm']):
            return 'Algorithm'
        
        # 数据结构相关
        if any(keyword in entity_lower for keyword in ['栈', '队列', '链表', '树', '图', '数组', '堆', '表', 'stack', 'queue', 'list', 'tree', 'graph', 'array', 'heap']):
            return 'DataStructure'
        
        # 应用场景相关
        if any(keyword in entity_lower for keyword in ['应用', '场景', '求解', '匹配', 'application', 'scenario']):
            return 'ApplicationScenario'
        
        # 操作相关
        if any(keyword in entity_lower for keyword in ['插入', '删除', '查找', '遍历', '初始化', '扩容', '入栈', '出栈', '入队', '出队']):
            return 'Operation'
        
        # 复杂度相关
        if any(keyword in entity_lower for keyword in ['o(', '复杂度', 'complexity', '时间', '空间']):
            return 'Complexity'
        
        # 原理或属性相关
        if any(keyword in entity_lower for keyword in ['lifo', 'fifo', '稳定性', '原地', '有穷性', '确定性', '最优']):
            return 'PrincipleOrProperty'
        
        # 默认返回概念类型
        return 'Concept'

    def create_nodes_with_types(self, data):
        """创建所有实体节点，使用数据中的类型信息"""
        entities = set()
        
        # 收集所有实体
        for item in data:
            head = self.normalize_entity(item.get('head', ''))
            tail = self.normalize_entity(item.get('tail', ''))
            
            if head:
                head_type = self.get_entity_type_from_data(head, item.get('head_type'))
                entities.add((head, head_type))
            
            if tail:
                tail_type = self.get_entity_type_from_data(tail, item.get('tail_type'))
                entities.add((tail, tail_type))
        
        # 创建节点
        created_count = 0
        for entity_name, entity_type in entities:
            if entity_name:
                # 创建节点，使用实体类型作为标签
                node = Node(entity_type, name=entity_name, type=entity_type)
                self.graph.create(node)
                created_count += 1
        
        print(f"✅ 创建了 {created_count} 个实体节点")
        return created_count

    def create_relationships_with_offsets(self, data):
        """创建实体间的关系，包含偏移量信息"""
        created_count = 0
        relation_types = set()
        
        for item in tqdm(data, desc="创建关系"):
            head = self.normalize_entity(item.get('head', ''))
            tail = self.normalize_entity(item.get('tail', ''))
            relation = item.get('relation', '')
            
            if not head or not tail or not relation:
                continue
            
            # 获取实体类型
            head_type = self.get_entity_type_from_data(head, item.get('head_type'))
            tail_type = self.get_entity_type_from_data(tail, item.get('tail_type'))
            
            # 验证关系类型约束（如果有定义的话）
            if relation in self.relation_dict:
                relation_info = self.relation_dict[relation]
                expected_head_type = relation_info.get('head_type')
                expected_tail_type = relation_info.get('tail_type')
                
                # 如果定义了类型约束，进行验证
                if expected_head_type and head_type != expected_head_type:
                    continue
                if expected_tail_type and tail_type != expected_tail_type:
                    continue
            
            # 查找头尾节点
            head_node = self.graph.nodes.match(head_type, name=head).first()
            tail_node = self.graph.nodes.match(tail_type, name=tail).first()
            
            if head_node and tail_node:
                # 创建关系，只保留语句信息
                rel_props = {
                    'source_sentence': item.get('sentence', ''),
                }
                
                relationship = Relationship(head_node, relation, tail_node, **rel_props)
                self.graph.create(relationship)
                created_count += 1
                relation_types.add(relation)
        
        print(f"✅ 创建了 {created_count} 个关系")
        print(f"📊 关系类型统计: {dict.fromkeys(relation_types, '✓')}")
        return created_count

    def create_indexes(self):
        """创建索引以提高查询性能"""
        try:
            # 为实体名称创建唯一约束
            self.graph.run("CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.name IS UNIQUE")
            
            # 为不同实体类型创建索引
            entity_types = ['DataStructure', 'Algorithm', 'Operation', 'Complexity', 'ApplicationScenario', 'PrincipleOrProperty', 'Concept']
            for entity_type in entity_types:
                self.graph.run(f"CREATE INDEX {entity_type.lower()}_name_index IF NOT EXISTS FOR (n:{entity_type}) ON (n.name)")
            
            print("✅ 索引创建完成")
        except Exception as e:
            print(f"⚠️ 创建索引时出现警告: {e}")

    def load_entity_offsets_data(self, file_path=None):
        """加载entity_offsets.json格式的数据"""
        if file_path is None:
            file_path = os.path.join(self.data_path, "entity_offsets.json")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"📁 成功加载数据文件: {file_path}")
            print(f"📊 原始数据条数: {len(data)}")
            
            # 数据预处理和过滤
            valid_data = []
            for item in data:
                # 标准化实体名称
                head = self.normalize_entity(item.get('head', ''))
                tail = self.normalize_entity(item.get('tail', ''))
                relation = item.get('relation', '')
                
                # 过滤无效关系
                if head and tail and relation and head != tail:
                    item['head'] = head
                    item['tail'] = tail
                    
                    # 设置置信度（如果没有的话）
                    if 'confidence' not in item:
                        item['confidence'] = 1.0
                    
                    # 只保留置信度高于阈值的关系
                    if item['confidence'] >= self.confidence:
                        valid_data.append(item)
            
            print(f"✅ 有效数据条数: {len(valid_data)}")
            return valid_data
            
        except FileNotFoundError:
            print(f"❌ 文件不存在: {file_path}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析错误: {e}")
            return []
        except Exception as e:
            print(f"❌ 加载数据时出错: {e}")
            return []

    def load_json_data(self, file_path):
        """加载JSON格式的数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"📁 成功加载数据文件: {file_path}")
            print(f"📊 原始数据条数: {len(data)}")
            
            # 数据预处理
            processed_data = []
            for item in data:
                if isinstance(item, dict):
                    head = self.normalize_entity(item.get('head', ''))
                    tail = self.normalize_entity(item.get('tail', ''))
                    relation = item.get('relation', item.get('predicate', ''))
                    
                    if head and tail and relation and head != tail:
                        processed_item = {
                            'head': head,
                            'tail': tail,
                            'relation': relation,
                            'confidence': item.get('confidence', 1.0),
                            'sentence': item.get('sentence', item.get('text', ''))
                        }
                        
                        if processed_item['confidence'] >= self.confidence:
                            processed_data.append(processed_item)
            
            print(f"✅ 有效数据条数: {len(processed_data)}")
            return processed_data
            
        except Exception as e:
            print(f"❌ 加载JSON数据时出错: {e}")
            return []

    def load_csv_data(self, file_path):
        """加载CSV格式的数据"""
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            print(f"📁 成功加载数据文件: {file_path}")
            print(f"📊 原始数据条数: {len(df)}")
            
            processed_data = []
            for _, row in df.iterrows():
                head = self.normalize_entity(str(row.get('head', row.get('subject', ''))))
                tail = self.normalize_entity(str(row.get('tail', row.get('object', ''))))
                relation = str(row.get('relation', row.get('predicate', '')))
                
                if head and tail and relation and head != tail:
                    processed_item = {
                        'head': head,
                        'tail': tail,
                        'relation': relation,
                        'confidence': float(row.get('confidence', 1.0)),
                        'sentence': str(row.get('sentence', row.get('text', '')))
                    }
                    
                    if processed_item['confidence'] >= self.confidence:
                        processed_data.append(processed_item)
            
            print(f"✅ 有效数据条数: {len(processed_data)}")
            return processed_data
            
        except Exception as e:
            print(f"❌ 加载CSV数据时出错: {e}")
            return []

    def remove_duplicate_relationships(self, data):
        """去除重复的关系"""
        seen = set()
        unique_data = []
        
        for item in data:
            # 创建关系的唯一标识
            key = (item['head'], item['relation'], item['tail'])
            if key not in seen:
                seen.add(key)
                unique_data.append(item)
        
        print(f"🔄 去重后数据条数: {len(unique_data)} (去除了 {len(data) - len(unique_data)} 条重复数据)")
        return unique_data

    def build_knowledge_graph(self, data_source='entity_offsets', file_path=None):
        """构建知识图谱"""
        print("🚀 开始构建知识图谱...")
        
        # 清理数据库
        self.clean_database()
        
        # 根据数据源加载数据
        if data_source == 'entity_offsets':
            data = self.load_entity_offsets_data(file_path)
        elif data_source == 'json':
            data = self.load_json_data(file_path)
        elif data_source == 'csv':
            data = self.load_csv_data(file_path)
        else:
            print(f"❌ 不支持的数据源类型: {data_source}")
            return
        
        if not data:
            print("❌ 没有有效数据，构建失败")
            return
        
        # 去除重复关系
        data = self.remove_duplicate_relationships(data)
        
        # 创建节点
        node_count = self.create_nodes_with_types(data)
        
        # 创建关系
        rel_count = self.create_relationships_with_offsets(data)
        
        # 创建索引
        self.create_indexes()
        
        print(f"🎉 知识图谱构建完成！")
        print(f"📊 统计信息:")
        print(f"   - 节点数量: {node_count}")
        print(f"   - 关系数量: {rel_count}")
        print(f"   - 数据源: {data_source}")

    def query_graph(self, query):
        """执行Cypher查询"""
        try:
            result = self.graph.run(query)
            return result.data()
        except Exception as e:
            print(f"❌ 查询执行失败: {e}")
            return []

    def get_graph_stats(self):
        """获取图谱统计信息"""
        try:
            # 节点统计
            node_count = self.graph.run("MATCH (n) RETURN count(n) as count").data()[0]['count']
            
            # 关系统计
            rel_count = self.graph.run("MATCH ()-[r]->() RETURN count(r) as count").data()[0]['count']
            
            # 节点类型统计
            node_types = self.graph.run("""
                MATCH (n) 
                RETURN labels(n)[0] as type, count(n) as count 
                ORDER BY count DESC
            """).data()
            
            # 关系类型统计
            rel_types = self.graph.run("""
                MATCH ()-[r]->() 
                RETURN type(r) as type, count(r) as count 
                ORDER BY count DESC
            """).data()
            
            print("📊 图谱统计信息:")
            print(f"   - 总节点数: {node_count}")
            print(f"   - 总关系数: {rel_count}")
            print("   - 节点类型分布:")
            for item in node_types:
                print(f"     * {item['type']}: {item['count']}")
            print("   - 关系类型分布:")
            for item in rel_types:
                print(f"     * {item['type']}: {item['count']}")
                
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='构建Neo4j知识图谱')
    parser.add_argument('--entity-offsets', type=str, nargs='?', const='default', 
                       help='使用entity_offsets.json数据源（可选指定文件路径）')
    parser.add_argument('--json', type=str, help='使用JSON数据源（指定文件路径）')
    parser.add_argument('--csv', type=str, help='使用CSV数据源（指定文件路径）')
    parser.add_argument('--confidence', type=float, default=0.7, help='置信度阈值（默认0.7）')
    parser.add_argument('--stats', action='store_true', help='显示图谱统计信息')
    
    args = parser.parse_args()
    
    # 创建知识图谱构建器
    kg_builder = Neo4jKnowledgeGraph(confidence=args.confidence)
    
    if args.stats:
        # 显示统计信息
        kg_builder.get_graph_stats()
    elif args.entity_offsets:
        # 使用entity_offsets数据源
        file_path = None if args.entity_offsets == 'default' else args.entity_offsets
        print("🔄 使用entity_offsets.json数据源")
        kg_builder.build_knowledge_graph(data_source='entity_offsets', file_path=file_path)
    elif args.json:
        # 使用JSON数据源
        print(f"🔄 使用JSON数据源: {args.json}")
        kg_builder.build_knowledge_graph(data_source='json', file_path=args.json)
    elif args.csv:
        # 使用CSV数据源
        print(f"🔄 使用CSV数据源: {args.csv}")
        kg_builder.build_knowledge_graph(data_source='csv', file_path=args.csv)
    else:
        # 默认使用entity_offsets数据源
        print("🔄 使用默认entity_offsets.json数据源")
        kg_builder.build_knowledge_graph(data_source='entity_offsets')