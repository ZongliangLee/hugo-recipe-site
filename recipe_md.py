from datetime import datetime
import os
import opencc
import json
import re
import logging
import requests
from pathlib import Path
import time

# 設置日誌記錄
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 設定 Markdown 檔案儲存路徑
RECIPE_DIR = 'content/recipes/'
IMAGE_DIR = 'static/images/recipes/'

# 確保目錄存在
try:
    os.makedirs(RECIPE_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    logger.info(f"確保目錄存在：{RECIPE_DIR}, {IMAGE_DIR}")
except Exception as e:
    logger.error(f"無法創建目錄：{str(e)}")
    raise

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def generate_image_with_comfyui(prompt, comfyui_api_url, recipe_name):
    """
    使用 ComfyUI 生成圖片並儲存
    """
    try:
        # 讀取 lora.json 工作流程
        with open("/Users/s6307/Documents/ComfyUI/user/default/workflows/lora.json", "r", encoding="utf-8") as f:
            workflow = json.load(f)

        # 找到正向提示的 CLIPTextEncode 節點（ID 6）
        for node in workflow["nodes"]:
            if node["id"] == 6 and node["type"] == "CLIPTextEncode":
                node["widgets_values"][0] = prompt
                break

        # 構建 ComfyUI API 請求
        payload = {
            "prompt": workflow
        }
        logger.info(f"傳送 ComfyUI 請求：{comfyui_api_url}")
        response = requests.post(comfyui_api_url, json=payload)
        response.raise_for_status()

        # 獲取 prompt_id
        result = response.json()
        prompt_id = result["prompt_id"]
        logger.info(f"ComfyUI 任務已提交，prompt_id：{prompt_id}")

        # 輪詢檢查任務狀態
        history_url = comfyui_api_url.replace("/prompt", "/history")
        while True:
            response = requests.get(f"{history_url}/{prompt_id}")
            response.raise_for_status()
            history = response.json()
            if prompt_id in history:
                break
            time.sleep(1)

        # 獲取生成的圖片
        output_node_id = "9"  # SaveImage 節點的 ID
        output_files = history[prompt_id]["outputs"][output_node_id]["images"]
        if not output_files:
            raise ValueError("未找到生成的圖片")

        # 下載圖片
        image_filename = sanitize_filename(f"{recipe_name}.jpg")
        image_path = os.path.join(IMAGE_DIR, image_filename)
        image_url = comfyui_api_url.replace("/prompt", f"/view?filename={output_files[0]['filename']}&subfolder={output_files[0].get('subfolder', '')}&type={output_files[0].get('type', 'output')}")
        image_response = requests.get(image_url)
        image_response.raise_for_status()

        with open(image_path, "wb") as f:
            f.write(image_response.content)
        logger.info(f"圖片已儲存：{image_path}")

        return f"/images/recipes/{image_filename}"
    except Exception as e:
        logger.error(f"使用 ComfyUI 生成圖片失敗：{str(e)}")
        raise

def recipe_to_md(recipes, comfyui_api_url):
    try:
        if not isinstance(recipes, list) or not recipes:
            raise ValueError("recipes 必須是一個非空列表")

        converter = opencc.OpenCC('s2t.json')
        for recipe in recipes:
            if "name" not in recipe or "image_prompt" not in recipe:
                raise ValueError("每個 recipe 必須包含 'name' 和 'image_prompt' 鍵")

            title = converter.convert(recipe["name"])
            filename_base = f"{datetime.now().strftime('%Y-%m-%d-%H%M%S')}_{title}"
            filename = sanitize_filename(filename_base) + ".md"
            logger.info(f"生成的檔案名稱：{filename}")

            json_str = json.dumps(recipe, ensure_ascii=False)
            converted_str = converter.convert(json_str)
            converted_recipe = json.loads(converted_str)

            required_keys = ["ingredients", "steps", "calories", "price"]
            for key in required_keys:
                if key not in converted_recipe:
                    raise ValueError(f"recipe 缺少必要的鍵：{key}")

            # 使用 ComfyUI 生成圖片
            image_url = generate_image_with_comfyui(converted_recipe["image_prompt"], comfyui_api_url, title)

            # 構建 Front Matter
            ingredients_yaml = "\n".join(
                f"  - name: \"{item['name']}\"\n    amount: \"{item['amount']}\""
                for item in converted_recipe["ingredients"]
            )
            steps_yaml = "\n".join(
                f"  - \"{step}\""
                for step in converted_recipe["steps"]
            )

            front_matter = f"""---
title: "{title}"
date: {datetime.now().strftime('%Y-%m-%d')}
draft: false
calories: "{converted_recipe['calories']}"
price: "{converted_recipe['price']}"
img: "{image_url}"
ingredients:
{ingredients_yaml}
steps:
{steps_yaml}
---
"""

            markdown = f"{front_matter}\n這是一道簡單的{title}，適合夏天食用。\n"
            path = os.path.join(RECIPE_DIR, filename)
            logger.info(f"準備寫入檔案：{path}")

            if not os.access(RECIPE_DIR, os.W_OK):
                raise PermissionError(f"沒有寫入權限：{RECIPE_DIR}")

            with open(path, "w", encoding="utf-8") as f:
                f.write(markdown)
            logger.info(f"成功寫入檔案：{path}")

        return filename

    except PermissionError as e:
        logger.error(f"寫入檔案失敗（權限問題）：{str(e)}")
        raise
    except Exception as e:
        logger.error(f"寫入檔案失敗：{str(e)}")
        raise

# 測試程式碼
if __name__ == "__main__":
    test_recipes = [
        {
            "name": "涼拌油麥菜",
            "servings": "適合 4 人的份量",
            "ingredients": [
                {"name": "油麥菜", "amount": "1", "unit": "把"},
                {"name": "蒜末", "amount": "1", "unit": "小匙"},
                {"name": "辣椒油", "amount": "1", "unit": "大匙"},
                {"name": "鹽", "amount": "適量", "unit": ""}
            ],
            "steps": [
                "將油麥菜清洗乾淨，切成段。",
                "鍋中加水煮沸，焯燉10秒後撈出瀝幹水分。",
                "加入蒜末、辣椒油和鹽調味即可。"
            ],
            "calories": "每人約 60 卡",
            "price": "零售價估算（單位：台幣）：30",
            "image_prompt": "an illustration of a 涼拌油麥菜, with glistening surface, placed on a white porcelain plate, surrounded by minced garlic and drizzled with chili oil. The dish is cooked to perfection, with tender texture, presented with soft lighting, minimal shadows, and meticulous watercolor style, emphasizing the freshness and flavor of the ingredients. Clean white background, realistic food drawing, magazine-style presentation."
        },
        {
            "name": "絲瓜炒蛋",
            "servings": "適合 4 人的份量",
            "ingredients": [
                {"name": "絲瓜", "amount": "2", "unit": "根"},
                {"name": "雞蛋", "amount": "4", "unit": "個"},
                {"name": "鹽", "amount": "適量", "unit": ""}
            ],
            "steps": [
                "將絲瓜去皮切段，雞蛋打散備用。",
                "熱鍋加油，炒香雞蛋後加入絲瓜翻炒。",
                "加鹽調味，炒至絲瓜軟嫩即可。"
            ],
            "calories": "每人約 100 卡",
            "price": "零售價估算（單位：台幣）：40",
            "image_prompt": "an illustration of a 絲瓜炒蛋, with glistening surface, placed on a white porcelain plate, garnished with chopped green onions. The dish is cooked to perfection, with tender texture, presented with soft lighting, minimal shadows, and meticulous watercolor style, emphasizing the freshness and flavor of the ingredients. Clean white background, realistic food drawing, magazine-style presentation."
        }
    ]

    try:
        comfyui_api_url = "http://localhost:8000/prompt"  # 更新端口為 8000
        filename = recipe_to_md(test_recipes, comfyui_api_url)
        print(f"返回的檔案名稱：{filename}")
    except Exception as e:
        print(f"錯誤：{str(e)}")