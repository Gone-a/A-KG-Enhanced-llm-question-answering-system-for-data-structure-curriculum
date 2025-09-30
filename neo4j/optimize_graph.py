#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱优化脚本
解决关系过于繁杂的问题，提升图谱质量
"""

from py2neo import Graph
import json
import os
from collections import defaultdict, Counter

class GraphOptimizer:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="123456"):
        """初始化Neo4j连接"""
        try:
            password = os.getenv("NEO4J_KEY", password)
            self.graph = Graph(uri, auth=(user, password))
            self.graph.run("RETURN 1")
            print("✅ Neo4j图数据库连接成功")
        except Exception as e:
            print(f"❌ Neo4j连接失败: {e}")
            raise e
    
    def analyze_graph_complexity(self):
        """分析图的复杂性"""
        print("🔍 分析图谱复杂性...")
        
        # 统计基本信息
        node_count = self.graph.run("MATCH (n) RETURN count(n) as count").data()[0]['count']
        rel_count = self.graph.run("MATCH ()-[r]->() RETURN count(r) as count").data()[0]['count']
        
        # 统计关系类型
        rel_types = self.graph.run("""
            MATCH ()-[r]->()
            RETURN type(r) as relation_type, count(r) as count
            ORDER BY count DESC
        """).data()
        
        # 统计双向关系
        bidirectional_query = """
            MATCH (a)-[r1]->(b), (b)-[r2]->(a)
            WHERE type(r1) = type(r2)
            RETURN type(r1) as relation_type, count(DISTINCT a) as bidirectional_pairs
        """
        bidirectional = self.graph.run(bidirectional_query).data()
        
        print(f"📊 图谱统计:")
        print(f"   - 节点数量: {node_count}")
        print(f"   - 关系数量: {rel_count}")
        print(f"   - 平均每个节点的关系数: {rel_count/node_count:.1f}")
        
        print(f"\n📊 关系类型分布:")
        for rel_type in rel_types:
            print(f"   - {rel_type['relation_type']}: {rel_type['count']} 个")
        
        print(f"\n🔄 双向关系统计:")
        total_bidirectional = 0
        for bid in bidirectional:
            pairs = bid['bidirectional_pairs']
            total_bidirectional += pairs * 2  # 每对双向关系包含2个关系
            print(f"   - {bid['relation_type']}: {pairs} 对双向关系")
        
        print(f"\n⚠️ 问题识别:")
        print(f"   - 双向关系占比: {total_bidirectional/rel_count*100:.1f}%")
        if total_bidirectional/rel_count > 0.3:
            print("   - 建议: 双向关系过多，需要优化")
        
        return {
            'node_count': node_count,
            'rel_count': rel_count,
            'rel_types': rel_types,
            'bidirectional_count': total_bidirectional
        }
    
    def remove_bidirectional_duplicates(self):
        """移除双向重复关系，只保留一个方向"""
        print("🧹 移除双向重复关系...")
        
        # 查找所有双向关系对
        bidirectional_query = """
            MATCH (a)-[r1]->(b), (b)-[r2]->(a)
            WHERE type(r1) = type(r2) AND id(a) < id(b)
            RETURN a.name as node_a, b.name as node_b, type(r1) as relation_type, 
                   id(r1) as r1_id, id(r2) as r2_id
        """
        
        bidirectional_pairs = self.graph.run(bidirectional_query).data()
        
        removed_count = 0
        for pair in bidirectional_pairs:
            # 删除其中一个关系（保留id较小的）
            delete_query = f"MATCH ()-[r]->() WHERE id(r) = {pair['r2_id']} DELETE r"
            self.graph.run(delete_query)
            removed_count += 1
        
        print(f"✅ 移除了 {removed_count} 个重复的双向关系")
        return removed_count
    
    def filter_low_quality_relations(self):
        """过滤低质量关系"""
        print("🔍 识别并移除低质量关系...")
        
        # 定义一些不合理的关系模式
        problematic_patterns = [
            # 应用场景不应该直接appliesTo数据结构（通常是算法appliesTo应用场景）
            ("ApplicationScenario", "appliesTo", "DataStructure"),
            ("ApplicationScenario", "appliesTo", "Algorithm"),
        ]
        
        removed_count = 0
        for head_type, relation, tail_type in problematic_patterns:
            query = f"""
                MATCH (a)-[r:{relation}]->(b)
                WHERE a.type = '{head_type}' AND b.type = '{tail_type}'
                DELETE r
                RETURN count(r) as deleted_count
            """
            try:
                result = self.graph.run(query).data()
                if result:
                    count = result[0].get('deleted_count', 0)
                    removed_count += count
                    print(f"   - 移除 {head_type} --[{relation}]--> {tail_type}: {count} 个")
            except:
                # 如果节点没有type属性，跳过
                pass
        
        print(f"✅ 移除了 {removed_count} 个低质量关系")
        return removed_count
    
    def merge_similar_relations(self):
        """合并相似的关系类型"""
        print("🔄 合并相似关系类型...")
        
        # 定义关系类型合并映射
        relation_mapping = {
            'usedIn': 'uses',  # usedIn 合并到 uses
            'implementedAs': 'uses',  # implementedAs 合并到 uses
            'provides': 'appliesTo',  # provides 合并到 appliesTo
        }
        
        merged_count = 0
        for old_rel, new_rel in relation_mapping.items():
            query = f"""
                MATCH (a)-[r:{old_rel}]->(b)
                CREATE (a)-[new_r:{new_rel}]->(b)
                DELETE r
                RETURN count(r) as merged_count
            """
            try:
                result = self.graph.run(query).data()
                if result:
                    count = result[0].get('merged_count', 0)
                    merged_count += count
                    print(f"   - {old_rel} -> {new_rel}: {count} 个关系")
            except Exception as e:
                print(f"   - 合并 {old_rel} 时出错: {e}")
        
        print(f"✅ 合并了 {merged_count} 个关系")
        return merged_count
    
    def add_relation_weights(self):
        """为关系添加权重属性"""
        print("⚖️ 为关系添加权重...")
        
        # 基于关系类型设置权重
        relation_weights = {
            'appliesTo': 0.9,      # 应用关系权重高
            'uses': 0.8,           # 使用关系权重较高
            'variantOf': 0.7,      # 变体关系权重中等
            'hasComplexity': 0.6,  # 复杂度关系权重较低
        }
        
        updated_count = 0
        for rel_type, weight in relation_weights.items():
            query = f"""
                MATCH ()-[r:{rel_type}]->()
                SET r.weight = {weight}
                RETURN count(r) as updated_count
            """
            try:
                result = self.graph.run(query).data()
                if result:
                    count = result[0].get('updated_count', 0)
                    updated_count += count
                    print(f"   - {rel_type}: {count} 个关系设置权重 {weight}")
            except Exception as e:
                print(f"   - 设置 {rel_type} 权重时出错: {e}")
        
        print(f"✅ 为 {updated_count} 个关系添加了权重")
        return updated_count
    
    def optimize_graph(self):
        """执行完整的图优化流程"""
        print("🚀 开始优化知识图谱...")
        
        # 1. 分析当前状态
        initial_stats = self.analyze_graph_complexity()
        
        # 2. 移除双向重复关系
        removed_bidirectional = self.remove_bidirectional_duplicates()
        
        # 3. 过滤低质量关系
        removed_low_quality = self.filter_low_quality_relations()
        
        # 4. 合并相似关系类型
        merged_relations = self.merge_similar_relations()
        
        # 5. 添加关系权重
        weighted_relations = self.add_relation_weights()
        
        # 6. 分析优化后状态
        print("\n📊 优化后统计:")
        final_stats = self.analyze_graph_complexity()
        
        # 7. 总结优化效果
        print(f"\n🎉 优化完成!")
        print(f"📈 优化效果:")
        print(f"   - 关系数量: {initial_stats['rel_count']} -> {final_stats['rel_count']}")
        print(f"   - 减少关系: {initial_stats['rel_count'] - final_stats['rel_count']} 个")
        print(f"   - 优化比例: {(initial_stats['rel_count'] - final_stats['rel_count'])/initial_stats['rel_count']*100:.1f}%")
        
        return final_stats
    
    def export_optimized_graph(self, output_path="/root/KG_inde/Vue/src/data/graph.json"):
        """导出优化后的图数据"""
        print("📤 导出优化后的图数据...")
        
        # 查询所有节点
        nodes_query = "MATCH (n) RETURN DISTINCT n.name as name ORDER BY n.name"
        
        # 查询所有关系（包含权重）
        relationships_query = """
            MATCH (a)-[r]->(b)
            RETURN a.name as source, b.name as target, type(r) as relation,
                   COALESCE(r.weight, 0.5) as weight
            ORDER BY weight DESC, a.name, b.name
        """
        
        try:
            # 获取数据
            nodes_result = self.graph.run(nodes_query).data()
            relationships_result = self.graph.run(relationships_query).data()
            
            # 构建nodes数组
            nodes = []
            for node in nodes_result:
                if node['name']:
                    nodes.append({
                        "id": node['name'],
                        "name": node['name']
                    })
            
            # 构建links数组
            links = []
            for rel in relationships_result:
                if rel['source'] and rel['target'] and rel['relation']:
                    link = {
                        "source": rel['source'],
                        "target": rel['target'],
                        "relation": rel['relation']
                    }
                    # 如果有权重，添加权重信息
                    if rel['weight'] > 0:
                        link['weight'] = rel['weight']
                    links.append(link)
            
            # 构建图数据
            graph_data = {
                "nodes": nodes,
                "links": links
            }
            
            # 保存文件
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 优化后的图数据已保存到: {output_path}")
            print(f"   - 节点数量: {len(nodes)}")
            print(f"   - 关系数量: {len(links)}")
            
        except Exception as e:
            print(f"❌ 导出数据时出错: {e}")
            raise e

def main():
    """主函数"""
    try:
        optimizer = GraphOptimizer()
        
        # 执行优化
        optimizer.optimize_graph()
        
        # 导出优化后的数据
        optimizer.export_optimized_graph()
        
        print("🎉 图谱优化完成！")
        
    except Exception as e:
        print(f"❌ 优化失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())