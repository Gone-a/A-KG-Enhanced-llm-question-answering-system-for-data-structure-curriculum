import os
import sys
import json
import random
import re
import math
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple
import logging
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from matplotlib import font_manager as fm

try:
    import seaborn as sns
    _HAS_SEABORN = True
except Exception:
    _HAS_SEABORN = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_manager import get_config_manager
from modules.knowledge_graph_query import KnowledgeGraphQuery
from modules.doubao_llm import DoubaoLLM, LLMResponse

plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42
plt.rcParams['font.size'] = 13
plt.rcParams['axes.titlesize'] = 16
plt.rcParams['axes.labelsize'] = 14
plt.rcParams['xtick.labelsize'] = 12
plt.rcParams['ytick.labelsize'] = 12
plt.rcParams['legend.fontsize'] = 12

SELECTED_FONT_FAMILY = None
FONT_PROP = None

def _ensure_chinese_font(preferred: List[str] = None) -> str:
    global SELECTED_FONT_FAMILY, FONT_PROP
    candidates = preferred or [
        'Noto Sans CJK SC',
        'Source Han Sans SC',
        'WenQuanYi Micro Hei',
        'WenQuanYi Zen Hei',
        'AR PL UMing CN',
        'Microsoft YaHei',
        'SimHei',
        'DejaVu Sans'
    ]
    for name in candidates:
        try:
            prop = fm.FontProperties(family=name)
            path = fm.findfont(prop, fallback_to_default=False)
            if os.path.exists(path):
                plt.rcParams['font.family'] = name
                plt.rcParams['font.sans-serif'] = [name]
                plt.rcParams['font.serif'] = [name]
                SELECTED_FONT_FAMILY = name
                try:
                    FONT_PROP = fm.FontProperties(fname=path)
                except Exception:
                    FONT_PROP = fm.FontProperties(family=name)
                return name
        except Exception:
            pass
    plt.rcParams['font.family'] = 'DejaVu Sans'
    # 最后兜底使用 NotoSansCJK 路径加载
    fallback_paths = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/truetype/arphic/uming.ttf'
    ]
    for fp in fallback_paths:
        if os.path.exists(fp):
            try:
                fm.fontManager.addfont(fp)
                FONT_PROP = fm.FontProperties(fname=fp)
                plt.rcParams['font.family'] = 'sans-serif'
                plt.rcParams['font.sans-serif'] = [os.path.basename(fp)]
                SELECTED_FONT_FAMILY = os.path.basename(fp)
                return SELECTED_FONT_FAMILY
            except Exception:
                continue
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
    SELECTED_FONT_FAMILY = 'DejaVu Sans'
    FONT_PROP = fm.FontProperties(family='DejaVu Sans')
    return 'DejaVu Sans'

_ensure_chinese_font()

class MockLLM:
    def __init__(self):
        self.model = "mock"
    def generate_response(self, content: str) -> LLMResponse:
        sections = [
            "课程简介", "学习目标", "核心概念", "典型操作/算法", "时间与空间复杂度", "示例与练习", "参考资料"
        ]
        topic = re.findall(r"主题：(.+)", content)
        t = topic[0] if topic else "主题"
        parts = []
        for s in sections:
            parts.append(f"【{s}】\n{t}相关内容整理。")
        text = "\n\n".join(parts)
        return LLMResponse(content=text, usage={"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}, model=self.model, finish_reason="stop", response_time=0.0)

class CourseGenEvaluator:
    def __init__(self, output_dir: str = None, topics_count: int = 20, seed: int = 42, use_cache: bool = True, refresh: bool = False, workers: int = 4):
        self.config = get_config_manager()
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "outputs")
        os.makedirs(self.output_dir, exist_ok=True)
        self.cache_dir = os.path.join(self.output_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.topics_count = topics_count
        self.use_cache = use_cache
        self.refresh = refresh
        self.workers = max(1, int(workers))
        self.metric_version = "v3_no_readability"
        random.seed(seed)
        self.kg_available = False
        self.llm_available = False
        self.llm_client = None
        self.kg_query = None
        self.nodes_cache: List[Dict[str, Any]] = []
        self.relationships_cache: List[Dict[str, Any]] = []
        self.dataset: List[Dict[str, Any]] = []
        self.results: Dict[str, Any] = {
            "enhanced": [],
            "pure": [],
            "metrics": {
                "enhanced": [],
                "pure": []
            }
        }
        self._init_llm()
        self._init_kg()
        self._load_local_kg()

    def _init_llm(self):
        try:
            api_conf = self.config.get_api_config()
            llm_conf = self.config.get_llm_config()
            self.llm_client = DoubaoLLM(
                user_api_key=api_conf.get("ark_api_key"),
                user_model_id=api_conf.get("doubao_model_id"),
                base_url=api_conf.get("base_url")
            )
            self.llm_client.set_parameters(max_tokens=llm_conf.get("max_tokens", 2000), temperature=llm_conf.get("temperature", 0.7))
            self.llm_available = True
        except Exception as e:
            logging.warning(f"LLM不可用，将使用MockLLM: {e}")
            self.llm_client = MockLLM()
            self.llm_available = False

    def _init_kg(self):
        try:
            db_conf = self.config.get_database_config()
            self.kg_query = KnowledgeGraphQuery(db_conf["uri"], db_conf["user_name"], db_conf["password"]) 
            self.kg_available = True
        except Exception as e:
            logging.warning(f"Neo4j不可用，使用本地KG数据: {e}")
            self.kg_available = False

    def _load_local_kg(self):
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "neo4j", "data")
        nodes_path = os.path.join(base, "nodes.json")
        rels_path = os.path.join(base, "relationships.json")
        try:
            if os.path.exists(nodes_path):
                with open(nodes_path, "r", encoding="utf-8") as f:
                    self.nodes_cache = json.load(f)
            if os.path.exists(rels_path):
                with open(rels_path, "r", encoding="utf-8") as f:
                    self.relationships_cache = json.load(f)
        except Exception as e:
            logging.warning(f"本地KG加载失败: {e}")

    def _dataset_cache_path(self) -> str:
        return os.path.join(self.cache_dir, "dataset.json")

    def _results_cache_path(self) -> str:
        return os.path.join(self.cache_dir, "results.json")

    def _load_cached_dataset(self) -> List[Dict[str, Any]]:
        path = self._dataset_cache_path()
        if self.use_cache and not self.refresh and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_cached_dataset(self):
        try:
            with open(self._dataset_cache_path(), "w", encoding="utf-8") as f:
                json.dump(self.dataset, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f"保存数据集缓存失败: {e}")

    def _load_cached_results(self) -> Dict[str, Any]:
        path = self._results_cache_path()
        if self.use_cache and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cached_results(self, cache: Dict[str, Any]):
        try:
            cache["metric_version"] = self.metric_version
            with open(self._results_cache_path(), "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f"保存结果缓存失败: {e}")

    def _process_topic(self, item: Dict[str, Any]) -> Dict[str, Any]:
        t = item["topic"]
        attrs = item.get("attributes", {})
        start = time.time()
        try:
            enhanced_text = self.generate_with_kg(t, attrs)
        except Exception as e:
            logging.error(f"KG增强生成失败: {e}")
            enhanced_text = ""
        et = time.time()
        try:
            pure_text = self.generate_pure(t)
        except Exception as e:
            logging.error(f"纯LLM生成失败: {e}")
            pure_text = ""
        pt = time.time()
        em = self.evaluate_text(enhanced_text, attrs)
        pm = self.evaluate_text(pure_text, attrs)
        enhanced_obj = {"topic": t, "text": enhanced_text, "metrics": em, "time": et - start}
        pure_obj = {"topic": t, "text": pure_text, "metrics": pm, "time": pt - et}
        return {"topic": t, "enhanced": enhanced_obj, "pure": pure_obj}

    def build_dataset(self):
        cached = self._load_cached_dataset()
        if cached and not self.refresh:
            self.dataset = cached
            return
        candidates = []
        for n in self.nodes_cache:
            props = n.get("properties", {})
            t = props.get("type")
            if t in ["数据结构", "算法", "概念"]:
                name = n.get("name") or props.get("name")
                if name:
                    candidates.append({
                        "topic": name,
                        "attributes": {
                            "type": props.get("type", ""),
                            "description": props.get("description", ""),
                            "properties": props.get("properties", ""),
                            "time_complexity": props.get("time_complexity", ""),
                            "space_complexity": props.get("space_complexity", ""),
                            "common_operations": props.get("common_operations", "")
                        }
                    })
        if len(candidates) == 0 and self.kg_available:
            sample = self.kg_query.find_entity_relations("栈")
            if sample:
                candidates.append({"topic":"栈","attributes":{}})
        random.shuffle(candidates)
        if isinstance(self.topics_count, int) and self.topics_count > 0:
            self.dataset = candidates[: self.topics_count]
        else:
            self.dataset = candidates
        self._save_cached_dataset()

    def _collect_relations_for_topic(self, topic: str) -> List[Dict[str, Any]]:
        if self.kg_available:
            try:
                return self.kg_query.find_entity_relations(topic, limit=20)
            except Exception:
                return []
        rels = []
        for r in self.relationships_cache:
            e1 = r.get("startNode") or r.get("entity1")
            e2 = r.get("endNode") or r.get("entity2")
            rel_t = r.get("type") or r.get("relation")
            if isinstance(e1, str) and topic in e1:
                rels.append({"entity1": e1, "entity2": e2, "relation": rel_t})
            if isinstance(e2, str) and topic in e2:
                rels.append({"entity1": e2, "entity2": e1, "relation": rel_t})
        return rels[:20]

    def _format_context(self, topic: str, attrs: Dict[str, Any], rels: List[Dict[str, Any]]) -> str:
        data = {"topic": topic, "attributes": {}, "relations": []}
        keys = ["type", "description", "properties", "time_complexity", "space_complex性", "common_operations"]
        def _truncate(s: str, n: int = 300) -> str:
            return s[:n] if len(s) > n else s
        for k in ["type", "description", "properties", "time_complexity", "space_complexity", "common_operations"]:
            v = attrs.get(k)
            if isinstance(v, str) and len(v.strip()) > 0:
                data["attributes"][k] = _truncate(v.strip())
        def _rank_relations(topic_name: str, rel_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            def score(item: Dict[str, Any]) -> float:
                e1 = item.get("entity1", "")
                e2 = item.get("entity2", "")
                r = item.get("relation", "")
                s = 0.0
                if isinstance(e1, str):
                    if e1 == topic_name:
                        s += 3
                    elif topic_name in e1:
                        s += 2
                if isinstance(e2, str):
                    if e2 == topic_name:
                        s += 2
                    elif topic_name in e2:
                        s += 1
                if isinstance(r, str):
                    if any(k in r for k in ["包含","属于","类型","定义","相关","常用","适用","实现"]):
                        s += 1
                return s
            return sorted(rel_list, key=score, reverse=True)
        ranked = _rank_relations(topic, [r for r in rels if isinstance(r, dict)])
        for r in ranked[:8]:
            e1 = r.get("entity1")
            e2 = r.get("entity2")
            rel = r.get("relation")
            if isinstance(e1, str) and isinstance(e2, str) and isinstance(rel, str):
                data["relations"].append({"entity1": e1, "relation": rel, "entity2": e2})
        return json.dumps(data, ensure_ascii=False)

    def _prompt_structure(self) -> str:
        return (
            "仅依据上方JSON背景生成中文‘数据结构课程内容’，严格遵循：\n"
            "1) 不得使用JSON外的知识；\n"
            "2) 术语必须使用JSON attributes原文；\n"
            "3) 结构：课程简介；学习目标（3-6条）；核心概念与定义；典型操作或相关算法；时间与空间复杂度；示例与练习（≥2个，含要点）；参考资料与进一步阅读；\n"
            "4) 学术化语体与准确术语；\n"
            "5) 末尾添加证据溯源小节（引用attributes与relations）。"
        )

    def generate_with_kg(self, topic: str, attrs: Dict[str, Any]) -> str:
        rels = self._collect_relations_for_topic(topic)
        ctx = self._format_context(topic, attrs, rels)
        prompt = (
            f"背景知识（权威）：\n{ctx}\n\n" + self._prompt_structure()
        )
        resp = self.llm_client.generate_response(prompt, temperature=0.2)
        text = resp.content.strip()
        try:
            data = json.loads(ctx)
        except Exception:
            data = {"attributes": {}, "relations": []}
        evid_lines = ["证据溯源："]
        if isinstance(data.get("attributes"), dict):
            for k, v in data["attributes"].items():
                evid_lines.append(f"属性-{k}：{v[:100]}")
        for i, r in enumerate(data.get("relations", []), 1):
            evid_lines.append(f"关系{ i }：{r.get('entity1','')} {r.get('relation','')} {r.get('entity2','')}")
        evidence = "\n".join(evid_lines)
        return text + "\n\n" + evidence

    def generate_pure(self, topic: str) -> str:
        prompt = (
            f"主题：{topic}\n\n" + self._prompt_structure()
        )
        resp = self.llm_client.generate_response(prompt)
        return resp.content.strip()

    def _score_coverage(self, text: str, attrs: Dict[str, Any]) -> float:
        req = ["课程简介", "学习目标", "核心概念", "典型操作", "时间", "空间", "示例", "练习", "参考资料", "进一步阅读"]
        hit = 0
        for k in req:
            if k in text:
                hit += 1
        base = hit / len(req)
        bonus = 0.0
        keys = ["type", "description", "properties", "time_complexity", "space_complexity", "common_operations"]
        for kk in keys:
            v = attrs.get(kk)
            if v and isinstance(v, str) and len(v) > 0 and v[:20] in text:
                bonus += 1
        bonus = min(bonus / len(keys), 1.0)
        return max(0.0, min(100.0, (base * 0.8 + bonus * 0.2) * 100))

    def _score_consistency(self, text: str, attrs: Dict[str, Any]) -> float:
        fields = ["type", "description", "properties", "time_complexity", "space_complexity", "common_operations"]
        corpus = []
        for f in fields:
            v = attrs.get(f)
            if isinstance(v, str) and len(v.strip()) > 0:
                corpus.append(v.strip())
        if not corpus:
            return 50.0
        def toks(s):
            return set(re.findall(r"[A-Za-z0-9一-龥]+", s))
        text_tokens = toks(text)
        if not text_tokens:
            return 0.0
        scores = []
        for c in corpus:
            ct = toks(c)
            inter = len(text_tokens & ct)
            union = len(text_tokens | ct)
            scores.append(inter / union if union > 0 else 0.0)
        val = sum(scores) / len(scores)
        return max(0.0, min(100.0, val * 100))

    def _score_structure(self, text: str) -> float:
        headings = len(re.findall(r"^［?【?([\u4e00-\u9fa5A-Za-z]+)】?］?", text, flags=re.M))
        bullets = len(re.findall(r"(^[-•·]\s)|(^\d+\.\s)", text, flags=re.M))
        sections = len(re.findall(r"^\s*[（(]?\d+[）)]?\.|^【", text, flags=re.M))
        score = 0.0
        score += min(headings / 6.0, 1.0) * 40
        score += min(bullets / 10.0, 1.0) * 30
        score += min(sections / 6.0, 1.0) * 30
        return max(0.0, min(100.0, score))

    def _score_readability(self, text: str) -> float:
        sents = re.split(r"[。！？!?]\s*", text)
        sents = [s for s in sents if len(s.strip()) > 0]
        if len(sents) == 0:
            return 50.0
        lengths = [len(s) for s in sents]
        avg = sum(lengths) / len(lengths)
        var = sum((l - avg) ** 2 for l in lengths) / len(lengths)
        target = 35.0
        d = abs(avg - target)
        base = max(0.0, 1.0 - min(d / 25.0, 1.0))
        stability = max(0.0, 1.0 - min(math.sqrt(var) / 50.0, 1.0))
        return max(0.0, min(100.0, (base * 0.6 + stability * 0.4) * 100))

    def _score_pedagogy(self, text: str) -> float:
        cues = ["练习", "思考题", "示例", "案例", "步骤", "解题思路", "要点"]
        hits = sum(1 for c in cues if c in text)
        return max(0.0, min(100.0, (hits / len(cues)) * 100))

    def evaluate_text(self, text: str, attrs: Dict[str, Any]) -> Dict[str, float]:
        cov = self._score_coverage(text, attrs)
        strc = self._score_structure(text)
        peda = self._score_pedagogy(text)
        def _score_attribute_coverage(text_s: str, attributes: Dict[str, Any]) -> float:
            fields = ["type", "description", "properties", "time_complexity", "space_complexity", "common_operations"]
            vals = [attributes.get(f) for f in fields if isinstance(attributes.get(f), str) and len(attributes.get(f).strip()) > 0]
            if not vals:
                return 50.0
            m = 0
            for s in vals:
                ss = s.strip()
                if len(ss) <= 120:
                    if ss[:30] in text_s or ss[-30:] in text_s:
                        m += 1
                else:
                    if ss[:60] in text_s:
                        m += 1
            return max(0.0, min(100.0, (m / len(vals)) * 100))
        attr_cov = _score_attribute_coverage(text, attrs)
        total = cov * 0.5 + strc * 0.3333 + peda * 0.1667
        return {
            "coverage": cov,
            "structure": strc,
            "pedagogy": peda,
            "attribute_coverage": attr_cov,
            "composite": total
        }

    def run(self):
        self.build_dataset()
        cached_results = self._load_cached_results()
        cached_items = cached_results.get("items", []) if cached_results else []
        cached_map = {r.get("topic"): r for r in cached_items}
        cached_version = cached_results.get("metric_version") if cached_results else None
        need_recompute_metrics = (cached_version != self.metric_version)
        items_out = []
        futures = []
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            pbar = tqdm(total=len(self.dataset), desc="生成与评估", unit="主题")
            for item in self.dataset:
                t = item["topic"]
                if self.use_cache and not self.refresh and t in cached_map:
                    prev = cached_map[t]
                    if need_recompute_metrics:
                        attrs = item.get("attributes", {})
                        enh_text = prev.get("enhanced", {}).get("text", "")
                        pure_text = prev.get("pure", {}).get("text", "")
                        em = self.evaluate_text(enh_text, attrs)
                        pm = self.evaluate_text(pure_text, attrs)
                        enhanced_obj = {
                            "topic": t,
                            "text": enh_text,
                            "metrics": em,
                            "time": prev.get("enhanced", {}).get("time", 0)
                        }
                        pure_obj = {
                            "topic": t,
                            "text": pure_text,
                            "metrics": pm,
                            "time": prev.get("pure", {}).get("time", 0)
                        }
                        self.results["enhanced"].append(enhanced_obj)
                        self.results["pure"].append(pure_obj)
                        self.results["metrics"]["enhanced"].append(em)
                        self.results["metrics"]["pure"].append(pm)
                        it = {"topic": t, "enhanced": enhanced_obj, "pure": pure_obj}
                        items_out.append(it)
                    else:
                        self.results["enhanced"].append(prev.get("enhanced", {}))
                        self.results["pure"].append(prev.get("pure", {}))
                        self.results["metrics"]["enhanced"].append(prev.get("enhanced", {}).get("metrics", {}))
                        self.results["metrics"]["pure"].append(prev.get("pure", {}).get("metrics", {}))
                        items_out.append(prev)
                    pbar.update(1)
                else:
                    futures.append(ex.submit(self._process_topic, item))
            for fut in as_completed(futures):
                try:
                    it = fut.result()
                except Exception:
                    it = {"topic": "", "enhanced": {"text": "", "metrics": {}}, "pure": {"text": "", "metrics": {}}}
                self.results["enhanced"].append(it["enhanced"])
                self.results["pure"].append(it["pure"])
                self.results["metrics"]["enhanced"].append(it["enhanced"]["metrics"])
                self.results["metrics"]["pure"].append(it["pure"]["metrics"])
                items_out.append(it)
                # 增量写入缓存
                try:
                    merged = cached_items[:]
                    exist_topics = {ix.get("topic") for ix in merged}
                    if it.get("topic") in exist_topics:
                        merged = [x if x.get("topic") != it.get("topic") else it for x in merged]
                    else:
                        merged.append(it)
                    history = cached_results.get("history", []) if cached_results else []
                    history.append(it)
                    self._save_cached_results({"items": merged, "history": history})
                except Exception:
                    pass
                pbar.update(1)
            pbar.close()
        merged = cached_items[:]
        exist_topics = {it.get("topic") for it in merged}
        for it in items_out:
            if it.get("topic") in exist_topics:
                merged = [x if x.get("topic") != it.get("topic") else it for x in merged]
            else:
                merged.append(it)
        history = cached_results.get("history", []) if cached_results else []
        history.extend(items_out)
        self._save_cached_results({"items": merged, "history": history})

    def _df_metrics(self) -> pd.DataFrame:
        rows = []
        for i in range(len(self.results["enhanced"])):
            t = self.results["enhanced"][i]["topic"]
            em = self.results["enhanced"][i]["metrics"]
            pm = self.results["pure"][i]["metrics"]
            rows.append({"topic": t, "method": "KG增强", **em})
            rows.append({"topic": t, "method": "纯LLM", **pm})
        return pd.DataFrame(rows)

    def save_results(self) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.output_dir, f"ds_course_gen_eval_{ts}.json")
        data = {
            "timestamp": ts,
            "topics": [x["topic"] for x in self.results["enhanced"]],
            "enhanced": self.results["enhanced"],
            "pure": self.results["pure"],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        latest = os.path.join(self.output_dir, "ds_course_gen_eval_latest.json")
        try:
            with open(latest, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return path

    def charts(self) -> List[str]:
        df = self._df_metrics()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = []
        if _HAS_SEABORN:
            sns.set_theme(style="whitegrid")
        fig1, ax1 = plt.subplots(figsize=(10,6))
        all_metrics = ["attribute_coverage","coverage","structure","pedagogy","composite"]
        agg_full = df.groupby("method")[all_metrics].mean()
        labels_map = {
            "attribute_coverage": "Attr Coverage",
            "coverage": "Coverage",
            "structure": "Structure",
            "pedagogy": "Pedagogy",
            "composite": "Composite"
        }
        x = range(len(all_metrics))
        kg_vals = [agg_full.loc["KG增强", m] for m in all_metrics]
        llm_vals = [agg_full.loc["纯LLM", m] for m in all_metrics]
        width = 0.35
        ax1.bar([i - width/2 for i in x], kg_vals, width, label="KG-Enhanced", color="#2E86AB")
        ax1.bar([i + width/2 for i in x], llm_vals, width, label="Vanilla LLM", color="#A23B72")
        ax1.set_xticks(list(x))
        ax1.set_xticklabels([labels_map.get(m, m) for m in all_metrics])
        for i, v in enumerate(kg_vals):
            ax1.text(i - width/2, v + 1, f"{v:.1f}", ha='center', va='bottom', fontproperties=FONT_PROP, fontsize=14)
        for i, v in enumerate(llm_vals):
            ax1.text(i + width/2, v + 1, f"{v:.1f}", ha='center', va='bottom', fontproperties=FONT_PROP, fontsize=14)
        for lab in ax1.get_xticklabels():
            lab.set_fontproperties(FONT_PROP)
            lab.set_fontsize(14)
        for lab in ax1.get_yticklabels():
            lab.set_fontproperties(FONT_PROP)
            lab.set_fontsize(14)
        ax1.set_ylabel("Score (0-100)", fontproperties=FONT_PROP, fontsize=16)
        ax1.set_title("Course Generation Metrics Comparison", fontproperties=FONT_PROP, fontsize=18)
        ax1.legend(prop=FONT_PROP, fontsize=14)
        for lab in ax1.get_yticklabels():
            lab.set_fontproperties(FONT_PROP)
        p1 = os.path.join(self.output_dir, f"figure_metrics_bar_{ts}.png")
        fig1.tight_layout()
        fig1.savefig(p1, dpi=300, bbox_inches="tight")
        try:
            fig1.savefig(os.path.join(self.output_dir, "figure_metrics_bar_latest.png"), dpi=300, bbox_inches="tight")
        except Exception:
            pass
        paths.append(p1)
        plt.close(fig1)

        fig2, ax2 = plt.subplots(figsize=(10,6))
        if _HAS_SEABORN:
            sns.boxplot(data=df, x="method", y="composite", hue="method", dodge=False, legend=False,
                        palette={"KG增强":"#2E86AB", "纯LLM":"#A23B72"}, ax=ax2)
        else:
            methods = ["KG增强","纯LLM"]
            comp = [df[df["method"]==m]["composite"].tolist() for m in methods]
            ax2.boxplot(comp, labels=methods)
        ax2.set_title("Composite Score Distribution", fontproperties=FONT_PROP, fontsize=16)
        ax2.set_ylabel("Composite Score (0-100)", fontproperties=FONT_PROP, fontsize=14)
        for lab in ax2.get_xticklabels():
            lab.set_fontproperties(FONT_PROP)
            lab.set_fontsize(12)
        for lab in ax2.get_yticklabels():
            lab.set_fontproperties(FONT_PROP)
            lab.set_fontsize(12)
        p2 = os.path.join(self.output_dir, f"figure_composite_box_{ts}.png")
        fig2.tight_layout()
        fig2.savefig(p2, dpi=300, bbox_inches="tight")
        try:
            fig2.savefig(os.path.join(self.output_dir, "figure_composite_box_latest.png"), dpi=300, bbox_inches="tight")
        except Exception:
            pass
        paths.append(p2)
        plt.close(fig2)

        fig3, ax3 = plt.subplots(figsize=(10,6))
        dfw = df.pivot(index="topic", columns="method", values="composite").reset_index()
        imp = dfw["KG增强"] - dfw["纯LLM"]
        ax3.scatter(dfw["纯LLM"], imp, c="#2E86AB")
        ax3.axhline(0, color="#666", linestyle="--", linewidth=1)
        ax3.set_xlabel("Vanilla LLM Composite Score", fontproperties=FONT_PROP, fontsize=14)
        ax3.set_ylabel("Improvement (KG-Enhanced − Vanilla)", fontproperties=FONT_PROP, fontsize=14)
        ax3.set_title("Topic-Level Improvement Distribution", fontproperties=FONT_PROP, fontsize=16)
        for lab in ax3.get_xticklabels():
            lab.set_fontproperties(FONT_PROP)
            lab.set_fontsize(12)
        for lab in ax3.get_yticklabels():
            lab.set_fontproperties(FONT_PROP)
            lab.set_fontsize(12)
        p3 = os.path.join(self.output_dir, f"figure_improvement_scatter_{ts}.png")
        fig3.tight_layout()
        fig3.savefig(p3, dpi=300, bbox_inches="tight")
        try:
            fig3.savefig(os.path.join(self.output_dir, "figure_improvement_scatter_latest.png"), dpi=300, bbox_inches="tight")
        except Exception:
            pass
        paths.append(p3)
        plt.close(fig3)

        fig4, ax4 = plt.subplots(figsize=(10,6))
        perf_rows = []
        for i in range(len(self.results["enhanced"])):
            perf_rows.append({"method":"KG增强","time":self.results["enhanced"][i]["time"]})
            perf_rows.append({"method":"纯LLM","time":self.results["pure"][i]["time"]})
        dpf = pd.DataFrame(perf_rows)
        if _HAS_SEABORN:
            sns.violinplot(data=dpf, x="method", y="time", hue="method", dodge=False, legend=False,
                           palette={"KG增强":"#2E86AB", "纯LLM":"#A23B72"}, ax=ax4, cut=0)
        else:
            methods = ["KG增强","纯LLM"]
            times = [dpf[dpf["method"]==m]["time"].tolist() for m in methods]
            ax4.boxplot(times, labels=methods)
        ax4.set_title("Response Time Distribution", fontproperties=FONT_PROP, fontsize=16)
        ax4.set_ylabel("Seconds", fontproperties=FONT_PROP, fontsize=14)
        for lab in ax4.get_xticklabels():
            lab.set_fontproperties(FONT_PROP)
            lab.set_fontsize(12)
        for lab in ax4.get_yticklabels():
            lab.set_fontproperties(FONT_PROP)
            lab.set_fontsize(12)
        p4 = os.path.join(self.output_dir, f"figure_time_violin_{ts}.png")
        fig4.tight_layout()
        fig4.savefig(p4, dpi=300, bbox_inches="tight")
        try:
            fig4.savefig(os.path.join(self.output_dir, "figure_time_violin_latest.png"), dpi=300, bbox_inches="tight")
        except Exception:
            pass
        paths.append(p4)
        plt.close(fig4)

        return paths

    def cleanup_outputs(self, keep: int = 1):
        try:
            files = [f for f in os.listdir(self.output_dir) if os.path.isfile(os.path.join(self.output_dir, f))]
            pngs = sorted([f for f in files if f.endswith('.png') and 'latest' not in f])
            jsons = sorted([f for f in files if f.startswith('ds_course_gen_eval_') and f.endswith('.json')])
            def remove_excess(arr):
                excess = arr[:-keep] if len(arr) > keep else []
                for fname in excess:
                    try:
                        os.remove(os.path.join(self.output_dir, fname))
                    except Exception:
                        pass
            remove_excess(pngs)
            remove_excess(jsons)
        except Exception as e:
            logging.warning(f"清理输出失败: {e}")

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topics", type=str, default="all")
    parser.add_argument("--output_dir", type=str, default=None)
    parser.add_argument("--font_path", type=str, default=None)
    parser.add_argument("--no_cache", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--keep", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--llm_timeout", type=int, default=25)
    args = parser.parse_args()
    # 自动字体加载优先：无需显式传参也能中文显示
    if args.font_path and os.path.exists(args.font_path):
        try:
            fm.fontManager.addfont(args.font_path)
            global FONT_PROP
            FONT_PROP = fm.FontProperties(fname=args.font_path)
            _ensure_chinese_font()
        except Exception as e:
            logging.warning(f"字体文件加载失败: {e}")
            _ensure_chinese_font()
    else:
        _ensure_chinese_font()
    topics_count = -1 if (isinstance(args.topics, str) and args.topics.lower() == 'all') else int(args.topics)
    # 默认强制使用缓存（除非显式 --no_cache），遇到缓存存在时优先复用
    ev = CourseGenEvaluator(output_dir=args.output_dir, topics_count=topics_count, use_cache=(not args.no_cache), refresh=args.refresh, workers=args.workers)
    ev.llm_timeout = args.llm_timeout
    ev.run()
    json_path = ev.save_results()
    figs = ev.charts()
    ev.cleanup_outputs(keep=args.keep)
    print("结果文件:", json_path)
    for p in figs:
        print("图表:", p)

if __name__ == "__main__":
    main()