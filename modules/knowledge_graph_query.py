# -*- coding: utf-8 -*-
"""
知识图谱查询模块
提供Neo4j图数据库查询功能，支持实体关系查询和图谱问答
"""

from py2neo import Graph
import os
from typing import List, Dict, Any, Optional
import logging
import re
import time
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import threading

class KnowledgeGraphQuery:
    """知识图谱查询器
    
    提供高效的图数据库查询接口，支持缓存和性能优化
    """
    
    # 常量定义
    MAX_ENTITY_LENGTH = 100
    MAX_ENTITIES_PER_QUERY = 50
    DEFAULT_CONFIDENCE_THRESHOLD = 0.8
    QUERY_RESULT_LIMIT = 1000
    FLOAT_PRECISION = 1e-10
    
    def __init__(self, neo4j_uri: str, username: str, password: str, max_workers: int = 4):
        """
        初始化知识图谱查询器
        
        Args:
            neo4j_uri: Neo4j数据库URI
            username: 用户名
            password: 密码
            max_workers: 最大并发工作线程数
            
        Raises:
            ConnectionError: 数据库连接失败
            ValueError: 参数验证失败
        """
        self._validate_params(neo4j_uri, username, password)
        
        try:
            # 连接Neo4j数据库
            self.graph = Graph(neo4j_uri, auth=(username, password))
            
            # 增加重试机制，等待Neo4j完全启动
            max_retries = 30
            retry_interval = 2
            
            for i in range(max_retries):
                try:
                    # 测试连接
                    self.graph.run("RETURN 1").data()
                    logging.info("Neo4j数据库连接成功")
                    break
                except Exception as e:
                    if i == max_retries - 1:
                        raise e
                    logging.info(f"Neo4j尚未准备就绪，正在重试 ({i+1}/{max_retries})...")
                    time.sleep(retry_interval)
            
        except Exception as e:
            logging.error(f"Neo4j数据库连接失败: {e}")
            raise ConnectionError(f"无法连接到Neo4j数据库: {e}")
        
        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # 查询缓存
        self.query_cache = {}
        self.cache_lock = threading.RLock()
        self.cache_ttl = 600  # 10分钟缓存
    
    def _validate_params(self, neo4j_uri: str, username: str, password: str):
        """验证初始化参数"""
        if not neo4j_uri or not isinstance(neo4j_uri, str):
            raise ValueError("neo4j_uri不能为空且必须是字符串")
        if not username or not isinstance(username, str):
            raise ValueError("username不能为空且必须是字符串")
        if not password or not isinstance(password, str):
            raise ValueError("password不能为空且必须是字符串")
    
    def _get_cache_key(self, query_type: str, *args) -> str:
        """生成缓存键"""
        return f"{query_type}:{'|'.join(str(arg) for arg in args)}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """获取缓存结果"""
        with self.cache_lock:
            if cache_key in self.query_cache:
                result, timestamp = self.query_cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    return result
                else:
                    del self.query_cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: Any):
        """缓存查询结果"""
        with self.cache_lock:
            self.query_cache[cache_key] = (result, time.time())
            # 清理过期缓存
            current_time = time.time()
            expired_keys = [
                key for key, (_, timestamp) in self.query_cache.items()
                if current_time - timestamp >= self.cache_ttl
            ]
            for key in expired_keys:
                del self.query_cache[key]

    def _format_entity_attributes(self, record: Dict[str, Any], entity_prefix: str) -> Dict[str, Any]:
        """
        格式化实体属性信息
        
        Args:
            record: 查询记录
            entity_prefix: 实体前缀（entity1或entity2）
            
        Returns:
            Dict[str, Any]: 格式化后的属性字典
        """
        attributes = {}
        
        # 基本属性
        type_key = f"{entity_prefix}_type"
        if record.get(type_key):
            attributes['type'] = record[type_key]
        
        # 描述信息
        desc_key = f"{entity_prefix}_description"
        if record.get(desc_key):
            attributes['description'] = record[desc_key]
        
        # 属性信息
        props_key = f"{entity_prefix}_properties"
        if record.get(props_key):
            attributes['properties'] = record[props_key]
        
        # 时间复杂度
        time_complexity_key = f"{entity_prefix}_time_complexity"
        if record.get(time_complexity_key):
            attributes['time_complexity'] = record[time_complexity_key]
        
        # 空间复杂度
        space_complexity_key = f"{entity_prefix}_space_complexity"
        if record.get(space_complexity_key):
            attributes['space_complexity'] = record[space_complexity_key]
        
        # 常见操作
        operations_key = f"{entity_prefix}_common_operations"
        if record.get(operations_key):
            attributes['common_operations'] = record[operations_key]
        
        return attributes

    def _sanitize_entity_name(self, entity_name: str) -> str:
        """清理实体名称，防止注入攻击"""
        if not entity_name:
            return ""
        
        # 移除危险字符
        sanitized = re.sub(r'[^\w\u4e00-\u9fff\s\-_]', '', entity_name)
        
        # 限制长度
        if len(sanitized) > self.MAX_ENTITY_LENGTH:
            sanitized = sanitized[:self.MAX_ENTITY_LENGTH]
        
        return sanitized.strip()

    def _validate_entities(self, entities: List[str]) -> List[str]:
        """验证和清理实体列表"""
        if not entities:
            return []
        
        validated = []
        for entity in entities[:self.MAX_ENTITIES_PER_QUERY]:
            sanitized = self._sanitize_entity_name(entity)
            if sanitized:
                validated.append(sanitized)
        
        return validated

    def _execute_query_with_cache(self, query: str, cache_key: str = None, **params) -> List[Dict[str, Any]]:
        """执行查询并缓存结果"""
        if cache_key:
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                return cached_result
        
        try:
            result = self.graph.run(query, **params).data()
            
            if cache_key:
                self._cache_result(cache_key, result)
            
            return result
            
        except Exception as e:
            logging.error(f"查询执行失败: {e}")
            return []

    def find_entities_by_relation(self, entities: List[str], relation: str, 
                                confidence_threshold: float = None) -> List[Dict[str, Any]]:
        """
        根据实体和关系查找相关实体
        
        Args:
            entities: 实体列表
            relation: 关系类型
            confidence_threshold: 置信度阈值
            
        Returns:
            List[Dict[str, Any]]: 查询结果，包含实体属性信息
        """
        if confidence_threshold is None:
            confidence_threshold = self.DEFAULT_CONFIDENCE_THRESHOLD
        
        validated_entities = self._validate_entities(entities)
        if not validated_entities or not relation:
            return []
        
        sanitized_relation = self._sanitize_entity_name(relation)
        if not sanitized_relation:
            return []
        
        cache_key = self._get_cache_key("find_entities_by_relation", 
                                      tuple(validated_entities), sanitized_relation, confidence_threshold)
        
        # 构建查询，包含实体属性
        entity_conditions = " OR ".join([f"n.name CONTAINS '{entity}'" for entity in validated_entities])
        
        query = f"""
        MATCH (n)-[r]->(m)
        WHERE ({entity_conditions}) AND type(r) CONTAINS '{sanitized_relation}'
        RETURN n.name as entity1, 
               n.type as entity1_type,
               n.description as entity1_description,
               n.properties as entity1_properties,
               n.time_complexity as entity1_time_complexity,
               n.space_complexity as entity1_space_complexity,
               n.common_operations as entity1_common_operations,
               type(r) as relation, 
               m.name as entity2,
               m.type as entity2_type,
               m.description as entity2_description,
               m.properties as entity2_properties,
               m.time_complexity as entity2_time_complexity,
               m.space_complexity as entity2_space_complexity,
               m.common_operations as entity2_common_operations
        LIMIT {self.QUERY_RESULT_LIMIT}
        """
        
        try:
            result = self._execute_query_with_cache(query, cache_key)
            
            # 格式化结果，包含属性信息
            formatted_result = []
            for record in result:
                if record.get('entity1') and record.get('entity2'):
                    result_item = {
                        'entity1': record['entity1'],
                        'entity1_attributes': self._format_entity_attributes(record, 'entity1'),
                        'entity2': record['entity2'],
                        'entity2_attributes': self._format_entity_attributes(record, 'entity2'),
                        'relation': record.get('relation', sanitized_relation)
                    }
                    formatted_result.append(result_item)
            
            return formatted_result
            
        except Exception as e:
            logging.error(f"根据关系查找实体失败: {e}")
            return []

    def find_relation_by_entities(self, entities: List[str], 
                                confidence_threshold: float = None,
                                bidirectional: bool = True,
                                include_indirect: bool = True) -> List[Dict[str, Any]]:
        """
        查找两个实体之间的关系
        
        Args:
            entities: 实体列表（至少2个）
            confidence_threshold: 置信度阈值
            bidirectional: 是否双向查找
            include_indirect: 是否包含间接关系
            
        Returns:
            List[Dict[str, Any]]: 关系列表，包含实体属性信息
        """
        if confidence_threshold is None:
            confidence_threshold = self.DEFAULT_CONFIDENCE_THRESHOLD
        
        validated_entities = self._validate_entities(entities)
        if len(validated_entities) < 2:
            return []
        
        entity1, entity2 = validated_entities[0], validated_entities[1]
        
        cache_key = self._get_cache_key("find_relation_by_entities", 
                                      entity1, entity2, confidence_threshold, bidirectional)
        
        # 构建查询，包含实体属性
        if bidirectional:
            query = f"""
            MATCH (n1)-[r]-(n2)
            WHERE (n1.name CONTAINS '{entity1}' AND n2.name CONTAINS '{entity2}') OR
                  (n1.name CONTAINS '{entity2}' AND n2.name CONTAINS '{entity1}')
            RETURN n1.name as entity1,
                   n1.type as entity1_type,
                   n1.description as entity1_description,
                   n1.properties as entity1_properties,
                   n1.time_complexity as entity1_time_complexity,
                   n1.space_complexity as entity1_space_complexity,
                   n1.common_operations as entity1_common_operations,
                   type(r) as relation,
                   n2.name as entity2,
                   n2.type as entity2_type,
                   n2.description as entity2_description,
                   n2.properties as entity2_properties,
                   n2.time_complexity as entity2_time_complexity,
                   n2.space_complexity as entity2_space_complexity,
                   n2.common_operations as entity2_common_operations
            LIMIT {self.QUERY_RESULT_LIMIT}
            """
        else:
            query = f"""
            MATCH (n1)-[r]->(n2)
            WHERE n1.name CONTAINS '{entity1}' AND n2.name CONTAINS '{entity2}'
            RETURN n1.name as entity1,
                   n1.type as entity1_type,
                   n1.description as entity1_description,
                   n1.properties as entity1_properties,
                   n1.time_complexity as entity1_time_complexity,
                   n1.space_complexity as entity1_space_complexity,
                   n1.common_operations as entity1_common_operations,
                   type(r) as relation,
                   n2.name as entity2,
                   n2.type as entity2_type,
                   n2.description as entity2_description,
                   n2.properties as entity2_properties,
                   n2.time_complexity as entity2_time_complexity,
                   n2.space_complexity as entity2_space_complexity,
                   n2.common_operations as entity2_common_operations
            LIMIT {self.QUERY_RESULT_LIMIT}
            """
        
        try:
            result = self._execute_query_with_cache(query, cache_key)
            
            # 格式化结果，包含属性信息
            formatted_result = []
            for record in result:
                if record.get('entity1') and record.get('entity2'):
                    result_item = {
                        'entity1': record['entity1'],
                        'entity1_attributes': self._format_entity_attributes(record, 'entity1'),
                        'entity2': record['entity2'],
                        'entity2_attributes': self._format_entity_attributes(record, 'entity2'),
                        'relation': record.get('relation', '未知关系')
                    }
                    formatted_result.append(result_item)
            
            return formatted_result
            
        except Exception as e:
            logging.error(f"查找实体间关系失败: {e}")
            return []

    def find_entity_relations(self, entity_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        查找实体的所有关系
        
        Args:
            entity_name: 实体名称
            limit: 结果限制数量
            
        Returns:
            List[Dict[str, Any]]: 关系列表，包含实体属性信息
        """
        sanitized_entity = self._sanitize_entity_name(entity_name)
        if not sanitized_entity:
            return []
        
        cache_key = self._get_cache_key("find_entity_relations", sanitized_entity, limit)
        
        query = f"""
        MATCH (n)-[r]-(m)
        WHERE n.name CONTAINS '{sanitized_entity}'
        RETURN n.name as entity1,
               n.type as entity1_type,
               n.description as entity1_description,
               n.properties as entity1_properties,
               n.time_complexity as entity1_time_complexity,
               n.space_complexity as entity1_space_complexity,
               n.common_operations as entity1_common_operations,
               type(r) as relation,
               m.name as entity2,
               m.type as entity2_type,
               m.description as entity2_description,
               m.properties as entity2_properties,
               m.time_complexity as entity2_time_complexity,
               m.space_complexity as entity2_space_complexity,
               m.common_operations as entity2_common_operations
        LIMIT {min(limit, self.QUERY_RESULT_LIMIT)}
        """
        
        try:
            result = self._execute_query_with_cache(query, cache_key)
            
            # 格式化结果，包含属性信息
            formatted_result = []
            for record in result:
                if record.get('entity1') and record.get('entity2'):
                    result_item = {
                        'entity1': record['entity1'],
                        'entity1_attributes': self._format_entity_attributes(record, 'entity1'),
                        'entity2': record['entity2'],
                        'entity2_attributes': self._format_entity_attributes(record, 'entity2'),
                        'relation': record.get('relation', '未知关系')
                    }
                    formatted_result.append(result_item)
            
            return formatted_result
            
        except Exception as e:
            logging.error(f"查找实体关系失败: {e}")
            return []

    def close(self):
        """关闭数据库连接和线程池"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)
            logging.info("知识图谱查询器已关闭")
        except Exception as e:
            logging.error(f"关闭知识图谱查询器时出错: {e}")

# 为了兼容性，保留原有的类名
DSAGraphQAFixed = KnowledgeGraphQuery