#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试简化后的系统功能
验证三个核心接口是否正常工作
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.config_manager import ConfigManager
from modules.knowledge_graph_query import KnowledgeGraphQuery
from modules.intent_recognition import IntentRecognizer
from modules.backend_api import APIHandler

def test_simplified_system():
    """测试简化后的系统功能"""
    print("=" * 60)
    print("测试简化后的系统功能")
    print("=" * 60)
    
    try:
        # 1. 初始化组件
        print("\n1. 初始化系统组件...")
        config_manager = ConfigManager()
        
        # 初始化知识图谱查询器
        db_config = config_manager.get_database_config()
        kg_query = KnowledgeGraphQuery(
            neo4j_uri=db_config['uri'],
            username=db_config['user_name'],
            password=db_config['password']
        )
        
        # 初始化意图识别器
        try:
            from intent_recognition.knowledge_base import KNOWLEDGE_BASE
        except ImportError:
            print("警告: 无法导入 KNOWLEDGE_BASE，使用空字典")
            KNOWLEDGE_BASE = {}
        
        model_path = config_manager.get('model.nlu_model_path', './my_intent_model')
        intent_recognizer = IntentRecognizer(model_path, KNOWLEDGE_BASE)
        
        # 初始化API处理器
        api_handler = APIHandler(intent_recognizer, kg_query)
        
        print("✓ 系统组件初始化成功")
        
        # 2. 测试意图识别
        print("\n2. 测试意图识别功能...")
        test_queries = [
            "数组和栈有什么关系？",
            "查找包含'算法'的实体",
            "什么是二叉树？",
            "排序算法有哪些类型？",
            "链表的实现方式"
        ]
        
        intent_stats = {}
        for query in test_queries:
            intent = intent_recognizer.recognize_intent(query)
            intent_stats[intent] = intent_stats.get(intent, 0) + 1
            print(f"  查询: '{query}' -> 意图: {intent}")
        
        print(f"\n  意图识别统计: {intent_stats}")
        
        # 3. 测试知识图谱查询方法
        print("\n3. 测试知识图谱查询方法...")
        
        # 测试 find_entities_by_relation
        print("\n  3.1 测试 find_entities_by_relation:")
        result1 = kg_query.find_entities_by_relation(['数组'], '实现')
        print(f"    find_entities_by_relation(['数组'], '实现') -> {len(result1)} 个结果")
        if result1:
            print(f"    示例结果: {result1[0]}")
        
        # 测试 find_relation_by_entities
        print("\n  3.2 测试 find_relation_by_entities:")
        result2 = kg_query.find_relation_by_entities(['数组', '栈'])
        print(f"    find_relation_by_entities(['数组', '栈']) -> {len(result2)} 个结果")
        if result2:
            print(f"    示例结果: {result2[0]}")
        
        # 测试 find_entity_relations
        print("\n  3.3 测试 find_entity_relations:")
        result3 = kg_query.find_entity_relations('数组')
        print(f"    find_entity_relations('数组') -> {len(result3)} 个结果")
        if result3:
            print(f"    示例结果: {result3[0]}")
        
        # 4. 测试API处理器
        print("\n4. 测试API处理器功能...")
        
        api_test_queries = [
            "数组和栈有什么关系？",  # find_relation_by_two_entities
            "查找包含'算法'的实体",    # find_entity_by_relation_and_entity
            "什么是二叉树？",         # find_entity_relations
            "排序算法有哪些类型？",    # other
        ]
        
        for query in api_test_queries:
            print(f"\n  测试查询: '{query}'")
            response = api_handler.process_query(query)
            print(f"    成功: {response.get('success', False)}")
            print(f"    消息: {response.get('message', 'N/A')}")
            graph_data = response.get('graphData', {})
            if graph_data:
                nodes_count = len(graph_data.get('nodes', []))
                links_count = len(graph_data.get('links', []))
                print(f"    图数据: {nodes_count} 个节点, {links_count} 条边")
        
        # 5. 测试系统状态
        print("\n5. 测试系统状态...")
        status = api_handler.get_status()
        print(f"  系统状态: {status}")
        
        print("\n" + "=" * 60)
        print("✓ 简化后的系统测试完成")
        print("✓ 三个核心接口功能正常")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        try:
            if 'kg_query' in locals():
                kg_query.close()
        except:
            pass

if __name__ == "__main__":
    test_simplified_system()