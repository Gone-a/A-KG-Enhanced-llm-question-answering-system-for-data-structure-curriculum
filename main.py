#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱问答系统 - 主程序

集成意图识别、知识图谱查询和后端API功能的统一入口
支持性能优化和模块化架构
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.config_manager import get_config_manager
from modules.intent_recognition import IntentRecognizer
from modules.knowledge_graph_query import KnowledgeGraphQuery
from modules.run_serve import RunServe
from modules.backend_api import APIHandler, create_flask_app
from modules.doubao_llm import DoubaoLLM
from modules.kg_llm_enhancer import KGLLMEnhancer

# 导入知识库
try:
    from intent_recognition.knowledge_base import KNOWLEDGE_BASE
except ImportError:
    KNOWLEDGE_BASE = {"entities": {}, "relations": {}}

class KnowledgeGraphApp:
    """知识图谱应用主类"""
    
    def __init__(self):
        self.config = get_config_manager()
        self.intent_recognizer = None
        self.kg_query = None
        self.api_handler = None
        self.app = None
    
    def initialize(self):
        """初始化应用程序"""
        import threading
        
        print("正在并行初始化系统组件...")
        
        # 初始化服务开启器
        self.run_serve = RunServe()
        
        # 创建事件用于协调输出
        self.backend_ready_event = threading.Event()
        
        # 定义初始化任务
        def init_neo4j():
            self.run_serve.check_and_start_neo4j()
            
        def init_vue():
            # 传入事件对象，Vue输出将等待事件被设置
            self.run_serve.start_vue_async(output_event=self.backend_ready_event)
            
        def init_nlu():
            model_path = self.config.get('model.nlu_model_path')
            self.intent_recognizer = IntentRecognizer(model_path, KNOWLEDGE_BASE, use_w2ner=True)
            
        def init_kg_query():
            db_config = self.config.get_database_config()
            self.kg_query = KnowledgeGraphQuery(
                db_config['uri'],
                db_config['user_name'], 
                db_config['password']
            )
            
        def init_llm():
            try:
                api_config = self.config.get_api_config()
                llm_config = self.config.get_llm_config()
                llm_client = DoubaoLLM(
                    user_api_key=api_config.get('ark_api_key'),
                    user_model_id=api_config.get('doubao_model_id'),
                    base_url=api_config.get('base_url')
                )
                llm_client.set_parameters(
                    max_tokens=llm_config['max_tokens'],
                    temperature=llm_config['temperature']
                )
                # 暂时保存llm_client，稍后统一组装
                self.llm_client = llm_client
            except ValueError as e:
                print(f"警告：LLM初始化失败 - {e}")
                print("将使用默认的空LLM客户端")
                self.llm_client = None

        # 并行执行初始化任务
        threads = []
        tasks = [init_neo4j, init_vue, init_nlu, init_kg_query, init_llm]
        
        for task in tasks:
            t = threading.Thread(target=task)
            t.start()
            threads.append(t)
            
        # 等待所有初始化任务完成
        for t in threads:
            t.join()
            
        # 组装依赖组件
        if self.llm_client and self.kg_query:
            self.enhancer = KGLLMEnhancer(self.llm_client, self.kg_query)
        else:
            self.enhancer = None
            
        if self.intent_recognizer and self.kg_query:
            self.intent_recognizer.set_kg_query(self.kg_query)
        
        # 初始化API处理器
        self.api_handler = APIHandler(self.intent_recognizer, self.kg_query, self.llm_client)
        
        # 创建Flask应用
        self.app = create_flask_app(self.api_handler)
        
        # 所有后端组件准备就绪，通知前端可以显示地址了
        print("后端服务初始化完成，系统准备就绪。")
        self.backend_ready_event.set()
    

    
    def run(self):
        """运行应用程序"""
        server_config = self.config.get_server_config()
        host = server_config.get('host', 'localhost')
        port = server_config.get('port', 5000)
        debug = server_config.get('debug', False)
        
        self.app.run(host=host, port=port, debug=debug)
    
def main():
    """主函数"""
    print("知识图谱问答系统启动中...")
    
    #print("01")
    app = KnowledgeGraphApp()
    #print("02")
    app.initialize()
    #print("03")
    app.run()

if __name__ == "__main__":
    main()
