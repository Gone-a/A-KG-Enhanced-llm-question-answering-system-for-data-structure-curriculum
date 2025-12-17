from typing import Dict, Any, List, Optional
import json
from concurrent.futures import ThreadPoolExecutor
from modules.doubao_llm import DoubaoLLM, LLMResponse
from modules.knowledge_graph_query import KnowledgeGraphQuery
from modules.config_manager import get_config_manager, ConfigManager

class KGContextBuilder:
    def __init__(self, kg_query: KnowledgeGraphQuery, relation_limit: int = 8, trunc_len: int = 300):
        self.kg_query = kg_query
        self.relation_limit = relation_limit
        self.trunc_len = trunc_len

    def _truncate(self, s: str) -> str:
        return s[: self.trunc_len] if isinstance(s, str) and len(s) > self.trunc_len else (s or "")

    def _score_relation(self, topic: str, item: Dict[str, Any]) -> float:
        e1 = item.get("entity1", "")
        e2 = item.get("entity2", "")
        r = item.get("relation", "")
        s = 0.0
        if isinstance(e1, str):
            if e1 == topic:
                s += 3
            elif topic in e1:
                s += 2
        if isinstance(e2, str):
            if e2 == topic:
                s += 2
            elif topic in e2:
                s += 1
        if isinstance(r, str):
            if any(k in r for k in ["包含","属于","类型","定义","相关","常用","适用","实现"]):
                s += 1
        return s

    def _merge_topic_attributes(self, topic: str, rels: List[Dict[str, Any]]) -> Dict[str, Any]:
        fields = ["type","description","properties","time_complexity","space_complexity","common_operations"]
        out: Dict[str, Any] = {}
        for it in rels:
            if it.get("entity1") == topic:
                attrs = it.get("entity1_attributes", {})
            elif it.get("entity2") == topic:
                attrs = it.get("entity2_attributes", {})
            else:
                attrs = {}
            for f in fields:
                v = attrs.get(f)
                if isinstance(v, str) and len(v.strip()) > 0 and f not in out:
                    out[f] = self._truncate(v.strip())
        return out

    def build_context(self, topic: str, kg_result: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if kg_result:
            rels = kg_result
        else:
            rels = self.kg_query.find_entity_relations(topic, limit=50)
            
        ranked = sorted([r for r in rels if isinstance(r, dict)], key=lambda x: self._score_relation(topic, x), reverse=True)
        picked = []
        for r in ranked:
            if len(picked) >= self.relation_limit:
                break
            e1 = r.get("entity1")
            e2 = r.get("entity2")
            rel = r.get("relation")
            if isinstance(e1, str) and isinstance(e2, str) and isinstance(rel, str):
                picked.append({"entity1": e1, "relation": rel, "entity2": e2})
        attrs = self._merge_topic_attributes(topic, rels)
        return {"topic": topic, "attributes": attrs, "relations": picked}

class KGLLMEnhancer:
    def __init__(self, llm: DoubaoLLM, kg_query: KnowledgeGraphQuery, temperature: float = 0.2, timeout: int = 25, relation_limit: int = 8, trunc_len: int = 300, config_manager: ConfigManager = None):
        self.config_manager = config_manager or ConfigManager()
        self.llm = llm
        self.kg_query = kg_query
        self.temperature = temperature
        self.timeout = timeout
        self.builder = KGContextBuilder(kg_query, relation_limit=relation_limit, trunc_len=trunc_len)

    def _prompt(self) -> str:
        return (
            "仅依据上方JSON背景生成中文‘数据结构课程内容’，严格遵循：\n"
            "1) 不得使用JSON外的知识；\n"
            "2) 术语必须使用JSON attributes原文；\n"
            "3) 结构：课程简介；学习目标（3-6条）；核心概念与定义；典型操作或相关算法；时间与空间复杂度；示例与练习（≥2个，含要点）；参考资料与进一步阅读；\n"
            "4) 学术化语体与准确术语；\n"
            "5) 末尾添加证据溯源小节（引用attributes与relations）。"
        )

    def _safe_llm(self, content: str, temperature: Optional[float] = None) -> LLMResponse:
        def _call():
            return self.llm.generate_response(content, temperature=temperature)
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_call)
            try:
                return fut.result(timeout=self.timeout)
            except Exception:
                return LLMResponse(content="", usage={"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}, model="fallback", finish_reason="error", response_time=0.0)

    def generate_with_kg(self, topic: str) -> str:
        ctx = self.builder.build_context(topic)
        prompt = f"背景知识（权威）：\n{json.dumps(ctx, ensure_ascii=False)}\n\n" + self._prompt()
        resp = self._safe_llm(prompt, temperature=self.temperature)
        text = resp.content.strip()
        evid = ["证据溯源："]
        attrs = ctx.get("attributes", {})
        for k, v in attrs.items():
            evid.append(f"属性-{k}：{(v or '')[:100]}")
        for i, r in enumerate(ctx.get("relations", []), 1):
            evid.append(f"关系{i}：{r.get('entity1','')} {r.get('relation','')} {r.get('entity2','')}")
        return text + "\n\n" + "\n".join(evid)

    def generate_pure(self, topic: str) -> str:
        content = f"主题：{topic}\n\n" + self._prompt()
        resp = self._safe_llm(content, temperature=None)
        return resp.content.strip()

    def answer_with_kg(self, user_query: str, topic: Optional[str] = None, kg_result: Optional[List[Dict[str, Any]]] = None) -> str:
        if kg_result:
            # 如果提供了kg_result，使用它来构建上下文，优先于topic查询
            # 如果topic未提供，尝试从kg_result中推断最相关的实体作为topic
            if not topic and kg_result:
                # 简单统计最常出现的实体
                from collections import Counter
                names = []
                for item in kg_result:
                     if isinstance(item, dict):
                        e1 = item.get('entity1')
                        e2 = item.get('entity2')
                        if isinstance(e1, str): names.append(e1)
                        if isinstance(e2, str): names.append(e2)
                if names:
                    topic = Counter(names).most_common(1)[0][0]
            
            ctx = self.builder.build_context(topic or "相关实体", kg_result=kg_result)
        elif topic:
            ctx = self.builder.build_context(topic)
        else:
            ctx = {"topic": "", "attributes": {}, "relations": []}
            
        prompt = (
            f"用户问题：{user_query}\n\n"
            f"权威背景（JSON）：\n{json.dumps(ctx, ensure_ascii=False)}\n\n"
            "请仅依据JSON中的信息作答；若信息不足，请明确说明并给出一般性解释。要求用专业且易懂的中文，合理引用属性与关系。"
        )
        resp = self._safe_llm(prompt, temperature=self.temperature)
        return resp.content.strip()

    def answer_pure(self, user_query: str) -> str:
        prompt = (
            f"用户问题：{user_query}\n\n"
            "请用专业且易懂的中文作答。若涉及数据结构与算法，给出准确术语与要点。"
        )
        resp = self._safe_llm(prompt, temperature=None)
        return resp.content.strip()

    @staticmethod
    def from_config(config_manager: ConfigManager = None) -> "KGLLMEnhancer":
        config_manager = config_manager or ConfigManager()
        api_conf = config_manager.get_api_config()
        db_conf = config_manager.get_database_config()
        llm = DoubaoLLM(user_api_key=api_conf.get("ark_api_key"), user_model_id=api_conf.get("doubao_model_id"), base_url=api_conf.get("base_url"), config_manager=config_manager)
        kg = KnowledgeGraphQuery(db_conf.get("uri"), db_conf.get("user_name"), db_conf.get("password"), config_manager=config_manager)
        return KGLLMEnhancer(llm, kg, config_manager=config_manager)
