import json
import random
import pandas as pd
import time  # 引入time模块，用于生成随时间变化的种子

def json_to_csv(input_json, output_csv):
    # （原代码不变）
    try:
        with open(input_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with open(output_csv, 'w', encoding='utf-8') as csv_file:
            csv_file.write("sentence,relation,head,tail,head_offset,tail_offset,head_type,tail_type\n")
        for i in data:
            if 'head' in i and 'tail' in i:
                head = i['head']
                tail = i['tail']
                sentence = '"' + str(i['sentence']).replace('"', '""') + '"'
                head_offset = i['head_offset']
                tail_offset = i['tail_offset']
                relation = i["relation"]
                with open(output_csv, 'a', encoding='utf-8') as csv_file:
                    csv_file.write(f"{sentence},{relation},{head},{tail},{head_offset},{tail_offset}\n")
    except FileNotFoundError:
        print(f"文件 {input_json} 未找到")
    except json.JSONDecodeError:
        print(f"无法解析 {input_json} 中的 JSON 数据")
    except Exception as e:
        print(f"写入 CSV 文件时出现错误: {e}")

def split_csv(input_csv, train_csv, test_csv, valid_csv):
    try:
        df = pd.read_csv(input_csv)
        
        # 检查是否存在confidence列
        if 'confidence' in df.columns:
            threshold = 0.8  # 设置阈值
            filtered_df = df[df['confidence'] > threshold]
        else:
            print("警告：未找到confidence列，使用全部数据")
            filtered_df = df
            
        # 增强随机性：设置随机种子为当前时间戳（随时间动态变化）
        # 每次运行时种子不同，shuffle结果更随机
        random.seed(time.time_ns())  # 使用纳秒级时间戳作为种子，精度更高
        
        # 打乱数据行 - 使用pandas的sample方法
        filtered_df = filtered_df.sample(frac=1, random_state=int(time.time_ns() % 2**32)).reset_index(drop=True)
        filtered_df.to_csv(input_csv, index=False, encoding='utf-8')
        
        total_lines = len(filtered_df)
        train_lines = int(total_lines * 0.6)
        test_lines = int(total_lines * 0.2)

        # 分割数据
        train_data = filtered_df[:train_lines]
        test_data = filtered_df[train_lines:train_lines + test_lines]
        valid_data = filtered_df[train_lines + test_lines:]

        # 保存到CSV文件
        train_data.to_csv(train_csv, index=False, encoding='utf-8')
        test_data.to_csv(test_csv, index=False, encoding='utf-8')
        valid_data.to_csv(valid_csv, index=False, encoding='utf-8')
        
        print(f"数据集划分完成:")
        print(f"训练集: {len(train_data)} 条数据 -> {train_csv}")
        print(f"测试集: {len(test_data)} 条数据 -> {test_csv}")
        print(f"验证集: {len(valid_data)} 条数据 -> {valid_csv}")
        
    except FileNotFoundError:
        print(f"文件 {input_csv} 未找到")
    except Exception as e:
        print(f"划分数据集时出现错误: {e}")

def main():
    input = "/root/KG_inde/DeepKE/example/re/standard/data/origin/entity_offsets.json"
    train_csv = "/root/KG_inde/DeepKE/example/re/standard/data/origin/train.csv"
    test_csv = "/root/KG_inde/DeepKE/example/re/standard/data/origin/test.csv"
    valid_csv = "/root/KG_inde/DeepKE/example/re/standard/data/origin/valid.csv"

    # 先将json转csv（如果需要的话，原代码main中未调用，若需要可添加）
    json_to_csv(input, train_csv)
    
    split_csv(train_csv, train_csv, test_csv, valid_csv)

if __name__ == "__main__":
    main()