# -*- coding: utf-8 -*-
"""
后端API模块
提供简化的REST接口，适配Vue3前端
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from .knowledge_graph_query import KnowledgeGraphQuery
from .intent_recognition import IntentRecognizer
from .doubao_llm import DoubaoLLM
import logging
import json
from typing import Dict, Any, List, Optional
import re

class APIHandler:
    """简化的API处理器
    
    负责处理用户请求，提供基本的聊天功能
    """
    
    def __init__(self, intent_recognizer, kg_query, llm_client=None):
        """初始化后端API"""
        self.kg_query = kg_query
        self.intent_recognizer = intent_recognizer
        self.llm_client = llm_client
        
        # 意图到KG接口的映射
        self.intent_to_kg_method = {
            "find_entity_by_relation_and_entity": self._handle_find_entity_by_relation,
            "find_relation_by_two_entities": self._handle_find_relation_between_entities,
            "find_single_entity": self._handle_find_single_entity,
            "other": self._handle_general_query
        }
        
        logging.info("API处理器初始化完成")
    
    def set_api_url(self, url: str):
        """
        设置API地址
        
        Args:
            url: API地址
        """
        self.api_url = url.strip()
        logging.info(f"API地址已设置为: {self.api_url}")

    def process_query(self, user_input: str) -> Dict[str, Any]:
        """
        处理用户查询（基于意图识别）
        
        Args:
            user_input: 用户输入
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        if not user_input or not user_input.strip():
            return {
                "success": False, 
                "message": "输入不能为空",
                "graphData": {}
            }
        
        user_input = user_input.strip()
        
        try:
            # 识别用户意图
            intent = self.intent_recognizer.recognize_intent(user_input)
            logging.info(f"识别到的意图: {intent}")
            
            # 根据意图调用相应的处理方法
            if intent in self.intent_to_kg_method:
                handler = self.intent_to_kg_method[intent]
                return handler(user_input)
            else:
                # 未知意图，使用通用查询
                return self._handle_general_query(user_input)
                
        except Exception as e:
            logging.error(f"查询处理失败: {e}")
            return {
                "success": False,
                "message": f"查询处理失败: {str(e)}",
                "graphData": {}
            }
    
    def _generate_llm_response(self, user_query: str, kg_result: List[Dict[str, Any]]) -> str:
        """
        基于知识图谱查询结果生成LLM回复
        
        Args:
            user_query: 用户原始查询
            kg_result: 知识图谱查询结果
            
        Returns:
            str: LLM生成的回复
        """
        if not self.llm_client:
            return "抱歉，LLM服务暂时不可用。"
        
        try:
            # 构建上下文信息
            context_info = []
            if kg_result:
                context_info.append("根据知识图谱查询到以下相关信息：")
                for i, item in enumerate(kg_result[:5], 1):  # 限制上下文长度
                    if isinstance(item, dict):
                        if 'entity1' in item and 'entity2' in item:
                            relation = item.get('relation', '相关')
                            context_info.append(f"{i}. {item['entity1']} {relation} {item['entity2']}")
                        elif 'entity' in item:
                            context_info.append(f"{i}. 实体: {item['entity']}")
            
            # 构建完整的提示
            context_str = "\n".join(context_info) if context_info else "未找到相关的知识图谱信息。"
            
            prompt = f"""用户问题：{user_query}

知识图谱查询结果：
{context_str}

请基于以上知识图谱信息，用专业且易懂的语言回答用户的问题。如果知识图谱中没有相关信息，请诚实说明并提供一般性的解答。"""
            
            # 调用LLM生成回复
            response = self.llm_client.generate_response(prompt)
            return response.content
            
        except Exception as e:
            logging.error(f"LLM回复生成失败: {e}")
            return f"抱歉，生成回复时出现错误：{str(e)}"
    
    def _handle_find_entity_by_relation(self, query: str) -> Dict[str, Any]:
        """处理根据关系查找实体的查询"""
        try:
            entities = self.intent_recognizer.extract_entities(query)
            relations = self.intent_recognizer.extract_relations(query)
            
            # 如果没有明确的关系，但有实体，尝试使用默认关系或通用查询
            if entities and not relations:
                # 对于"有哪些"、"包含"等查询，使用包含关系
                if any(keyword in query for keyword in ["有哪些", "包含", "属于", "类型", "分类", "种类"]):
                    relations = ["包含"]  # 使用默认的包含关系
                else:
                    # 如果没有关系词，转为实体关系查询
                    return self._handle_find_entity_relations(query)
            
            if entities and relations:
                # 使用知识图谱查询
                result = self.kg_query.find_entities_by_relation(entities, relations[0])
                
                # 生成LLM回复
                llm_response = self._generate_llm_response(query, result)
                
                return {
                    "success": True,
                    "message": llm_response,
                    "graphData": self._convert_to_graph_data(result),
                    "kg_result": result[:10]  # 保留原始KG结果供调试
                }
            else:
                # 即使没有找到实体或关系，也尝试生成LLM回复
                llm_response = self._generate_llm_response(query, [])
                return {
                    "success": True,  # 改为True，因为LLM可以回答
                    "message": llm_response,
                    "graphData": {}
                }
                
        except Exception as e:
            logging.error(f"处理根据关系查找实体查询失败: {e}")
            # 即使出错也尝试生成基本回复
            llm_response = self._generate_llm_response(query, [])
            return {
                "success": True,  # 改为True，因为LLM可以回答
                "message": llm_response,
                "graphData": {}
            }
    
    def _handle_find_relation_between_entities(self, query: str) -> Dict[str, Any]:
        """处理查找两个实体间关系的查询"""
        try:
            entities = self.intent_recognizer.extract_entities(query)
            
            if len(entities) >= 2:
                # 使用知识图谱查询
                result = self.kg_query.find_relation_by_entities(entities[:2])
                
                # 生成LLM回复
                llm_response = self._generate_llm_response(query, result)
                
                return {
                    "success": True,
                    "message": llm_response,
                    "graphData": self._convert_to_graph_data(result),
                    "kg_result": result[:10]  # 保留原始KG结果供调试
                }
            else:
                # 即使没有找到足够实体，也尝试生成LLM回复
                llm_response = self._generate_llm_response(query, [])
                return {
                    "success": False,
                    "message": llm_response,
                    "graphData": {}
                }
                
        except Exception as e:
            logging.error(f"处理实体间关系查询失败: {e}")
            # 即使出错也尝试生成基本回复
            llm_response = self._generate_llm_response(query, [])
            return {
                "success": False,
                "message": llm_response,
                "graphData": {}
            }
    
    def _handle_find_single_entity(self, query: str) -> Dict[str, Any]:
        """处理单实体查询（查找实体的所有关系）"""
        try:
            entities = self.intent_recognizer.extract_entities(query)
            
            if entities:
                entity = entities[0]
                
                # 使用知识图谱查询
                result = self.kg_query.find_entity_relations(entity)
                
                # 生成LLM回复
                llm_response = self._generate_llm_response(query, result)
                
                return {
                    "success": True,
                    "message": llm_response,
                    "graphData": self._convert_to_graph_data(result),
                    "kg_result": result[:10]  # 保留原始KG结果供调试
                }
            else:
                # 即使没有找到实体，也尝试生成LLM回复
                llm_response = self._generate_llm_response(query, [])
                return {
                    "success": False,
                    "message": llm_response,
                    "graphData": {}
                }
                
        except Exception as e:
            logging.error(f"处理单实体查询失败: {e}")
            # 即使出错也尝试生成基本回复
            llm_response = self._generate_llm_response(query, [])
            return {
                "success": False,
                "message": llm_response,
                "graphData": {}
            }
    
    def _handle_general_query(self, query: str) -> Dict[str, Any]:
        """处理通用查询"""
        try:
            # 对于通用查询，直接使用LLM生成回复
            llm_response = self._generate_llm_response(query, [])
            
            return {
                "success": True,
                "message": llm_response,
                "graphData": {}
            }
        except Exception as e:
            logging.error(f"处理通用查询失败: {e}")
            return {
                "success": False,
                "message": f"抱歉，处理您的问题时出现错误：{str(e)}",
                "graphData": {}
            }
    
    def _convert_to_graph_data(self, result: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        将查询结果转换为图数据格式
        
        Args:
            result: 查询结果
            
        Returns:
            Dict[str, Any]: 图数据格式
        """
        if not result:
            return {}
        
        nodes = []
        links = []
        node_ids = set()
        link_keys = set()  # 用于去重边
        
        for item in result:
            if isinstance(item, dict):
                # 处理简单格式的结果
                if 'entity1' in item and 'entity2' in item and isinstance(item['entity1'], str):
                    entity1 = item['entity1']
                    entity2 = item['entity2']
                    relation = item.get('relation', '关系')
                    
                    # 添加节点
                    if entity1 not in node_ids:
                        nodes.append({"id": entity1, "name": entity1, "group": 1})
                        node_ids.add(entity1)
                    
                    if entity2 not in node_ids:
                        nodes.append({"id": entity2, "name": entity2, "group": 1})
                        node_ids.add(entity2)
                    
                    # 检查边是否已存在（双向检查）
                    link_key1 = (entity1, entity2, relation)
                    link_key2 = (entity2, entity1, relation)
                    
                    if link_key1 not in link_keys and link_key2 not in link_keys:
                        links.append({
                            "source": entity1,
                            "target": entity2,
                            "relation": relation,
                            "value": 1
                        })
                        link_keys.add(link_key1)
                
                # 处理增强格式的结果
                elif 'entity1' in item and isinstance(item['entity1'], dict):
                    entity1_name = item['entity1'].get('name', '未知')
                    entity2_name = item['entity2'].get('name', '未知') if isinstance(item.get('entity2'), dict) else str(item.get('entity2', '未知'))
                    relation_type = item['relation'].get('type', '关系') if isinstance(item.get('relation'), dict) else str(item.get('relation', '关系'))
                    
                    # 添加节点
                    if entity1_name not in node_ids:
                        nodes.append({"id": entity1_name, "name": entity1_name, "group": 1})
                        node_ids.add(entity1_name)
                    
                    if entity2_name not in node_ids:
                        nodes.append({"id": entity2_name, "name": entity2_name, "group": 1})
                        node_ids.add(entity2_name)
                    
                    # 检查边是否已存在（双向检查）
                    link_key1 = (entity1_name, entity2_name, relation_type)
                    link_key2 = (entity2_name, entity1_name, relation_type)
                    
                    if link_key1 not in link_keys and link_key2 not in link_keys:
                        links.append({
                            "source": entity1_name,
                            "target": entity2_name,
                            "relation": relation_type,
                            "value": 1
                        })
                        link_keys.add(link_key1)
        
        return {
            "nodes": nodes[:20],  # 限制节点数量
            "links": links[:30]   # 限制边数量
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取系统状态
        
        Returns:
            Dict[str, Any]: 系统状态信息
        """
        return {
            "intent_recognizer": self.intent_recognizer is not None,
            "knowledge_graph": self.kg_query is not None,
            "llm_client": self.llm_client is not None
        }

def create_flask_app(api_handler=None) -> Flask:
    """
    创建Flask应用
    
    Args:
        api_handler: API处理器实例（可选）
    
    Returns:
        配置好的Flask应用
    """
    app = Flask(__name__)
    
    # 配置Flask应用
    app.config['JSON_AS_ASCII'] = False  # 支持中文JSON
    
    # 配置CORS - 允许所有来源
    CORS(app, resources={
        r"/*": {
            "origins": ["*"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
        }
    })
    
    # 使用传入的API处理器或创建新的
    if api_handler is None:
        api_handler = APIHandler()
    
    # 简单的错误处理
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "接口不存在"}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "服务器内部错误"}), 500
    
    # 主要的聊天接口 - 兼容前端的 /test 路由
    @app.route("/reply", methods=["POST"])
    def chat():
        """聊天接口 - 兼容前端"""
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"message": "缺少message参数"})
        
        message = data['message'].strip()
        if not message:
            return jsonify({"message": "消息不能为空"})
        
        # 处理查询
        result = api_handler.process_query(message)
        
        # 获取图数据
        graph_dict = result.get('graphData', {})
        
        # 记录调试信息
        logging.info(f"查询结果: {result}")
        logging.info(f"图数据: {graph_dict}")
        
        # 返回前端期望的格式，现在包含LLM生成的回复
        return jsonify({
            "message": result["message"],  # 现在是LLM生成的专业回复
            "graphData": graph_dict,
            "success": result.get("success", False),
            "kg_result": result.get("kg_result", [])  # 可选：原始KG结果供调试
        })
    
    
    @app.route("/set_api", methods=["POST"])
    def set_api():
        """设置API地址接口 - 兼容前端"""
        data = request.get_json()
        print(data)
        conf={
            "key":"api",
            "value":{
                'api_key': data["apiKey"],
                'model_name': data["model"],
                'base_url': data["baseUrl"]
            }
        }
        if conf['value']['api_key'] is not None:

            api_handler.llm_client.ark_api_key=conf['value']['api_key']

        if conf['value']['model_name'] is not None:

            api_handler.llm_client.doubao_model_id=conf['value']['model_name']
        # TODO 设置api

        return "API设置成功"
        
    
    @app.route("/set_database", methods=["POST"])
    def set_database():
        data = request.get_json()
        print(data)
        conf={
            'key':'database',
            'value':{
                'database.user_name':data["username"],
                'database.password':data["password"],
                'database.uri':data["boltUrl"],
                'database.browserUrl':data["browserUrl"]
            }
        }

        # TODO 设置数据库

        return "数据库设置成功"
    
    @app.route("/switchChat", methods=["POST"])
    def switchChat():
        data = request.get_json()
        # print(data)
        # data 是 json 格式 [{sender:,test:,timestamp:}]
        converted = []
        for item in data:
            # 假设sender的值是"user"或"assistant"，如果实际情况不同需要调整这里的映射关系
            converted_item = {
                "role": item["sender"],
                "content": item["text"]
            }
            converted.append(converted_item)
            # TODO 改变模型的上下文
        api_handler.llm_client.history_messages=converted
        return data

    # 单实体完整信息查询接口
    @app.route("/entity/complete_info", methods=["POST"])
    def get_entity_complete_info():
        """获取单个实体的完整信息接口"""
        try:
            data = request.get_json()
            if not data or 'entity_name' not in data:
                return jsonify({
                    "success": False,
                    "error": "缺少entity_name参数"
                }), 400
            
            entity_name = data['entity_name'].strip()
            if not entity_name:
                return jsonify({
                    "success": False,
                    "error": "实体名称不能为空"
                }), 400
            
            # 获取可选参数
            limit = data.get('limit', 100)
            
            # 检查知识图谱查询器是否可用
            if not api_handler.kg_query:
                return jsonify({
                    "success": False,
                    "error": "知识图谱查询器未初始化"
                }), 500
            
            # 调用新的完整信息查询方法
            result = api_handler.kg_query.get_entity_complete_info(entity_name, limit)
            
            return jsonify(result)
            
        except Exception as e:
            logging.error(f"获取实体完整信息失败: {e}")
            return jsonify({
                "success": False,
                "error": f"服务器内部错误: {str(e)}"
            }), 500
    
    # 健康检查接口
    @app.route("/health", methods=["GET"])
    def health_check():
        """健康检查接口"""
        status = api_handler.get_status()
        return jsonify({
            "status": "healthy",
            "system_status": status
        })
    
    @app.route("/test", methods=["GET"])
    def reply():
        return "测试"
    return app


# 创建应用实例的便捷函数
def create_app():
    """创建Flask应用实例"""
    return create_flask_app()