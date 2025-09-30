#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j图数据导出脚本
将Neo4j中的知识图谱数据导出为graph.json格式
"""

from py2neo import Graph
import json
import os
from collections import defaultdict

class Neo4jGraphExporter:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="123456"):
        """初始化Neo4j连接"""
        try:
            password = os.getenv("NEO4J_KEY", password)
            self.graph = Graph(uri, auth=(user, password))
            # 测试连接
            self.graph.run("RETURN 1")
            print("✅ Neo4j图数据库连接成功")
        except Exception as e:
            print(f"❌ Neo4j连接失败: {e}")
            raise e
    
    def export_graph_data(self):
        """导出图数据为graph.json格式"""
        print("🔄 开始导出图数据...")
        
        # 查询所有节点
        nodes_query = """
        MATCH (n)
        RETURN DISTINCT n.name as name
        ORDER BY n.name
        """
        
        # 查询所有关系
        relationships_query = """
        MATCH (a)-[r]->(b)
        RETURN a.name as source, b.name as target, type(r) as relation
        ORDER BY a.name, b.name
        """
        
        try:
            # 获取节点数据
            nodes_result = self.graph.run(nodes_query).data()
            print(f"📊 找到 {len(nodes_result)} 个节点")
            
            # 获取关系数据
            relationships_result = self.graph.run(relationships_query).data()
            print(f"📊 找到 {len(relationships_result)} 个关系")
            
            # 构建nodes数组（去重）
            nodes_set = set()
            nodes = []
            
            for node in nodes_result:
                name = node['name']
                if name and name not in nodes_set:
                    nodes_set.add(name)
                    nodes.append({
                        "id": name,
                        "name": name
                    })
            
            # 构建links数组（去重）
            links_set = set()
            links = []
            
            for rel in relationships_result:
                source = rel['source']
                target = rel['target']
                relation = rel['relation']
                
                if source and target and relation:
                    # 创建唯一标识符用于去重
                    link_id = f"{source}|{target}|{relation}"
                    if link_id not in links_set:
                        links_set.add(link_id)
                        links.append({
                            "source": source,
                            "target": target,
                            "relation": relation
                        })
            
            # 构建最终的图数据结构
            graph_data = {
                "nodes": nodes,
                "links": links
            }
            
            print(f"✅ 导出完成:")
            print(f"   - 节点数量: {len(nodes)}")
            print(f"   - 关系数量: {len(links)}")
            
            return graph_data
            
        except Exception as e:
            print(f"❌ 导出数据时出错: {e}")
            raise e
    
    def save_to_file(self, graph_data, output_path):
        """保存图数据到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存为JSON文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 图数据已保存到: {output_path}")
            
        except Exception as e:
            print(f"❌ 保存文件时出错: {e}")
            raise e

def main():
    """主函数"""
    try:
        # 创建导出器
        exporter = Neo4jGraphExporter()
        
        # 导出图数据
        graph_data = exporter.export_graph_data()
        
        # 保存到目标文件
        output_path = "/root/KG_inde/Vue/src/data/graph.json"
        exporter.save_to_file(graph_data, output_path)
        
        print("🎉 图数据导出完成！")
        
    except Exception as e:
        print(f"❌ 导出失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())