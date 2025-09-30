import csv
import json
import os

def csv_to_json(csv_file_path, json_file_path):
    """将CSV格式的知识图谱数据转换为JSON格式"""
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile, open(json_file_path, 'w', encoding='utf-8') as jsonfile:
            reader = csv.DictReader(csvfile)
            data = {'nodes': [], 'links': []}
            
            # 关系类型映射字典 - 将英文关系名映射为中文
            relation_dict = {
                
                
                "hasComplexity": "基于...评估",
                "uses": "使用...结构",
                "variantOf": "属于...变体",
                "appliesTo": "适用于...场景",
                "provides": "提供...接口",
                "implementedAs": "实现...算法",
                "usedIn": "应用于...领域"

                
            }
            
            # 用于去重的集合
            existing_nodes = set()
            existing_links = set()
            
            for row in reader:
                # 跳过无效数据
                if not row.get('head') or not row.get('tail') or not row.get('relation'):
                    continue
                    
                # 跳过置信度过低的数据（如果有confidence字段）
                if 'confidence' in row and float(row['confidence']) < 0.7:
                    continue
                
                head_entity = row['head'].strip()
                tail_entity = row['tail'].strip()
                relation = row['relation'].strip()
                
                # 创建链接
                link = {
                    'source': head_entity,
                    'target': tail_entity,
                    'relation': relation_dict.get(relation, relation),
                }
                
                # 创建节点
                head_node = {'id': head_entity, 'name': head_entity}
                tail_node = {'id': tail_entity, 'name': tail_entity}
                
                # 去重添加节点
                if head_entity not in existing_nodes:
                    data['nodes'].append(head_node)
                    existing_nodes.add(head_entity)
                    
                if tail_entity not in existing_nodes:
                    data['nodes'].append(tail_node)
                    existing_nodes.add(tail_entity)
                
                # 去重添加链接
                link_key = f"{head_entity}|{tail_entity}|{relation}"
                if link_key not in existing_links:
                    data['links'].append(link)
                    existing_links.add(link_key)
            
            # 写入JSON文件
            json.dump(data, jsonfile, ensure_ascii=False, indent=2)
            print(f"✅ 成功转换: {len(data['nodes'])} 个节点, {len(data['links'])} 个关系")
            
    except FileNotFoundError:
        print(f"❌ 文件未找到: {csv_file_path}")
        raise
    except Exception as e:
        print(f"❌ 转换过程中出错: {e}")
        raise

if __name__ == '__main__':
    # 使用绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(current_dir, 'data', 'predictions.csv')
    json_file_path = os.path.join(current_dir, 'data', 'predictions.json')
    
    print(f"🔄 开始转换CSV到JSON...")
    print(f"输入文件: {csv_file_path}")
    print(f"输出文件: {json_file_path}")
    
    if os.path.exists(csv_file_path):
        csv_to_json(csv_file_path, json_file_path)
        print(f"🎉 转换完成！输出文件: {json_file_path}")
    else:
        print(f"❌ CSV文件不存在: {csv_file_path}")
