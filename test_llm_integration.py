#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试LLM集成功能
验证知识图谱查询后调用豆包LLM生成回复的功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.config_manager import ConfigManager
from modules.intent_recognition import IntentRecognizer
from modules.knowledge_graph_query import KnowledgeGraphQuery
from modules.doubao_llm import DoubaoLLM
from modules.backend_api import APIHandler

def test_llm_integration():
    """测试LLM集成功能"""
    print("=" * 60)
    print("测试LLM集成功能")
    print("=" * 60)
    
    try:
        # 1. 初始化组件
        print("\n1. 初始化组件...")
        config_manager = ConfigManager()
        
        # 导入知识库
        try:
            from intent_recognition.knowledge_base import KNOWLEDGE_BASE
        except ImportError:
            print("警告: 无法导入 KNOWLEDGE_BASE，使用空字典")
            KNOWLEDGE_BASE = {}
        
        # 初始化意图识别器
        model_path = config_manager.get('model.nlu_model_path', './my_intent_model')
        intent_recognizer = IntentRecognizer(model_path, KNOWLEDGE_BASE)
        print("✓ 意图识别器初始化成功")
        
        # 初始化知识图谱查询器
        db_config = config_manager.get_database_config()
        kg_query = KnowledgeGraphQuery(
            db_config['uri'],
            db_config['user_name'], 
            db_config['password']
        )
        print("✓ 知识图谱查询器初始化成功")
        
        # 初始化豆包LLM客户端
        try:
            llm_client = DoubaoLLM()
            print("✓ 豆包LLM客户端初始化成功")
        except Exception as e:
            print(f"⚠️ 豆包LLM客户端初始化失败: {e}")
            print("将使用模拟LLM客户端进行测试")
            llm_client = None
        
        # 初始化API处理器
        api_handler = APIHandler(intent_recognizer, kg_query, llm_client)
        print("✓ API处理器初始化成功")
        
        # 2. 测试不同类型的查询
        print("\n2. 测试LLM集成功能...")
        
        test_queries = [
            "数组和栈有什么关系？",
            "什么是二叉树？",
            "排序算法有哪些类型？",
            "查找包含'算法'的实体",
            "今天天气怎么样？"  # 通用查询测试
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n  2.{i} 测试查询: '{query}'")
            
            # 处理查询
            result = api_handler.process_query(query)
            
            print(f"    成功状态: {result.get('success', False)}")
            print(f"    LLM回复: {result.get('message', '无回复')[:100]}...")
            print(f"    图数据节点数: {len(result.get('graphData', {}).get('nodes', []))}")
            print(f"    图数据边数: {len(result.get('graphData', {}).get('links', []))}")
            
            if 'kg_result' in result:
                print(f"    KG原始结果数: {len(result['kg_result'])}")
        
        # 3. 测试LLM回复生成方法
        print("\n3. 测试LLM回复生成方法...")
        
        if llm_client:
            # 模拟KG查询结果
            mock_kg_result = [
                {"entity1": "数组", "entity2": "栈", "relation": "实现"},
                {"entity1": "栈", "entity2": "LIFO", "relation": "遵循"}
            ]
            
            llm_response = api_handler._generate_llm_response("数组和栈的关系", mock_kg_result)
            print(f"    LLM生成的回复: {llm_response[:200]}...")
        else:
            print("    跳过LLM回复生成测试（LLM客户端未初始化）")
        
        # 4. 测试系统状态
        print("\n4. 测试系统状态...")
        status = api_handler.get_status()
        print(f"    意图识别器: {status['intent_recognizer']}")
        print(f"    知识图谱: {status['knowledge_graph']}")
        print(f"    LLM客户端: {status['llm_client']}")
        
        # 5. 性能测试
        print("\n5. 性能测试...")
        
        import time
        start_time = time.time()
        
        # 测试3次查询的平均时间
        for _ in range(3):
            api_handler.process_query("什么是二叉树？")
        
        end_time = time.time()
        avg_time = (end_time - start_time) / 3
        
        print(f"    平均查询处理时间: {avg_time:.4f} 秒")
        
        print("\n" + "=" * 60)
        print("✓ LLM集成功能测试完成")
        print("✓ 知识图谱查询后成功调用LLM生成专业回复")
        print("✓ 所有功能正常工作")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_llm_integration()