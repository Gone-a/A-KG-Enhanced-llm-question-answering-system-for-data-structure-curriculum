#!/usr/bin/env python3
"""
将Neo4j知识图谱数据转换为Vue前端需要的格式
"""
import json
import os

def convert_neo4j_to_vue_format(neo4j_file_path, vue_file_path):
    """
    将Neo4j格式的数据转换为Vue格式
    
    Args:
        neo4j_file_path: Neo4j数据文件路径
        vue_file_path: Vue格式输出文件路径
    """
    try:
        # 读取Neo4j格式数据
        with open(neo4j_file_path, 'r', encoding='utf-8') as f:
            neo4j_data = json.load(f)
        
        # 转换nodes格式
        vue_nodes = []
        for node in neo4j_data.get('nodes', []):
            vue_node = {
                "id": node['name'],
                "name": node['name']
            }
            vue_nodes.append(vue_node)
        
        # 转换relationships为links格式
        vue_links = []
        for rel in neo4j_data.get('relationships', []):
            vue_link = {
                "source": rel['source'],
                "target": rel['target'],
                "relation": rel['relation']
            }
            vue_links.append(vue_link)
        
        # 构建Vue格式数据
        vue_data = {
            "nodes": vue_nodes,
            "links": vue_links
        }
        
        # 写入Vue格式文件
        with open(vue_file_path, 'w', encoding='utf-8') as f:
            json.dump(vue_data, f, ensure_ascii=False, indent=2)
        
        print(f"转换完成！")
        print(f"节点数量: {len(vue_nodes)}")
        print(f"关系数量: {len(vue_links)}")
        print(f"输出文件: {vue_file_path}")
        
    except FileNotFoundError as e:
        print(f"文件未找到: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
    except Exception as e:
        print(f"转换过程中发生错误: {e}")

def main():
    """主函数"""
    # 定义文件路径
    neo4j_file = "/root/KG_inde/neo4j/data/full_graph_data.json"
    vue_file = "/root/KG_inde/Vue/src/data/graph.json"
    
    # 检查源文件是否存在
    if not os.path.exists(neo4j_file):
        print(f"源文件不存在: {neo4j_file}")
        return
    
    # 确保目标目录存在
    os.makedirs(os.path.dirname(vue_file), exist_ok=True)
    
    # 执行转换
    convert_neo4j_to_vue_format(neo4j_file, vue_file)

if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
导出优化后的知识图谱数据到data目录
"""

import json
import os
from neo4j import GraphDatabase
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GraphDataExporter:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="123456"):
        # 从环境变量获取密码，如果没有则使用默认值
        password = os.getenv("NEO4J_KEY", password)
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.data_dir = "/root/KG_inde/neo4j/data"
        
        # 确保data目录存在
        os.makedirs(self.data_dir, exist_ok=True)
    
    def close(self):
        self.driver.close()
    
    def export_nodes(self):
        """导出所有节点数据"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (n)
                RETURN n.name as name, labels(n) as labels, properties(n) as properties
                ORDER BY n.name
            """)
            
            nodes = []
            for record in result:
                node_data = {
                    "name": record["name"],
                    "labels": record["labels"],
                    "properties": dict(record["properties"])
                }
                nodes.append(node_data)
            
            logger.info(f"导出了 {len(nodes)} 个节点")
            return nodes
    
    def export_relationships(self):
        """导出所有关系数据"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a)-[r]->(b)
                RETURN a.name as source, b.name as target, 
                       type(r) as relation, properties(r) as properties
                ORDER BY a.name, b.name
            """)
            
            relationships = []
            for record in result:
                rel_data = {
                    "source": record["source"],
                    "target": record["target"],
                    "relation": record["relation"],
                    "properties": dict(record["properties"])
                }
                relationships.append(rel_data)
            
            logger.info(f"导出了 {len(relationships)} 个关系")
            return relationships
    
    def export_statistics(self):
        """导出图谱统计信息"""
        with self.driver.session() as session:
            # 节点统计
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            
            # 关系统计
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            
            # 节点类型统计
            node_types = session.run("""
                MATCH (n)
                RETURN labels(n) as labels, count(*) as count
                ORDER BY count DESC
            """).data()
            
            # 关系类型统计
            rel_types = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(*) as count
                ORDER BY count DESC
            """).data()
            
            # 权重分布统计
            weight_stats = session.run("""
                MATCH ()-[r]->()
                WHERE r.weight IS NOT NULL
                RETURN r.weight as weight, count(*) as count
                ORDER BY r.weight DESC
            """).data()
            
            stats = {
                "export_time": datetime.now().isoformat(),
                "total_nodes": node_count,
                "total_relationships": rel_count,
                "node_types": node_types,
                "relationship_types": rel_types,
                "weight_distribution": weight_stats
            }
            
            logger.info(f"统计信息: {node_count} 个节点, {rel_count} 个关系")
            return stats
    
    def save_to_files(self):
        """保存所有数据到文件"""
        try:
            # 导出节点
            nodes = self.export_nodes()
            nodes_file = os.path.join(self.data_dir, "nodes.json")
            with open(nodes_file, 'w', encoding='utf-8') as f:
                json.dump(nodes, f, ensure_ascii=False, indent=2)
            logger.info(f"节点数据已保存到: {nodes_file}")
            
            # 导出关系
            relationships = self.export_relationships()
            rels_file = os.path.join(self.data_dir, "relationships.json")
            with open(rels_file, 'w', encoding='utf-8') as f:
                json.dump(relationships, f, ensure_ascii=False, indent=2)
            logger.info(f"关系数据已保存到: {rels_file}")
            
            # 导出统计信息
            stats = self.export_statistics()
            stats_file = os.path.join(self.data_dir, "statistics.json")
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            logger.info(f"统计信息已保存到: {stats_file}")
            
            # 创建完整的图谱数据文件（用于备份）
            full_graph = {
                "metadata": {
                    "export_time": datetime.now().isoformat(),
                    "total_nodes": len(nodes),
                    "total_relationships": len(relationships)
                },
                "nodes": nodes,
                "relationships": relationships,
                "statistics": stats
            }
            
            full_file = os.path.join(self.data_dir, "full_graph_data.json")
            with open(full_file, 'w', encoding='utf-8') as f:
                json.dump(full_graph, f, ensure_ascii=False, indent=2)
            logger.info(f"完整图谱数据已保存到: {full_file}")
            
            return {
                "nodes_file": nodes_file,
                "relationships_file": rels_file,
                "statistics_file": stats_file,
                "full_graph_file": full_file,
                "node_count": len(nodes),
                "relationship_count": len(relationships)
            }
            
        except Exception as e:
            logger.error(f"导出数据时发生错误: {e}")
            raise

def main():
    exporter = GraphDataExporter()
    try:
        logger.info("开始导出知识图谱数据...")
        result = exporter.save_to_files()
        
        print("\n=== 数据导出完成 ===")
        print(f"节点数量: {result['node_count']}")
        print(f"关系数量: {result['relationship_count']}")
        print(f"数据保存位置: /root/KG_inde/neo4j/data/")
        print("\n导出的文件:")
        for key, path in result.items():
            if key.endswith('_file'):
                print(f"  - {os.path.basename(path)}")
        
    except Exception as e:
        logger.error(f"导出失败: {e}")
    finally:
        exporter.close()

if __name__ == "__main__":
    main()