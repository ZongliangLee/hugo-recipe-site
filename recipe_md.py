from datetime import datetime
import os
import opencc
import json

# 設定 Markdown 檔案儲存路徑
RECIPE_DIR = 'hugo-recipe-site/content/recipes/'

# 確保該目錄存在
os.makedirs(RECIPE_DIR, exist_ok=True)

def recipe_to_md(recipe):
    title = recipe["name"]
    filename = f"{datetime.now().strftime('%Y-%m-%d-%H%M%S')}_{title}.md"
    
    converter = opencc.OpenCC('s2t.json')
    json_str = json.dumps(recipe, ensure_ascii=False)
    converted_str = converter.convert(json_str)
    converted_recipe = json.loads(converted_str)

    ingredients_md = "\n".join(
    f"- {item['name']}：{item['amount']}{' ' + item['unit'] if item['unit'] and item['amount'].replace('.', '', 1).isdigit() else ''}"
    for item in converted_recipe["ingredients"]
)



    steps_md = "\n".join(
        f"{idx+1}. {step}" for idx, step in enumerate(converted_recipe["steps"])
    )

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

    path = os.path.join(RECIPE_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown)

    return filename
