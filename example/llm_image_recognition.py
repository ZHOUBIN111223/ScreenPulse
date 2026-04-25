"""
LLM 图片识别 - 英文命名
使用 gemma4:e2b 模型识别图片内容并给出英文名称
"""

import base64
import os
import requests

# API 配置
API_URL = "http://127.0.0.1:8000/v1/chat/completions"
API_KEY = "lmsk_4ab791d3f3020e8dfcaf02791d930f74fb7ba6c301c34896f330640b5d661207"
MODEL = "gemma4:e2b"

DATA_DIR = "data"


def encode_image_to_base64(image_path: str) -> str:
    """将图片编码为 base64 字符串"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def identify_image(image_path: str) -> str:
    """使用 LLM 识别图片并返回英文名称"""
    base64_image = encode_image_to_base64(image_path)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Please identify the main content of this image and provide a short English name (2-4 words, using underscores for spaces). Example: 'desktop_screenshot', 'document_paper', 'code_editor'. Just output the name, nothing else."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    }

    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    result = response.json()
    return result["choices"][0]["message"]["content"].strip()


def main():
    """主函数：识别 data 目录下的所有图片"""
    if not os.path.exists(DATA_DIR):
        print(f"错误：目录 {DATA_DIR} 不存在")
        return

    # 获取所有图片文件
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
    image_files = [
        f for f in os.listdir(DATA_DIR)
        if os.path.splitext(f.lower())[1] in image_extensions
    ]

    if not image_files:
        print(f"在 {DATA_DIR} 目录下未找到图片文件")
        return

    print(f"找到 {len(image_files)} 张图片，开始识别...\n")

    results = {}
    for filename in image_files:
        image_path = os.path.join(DATA_DIR, filename)
        print(f"正在识别: {filename}")
        try:
            english_name = identify_image(image_path)
            results[filename] = english_name
            print(f"  -> {english_name}")
        except Exception as e:
            print(f"  -> 识别失败: {e}")
            results[filename] = "识别失败"

    print("\n" + "=" * 50)
    print("识别结果汇总:")
    print("=" * 50)
    for filename, name in results.items():
        print(f"{filename}: {name}")


if __name__ == "__main__":
    main()
