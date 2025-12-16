import sys
import os

# 将项目根目录添加到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from py2neo import Graph, Node, Relationship
import json
from tqdm import tqdm
import re
from modules.config_manager import ConfigManager

class Neo4jEntityAttributeImporter:
    def __init__(self, config_manager: ConfigManager = None):
        """初始化Neo4j图数据库连接，用于导入实体属性
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager or ConfigManager()
        db_config = self.config_manager.get_database_config()
        
        # Neo4j连接配置
        try:
            self.graph = Graph(
                db_config.get('uri', 'bolt://localhost:7687'), 
                auth=(
                    db_config.get('user_name', 'neo4j'), 
                    db_config.get('password', '123456')
                )
            )
            # 测试连接
            self.graph.run("RETURN 1")
            print("✅ Neo4j图数据库连接成功")
        except Exception as e:
            print(f"❌ Neo4j连接失败: {e}")
            raise e
        self.default_data_dir = "/root/KG_inde/neo4j/data"

    def normalize_entity_name(self, name):
        """标准化实体名称，与product.py保持一致"""
        if not name:
            return ""
        
        # 去除多余的空格和特殊字符
        name = re.sub(r'\s+', ' ', name.strip())
        
        # 去除括号内容（如：快速排序(QuickSort) -> 快速排序）
        name = re.sub(r'\([^)]*\)', '', name)
        
        # 去除引号
        name = name.replace('"', '').replace("'", '')
        
        return name.strip()

    def load_entity_data(self, file_path):
        """加载实体属性数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"📁 成功加载实体属性数据: {file_path}")
            print(f"📊 实体数量: {len(data)}")
            return data
            
        except FileNotFoundError:
            print(f"❌ 文件不存在: {file_path}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析错误: {e}")
            return []
        except Exception as e:
            print(f"❌ 加载数据时出错: {e}")
            return []

    def find_entity_node(self, entity_name, entity_type=None):
        """查找图中的实体节点"""
        # 标准化实体名称
        normalized_name = self.normalize_entity_name(entity_name)
        
        # 如果指定了类型，优先按类型查找
        if entity_type:
            query = f"MATCH (n:{entity_type}) WHERE n.name = $name RETURN n"
            result = self.graph.run(query, name=normalized_name).data()
            if result:
                return result[0]['n']
        
        # 按名称查找（不限类型）
        query = "MATCH (n) WHERE n.name = $name RETURN n"
        result = self.graph.run(query, name=normalized_name).data()
        if result:
            return result[0]['n']
        
        return None

    def create_entity_with_attributes(self, entity_data):
        """创建带属性的实体节点"""
        entity_name = entity_data.get('name', '')
        entity_type = entity_data.get('type', 'Entity')
        
        if not entity_name:
            return None
        
        # 标准化实体名称
        normalized_name = self.normalize_entity_name(entity_name)
        
        # 准备节点属性
        node_props = {
            'name': normalized_name,
            'type': entity_type
        }
        
        # 动态处理所有属性字段
        for key, value in entity_data.items():
            # 跳过已处理的基本字段
            if key in ['name', 'type']:
                continue
            
            # 处理不同类型的属性值
            formatted_value = self.format_attribute_value(key, value)
            if formatted_value:
                node_props[key] = formatted_value
        
        # 创建节点
        node = Node(entity_type, **node_props)
        self.graph.create(node)
        
        return node

    def format_attribute_value(self, key, value):
        """格式化属性值为字符串，统一处理所有类型的属性"""
        if not value:
            return ""
        
        # 字符串类型直接返回
        if isinstance(value, str):
            return value
        
        # 列表类型处理
        if isinstance(value, list):
            # 对于common_operations这样的复杂列表
            if key == 'common_operations':
                return self.format_common_operations(value)
            # 普通列表用分号连接
            else:
                formatted_items = []
                for item in value:
                    if isinstance(item, dict):
                        # 字典项格式化为键值对
                        dict_parts = []
                        for k, v in item.items():
                            dict_parts.append(f"{k}: {v}")
                        formatted_items.append(f"({', '.join(dict_parts)})")
                    else:
                        formatted_items.append(str(item))
                return '; '.join(formatted_items)
        
        # 字典类型处理
        if isinstance(value, dict):
            # 对于time_complexity这样的复杂字典
            if key == 'time_complexity':
                return self.format_time_complexity(value)
            # 普通字典处理
            else:
                dict_parts = []
                for k, v in value.items():
                    if isinstance(v, dict):
                        # 嵌套字典处理
                        nested_parts = []
                        for nk, nv in v.items():
                            nested_parts.append(f"{nk}: {nv}")
                        dict_parts.append(f"{k} ({', '.join(nested_parts)})")
                    else:
                        dict_parts.append(f"{k}: {v}")
                return '; '.join(dict_parts)
        
        # 其他类型转为字符串
        return str(value)

    def format_time_complexity(self, time_complexity_data):
        """格式化时间复杂度数据为字符串"""
        if not time_complexity_data:
            return ""
        
        if isinstance(time_complexity_data, str):
            return time_complexity_data
        
        if isinstance(time_complexity_data, dict):
            formatted_parts = []
            for operation, complexity_info in time_complexity_data.items():
                if isinstance(complexity_info, dict):
                    # 嵌套字典格式：operation -> {best_case, average_case, worst_case}
                    cases = []
                    for case, value in complexity_info.items():
                        cases.append(f"{case}: {value}")
                    formatted_parts.append(f"{operation} ({', '.join(cases)})")
                else:
                    # 简单格式：operation -> complexity
                    formatted_parts.append(f"{operation}: {complexity_info}")
            return '; '.join(formatted_parts)
        
        return str(time_complexity_data)

    def format_common_operations(self, operations_data):
        """格式化常见操作数据为字符串"""
        if not operations_data:
            return ""
        
        if isinstance(operations_data, str):
            return operations_data
        
        if isinstance(operations_data, list):
            formatted_operations = []
            for op in operations_data:
                if isinstance(op, dict):
                    op_name = op.get('name', op.get('operation_name', ''))
                    op_desc = op.get('description', '')
                    op_usage = op.get('typical_usage', '')
                    
                    op_str = op_name
                    if op_desc:
                        op_str += f": {op_desc}"
                    if op_usage:
                        op_str += f" (用途: {op_usage})"
                    
                    formatted_operations.append(op_str)
                else:
                    formatted_operations.append(str(op))
            return '; '.join(formatted_operations)
        
        return str(operations_data)

    def update_existing_entity(self, entity_node, entity_data):
        """更新现有实体节点的属性"""
        update_props = {}
        
        # 动态处理所有属性字段
        for key, value in entity_data.items():
            # 跳过已处理的基本字段
            if key in ['name', 'type']:
                continue
            
            # 处理不同类型的属性值
            formatted_value = self.format_attribute_value(key, value)
            if formatted_value:
                update_props[key] = formatted_value
        
        # 更新节点属性
        if update_props:
            for key, value in update_props.items():
                entity_node[key] = value
            self.graph.push(entity_node)
            return True
        
        return False

    def clean_database(self):
        try:
            self.graph.run("MATCH (n) DETACH DELETE n")
            print("🧹 已清空所有节点与关系")
        except Exception as e:
            print(f"❌ 清库失败: {e}")

    def create_nodes_from_export(self, nodes):
        created = 0
        for item in tqdm(nodes, desc="导入节点"):
            name = item.get("name")
            labels = item.get("labels") or ["实体"]
            props = item.get("properties") or {}
            if not name:
                continue
            props["name"] = name
            try:
                node = Node(*labels, **props)
                self.graph.create(node)
                created += 1
            except Exception as e:
                print(f"⚠️ 节点导入失败: {name} - {e}")
        print(f"✅ 导入节点数量: {created}")
        return created

    def create_relationships_from_export(self, relationships):
        created = 0
        for rel in tqdm(relationships, desc="导入关系"):
            source = rel.get("source")
            target = rel.get("target")
            rel_type = rel.get("relation")
            props = rel.get("properties") or {}
            if not source or not target or not rel_type:
                continue
            try:
                a = self.graph.nodes.match(name=source).first()
                b = self.graph.nodes.match(name=target).first()
                if not a or not b:
                    continue
                relationship = Relationship(a, rel_type, b, **props)
                self.graph.create(relationship)
                created += 1
            except Exception as e:
                print(f"⚠️ 关系导入失败: {source}-{rel_type}->{target} - {e}")
        print(f"✅ 导入关系数量: {created}")
        return created

    def import_full_graph(self, full_file_path=None, clean=True):
        if full_file_path is None:
            full_file_path = os.path.join(self.default_data_dir, "full_graph_data.json")
        try:
            with open(full_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ 读取完整图谱数据失败: {e}")
            return
        if clean:
            self.clean_database()
        nodes = data.get("nodes") or []
        relationships = data.get("relationships") or []
        print(f"📁 数据文件: {full_file_path}")
        print(f"📊 待导入节点: {len(nodes)}，关系: {len(relationships)}")
        n = self.create_nodes_from_export(nodes)
        r = self.create_relationships_from_export(relationships)
        print("🎉 重新导入完成")
        print(f"   - 节点: {n}")
        print(f"   - 关系: {r}")

    def import_nodes_file(self, nodes_file_path=None, clean=False):
        if nodes_file_path is None:
            nodes_file_path = os.path.join(self.default_data_dir, "nodes.json")
        try:
            with open(nodes_file_path, "r", encoding="utf-8") as f:
                nodes = json.load(f)
        except Exception as e:
            print(f"❌ 读取节点文件失败: {e}")
            return
        if clean:
            self.clean_database()
        print(f"📁 节点文件: {nodes_file_path}")
        print(f"📊 待导入节点: {len(nodes)}")
        self.create_nodes_from_export(nodes)

    def import_relationships_file(self, rels_file_path=None):
        if rels_file_path is None:
            rels_file_path = os.path.join(self.default_data_dir, "relationships.json")
        try:
            with open(rels_file_path, "r", encoding="utf-8") as f:
                rels = json.load(f)
        except Exception as e:
            print(f"❌ 读取关系文件失败: {e}")
            return
        print(f"📁 关系文件: {rels_file_path}")
        print(f"📊 待导入关系: {len(rels)}")
        self.create_relationships_from_export(rels)

    def import_entity_attributes(self, data_file_path):
        """导入实体属性到Neo4j图数据库"""
        print("🚀 开始导入实体属性...")
        
        # 加载数据
        entities_data = self.load_entity_data(data_file_path)
        if not entities_data:
            print("❌ 没有有效数据，导入失败")
            return
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for entity_data in tqdm(entities_data, desc="导入实体属性"):
            entity_name = entity_data.get('name', '')
            entity_type = entity_data.get('type', 'Entity')
            
            if not entity_name:
                skipped_count += 1
                continue
            
            # 查找现有节点
            existing_node = self.find_entity_node(entity_name, entity_type)
            
            if existing_node:
                # 更新现有节点
                if self.update_existing_entity(existing_node, entity_data):
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                # 创建新节点
                new_node = self.create_entity_with_attributes(entity_data)
                if new_node:
                    created_count += 1
                else:
                    skipped_count += 1
        
        print(f"🎉 实体属性导入完成！")
        print(f"📊 统计信息:")
        print(f"   - 新创建节点: {created_count}")
        print(f"   - 更新现有节点: {updated_count}")
        print(f"   - 跳过的节点: {skipped_count}")
        print(f"   - 总处理数量: {len(entities_data)}")

    def get_entity_stats(self):
        """获取实体统计信息"""
        try:
            # 节点统计
            node_count = self.graph.run("MATCH (n) RETURN count(n) as count").data()[0]['count']
            
            # 带属性的节点统计
            nodes_with_desc = self.graph.run("MATCH (n) WHERE n.description IS NOT NULL RETURN count(n) as count").data()[0]['count']
            nodes_with_props = self.graph.run("MATCH (n) WHERE n.properties IS NOT NULL RETURN count(n) as count").data()[0]['count']
            nodes_with_time_complexity = self.graph.run("MATCH (n) WHERE n.time_complexity IS NOT NULL RETURN count(n) as count").data()[0]['count']
            nodes_with_space_complexity = self.graph.run("MATCH (n) WHERE n.space_complexity IS NOT NULL RETURN count(n) as count").data()[0]['count']
            
            # 节点类型统计
            node_types = self.graph.run("""
                MATCH (n) 
                RETURN labels(n)[0] as type, count(n) as count 
                ORDER BY count DESC
            """).data()
            
            print("📊 实体属性统计信息:")
            print(f"   - 总节点数: {node_count}")
            print(f"   - 带描述的节点: {nodes_with_desc}")
            print(f"   - 带属性的节点: {nodes_with_props}")
            print(f"   - 带时间复杂度的节点: {nodes_with_time_complexity}")
            print(f"   - 带空间复杂度的节点: {nodes_with_space_complexity}")
            print("   - 节点类型分布:")
            for item in node_types:
                print(f"     * {item['type']}: {item['count']}")
                
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='导入实体属性到Neo4j知识图谱')
    parser.add_argument('--data', type=str, default='/root/KG_inde/neo4j/data/data_structure_kg_optimized.json',
                       help='实体属性数据文件路径')
    parser.add_argument('--stats', action='store_true', help='显示实体属性统计信息')
    parser.add_argument('--full', type=str, nargs='?', const='default', help='从full_graph_data.json重新导入节点和关系')
    parser.add_argument('--nodes-file', type=str, help='仅导入节点文件（nodes.json）')
    parser.add_argument('--rels-file', type=str, help='仅导入关系统文件（relationships.json）')
    parser.add_argument('--clean', action='store_true', help='导入前清空数据库')
    
    args = parser.parse_args()
    
    # 创建实体属性导入器
    importer = Neo4jEntityAttributeImporter()
    
    if args.stats:
        # 显示统计信息
        importer.get_entity_stats()
    elif args.full is not None:
        if args.full == 'default':
            importer.import_full_graph(clean=args.clean)
        else:
            importer.import_full_graph(args.full, clean=args.clean)
    elif args.nodes_file:
        importer.import_nodes_file(args.nodes_file, clean=args.clean)
    elif args.rels_file:
        importer.import_relationships_file(args.rels_file)
    else:
        # 导入实体属性
        print(f"🔄 使用数据文件: {args.data}")
        importer.import_entity_attributes(args.data)
