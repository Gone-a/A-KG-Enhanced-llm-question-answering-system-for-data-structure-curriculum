import os
import sys
import json
import time
import logging
import jieba
import nltk
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge import Rouge
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List, Dict, Any
from tqdm import tqdm
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_manager import get_config_manager
from modules.doubao_llm import DoubaoLLM
from modules.knowledge_graph_query import KnowledgeGraphQuery
from modules.kg_llm_enhancer import KGLLMEnhancer

from matplotlib import font_manager as fm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ensure Chinese Font for Matplotlib
def _ensure_chinese_font():
    plt.rcParams['axes.unicode_minus'] = False
    candidates = [
        'Noto Sans CJK SC', 'Source Han Sans SC', 'WenQuanYi Micro Hei',
        'Microsoft YaHei', 'SimHei', 'DejaVu Sans'
    ]
    for name in candidates:
        try:
            prop = fm.FontProperties(family=name)
            path = fm.findfont(prop, fallback_to_default=False)
            if os.path.exists(path):
                plt.rcParams['font.family'] = name
                plt.rcParams['font.sans-serif'] = [name]
                return
        except Exception:
            continue
    # Fallback to font path if needed, similar to other scripts
    fallback_paths = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'
    ]
    for fp in fallback_paths:
        if os.path.exists(fp):
            fm.fontManager.addfont(fp)
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = [os.path.basename(fp)]
            return

_ensure_chinese_font()

class MockKGQuery:
    def __init__(self, nodes, rels):
        self.nodes = nodes
        self.rels = rels

    def find_entity_relations(self, topic: str, limit: int = 50) -> List[Dict[str, Any]]:
        # Simulate KG query using local cache
        results = []
        # Find node properties first
        node_attrs = {}
        for n in self.nodes:
            props = n.get("properties", {})
            name = n.get("name") or props.get("name")
            if name == topic:
                node_attrs = props
                break
        
        # Find relations
        count = 0
        for r in self.rels:
            if count >= limit: break
            e1 = r.get("startNode") or r.get("entity1") or r.get("source")
            e2 = r.get("endNode") or r.get("entity2") or r.get("target")
            rel_type = r.get("type") or r.get("relation")
            
            if isinstance(e1, str) and topic in e1:
                results.append({
                    "entity1": e1, 
                    "entity2": e2, 
                    "relation": rel_type,
                    "entity1_attributes": node_attrs if e1 == topic else {}
                })
                count += 1
            elif isinstance(e2, str) and topic in e2:
                results.append({
                    "entity1": e1, 
                    "entity2": e2, 
                    "relation": rel_type,
                    "entity2_attributes": node_attrs if e2 == topic else {}
                })
                count += 1
                
        # If no relations found but we have node attributes, add a dummy entry to carry attributes
        if not results and node_attrs:
             results.append({
                "entity1": topic,
                "entity2": "",
                "relation": "self",
                "entity1_attributes": node_attrs
             })
             
        return results

class ModelEvaluator:
    def __init__(self, output_dir="evaluation_results"):
        self.config = get_config_manager()
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Initialize components
        self._init_llm()
        self._init_kg()
        
        # Initialize KG-LLM Enhancer
        if self.llm_client:
            # We can use enhancer even if KG is not connected (it might use fallback or we mock it)
            # However, KGLLMEnhancer expects a KGQuery object.
            # If self.kg_query is None, we need a MockKGQuery that uses local cache
            if not self.kg_query:
                 self.kg_query = MockKGQuery(self.nodes_cache, self.relationships_cache)
            self.enhancer = KGLLMEnhancer(self.llm_client, self.kg_query)
        else:
            self.enhancer = None
            logging.warning("KG-LLM Enhancer initialization failed due to missing components.")

        # Initialize Rouge
        self.rouge = Rouge()
        
        # Ensure NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')

    def _init_llm(self):
        try:
            api_conf = self.config.get_api_config()
            self.llm_client = DoubaoLLM(
                user_api_key=api_conf.get("ark_api_key"),
                user_model_id=api_conf.get("doubao_model_id"),
                base_url=api_conf.get("base_url")
            )
            logging.info("LLM initialized successfully.")
        except Exception as e:
            logging.error(f"LLM initialization failed: {e}")
            self.llm_client = None

    def _init_kg(self):
        try:
            db_conf = self.config.get_database_config()
            self.kg_query = KnowledgeGraphQuery(db_conf["uri"], db_conf["user_name"], db_conf["password"])
            logging.info("Knowledge Graph initialized successfully.")
        except Exception as e:
            logging.warning(f"Neo4j connection failed, falling back to local KG data: {e}")
            self.kg_query = None # Will rely on local cache if needed, but for now just fail gracefully or mock
            # Try to load local cache similar to eval_ds_course_generation.py
            self._load_local_kg()

    def _load_local_kg(self):
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "neo4j", "data")
        nodes_path = os.path.join(base, "nodes.json")
        rels_path = os.path.join(base, "relationships.json")
        self.nodes_cache = []
        self.relationships_cache = []
        try:
            if os.path.exists(nodes_path):
                with open(nodes_path, "r", encoding="utf-8") as f:
                    self.nodes_cache = json.load(f)
            if os.path.exists(rels_path):
                with open(rels_path, "r", encoding="utf-8") as f:
                    self.relationships_cache = json.load(f)
            if self.nodes_cache:
                logging.info(f"Loaded {len(self.nodes_cache)} nodes from local cache.")
        except Exception as e:
            logging.warning(f"Local KG load failed: {e}")

    def calculate_bleu(self, reference, candidate):
        """Calculate BLEU score using jieba for Chinese tokenization"""
        ref_tokens = list(jieba.cut(reference))
        cand_tokens = list(jieba.cut(candidate))
        smooth = SmoothingFunction().method1
        return sentence_bleu([ref_tokens], cand_tokens, smoothing_function=smooth)

    def calculate_rouge(self, reference, candidate):
        """Calculate ROUGE scores"""
        # Rouge expects space-separated tokens for Chinese
        ref_tokens = ' '.join(jieba.cut(reference))
        cand_tokens = ' '.join(jieba.cut(candidate))
        if not ref_tokens or not cand_tokens:
            return {'rouge-1': {'f': 0}, 'rouge-2': {'f': 0}, 'rouge-l': {'f': 0}}
        try:
            scores = self.rouge.get_scores(cand_tokens, ref_tokens)[0]
            return scores
        except Exception:
            return {'rouge-1': {'f': 0}, 'rouge-2': {'f': 0}, 'rouge-l': {'f': 0}}

    def calculate_similarity(self, text1, text2):
        """Calculate Cosine Similarity using TF-IDF"""
        # Use character-level n-grams for better Chinese similarity
        vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(1, 2))
        try:
            tfidf = vectorizer.fit_transform([text1, text2])
            return cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        except ValueError:
            return 0.0

    def get_ground_truth(self, topic):
        """
        Ideally, this should fetch human-verified content.
        For this automated test, we'll construct a 'pseudo-ground-truth' 
        from the Knowledge Graph attributes directly if available.
        """
        attributes = {}
        
        if self.kg_query:
            try:
                rels = self.kg_query.find_entity_relations(topic, limit=50)
                for r in rels:
                    if r.get('entity1') == topic:
                        attributes.update(r.get('entity1_attributes', {}))
                    elif r.get('entity2') == topic:
                        attributes.update(r.get('entity2_attributes', {}))
            except Exception:
                pass
        
        # Fallback to local cache if KG query failed or returned nothing
        if not attributes and hasattr(self, 'nodes_cache'):
            for n in self.nodes_cache:
                props = n.get("properties", {})
                name = n.get("name") or props.get("name")
                if name == topic:
                    attributes = props
                    break

        if not attributes:
            return ""
            
        # Construct a descriptive text from attributes
        truth_parts = []
        if 'description' in attributes:
            truth_parts.append(attributes['description'])
        if 'properties' in attributes:
            truth_parts.append(attributes['properties'])
        if 'common_operations' in attributes:
            truth_parts.append(attributes['common_operations'])
            
        return "\n".join(truth_parts)


    def run_comparison(self, topics: List[str]):
        results = []
        
        print(f"Starting comparison for {len(topics)} topics...")
        
        for topic in tqdm(topics):
            print(f"\nEvaluating topic: {topic}")
            
            # 1. Get Ground Truth (from KG attributes)
            ground_truth = self.get_ground_truth(topic)
            if not ground_truth:
                logging.warning(f"No ground truth found for {topic}, metrics requiring reference will be 0.")
            
            # 2. Generate with Pure LLM
            start_time = time.time()
            try:
                pure_response = self.llm_client.generate_response(f"请详细介绍数据结构中的：{topic}").content
            except Exception as e:
                logging.error(f"Pure LLM generation failed: {e}")
                pure_response = ""
            pure_time = time.time() - start_time
            
            # 3. Generate with KG-LLM
            start_time = time.time()
            try:
                kg_response = self.enhancer.generate_with_kg(topic)
            except Exception as e:
                logging.error(f"KG-LLM generation failed: {e}")
                kg_response = ""
            kg_time = time.time() - start_time
            
            # 4. Calculate Metrics
            metrics = {
                "topic": topic,
                "pure_time": pure_time,
                "kg_time": kg_time,
                "pure_len": len(pure_response),
                "kg_len": len(kg_response)
            }
            
            # Semantic Similarity
            if ground_truth:
                metrics["pure_sim"] = self.calculate_similarity(pure_response, ground_truth)
                metrics["kg_sim"] = self.calculate_similarity(kg_response, ground_truth)
                
                pure_rouge = self.calculate_rouge(ground_truth, pure_response)
                kg_rouge = self.calculate_rouge(ground_truth, kg_response)
                metrics["pure_rouge_l"] = pure_rouge['rouge-l']['f']
                metrics["kg_rouge_l"] = kg_rouge['rouge-l']['f']
                
                metrics["pure_bleu"] = self.calculate_bleu(ground_truth, pure_response)
                metrics["kg_bleu"] = self.calculate_bleu(ground_truth, kg_response)
            else:
                metrics["pure_sim"] = 0.0
                metrics["kg_sim"] = 0.0
                metrics["pure_rouge_l"] = 0.0
                metrics["kg_rouge_l"] = 0.0
                metrics["pure_bleu"] = 0.0
                metrics["kg_bleu"] = 0.0
                
            # Entity Recall
            try:
                # Use MockKGQuery if using local fallback, otherwise access enhancer's kg_query
                kg_query = self.enhancer.kg_query
                
                # Check if kg_query is initialized and has find_entity_relations
                if kg_query and hasattr(kg_query, 'find_entity_relations'):
                    relations = kg_query.find_entity_relations(topic)
                    related_entities = set()
                    for r in relations:
                        if r['entity1'] != topic: related_entities.add(r['entity1'])
                        if r['entity2'] != topic: related_entities.add(r['entity2'])
                    
                    metrics["pure_entity_recall"] = sum(1 for e in related_entities if e in pure_response)
                    metrics["kg_entity_recall"] = sum(1 for e in related_entities if e in kg_response)
                    metrics["total_entities"] = len(related_entities)
                else:
                    logging.warning(f"KG query capability not available for topic {topic}")
                    metrics["pure_entity_recall"] = 0
                    metrics["kg_entity_recall"] = 0
                    metrics["total_entities"] = 0

            except Exception as e:
                logging.error(f"Entity recall calculation failed: {e}")
                metrics["pure_entity_recall"] = 0
                metrics["kg_entity_recall"] = 0
                metrics["total_entities"] = 0

            results.append(metrics)
            
        return pd.DataFrame(results)

    def visualize_results(self, df):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Similarity Comparison
        if "pure_sim" in df.columns:
            plt.figure(figsize=(10, 6))
            x = np.arange(len(df))
            width = 0.35
            plt.bar(x - width/2, df["pure_sim"], width, label='Vanilla LLM')
            plt.bar(x + width/2, df["kg_sim"], width, label='KG-LLM')
            plt.xlabel('Topics')
            plt.ylabel('Cosine Similarity with Ground Truth')
            plt.title('Content Accuracy Comparison (Similarity to KG Truth)')
            plt.xticks(x, df["topic"], rotation=45)
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, f"similarity_comparison_{timestamp}.png"))
            plt.close()

        # 2. Entity Recall Comparison
        if "pure_entity_recall" in df.columns:
            plt.figure(figsize=(10, 6))
            x = np.arange(len(df))
            width = 0.35
            plt.bar(x - width/2, df["pure_entity_recall"], width, label='Vanilla LLM')
            plt.bar(x + width/2, df["kg_entity_recall"], width, label='KG-LLM')
            # Fix for pandas series indexing error in matplotlib
            total_entities = df["total_entities"].to_numpy()
            plt.plot(x, total_entities, 'r--', label='Total Entities (KG)', marker='o')
            plt.xlabel('Topics')
            plt.ylabel('Number of Related Entities Mentioned')
            plt.title('Knowledge Density Comparison (Entity Recall)')
            plt.xticks(x, df["topic"], rotation=45)
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, f"entity_recall_{timestamp}.png"))
            plt.close()

        kg_sim = float(df["kg_sim"].mean()) if "kg_sim" in df.columns else 0.0
        pure_sim = float(df["pure_sim"].mean()) if "pure_sim" in df.columns else 0.0
        kg_rouge = float(df["kg_rouge_l"].mean()) if "kg_rouge_l" in df.columns else 0.0
        pure_rouge = float(df["pure_rouge_l"].mean()) if "pure_rouge_l" in df.columns else 0.0
        kg_bleu = float(df["kg_bleu"].mean()) if "kg_bleu" in df.columns else 0.0
        pure_bleu = float(df["pure_bleu"].mean()) if "pure_bleu" in df.columns else 0.0
        if {"pure_entity_recall", "kg_entity_recall", "total_entities"}.issubset(df.columns):
            pure_ent_rates = np.where(df["total_entities"] > 0, df["pure_entity_recall"] / df["total_entities"], 0.0)
            kg_ent_rates = np.where(df["total_entities"] > 0, df["kg_entity_recall"] / df["total_entities"], 0.0)
            pure_ent = float(np.mean(pure_ent_rates))
            kg_ent = float(np.mean(kg_ent_rates))
        else:
            pure_ent = 0.0
            kg_ent = 0.0
        kg_values = [kg_sim, kg_rouge, kg_bleu, kg_ent]
        llm_values = [pure_sim, pure_rouge, pure_bleu, pure_ent]
        labels = ["Similarity", "ROUGE-L", "BLEU", "Entity Recall (Rate)"]
        plt.figure(figsize=(9, 6))
        x = np.arange(len(labels))
        width = 0.26
        colors = ['#2E86AB', '#A23B72']
        bars1 = plt.bar(x - width/2, llm_values, width, label='Vanilla LLM', color=colors[1], alpha=0.9, edgecolor='#2F2F2F', linewidth=0.6)
        bars2 = plt.bar(x + width/2, kg_values, width, label='KG-LLM', color=colors[0], alpha=0.9, edgecolor='#2F2F2F', linewidth=0.6)
        plt.xticks(x, labels, fontsize=15)
        plt.ylabel('Metric Value', fontsize=16)
        plt.title('Metrics Comparison (Raw Averages Across Topics)', fontsize=18)
        plt.grid(axis='y', linestyle='--', alpha=0.25)
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, 1.03), ncol=2, frameon=False, fontsize=14)
        ymax = max(max(llm_values), max(kg_values)) * 1.15
        plt.ylim(0, ymax)
        for bar in bars1:
            h = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, h, f"{h:.3f}", ha='center', va='bottom', fontsize=13)
        for bar in bars2:
            h = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, h, f"{h:.3f}", ha='center', va='bottom', fontsize=13)
        plt.margins(x=0.04)
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, f"figure_metrics_bar_{timestamp}.png"), dpi=300, bbox_inches='tight')
        try:
            plt.savefig(os.path.join(self.output_dir, "figure_metrics_bar_latest.png"), dpi=300, bbox_inches='tight')
        except Exception:
            pass
        plt.close()

        # 3. Time Comparison
        plt.figure(figsize=(10, 6))
        x = np.arange(len(df))
        width = 0.35
        plt.bar(x - width/2, df["pure_time"], width, label='Vanilla LLM')
        plt.bar(x + width/2, df["kg_time"], width, label='KG-LLM')
        plt.xlabel('Topics')
        plt.ylabel('Response Time (s)')
        plt.title('Performance Comparison (Response Time)')
        plt.xticks(x, df["topic"], rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, f"time_comparison_{timestamp}.png"))
        plt.close()
        
        # Save raw data
        df.to_csv(os.path.join(self.output_dir, f"evaluation_metrics_{timestamp}.csv"), index=False)
        print(f"Results and charts saved to {self.output_dir}")

def regenerate_metrics_bar_from_csv(csv_path, output_png_path=None):
    df = pd.read_csv(csv_path)
    kg_sim = float(df["kg_sim"].mean()) if "kg_sim" in df.columns else 0.0
    pure_sim = float(df["pure_sim"].mean()) if "pure_sim" in df.columns else 0.0
    kg_rouge = float(df["kg_rouge_l"].mean()) if "kg_rouge_l" in df.columns else 0.0
    pure_rouge = float(df["pure_rouge_l"].mean()) if "pure_rouge_l" in df.columns else 0.0
    kg_bleu = float(df["kg_bleu"].mean()) if "kg_bleu" in df.columns else 0.0
    pure_bleu = float(df["pure_bleu"].mean()) if "pure_bleu" in df.columns else 0.0
    if {"pure_entity_recall", "kg_entity_recall", "total_entities"}.issubset(df.columns):
        pure_ent_rates = np.where(df["total_entities"] > 0, df["pure_entity_recall"] / df["total_entities"], 0.0)
        kg_ent_rates = np.where(df["total_entities"] > 0, df["kg_entity_recall"] / df["total_entities"], 0.0)
        pure_ent = float(np.mean(pure_ent_rates))
        kg_ent = float(np.mean(kg_ent_rates))
    else:
        pure_ent = 0.0
        kg_ent = 0.0
    kg_values = [kg_sim, kg_rouge, kg_bleu, kg_ent]
    llm_values = [pure_sim, pure_rouge, pure_bleu, pure_ent]
    labels = ["Similarity", "ROUGE-L", "BLEU", "Entity Recall (Rate)"]
    fig = plt.figure(figsize=(9, 6))
    x = np.arange(len(labels))
    width = 0.26
    colors = ['#2E86AB', '#A23B72']
    bars1 = plt.bar(x - width/2, llm_values, width, label='Vanilla LLM', color=colors[1], alpha=0.9, edgecolor='#2F2F2F', linewidth=0.6)
    bars2 = plt.bar(x + width/2, kg_values, width, label='KG-LLM', color=colors[0], alpha=0.9, edgecolor='#2F2F2F', linewidth=0.6)
    plt.xticks(x, labels, fontsize=15)
    plt.ylabel('Metric Value', fontsize=16)
    plt.title('Metrics Comparison (Raw Averages Across Topics)', fontsize=18)
    plt.grid(axis='y', linestyle='--', alpha=0.25)
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, 1.03), ncol=2, frameon=False, fontsize=14)
    ymax = max(max(llm_values), max(kg_values)) * 1.15
    plt.ylim(0, ymax)
    for bar in bars1:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, h, f"{h:.3f}", ha='center', va='bottom', fontsize=13)
    for bar in bars2:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, h, f"{h:.3f}", ha='center', va='bottom', fontsize=13)
    plt.margins(x=0.04)
    plt.tight_layout()
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "evaluation_results")
    os.makedirs(output_dir, exist_ok=True)
    if output_png_path:
        plt.savefig(output_png_path, dpi=300, bbox_inches='tight')
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plt.savefig(os.path.join(output_dir, f"figure_metrics_bar_{timestamp}.png"), dpi=300, bbox_inches='tight')
        try:
            plt.savefig(os.path.join(output_dir, "figure_metrics_bar_latest.png"), dpi=300, bbox_inches='tight')
        except Exception:
            pass
    plt.close(fig)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--from_csv", type=str, default=None)
    parser.add_argument("--overwrite_png", type=str, default=None)
    args = parser.parse_args()
    if args.from_csv:
        regenerate_metrics_bar_from_csv(args.from_csv, args.overwrite_png)
        return
    
    # Load topics from vocab_dict.csv
    vocab_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vocab_dict.csv")
    test_topics = []
    if os.path.exists(vocab_path):
        try:
            vocab_df = pd.read_csv(vocab_path, header=None, names=["entity", "type"])
            # Filter for DataStructure and Algorithm types if desired, or take all
            # Here we take top 50 entities to keep evaluation time reasonable, 
            # or you can use .sample(50) for random selection.
            # Let's use a mix of DataStructure and Algorithm
            ds_topics = vocab_df[vocab_df["type"] == "DataStructure"]["entity"].tolist()
            algo_topics = vocab_df[vocab_df["type"] == "Algorithm"]["entity"].tolist()
            
            # Combine and take up to 50 unique topics
            test_topics = list(set(ds_topics[:25] + algo_topics[:25]))
            
            # If we still have fewer than 50, add more
            if len(test_topics) < 50:
                remaining = [t for t in vocab_df["entity"].tolist() if t not in test_topics]
                test_topics.extend(remaining[:50-len(test_topics)])
                
            print(f"Loaded {len(test_topics)} topics from {vocab_path}")
        except Exception as e:
            print(f"Error reading vocab_dict.csv: {e}")
            test_topics = ["二叉树", "哈希表", "快速排序", "链表", "图的遍历"]
    else:
        print(f"vocab_dict.csv not found at {vocab_path}, using default topics.")
        test_topics = ["二叉树", "哈希表", "快速排序", "链表", "图的遍历"]

    evaluator = ModelEvaluator()
    if not evaluator.llm_client or not evaluator.kg_query:
        print("Evaluation cannot proceed due to missing LLM or KG connection.")
        return
    print("Starting KG-LLM vs Vanilla LLM Evaluation...")
    df_results = evaluator.run_comparison(test_topics)
    print("\nEvaluation Results Summary:")
    print(df_results.mean(numeric_only=True))
    evaluator.visualize_results(df_results)

if __name__ == "__main__":
    main()
