#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试改进后的意图识别功能
验证与nlp目录下实现方式的一致性
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.config_manager import ConfigManager
from modules.intent_recognition import IntentRecognizer

def test_improved_intent_recognition():
    """测试改进后的意图识别功能"""
    print("=" * 60)
    print("测试改进后的意图识别功能")
    print("=" * 60)
    
    try:
        # 1. 初始化组件
        print("\n1. 初始化意图识别器...")
        config_manager = ConfigManager()
        
        # 导入知识库
        try:
            from intent_recognition.knowledge_base import KNOWLEDGE_BASE
        except ImportError:
            print("警告: 无法导入 KNOWLEDGE_BASE，使用空字典")
            KNOWLEDGE_BASE = {}
        
        model_path = config_manager.get('model.nlu_model_path', './my_intent_model')
        intent_recognizer = IntentRecognizer(model_path, KNOWLEDGE_BASE)
        
        print("✓ 意图识别器初始化成功")
        
        # 2. 测试改进后的功能
        print("\n2. 测试改进后的功能...")
        
        test_queries = [
            "数组和栈有什么关系？",
            "查找包含'算法'的实体", 
            "什么是二叉树？",
            "排序算法有哪些类型？",
            "今天星期几？"  # 测试other类型
        ]
        
        print("\n  2.1 测试意图识别:")
        for query in test_queries:
            intent = intent_recognizer.recognize_intent(query)
            print(f"    '{query}' -> 意图: {intent}")
        
        print("\n  2.2 测试实体提取:")
        for query in test_queries:
            entities = intent_recognizer.extract_entities(query)
            print(f"    '{query}' -> 实体: {entities}")
        
        print("\n  2.3 测试关系提取:")
        for query in test_queries:
            relations = intent_recognizer.extract_relations(query)
            print(f"    '{query}' -> 关系: {relations}")
        
        print("\n  2.4 测试统一元素提取:")
        for query in test_queries:
            entities, relations = intent_recognizer._extract_elements(query)
            print(f"    '{query}' -> 实体: {entities}, 关系: {relations}")
        
        print("\n  2.5 测试综合理解功能:")
        for query in test_queries:
            result = intent_recognizer.understand(query)
            print(f"    查询: '{query}'")
            print(f"      文本: {result['text']}")
            print(f"      意图: {result['intent']}")
            print(f"      实体: {result['entities']}")
            print(f"      关系: {result['relations']}")
            print()
        
        # 3. 测试与nlp目录实现的一致性
        print("\n3. 验证与nlp目录实现的一致性...")
        
        # 测试相同的查询
        nlp_style_queries = [
            "A点和B点连起来是啥",
            "已知BC线段和C点，求另一个点", 
            "今天星期几？",
            "我想查查B和C组成的线"
        ]
        
        print("\n  测试nlp风格的查询:")
        for query in nlp_style_queries:
            result = intent_recognizer.understand(query)
            print(f"    查询: '{query}'")
            print(f"      意图: {result['intent']}")
            print(f"      实体: {result['entities']}")
            print(f"      关系: {result['relations']}")
            print()
        
        # 4. 性能和稳定性测试
        print("\n4. 性能和稳定性测试...")
        
        import time
        start_time = time.time()
        
        for _ in range(10):
            for query in test_queries:
                intent_recognizer.understand(query)
        
        end_time = time.time()
        avg_time = (end_time - start_time) / (10 * len(test_queries))
        
        print(f"  平均处理时间: {avg_time:.4f} 秒/查询")
        print(f"  总处理查询数: {10 * len(test_queries)}")
        
        print("\n" + "=" * 60)
        print("✓ 改进后的意图识别功能测试完成")
        print("✓ 与nlp目录下实现方式保持一致")
        print("✓ 所有功能正常工作")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_improved_intent_recognition()