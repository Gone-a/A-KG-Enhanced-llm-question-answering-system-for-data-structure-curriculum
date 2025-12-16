# -*- coding: utf-8 -*-
"""
意图识别模块
提供NLU模型加载、意图识别和实体关系提取功能
"""

import torch
import json
import os
from typing import Dict, List, Any
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModel
import logging
from relation_extend.ner_only import NERProcessor

class IntentRecognizer:
    """意图识别器
    
    负责加载NLU模型，进行意图识别和实体关系提取
    """
    
    def __init__(self, model_path: str, knowledge_base: Dict[str, Any], use_w2ner: bool = True):
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
        self.use_w2ner = use_w2ner
        self.ner_processor = None
        self.embed_tokenizer = None
        self.embed_model = None
        self.embed_device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        self.kg_query = None
        
        self._load_model()
        if self.use_w2ner:
            try:
                self.ner_processor = NERProcessor(txt_file_path="")
            except Exception as e:
                logging.error(f"加载W2NER失败: {e}")
                self.use_w2ner = False
        self._load_embedder()
        
    def _load_model(self):
        """加载NLU模型"""
        try:
            if not (self.model_path and os.path.isdir(self.model_path)):
                logging.info(f"NLU本地模型目录不存在或未提供，跳过深度学习意图识别加载: {self.model_path}")
                self.tokenizer = None
                self.model = None
                self.id2label = None
                return
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_path, local_files_only=True)
            
            # 2. 加载标签映射
            label_map_path = os.path.join(self.model_path, "label_map.json")
            with open(label_map_path, 'r', encoding='utf-8') as f:
                label_map = json.load(f)
                # 注意：JSON加载后key会变成字符串，需要转换回整数
                self.id2label = {int(k): v for k, v in label_map['id2label'].items()}
                
            logging.info("深度学习NLU模型加载成功！")
            
        except Exception as e:
            logging.info(f"NLU模型加载失败，使用规则意图识别: {e}")
            self.tokenizer = None
            self.model = None
            self.id2label = None
    
    def _load_embedder(self):
        try:
            base = "/root/KG_inde/relation_extend/bert-base-chinese"
            self.embed_tokenizer = AutoTokenizer.from_pretrained(base)
            self.embed_model = AutoModel.from_pretrained(base)
            self.embed_model.to(self.embed_device)
            self.embed_model.eval()
        except Exception as e:
            logging.error(f"加载嵌入模型失败: {e}")
            self.embed_tokenizer = None
            self.embed_model = None
    
    def set_kg_query(self, kg_query):
        self.kg_query = kg_query
    
    def _text_embedding(self, text: str):
        if not (self.embed_model and self.embed_tokenizer):
            return None
        try:
            with torch.no_grad():
                inputs = self.embed_tokenizer(text, return_tensors="pt", truncation=True, padding=True)
                for k in inputs:
                    inputs[k] = inputs[k].to(self.embed_device)
                outputs = self.embed_model(**inputs)
                hidden = outputs.last_hidden_state
                emb = hidden.mean(dim=1).squeeze(0).cpu().numpy()
                return emb
        except Exception as e:
            logging.error(f"文本嵌入失败: {e}")
            return None
    
    def _cosine(self, a, b) -> float:
        import numpy as np
        if a is None or b is None:
            return 0.0
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))
    
    def _augment_candidates(self, text: str) -> List[str]:
        # 使用知识库同义词进行增广匹配
        cands = set()
        try:
            from intent_recognition.knowledge_base import KNOWLEDGE_BASE
            kb_entities = KNOWLEDGE_BASE.get("entities", {})
            for std_name, synonyms in kb_entities.items():
                for syn in synonyms:
                    if syn and syn in text:
                        cands.add(syn)
                        cands.add(std_name)
        except Exception:
            pass
        # 简单句式抽取：X和Y 等连接词
        import re
        pair_pat = r'([\\u4e00-\\u9fa5A-Za-z\\+]+?)(?:和|与)([\\u4e00-\\u9fa5A-Za-z\\+]+?)(?:的|之|，|,|。|关系|区别)'
        for m in re.finditer(pair_pat, text):
            x = m.group(1).strip()
            y = m.group(2).strip()
            if x:
                cands.add(x)
            if y:
                cands.add(y)
        return list(cands)
    
    def _postprocess_entities(self, text: str, entities_raw: List[dict]) -> List[str]:
        items = []
        # 原始候选
        for e in entities_raw:
            t = e.get("text") if isinstance(e, dict) else str(e)
            if not t:
                continue
            s = e.get("start") if isinstance(e, dict) else text.find(t)
            epos = e.get("end") if isinstance(e, dict) else (s + len(t) if s >= 0 else -1)
            label = e.get("label") if isinstance(e, dict) else None
            items.append({"text": t, "start": s, "end": epos, "label": label})
        # 增广候选
        for t in self._augment_candidates(text):
            if t and all(t != it["text"] for it in items):
                s = text.find(t)
                epos = s + len(t) if s >= 0 else -1
                items.append({"text": t, "start": s, "end": epos, "label": "NAMED_ENTITY"})
        uniq = {}
        for it in items:
            k = it["text"]
            if k not in uniq:
                uniq[k] = it
            else:
                a = uniq[k]
                if it.get("label") == "NAMED_ENTITY" and a.get("label") != "NAMED_ENTITY":
                    uniq[k] = it
        items = list(uniq.values())
        items = [it for it in items if isinstance(it["text"], str) and len(it["text"].strip()) > 1]
        # 最长匹配原则：按长度降序取非重叠片段，过滤泛词
        keep = []
        items_sorted = sorted(items, key=lambda x: len(x["text"]), reverse=True)
        taken_spans = []
        stopwords = {"排序", "树", "路径", "图", "算法"}
        for it in items_sorted:
            txt = it["text"]
            s = it["start"]
            epos = it["end"]
            if txt in stopwords:
                continue
            if s >= 0 and epos >= 0:
                overlap = any(not (epos <= ts or s >= te) for ts, te in taken_spans)
                if overlap:
                    continue
                taken_spans.append((s, epos))
            keep.append(it)
        query_emb = self._text_embedding(text)
        scored = []
        for it in keep:
            ent_emb = self._text_embedding(it["text"])
            sim = self._cosine(query_emb, ent_emb)
            length_w = max(1.0, (len(it["text"]) ** 0.5))
            label_w = 1.2 if it.get("label") == "NAMED_ENTITY" else 1.0
            bonus = 1.5 if it["text"] in {"时间复杂度"} else 1.0
            score = sim * length_w * label_w * bonus
            scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        result = [x[1]["text"] for x in scored]
        # KG存在性优先（可选）
        if self.kg_query:
            def in_kg(name: str) -> bool:
                try:
                    rs = self.kg_query.find_entity_relations(name, limit=1)
                    return bool(rs)
                except Exception:
                    return False
            # 排序时提升在KG中存在的项
            result = sorted(result, key=lambda n: (0 if in_kg(n) else 1, -len(n)))
        result = list(dict.fromkeys(result))
        return result
    
    def recognize_intent(self, text: str) -> str:
        """
        使用加载的深度学习模型进行意图识别
        
        Args:
            text: 输入文本
            
        Returns:
            str: 识别的意图类别
        """
        intent_model = None
        if self.model and self.tokenizer:
            try:
                inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True)
                with torch.no_grad():
                    logits = self.model(**inputs).logits
                predicted_class_id = logits.argmax().item()
                intent_model = self.id2label.get(predicted_class_id, "unknown")
            except Exception as e:
                logging.error(f"BERT模型意图识别失败: {e}")
        rule_intent = self._rule_based_intent_recognition(text)
        if intent_model and intent_model != "unknown":
            if intent_model == "other" and rule_intent != "other":
                return rule_intent
            return intent_model
        return rule_intent
    
    def _rule_based_intent_recognition(self, text: str) -> str:
        """
        基于规则的意图识别（只保留三个核心意图）
        
        Args:
            text: 输入文本
            
        Returns:
            str: 识别的意图类别
        """
        text_lower = text.lower()
        
        # 实体间关系查询模式
        relation_between_patterns = [
            "关系", "联系", "区别", "差异", "相同", "不同", "比较"
        ]
        
        # 根据关系查找实体模式
        find_by_relation_patterns = [
            "有哪些", "包含", "属于", "类型", "分类", "种类"
        ]
        
        # 单实体查询模式（包含原来的实体关系查询模式）
        single_entity_patterns = [
            "查询", "搜索", "找", "显示", "展示", "获取",
            "什么是", "介绍", "详细信息", "属性", "特点", "定义",
            "有什么", "的", "复杂度", "算法", "数据结构", "排序"
        ]
        
        # 检查各种模式
        if any(pattern in text_lower for pattern in relation_between_patterns):
            return "find_relation_by_two_entities"
        elif any(pattern in text_lower for pattern in find_by_relation_patterns):
            return "find_entity_by_relation_and_entity"
        elif any(pattern in text_lower for pattern in single_entity_patterns):
            return "find_entity_definition"
        
        return "other"
    
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
        if self.use_w2ner and self.ner_processor:
            try:
                res = self.ner_processor.run_ner_prediction([text])
                ents = self._postprocess_entities(text, res[0].get("entities", []))
                if ents:
                    return ents
                else:
                    entities, _ = self._extract_elements(text)
                    return entities
            except Exception as e:
                logging.error(f"W2NER实体识别失败，回退到词典匹配: {e}")
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
