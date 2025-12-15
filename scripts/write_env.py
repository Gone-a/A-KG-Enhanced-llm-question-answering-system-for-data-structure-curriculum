# -*- coding: utf-8 -*-
"""
在项目根目录创建或更新 .env 的CLI脚本。
示例：
python scripts/write_env.py --neo4j_uri bolt://localhost:7687 --neo4j_username neo4j --neo4j_password password \
  --ark_api_key xxx --doubao_model_id yyy --ark_api_base_url https://ark.cn-beijing.volces.com/api/v3
"""

import argparse
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="写入项目根目录 .env")
    p.add_argument('--neo4j_uri', required=True)
    p.add_argument('--neo4j_username', required=True)
    p.add_argument('--neo4j_password', required=True)
    p.add_argument('--ark_api_key', required=True)
    p.add_argument('--doubao_model_id', required=True)
    p.add_argument('--ark_api_base_url', default='https://ark.cn-beijing.volces.com/api/v3')
    return p.parse_args()


def main():
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    env_path = root / '.env'
    lines = [
        f"NEO4J_URI={args.neo4j_uri}",
        f"NEO4J_USERNAME={args.neo4j_username}",
        f"NEO4J_PASSWORD={args.neo4j_password}",
        f"ARK_API_KEY={args.ark_api_key}",
        f"DOUBAO_MODEL_ID={args.doubao_model_id}",
        f"ARK_API_BASE_URL={args.ark_api_base_url}",
    ]
    env_path.write_text("\n".join(lines) + "\n", encoding='utf-8')
    print(f"已写入: {env_path}")


if __name__ == '__main__':
    main()