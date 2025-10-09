#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱与大语言模型对比实验
对比有知识图谱增强和纯大语言模型在数据结构算法题目上的表现
"""

import os
import sys
import time
import re
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from typing import List, Dict, Any, Tuple
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_manager import get_config_manager
from modules.intent_recognition import IntentRecognizer
from modules.knowledge_graph_query import KnowledgeGraphQuery
from modules.backend_api import APIHandler
from modules.doubao_llm import DoubaoLLM

# 导入知识库
try:
    from intent_recognition.knowledge_base import KNOWLEDGE_BASE
except ImportError:
    KNOWLEDGE_BASE = {"entities": {}, "relations": {}}

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ExperimentRunner:
    """实验运行器"""
    
    def __init__(self):
        self.config = get_config_manager()
        self.questions = []
        self.answers = []
        self.results = {
            'kg_enhanced': [],  # 知识图谱增强结果
            'pure_llm': [],     # 纯LLM结果
            'performance': {
                'kg_enhanced': [],  # 响应时间
                'pure_llm': []
            }
        }
        
        # 初始化组件
        self._initialize_components()
        
    def _initialize_components(self):
        """初始化实验组件"""
        logging.info("初始化实验组件...")
        
        # 初始化LLM客户端
        try:
            api_config = self.config.get_api_config()
            llm_config = self.config.get_llm_config()
            self.llm_client = DoubaoLLM(
                user_api_key=api_config.get('ark_api_key'),
                user_model_id=api_config.get('doubao_model_id'),
                base_url=api_config.get('base_url')
            )
            self.llm_client.set_parameters(
                max_tokens=llm_config['max_tokens'],
                temperature=llm_config['temperature']
            )
        except Exception as e:
            logging.error(f"LLM初始化失败: {e}")
            raise
        
        # 尝试初始化知识图谱相关组件
        self.kg_available = False
        try:
            # 初始化意图识别器
            model_path = self.config.get('model.nlu_model_path')
            self.intent_recognizer = IntentRecognizer(model_path, KNOWLEDGE_BASE)
            
            # 初始化知识图谱查询器
            db_config = self.config.get_database_config()
            self.kg_query = KnowledgeGraphQuery(
                db_config['uri'],
                db_config['user_name'], 
                db_config['password']
            )
            
            # 初始化API处理器（用于知识图谱增强）
            self.api_handler = APIHandler(self.intent_recognizer, self.kg_query, self.llm_client)
            self.kg_available = True
            logging.info("知识图谱组件初始化成功")
        except Exception as e:
            logging.warning(f"知识图谱组件初始化失败，将使用模拟模式: {e}")
            self.kg_available = False
        
        logging.info("组件初始化完成")
    
    def load_data(self):
        """加载题目和答案数据"""
        logging.info("加载题目和答案数据...")
        
        # 读取题目文件
        question_file = os.path.join(os.path.dirname(__file__), 'data', 'ques.txt')
        with open(question_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # 按行分割内容
        lines = content.split('\n')
        
        current_question = None
        current_options = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 检查是否是选项
            if re.match(r'^[A-D]\.\s', line):
                current_options.append(line)
            # 检查是否是答案
            elif line.startswith('答案：'):
                answer_match = re.search(r'答案：([A-D])', line)
                if answer_match and current_question and len(current_options) == 4:
                    answer = answer_match.group(1)
                    
                    question = {
                        'text': current_question,
                        'options': current_options
                    }
                    self.questions.append(question)
                    self.answers.append(answer)
                    
                    # 重置当前题目状态
                    current_question = None
                    current_options = []
            # 如果不是选项也不是答案，且当前没有题目，则作为新题目
            elif not current_question and not re.match(r'^[A-D]\.\s', line) and not line.startswith('答案：'):
                current_question = line
        
        logging.info(f"加载完成: {len(self.questions)}道题目, {len(self.answers)}个答案")
        
        # 确保题目和答案数量匹配
        min_count = min(len(self.questions), len(self.answers))
        self.questions = self.questions[:min_count]
        self.answers = self.answers[:min_count]
        
        logging.info(f"实际使用: {len(self.questions)}道题目")
    
    def kg_enhanced_answer(self, question: Dict[str, Any]) -> Tuple[str, float]:
        """使用知识图谱增强的问答"""
        start_time = time.time()
        
        try:
            # 构建完整的问题文本
            full_question = question['text'] + '\n' + '\n'.join(question['options'])
            
            
            # 使用API处理器进行查询（包含知识图谱增强）
            result = self.api_handler.process_query(full_question)
            
            # 提取答案
            if result.get('success') and 'message' in result:
                response_text = result['message']
            else:
                response_text = "无法获取答案"
           
            
            # 从响应中提取选项答案
            answer = self._extract_answer_from_response(response_text)
            
        except Exception as e:
            logging.error(f"知识图谱增强问答失败: {e}")
            answer = "ERROR"
        
        response_time = time.time() - start_time
        return answer, response_time
    
    def pure_llm_answer(self, question: Dict[str, Any]) -> Tuple[str, float]:
        """使用纯大语言模型问答"""
        start_time = time.time()
        
        try:
            # 构建完整的问题文本
            full_question = question['text'] + '\n' + '\n'.join(question['options'])
            
            # 添加明确的指令
            prompt = f"""请回答以下数据结构与算法选择题，只需要回答选项字母（A、B、C或D）：

{full_question}

请直接回答选项字母："""
            
            # 直接调用LLM
            response = self.llm_client.generate_response(prompt)
            response_text = response.content
            
            # 从响应中提取选项答案
            answer = self._extract_answer_from_response(response_text)
            
        except Exception as e:
            logging.error(f"纯LLM问答失败: {e}")
            answer = "ERROR"
        
        response_time = time.time() - start_time
        return answer, response_time
    
    def _extract_answer_from_response(self, response_text: str) -> str:
        """从响应文本中提取答案选项"""
        # 查找明确的选项答案
        patterns = [
            r'答案[是为]?\s*[：:]\s*([A-D])',
            r'选择\s*([A-D])',
            r'正确答案[是为]?\s*([A-D])',
            r'^([A-D])[）)]',
            r'([A-D])[）)]\s*是?正确',
            r'选项\s*([A-D])',
            r'\b([A-D])\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response_text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).upper()
        
        # 如果没有找到明确答案，返回第一个出现的选项字母
        for char in ['A', 'B', 'C', 'D']:
            if char in response_text.upper():
                return char
        
        return "UNKNOWN"
    
    def run_experiment(self):
        """运行完整实验"""
        logging.info("开始运行对比实验...")
        
        total_questions = len(self.questions)
        
        for i, question in enumerate(self.questions):
            logging.info(f"处理第 {i+1}/{total_questions} 题")
            
            # 知识图谱增强问答
            kg_answer, kg_time = self.kg_enhanced_answer(question)
            self.results['kg_enhanced'].append(kg_answer)
            self.results['performance']['kg_enhanced'].append(kg_time)
            
            # 纯LLM问答
            llm_answer, llm_time = self.pure_llm_answer(question)
            self.results['pure_llm'].append(llm_answer)
            self.results['performance']['pure_llm'].append(llm_time)
            
            logging.info(f"题目 {i+1}: KG增强={kg_answer}, 纯LLM={llm_answer}, 正确答案={self.answers[i]}")
            
            # 避免请求过于频繁
            time.sleep(0.5)
        
        logging.info("实验完成")
    
    def calculate_accuracy(self):
        """计算准确率"""
        if len(self.answers) == 0:
            logging.warning("没有题目数据，无法计算准确率")
            return {
                'kg_enhanced': {
                    'correct': 0,
                    'total': 0,
                    'accuracy': 0.0
                },
                'pure_llm': {
                    'correct': 0,
                    'total': 0,
                    'accuracy': 0.0
                }
            }
        
        kg_correct = sum(1 for i, answer in enumerate(self.results['kg_enhanced']) 
                        if answer == self.answers[i])
        llm_correct = sum(1 for i, answer in enumerate(self.results['pure_llm']) 
                         if answer == self.answers[i])
        
        total = len(self.answers)
        kg_accuracy = kg_correct / total * 100
        llm_accuracy = llm_correct / total * 100
        
        return {
            'kg_enhanced': {
                'correct': kg_correct,
                'total': total,
                'accuracy': kg_accuracy
            },
            'pure_llm': {
                'correct': llm_correct,
                'total': total,
                'accuracy': llm_accuracy
            }
        }
    
    def analyze_performance(self):
        """分析性能指标"""
        kg_times = self.results['performance']['kg_enhanced']
        llm_times = self.results['performance']['pure_llm']
        
        return {
            'kg_enhanced': {
                'avg_time': sum(kg_times) / len(kg_times),
                'min_time': min(kg_times),
                'max_time': max(kg_times),
                'total_time': sum(kg_times)
            },
            'pure_llm': {
                'avg_time': sum(llm_times) / len(llm_times),
                'min_time': min(llm_times),
                'max_time': max(llm_times),
                'total_time': sum(llm_times)
            }
        }
    
    def generate_charts(self):
        """生成对比分析图表"""
        logging.info("生成对比分析图表...")
        
        # 检查是否有数据
        if len(self.answers) == 0:
            logging.warning("没有题目数据，跳过图表生成")
            return self.calculate_accuracy(), self.analyze_performance()
        
        # 计算准确率和性能指标
        accuracy_stats = self.calculate_accuracy()
        performance_stats = self.analyze_performance()
        
        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('知识图谱增强 vs 纯大语言模型对比分析', fontsize=16, fontweight='bold')
        
        # 1. 准确率对比柱状图
        ax1 = axes[0, 0]
        methods = ['知识图谱增强', '纯大语言模型']
        accuracies = [accuracy_stats['kg_enhanced']['accuracy'], 
                     accuracy_stats['pure_llm']['accuracy']]
        colors = ['#2E86AB', '#A23B72']
        
        bars = ax1.bar(methods, accuracies, color=colors, alpha=0.8)
        ax1.set_title('准确率对比', fontweight='bold')
        ax1.set_ylabel('准确率 (%)')
        ax1.set_ylim(0, 100)
        
        # 添加数值标签
        for bar, acc in zip(bars, accuracies):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{acc:.1f}%', ha='center', va='bottom', fontweight='bold')
        
        # 2. 响应时间对比箱线图
        ax2 = axes[0, 1]
        time_data = [self.results['performance']['kg_enhanced'],
                    self.results['performance']['pure_llm']]
        
        if len(time_data[0]) > 0 and len(time_data[1]) > 0:
            box_plot = ax2.boxplot(time_data, labels=methods, patch_artist=True)
            box_plot['boxes'][0].set_facecolor(colors[0])
            box_plot['boxes'][1].set_facecolor(colors[1])
        else:
            ax2.text(0.5, 0.5, '无性能数据', ha='center', va='center', transform=ax2.transAxes)
        
        ax2.set_title('响应时间分布', fontweight='bold')
        ax2.set_ylabel('响应时间 (秒)')
        
        # 3. 逐题准确性对比
        ax3 = axes[1, 0]
        if len(self.answers) > 0:
            question_nums = list(range(1, len(self.answers) + 1))
            kg_correct_list = [1 if self.results['kg_enhanced'][i] == self.answers[i] else 0 
                              for i in range(len(self.answers))]
            llm_correct_list = [1 if self.results['pure_llm'][i] == self.answers[i] else 0 
                               for i in range(len(self.answers))]
            
            # 计算滑动平均准确率
            window_size = min(10, len(self.answers))
            kg_rolling = pd.Series(kg_correct_list).rolling(window=window_size, min_periods=1).mean()
            llm_rolling = pd.Series(llm_correct_list).rolling(window=window_size, min_periods=1).mean()
            
            ax3.plot(question_nums, kg_rolling, label='知识图谱增强', color=colors[0], linewidth=2)
            ax3.plot(question_nums, llm_rolling, label='纯大语言模型', color=colors[1], linewidth=2)
            ax3.set_title(f'滑动平均准确率趋势 (窗口大小: {window_size})', fontweight='bold')
            ax3.set_xlabel('题目编号')
            ax3.set_ylabel('准确率')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, '无题目数据', ha='center', va='center', transform=ax3.transAxes)
        
        # 4. 性能指标对比雷达图
        ax4 = axes[1, 1]
        
        if len(self.answers) > 0 and len(self.results['performance']['kg_enhanced']) > 0:
            # 准备雷达图数据
            categories = ['准确率', '平均响应时间\n(归一化)', '稳定性\n(1/标准差)']
            
            # 归一化数据
            kg_acc_norm = accuracy_stats['kg_enhanced']['accuracy'] / 100
            llm_acc_norm = accuracy_stats['pure_llm']['accuracy'] / 100
            
            max_time = max(performance_stats['kg_enhanced']['avg_time'], 
                          performance_stats['pure_llm']['avg_time'])
            kg_time_norm = 1 - (performance_stats['kg_enhanced']['avg_time'] / max_time) if max_time > 0 else 0
            llm_time_norm = 1 - (performance_stats['pure_llm']['avg_time'] / max_time) if max_time > 0 else 0
            
            kg_std = pd.Series(self.results['performance']['kg_enhanced']).std()
            llm_std = pd.Series(self.results['performance']['pure_llm']).std()
            max_std = max(kg_std, llm_std)
            kg_stability = 1 - (kg_std / max_std) if max_std > 0 else 1
            llm_stability = 1 - (llm_std / max_std) if max_std > 0 else 1
            
            kg_values = [kg_acc_norm, kg_time_norm, kg_stability]
            llm_values = [llm_acc_norm, llm_time_norm, llm_stability]
            
            # 创建简化的对比图
            x = range(len(categories))
            width = 0.35
            
            ax4.bar([i - width/2 for i in x], kg_values, width, label='知识图谱增强', 
                   color=colors[0], alpha=0.8)
            ax4.bar([i + width/2 for i in x], llm_values, width, label='纯大语言模型', 
                   color=colors[1], alpha=0.8)
            
            ax4.set_title('综合性能对比', fontweight='bold')
            ax4.set_ylabel('归一化得分')
            ax4.set_xticks(x)
            ax4.set_xticklabels(categories)
            ax4.legend()
            ax4.set_ylim(0, 1)
        else:
            ax4.text(0.5, 0.5, '无性能数据', ha='center', va='center', transform=ax4.transAxes)
        
        plt.tight_layout()
        
        # 保存图表
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chart_file = f'/root/KG_inde/test/comparison_analysis_{timestamp}.png'
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        logging.info(f"图表已保存: {chart_file}")
        
        plt.show()
        
        return accuracy_stats, performance_stats
    
    def save_results(self):
        """保存实验结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f'/root/KG_inde/test/experiment_results_{timestamp}.json'
        
        # 准备保存的数据
        save_data = {
            'timestamp': timestamp,
            'total_questions': len(self.questions),
            'results': self.results,
            'correct_answers': self.answers,
            'accuracy_stats': self.calculate_accuracy(),
            'performance_stats': self.analyze_performance()
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        logging.info(f"实验结果已保存: {results_file}")
        return results_file

def main():
    """主函数"""
    print("=" * 60)
    print("知识图谱与大语言模型对比实验")
    print("=" * 60)
    
    try:
        # 创建实验运行器
        runner = ExperimentRunner()
        
        # 加载数据
        runner.load_data()
        
        # 运行实验
        runner.run_experiment()
        
        # 生成分析图表
        accuracy_stats, performance_stats = runner.generate_charts()
        
        # 保存结果
        results_file = runner.save_results()
        
        # 打印总结
        print("\n" + "=" * 60)
        print("实验结果总结")
        print("=" * 60)
        
        print(f"\n📊 准确率对比:")
        print(f"  知识图谱增强: {accuracy_stats['kg_enhanced']['correct']}/{accuracy_stats['kg_enhanced']['total']} "
              f"({accuracy_stats['kg_enhanced']['accuracy']:.1f}%)")
        print(f"  纯大语言模型: {accuracy_stats['pure_llm']['correct']}/{accuracy_stats['pure_llm']['total']} "
              f"({accuracy_stats['pure_llm']['accuracy']:.1f}%)")
        
        print(f"\n⏱️ 性能对比:")
        print(f"  知识图谱增强平均响应时间: {performance_stats['kg_enhanced']['avg_time']:.2f}秒")
        print(f"  纯大语言模型平均响应时间: {performance_stats['pure_llm']['avg_time']:.2f}秒")
        
        improvement = accuracy_stats['kg_enhanced']['accuracy'] - accuracy_stats['pure_llm']['accuracy']
        print(f"\n📈 准确率提升: {improvement:+.1f}%")
        
        print(f"\n💾 详细结果已保存至: {results_file}")
        print("=" * 60)
        
    except Exception as e:
        logging.error(f"实验运行失败: {e}")
        raise

if __name__ == "__main__":
    main()