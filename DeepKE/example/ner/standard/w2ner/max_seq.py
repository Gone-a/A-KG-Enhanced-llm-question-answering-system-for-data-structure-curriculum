import re
from transformers import BertTokenizer

# ===== 配置 =====
txt_file_path = "/root/KG_inde/DeepKE/example/ner/standard/w2ner/data/data_stream.txt"  # 替换为你的数据文件路径
bert_name = "bert-base-chinese"  # 请确认 DeepKE 配置中使用的 BERT 模型名

# 如果你用的是 RoBERTa-wwm-ext，可改为：
# bert_name = "hfl/chinese-roberta-wwm-ext"

# ===== 加载 tokenizer（W2NER 默认用 BertTokenizer）=====
tokenizer = BertTokenizer.from_pretrained(bert_name)

# ===== 读取文件 =====
with open(txt_file_path, "r", encoding="utf-8") as f:
    text = f.read()

# ===== 按中文句子分割 =====
# 支持 。！？；等常见中文句末标点，也处理换行
sentences = re.split(r'(?<=[。！？；])\s*|\n+', text)
sentences = [s.strip() for s in sentences if s.strip()]

# ===== 统计最长句子的 token 长度 =====
max_len = 0
longest_sent = ""

for sent in sentences:
    # W2NER 输入时会自动加 [CLS] 和 [SEP]
    tokens = tokenizer.tokenize(sent)  # 不包含特殊 token
    token_len_with_special = len(tokens) + 2  # + [CLS] + [SEP]
    
    if token_len_with_special > max_len:
        max_len = token_len_with_special
        longest_sent = sent

# ===== 输出结果 =====
print(f"最长句子（含 [CLS]/[SEP] 共 {max_len} tokens）：\n{longest_sent}\n")
print(f"建议在 DeepKE 的 config.yaml 中设置：max_seq_len: {max_len}")
print(f"（通常向上取整到 64/128/256/512 等，如 {min(512, ((max_len + 63) // 64) * 64)}）")