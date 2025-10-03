# -*- coding: utf-8 -*-
"""
意图识别模块
提供NLU模型加载、意图识别和实体关系提取功能
"""

import torch
import json
import os
from typing import Dict, List, Any
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import logging

class IntentRecognizer:
    """意图识别器
    
    负责加载NLU模型，进行意图识别和实体关系提取
    """
    
    def __init__(self, model_path: str, knowledge_base: Dict[str, Any]):
        """
        初始化意图识别器
        
        Args:
            model_path: NLU模型路径
            knowledge_base: 知识库字典，包含entities和relations
        """
        self.model_path = model_path
        self.knowledge_base = knowledge_base
        self.tokenizer = None
        self.model = None
        self.id2label = None
        self.entities_kb = knowledge_base.get("entities", {})
        self.relations_kb = knowledge_base.get("relations", {})
        
        self._load_model()
        
    def _load_model(self):
        """加载NLU模型"""
        try:
            # 1. 加载模型和分词器
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
            
            # 2. 加载标签映射
            label_map_path = os.path.join(self.model_path, "label_map.json")
            with open(label_map_path, 'r', encoding='utf-8') as f:
                label_map = json.load(f)
                # 注意：JSON加载后key会变成字符串，需要转换回整数
                self.id2label = {int(k): v for k, v in label_map['id2label'].items()}
                
            logging.info("深度学习NLU模型加载成功！")
            
        except Exception as e:
            logging.error(f"加载意图识别模型失败: {e}")
            raise
    
    def recognize_intent(self, text: str) -> str:
        """
        使用加载的深度学习模型进行意图识别
        
        Args:
            text: 输入文本
            
        Returns:
            str: 识别的意图类别
        """
        # 首先尝试规则匹配
        rule_based_intent = self._rule_based_intent_recognition(text)
        if rule_based_intent != "unknown":
            return rule_based_intent
        
        # 如果规则匹配失败，使用深度学习模型预测
        if not self.model or not self.tokenizer:
            logging.warning("模型未正确加载，仅使用规则匹配")
            return "unknown"
            
        try:
            # 1. 对输入文本进行编码
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True)
            
            # 2. 模型预测（推理时不需要计算梯度）
            with torch.no_grad():
                logits = self.model(**inputs).logits
                
            # 3. 解码结果
            predicted_class_id = logits.argmax().item()
            intent = self.id2label.get(predicted_class_id, "unknown")
            
            return intent
            
        except Exception as e:
            logging.error(f"意图识别失败: {e}")
            return "unknown"
    
    def _rule_based_intent_recognition(self, text: str) -> str:
        """
        基于规则的意图识别（只保留三个核心意图）
        
        Args:
            text: 输入文本
            
        Returns:
            str: 识别的意图类别
        """
        text_lower = text.lower()
        
        # 实体关系查询模式
        entity_relation_patterns = [
            "什么是", "介绍", "详细信息", "属性", "特点", "定义"
        ]
        
        # 实体间关系查询模式
        relation_between_patterns = [
            "关系", "联系", "区别", "差异", "相同", "不同", "比较"
        ]
        
        # 根据关系查找实体模式
        find_by_relation_patterns = [
            "有哪些", "包含", "属于", "类型", "分类", "种类"
        ]
        
        # 单实体查询模式
        single_entity_patterns = [
            "查询", "搜索", "找", "显示", "展示", "获取"
        ]
        
        # 检查各种模式
        if any(pattern in text_lower for pattern in entity_relation_patterns):
            return "find_entity_relations"
        elif any(pattern in text_lower for pattern in relation_between_patterns):
            return "find_relation_by_two_entities"
        elif any(pattern in text_lower for pattern in find_by_relation_patterns):
            return "find_entity_by_relation_and_entity"
        elif any(pattern in text_lower for pattern in single_entity_patterns):
            return "find_single_entity"
        
        return "unknown"
    
    def _extract_elements(self, text: str) -> tuple:
        """
        从文本中提取实体和关系（使用关键字匹配）
        
        Args:
            text: 输入文本
            
        Returns:
            tuple: (found_entities, found_relations) 提取的实体和关系列表
        """
        found_entities = []
        found_relations = []
        
        # 提取实体
        for entity_id, synonyms in self.entities_kb.items():
            for synonym in synonyms:
                if synonym in text:
                    found_entities.append(entity_id)
                    break
        
        # 提取关系
        for relation_id, synonyms in self.relations_kb.items():
            for synonym in synonyms:
                if synonym in text:
                    found_relations.append(relation_id)
                    break
                    
        return found_entities, found_relations
    
    def extract_entities(self, text: str) -> List[str]:
        """
        从文本中提取实体（保持向后兼容性）
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 提取的实体列表
        """
        entities, _ = self._extract_elements(text)
        return entities
    
    def extract_relations(self, text: str) -> List[str]:
        """
        从文本中提取关系（保持向后兼容性）
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 提取的关系列表
        """
        _, relations = self._extract_elements(text)
        return relations
    
    def understand(self, text: str) -> Dict[str, Any]:
        """
        NLU模组的主函数，整合所有功能
        
        Args:
            text: 输入文本
            
        Returns:
            Dict: 包含text、intent、entities、relations的字典
        """
        # 步骤1: 使用深度学习模型识别意图
        intent = self.recognize_intent(text)
        
        # 步骤2: 使用关键字匹配提取元素
        entities, relations = self._extract_elements(text)
        
        # 步骤3: 组装结果
        return {
            "text": text,
            "intent": intent,
            "entities": entities,
            "relations": relations
        }