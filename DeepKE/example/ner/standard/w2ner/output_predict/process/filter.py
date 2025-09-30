import json
import os

# 使用绝对路径，指向项目根目录的predict.json文件
input_file = "/root/KG_inde/predict.json"
output_file = "/root/KG_inde/DeepKE/example/ner/standard/w2ner/output_predict/process/filtered.json"

with open(input_file, 'r', encoding='utf-8') as json_file:
    json_data = json.load(json_file)

    # 过滤重复三元组,保存对应语句
    triplet_to_sentence = {}
    unique_triplets = set()
    filtered_data = []
    
    for item in json_data:
        # 根据实际数据格式，三元组由head、tail、head_offset、tail_offset组成
        # 这样可以区分同样的head-tail对但在不同位置的情况
        triplet = (item['head'], item['tail'], item['head_offset'], item['tail_offset'])
        if triplet not in unique_triplets:
            unique_triplets.add(triplet)
            filtered_data.append(item)
            triplet_to_sentence[triplet] = item['sentence']

    print(f"原始数据条数: {len(json_data)}")
    print(f"去重后数据条数: {len(filtered_data)}")
    print(f"去除重复条数: {len(json_data) - len(filtered_data)}")
    
    # 保存过滤后的JSON文件
    """
    输出格式:{
    "sentence": "数组属于线性结构",
    "head": "数组",
    "tail": "线性结构",
    "head_offset": "0",
    "tail_offset": "4"
    }
    """
    with open(output_file, 'w', encoding='utf-8') as output_json:
        json.dump(filtered_data, output_json, ensure_ascii=False, indent=2)
    
    print(f"过滤后的数据已保存到: {output_file}")
            
