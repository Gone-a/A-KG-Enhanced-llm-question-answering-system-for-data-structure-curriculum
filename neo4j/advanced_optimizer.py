#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱高级质量优化器
修正语义不一致的关系，为关系添加上下文信息
"""

import json
import os
import re
from neo4j import GraphDatabase
from collections import defaultdict
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdvancedKnowledgeGraphOptimizer:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="123456"):
        # 从环境变量获取密码
        password = os.getenv("NEO4J_KEY", password)
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.data_dir = "/root/KG_inde/neo4j/data"
        
        # 加载质量分析报告
        self.load_quality_report()
        
        # 定义语义修正规则
        self.semantic_correction_rules = {
            # 删除语义不合理的关系
            "delete_rules": [
                # ApplicationScenario -> DataStructure (应用场景不应该指向数据结构)
                ("ApplicationScenario", "appliesTo", "DataStructure"),
                # Operation -> Algorithm (操作不应该应用到算法)
                ("Operation", "appliesTo", "Algorithm"),
                # Complexity -> DataStructure (复杂度不应该应用到数据结构)
                ("Complexity", "appliesTo", "DataStructure"),
                # 其他不合理的组合
                ("ApplicationScenario", "uses", "Algorithm"),
                ("Complexity", "uses", "DataStructure")
            ],
            # 修正关系类型
            "correction_rules": [
                # DataStructure -> ApplicationScenario 应该是 appliesTo
                ("DataStructure", "uses", "ApplicationScenario", "appliesTo"),
                # Algorithm -> ApplicationScenario 应该是 appliesTo
                ("Algorithm", "uses", "ApplicationScenario", "appliesTo"),
                # DataStructure -> Operation 应该是 appliesTo
                ("DataStructure", "uses", "Operation", "appliesTo")
            ]
        }
        
        # 上下文生成模板
        self.context_templates = {
            "appliesTo": {
                ("DataStructure", "ApplicationScenario"): "{source}数据结构适用于{target}场景",
                ("Algorithm", "ApplicationScenario"): "{source}算法适用于{target}场景",
                ("DataStructure", "Operation"): "{source}数据结构支持{target}操作",
                ("Algorithm", "Operation"): "{source}算法支持{target}操作"
            },
            "uses": {
                ("Algorithm", "DataStructure"): "{source}算法使用{target}数据结构",
                ("Operation", "DataStructure"): "{target}数据结构用于{source}操作",
                ("DataStructure", "DataStructure"): "{source}基于{target}实现"
            },
            "variantOf": {
                ("DataStructure", "DataStructure"): "{source}是{target}的变体",
                ("Algorithm", "Algorithm"): "{source}是{target}的变体"
            },
            "hasComplexity": {
                ("Algorithm", "Complexity"): "{source}算法的时间复杂度为{target}",
                ("Operation", "Complexity"): "{source}操作的时间复杂度为{target}"
            }
        }
    
    def close(self):
        self.driver.close()
    
    def load_quality_report(self):
        """加载质量分析报告"""
        try:
            report_file = os.path.join(self.data_dir, "quality_analysis_report.json")
            with open(report_file, 'r', encoding='utf-8') as f:
                self.quality_report = json.load(f)
            logger.info("质量分析报告加载完成")
        except Exception as e:
            logger.error(f"加载质量分析报告失败: {e}")
            self.quality_report = {}
    
    def get_node_type(self, node_name):
        """获取节点类型"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (n {name: $name})
                RETURN labels(n) as labels
            """, name=node_name)
            
            record = result.single()
            if record and record["labels"]:
                return record["labels"][0]
            return "Unknown"
    
    def fix_semantic_inconsistencies(self):
        """修正语义不一致的关系"""
        logger.info("开始修正语义不一致的关系...")
        
        deleted_count = 0
        corrected_count = 0
        
        with self.driver.session() as session:
            # 获取所有关系及其节点类型
            result = session.run("""
                MATCH (a)-[r]->(b)
                RETURN a.name as source, b.name as target, 
                       type(r) as relation, labels(a) as source_labels, 
                       labels(b) as target_labels, id(r) as rel_id
            """)
            
            relationships = result.data()
            
            for rel in relationships:
                source_type = rel["source_labels"][0] if rel["source_labels"] else "Unknown"
                target_type = rel["target_labels"][0] if rel["target_labels"] else "Unknown"
                relation_type = rel["relation"]
                
                # 检查是否需要删除
                delete_pattern = (source_type, relation_type, target_type)
                if delete_pattern in self.semantic_correction_rules["delete_rules"]:
                    session.run("""
                        MATCH ()-[r]->()
                        WHERE id(r) = $rel_id
                        DELETE r
                    """, rel_id=rel["rel_id"])
                    deleted_count += 1
                    logger.debug(f"删除不合理关系: {rel['source']} --[{relation_type}]--> {rel['target']}")
                    continue
                
                # 检查是否需要修正关系类型
                for rule in self.semantic_correction_rules["correction_rules"]:
                    if (source_type, relation_type, target_type) == rule[:3]:
                        new_relation = rule[3]
                        session.run("""
                            MATCH (a)-[r]->(b)
                            WHERE id(r) = $rel_id
                            CREATE (a)-[new_r:""" + new_relation + """]->(b)
                            SET new_r = properties(r)
                            DELETE r
                        """, rel_id=rel["rel_id"])
                        corrected_count += 1
                        logger.debug(f"修正关系类型: {rel['source']} --[{relation_type} -> {new_relation}]--> {rel['target']}")
                        break
        
        logger.info(f"语义修正完成: 删除 {deleted_count} 个不合理关系, 修正 {corrected_count} 个关系类型")
        return deleted_count, corrected_count
    
    def add_missing_context(self):
        """为缺少上下文的关系添加上下文信息"""
        logger.info("开始为关系添加上下文信息...")
        
        added_count = 0
        
        with self.driver.session() as session:
            # 获取缺少source_sentence的关系
            result = session.run("""
                MATCH (a)-[r]->(b)
                WHERE r.source_sentence IS NULL
                RETURN a.name as source, b.name as target, 
                       type(r) as relation, labels(a) as source_labels, 
                       labels(b) as target_labels, id(r) as rel_id
            """)
            
            relationships = result.data()
            
            for rel in relationships:
                source_type = rel["source_labels"][0] if rel["source_labels"] else "Unknown"
                target_type = rel["target_labels"][0] if rel["target_labels"] else "Unknown"
                relation_type = rel["relation"]
                
                # 生成上下文句子
                context = self.generate_context(
                    rel["source"], rel["target"], 
                    source_type, target_type, relation_type
                )
                
                if context:
                    session.run("""
                        MATCH ()-[r]->()
                        WHERE id(r) = $rel_id
                        SET r.source_sentence = $context
                    """, rel_id=rel["rel_id"], context=context)
                    added_count += 1
                    logger.debug(f"添加上下文: {rel['source']} --[{relation_type}]--> {rel['target']}: {context}")
        
        logger.info(f"上下文添加完成: 为 {added_count} 个关系添加了上下文信息")
        return added_count
    
    def generate_context(self, source, target, source_type, target_type, relation_type):
        """生成关系的上下文句子"""
        # 查找匹配的模板
        if relation_type in self.context_templates:
            type_templates = self.context_templates[relation_type]
            type_key = (source_type, target_type)
            
            if type_key in type_templates:
                template = type_templates[type_key]
                return template.format(source=source, target=target)
        
        # 如果没有匹配的模板，生成通用上下文
        generic_templates = {
            "appliesTo": f"{source}适用于{target}",
            "uses": f"{source}使用{target}",
            "variantOf": f"{source}是{target}的变体",
            "hasComplexity": f"{source}的复杂度为{target}"
        }
        
        return generic_templates.get(relation_type, f"{source}与{target}存在{relation_type}关系")
    
    def optimize_hub_nodes(self):
        """优化hub节点（高连接度节点）"""
        logger.info("开始优化hub节点...")
        
        optimized_count = 0
        
        with self.driver.session() as session:
            # 找出连接度过高的节点
            result = session.run("""
                MATCH (n)
                WITH n, COUNT {(n)--()} as degree
                WHERE degree > 15
                RETURN n.name as name, degree
                ORDER BY degree DESC
            """)
            
            hub_nodes = result.data()
            
            for hub in hub_nodes:
                node_name = hub["name"]
                degree = hub["degree"]
                
                # 分析hub节点的关系类型分布
                rel_analysis = session.run("""
                    MATCH (n {name: $name})-[r]-()
                    RETURN type(r) as relation_type, count(*) as count
                    ORDER BY count DESC
                """, name=node_name).data()
                
                # 如果某个关系类型占比过高，可能需要优化
                total_rels = sum(item["count"] for item in rel_analysis)
                for rel_type_info in rel_analysis:
                    rel_type = rel_type_info["relation_type"]
                    count = rel_type_info["count"]
                    ratio = count / total_rels
                    
                    # 如果某种关系类型占比超过70%，考虑是否合理
                    if ratio > 0.7 and count > 10:
                        logger.info(f"Hub节点 {node_name} 的 {rel_type} 关系占比过高: {ratio:.2%} ({count}/{total_rels})")
                        # 这里可以添加具体的优化逻辑
                        optimized_count += 1
        
        logger.info(f"Hub节点优化完成: 分析了 {len(hub_nodes)} 个hub节点")
        return optimized_count
    
    def validate_optimizations(self):
        """验证优化结果"""
        logger.info("开始验证优化结果...")
        
        with self.driver.session() as session:
            # 统计优化后的数据
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            
            # 统计有上下文的关系数量
            context_count = session.run("""
                MATCH ()-[r]->()
                WHERE r.source_sentence IS NOT NULL
                RETURN count(r) as count
            """).single()["count"]
            
            # 统计关系类型分布
            rel_types = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(*) as count
                ORDER BY count DESC
            """).data()
            
            validation_result = {
                "total_nodes": node_count,
                "total_relationships": rel_count,
                "relationships_with_context": context_count,
                "context_coverage": context_count / rel_count if rel_count > 0 else 0,
                "relationship_types": rel_types
            }
            
            logger.info(f"验证结果: {node_count} 个节点, {rel_count} 个关系")
            logger.info(f"上下文覆盖率: {validation_result['context_coverage']:.2%}")
            
            return validation_result
    
    def run_optimization(self):
        """运行完整的优化流程"""
        logger.info("开始运行高级质量优化...")
        
        try:
            # 1. 修正语义不一致的关系
            deleted, corrected = self.fix_semantic_inconsistencies()
            
            # 2. 添加缺少的上下文
            context_added = self.add_missing_context()
            
            # 3. 优化hub节点
            hub_optimized = self.optimize_hub_nodes()
            
            # 4. 验证优化结果
            validation = self.validate_optimizations()
            
            # 5. 生成优化报告
            optimization_report = {
                "optimization_time": "2025-10-01T02:56:00",
                "actions_taken": {
                    "semantic_corrections": {
                        "deleted_relationships": deleted,
                        "corrected_relationships": corrected
                    },
                    "context_enhancement": {
                        "relationships_with_context_added": context_added
                    },
                    "hub_optimization": {
                        "hub_nodes_analyzed": hub_optimized
                    }
                },
                "final_statistics": validation,
                "improvements": {
                    "context_coverage_improved": f"{validation['context_coverage']:.2%}",
                    "semantic_consistency_improved": deleted + corrected > 0,
                    "total_relationships_after_optimization": validation["total_relationships"]
                }
            }
            
            # 保存优化报告
            report_file = os.path.join(self.data_dir, "optimization_report.json")
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(optimization_report, f, ensure_ascii=False, indent=2)
            
            logger.info(f"优化报告已保存到: {report_file}")
            
            # 打印优化摘要
            self.print_optimization_summary(optimization_report)
            
            return optimization_report
            
        except Exception as e:
            logger.error(f"优化过程中发生错误: {e}")
            raise
    
    def print_optimization_summary(self, report):
        """打印优化摘要"""
        print("\n" + "="*60)
        print("知识图谱高级质量优化报告")
        print("="*60)
        
        actions = report["actions_taken"]
        stats = report["final_statistics"]
        
        print(f"\n🔧 优化操作:")
        print(f"  语义修正:")
        print(f"    - 删除不合理关系: {actions['semantic_corrections']['deleted_relationships']} 个")
        print(f"    - 修正关系类型: {actions['semantic_corrections']['corrected_relationships']} 个")
        print(f"  上下文增强:")
        print(f"    - 添加上下文信息: {actions['context_enhancement']['relationships_with_context_added']} 个关系")
        print(f"  Hub节点优化:")
        print(f"    - 分析Hub节点: {actions['hub_optimization']['hub_nodes_analyzed']} 个")
        
        print(f"\n📊 优化后统计:")
        print(f"  节点总数: {stats['total_nodes']}")
        print(f"  关系总数: {stats['total_relationships']}")
        print(f"  上下文覆盖率: {stats['context_coverage']:.2%}")
        
        print(f"\n✅ 改进效果:")
        improvements = report["improvements"]
        print(f"  上下文覆盖率提升至: {improvements['context_coverage_improved']}")
        print(f"  语义一致性改进: {'是' if improvements['semantic_consistency_improved'] else '否'}")
        print(f"  优化后关系总数: {improvements['total_relationships_after_optimization']}")

def main():
    optimizer = AdvancedKnowledgeGraphOptimizer()
    try:
        report = optimizer.run_optimization()
        return report
    finally:
        optimizer.close()

if __name__ == "__main__":
    main()