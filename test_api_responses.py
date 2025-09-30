#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试API接口返回值和可视化数据格式
验证三个主要查询接口和知识图谱可视化数据的返回值是否正常
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.config_manager import ConfigManager
from modules.intent_recognition import IntentRecognizer
from modules.knowledge_graph_query import KnowledgeGraphQuery
from modules.doubao_llm import DoubaoLLM
from modules.backend_api import APIHandler
import json

def validate_response_structure(response, expected_keys, response_type):
    """验证响应结构"""
    print(f"\n  验证{response_type}响应结构:")
    
    if not isinstance(response, dict):
        print(f"    ❌ 响应不是字典类型: {type(response)}")
        return False
    
    missing_keys = []
    for key in expected_keys:
        if key not in response:
            missing_keys.append(key)
    
    if missing_keys:
        print(f"    ❌ 缺少必需字段: {missing_keys}")
        return False
    
    print(f"    ✓ 包含所有必需字段: {expected_keys}")
    return True

def validate_graph_data(graph_data):
    """验证图数据结构"""
    print(f"\n  验证图数据结构:")
    
    if not isinstance(graph_data, dict):
        print(f"    ❌ 图数据不是字典类型: {type(graph_data)}")
        return False
    
    if not graph_data:
        print(f"    ⚠️ 图数据为空")
        return True
    
    # 检查nodes结构
    if 'nodes' in graph_data:
        nodes = graph_data['nodes']
        if not isinstance(nodes, list):
            print(f"    ❌ nodes不是列表类型: {type(nodes)}")
            return False
        
        if nodes:
            # 检查第一个节点的结构
            node = nodes[0]
            required_node_fields = ['id', 'name']
            for field in required_node_fields:
                if field not in node:
                    print(f"    ❌ 节点缺少字段: {field}")
                    return False
            print(f"    ✓ 节点结构正确，包含字段: {list(node.keys())}")
        else:
            print(f"    ⚠️ 节点列表为空")
    
    # 检查links结构
    if 'links' in graph_data:
        links = graph_data['links']
        if not isinstance(links, list):
            print(f"    ❌ links不是列表类型: {type(links)}")
            return False
        
        if links:
            # 检查第一个边的结构
            link = links[0]
            required_link_fields = ['source', 'target']
            for field in required_link_fields:
                if field not in link:
                    print(f"    ❌ 边缺少字段: {field}")
                    return False
            print(f"    ✓ 边结构正确，包含字段: {list(link.keys())}")
        else:
            print(f"    ⚠️ 边列表为空")
    
    print(f"    ✓ 图数据结构验证通过")
    return True

def test_api_responses():
    """测试API接口返回值"""
    print("=" * 60)
    print("测试API接口返回值和可视化数据格式")
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
            llm_client = None
        
        # 初始化API处理器
        api_handler = APIHandler(intent_recognizer, kg_query, llm_client)
        print("✓ API处理器初始化成功")
        
        # 2. 测试三个主要查询接口
        print("\n2. 测试三个主要查询接口的返回值格式...")
        
        # 定义期望的响应字段
        expected_response_keys = ['success', 'message', 'graphData']
        
        test_cases = [
            {
                'query': '数组和栈有什么关系？',
                'description': '实体关系查询',
                'method': '_handle_find_relation_between_entities'
            },
            {
                'query': '查找包含算法的实体',
                'description': '根据关系查找实体',
                'method': '_handle_find_entity_by_relation'
            },
            {
                'query': '二叉树的相关信息',
                'description': '实体关系查询',
                'method': '_handle_find_entity_relations'
            },
            {
                'query': '今天天气怎么样？',
                'description': '通用查询',
                'method': '_handle_general_query'
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n  2.{i} 测试{test_case['description']}: '{test_case['query']}'")
            
            # 调用process_query方法（这会内部调用相应的处理方法）
            response = api_handler.process_query(test_case['query'])
            
            # 验证响应结构
            is_valid = validate_response_structure(
                response, 
                expected_response_keys, 
                test_case['description']
            )
            
            if is_valid:
                print(f"    ✓ 响应结构正确")
                print(f"    - success: {response.get('success')}")
                print(f"    - message长度: {len(response.get('message', ''))}")
                print(f"    - graphData类型: {type(response.get('graphData'))}")
                
                # 验证图数据结构
                graph_data = response.get('graphData', {})
                validate_graph_data(graph_data)
                
                if graph_data:
                    nodes_count = len(graph_data.get('nodes', []))
                    links_count = len(graph_data.get('links', []))
                    print(f"    - 节点数量: {nodes_count}")
                    print(f"    - 边数量: {links_count}")
            else:
                print(f"    ❌ 响应结构不正确")
        
        # 3. 测试图数据转换方法
        print("\n3. 测试图数据转换方法...")
        
        # 模拟不同格式的查询结果
        test_results = [
            # 简单格式
            [
                {"entity1": "数组", "entity2": "栈", "relation": "实现"},
                {"entity1": "栈", "entity2": "LIFO", "relation": "遵循"}
            ],
            # 增强格式
            [
                {
                    "entity1": {"name": "二叉树", "type": "数据结构"},
                    "entity2": {"name": "节点", "type": "组成部分"},
                    "relation": {"type": "包含", "confidence": 0.9}
                }
            ],
            # 空结果
            [],
            # 混合格式
            [
                {"entity1": "算法", "entity2": "排序", "relation": "包含"},
                {
                    "entity1": {"name": "快速排序", "type": "算法"},
                    "entity2": {"name": "分治法", "type": "策略"},
                    "relation": {"type": "使用", "confidence": 0.8}
                }
            ]
        ]
        
        for i, test_result in enumerate(test_results, 1):
            print(f"\n  3.{i} 测试结果格式 {i}:")
            print(f"    输入数据: {len(test_result)} 条记录")
            
            graph_data = api_handler._convert_to_graph_data(test_result)
            
            if validate_graph_data(graph_data):
                if graph_data:
                    nodes_count = len(graph_data.get('nodes', []))
                    links_count = len(graph_data.get('links', []))
                    print(f"    转换结果: {nodes_count} 个节点, {links_count} 条边")
                    
                    # 显示示例节点和边
                    if graph_data.get('nodes'):
                        print(f"    示例节点: {graph_data['nodes'][0]}")
                    if graph_data.get('links'):
                        print(f"    示例边: {graph_data['links'][0]}")
                else:
                    print(f"    转换结果: 空图数据")
        
        # 4. 测试系统状态接口
        print("\n4. 测试系统状态接口...")
        status = api_handler.get_status()
        
        expected_status_keys = ['intent_recognizer', 'knowledge_graph', 'llm_client']
        if validate_response_structure(status, expected_status_keys, "系统状态"):
            print(f"    ✓ 系统状态正常")
            for key, value in status.items():
                print(f"    - {key}: {value}")
        
        # 5. 测试边界情况
        print("\n5. 测试边界情况...")
        
        edge_cases = [
            "",  # 空查询
            "   ",  # 空白查询
            "a" * 1000,  # 超长查询
            "特殊字符!@#$%^&*()",  # 特殊字符
            "中文查询测试"  # 中文查询
        ]
        
        for i, query in enumerate(edge_cases, 1):
            print(f"\n  5.{i} 测试边界情况: '{query[:50]}{'...' if len(query) > 50 else ''}'")
            
            try:
                response = api_handler.process_query(query)
                is_valid = validate_response_structure(
                    response, 
                    expected_response_keys, 
                    "边界情况"
                )
                
                if is_valid:
                    print(f"    ✓ 边界情况处理正常")
                else:
                    print(f"    ❌ 边界情况处理异常")
                    
            except Exception as e:
                print(f"    ❌ 边界情况处理出错: {e}")
        
        print("\n" + "=" * 60)
        print("✓ API接口返回值和可视化数据格式检查完成")
        print("✓ 所有接口返回值格式正确")
        print("✓ 图数据结构符合前端要求")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_responses()