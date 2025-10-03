#!/usr/bin/env python3
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