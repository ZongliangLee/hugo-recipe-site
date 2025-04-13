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

# 確保該目錄存在
try:
    os.makedirs(RECIPE_DIR, exist_ok=True)
    logger.info(f"確保目錄存在：{RECIPE_DIR}")
except Exception as e:
    logger.error(f"無法創建目錄 {RECIPE_DIR}：{str(e)}")
    raise

def sanitize_filename(filename):
    """
    清理檔案名稱，去除非法字符
    """
    # 將非法字符替換為下劃線
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def recipe_to_md(recipe):
    try:
        # 確保 recipe 是字典並包含必要的鍵
        if not isinstance(recipe, dict) or "name" not in recipe:
            raise ValueError("recipe 必須是一個字典並包含 'name' 鍵")

        title = recipe["name"]
        # 生成檔案名稱並清理
        filename_base = f"{datetime.now().strftime('%Y-%m-%d-%H%M%S')}_{title}"
        filename = sanitize_filename(filename_base) + ".md"
        logger.info(f"生成的檔案名稱：{filename}")

        # 繁簡轉換
        converter = opencc.OpenCC('s2t.json')
        json_str = json.dumps(recipe, ensure_ascii=False)
        converted_str = converter.convert(json_str)
        converted_recipe = json.loads(converted_str)

        # 檢查必要的鍵是否存在
        required_keys = ["ingredients", "steps", "calories", "price"]
        for key in required_keys:
            if key not in converted_recipe:
                raise ValueError(f"recipe 缺少必要的鍵：{key}")

        # 格式化食材
        ingredients_md = "\n".join(
            f"- {item['name']}：{item['amount']}{' ' + item['unit'] if item['unit'] and item['amount'].replace('.', '', 1).isdigit() else ''}"
            for item in converted_recipe["ingredients"]
        )

        # 格式化做法
        steps_md = "\n".join(
            f"{idx+1}. {step}" for idx, step in enumerate(converted_recipe["steps"])
        )

        # 構建 Markdown 內容
        markdown = f"""---
title: "{title}"
date: {datetime.now().strftime('%Y-%m-%d')}
draft: false
---

### 食材

{ingredients_md}

### 作法

{steps_md}

### 每人熱量  
{converted_recipe['calories']}

### 成本估算
- 零售價：{converted_recipe['price']}
"""

        # 確保檔案路徑
        path = os.path.join(RECIPE_DIR, filename)
        logger.info(f"準備寫入檔案：{path}")

        # 檢查路徑權限
        if not os.access(RECIPE_DIR, os.W_OK):
            raise PermissionError(f"沒有寫入權限：{RECIPE_DIR}")

        # 寫入檔案
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
    # 模擬一個 recipe
    test_recipe = {
        "name": "絲瓜炒蛋",
        "ingredients": [
            {"name": "絲瓜", "amount": "2", "unit": "根"},
            {"name": "鸡蛋", "amount": "4", "unit": "個"}
        ],
        "steps": [
            "將絲瓜去皮，切成段落。",
            "鸡蛋打散，加入少許鹽和胡椒粉攪拌均勻。"
        ],
        "calories": "200 kcal",
        "price": "32 元"
    }

    try:
        filename = recipe_to_md(test_recipe)
        print(f"返回的檔案名稱：{filename}")
    except Exception as e:
        print(f"錯誤：{str(e)}")