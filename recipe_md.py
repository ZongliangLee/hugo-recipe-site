from datetime import datetime
import os
import opencc
import json
import re
import logging

# 設置日誌記錄
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 設定 Markdown 檔案儲存路徑
RECIPE_DIR = 'content/recipes/'

try:
    os.makedirs(RECIPE_DIR, exist_ok=True)
    logger.info(f"確保目錄存在：{RECIPE_DIR}")
except Exception as e:
    logger.error(f"無法創建目錄 {RECIPE_DIR}：{str(e)}")
    raise

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def recipe_to_md(recipe):
    try:
        if not isinstance(recipe, dict) or "name" not in recipe:
            raise ValueError("recipe 必須是一個字典並包含 'name' 鍵")

        converter = opencc.OpenCC('s2t.json')
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
ingredients:
{ingredients_yaml}
steps:
{steps_yaml}
---
"""

        # 構建正文（可選）
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
    test_recipe = {
        "name": "涼拌油麥菜",
        "ingredients": [
            {"name": "油麥菜", "amount": "1把"},
            {"name": "蒜末", "amount": "1小匙"},
            {"name": "辣椒油", "amount": "1大匙"},
            {"name": "鹽", "amount": "適量"}
        ],
        "steps": [
            "將油麥菜清洗乾淨，切成段。",
            "鍋中加水煮沸，焯燉10秒後撈出瀝幹水分。",
            "加入蒜末、辣椒油和鹽調味即可。"
        ],
        "calories": "每人約 60 卡",
        "price": "零售價估算（單位：臺幣）：30"
    }

    try:
        filename = recipe_to_md(test_recipe)
        print(f"返回的檔案名稱：{filename}")
    except Exception as e:
        print(f"錯誤：{str(e)}")