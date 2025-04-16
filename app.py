from flask import Flask, jsonify, request
import sqlite3
import requests
import datetime
from datetime import timedelta
from flask_cors import CORS
import json
import re
from recipe_md import recipe_to_md, generate_image_with_comfyui
from json_repair import repair_json
from git import Repo, GitCommandError
import os


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# DB 連線設定
DATABASE = 'new.db'
# 不重複菜單天數
UNIQUE_RECIPES_DAYS = 7
IMAGE_MODEL="flux_api.json"

comfyui_api_url = "http://localhost:8188/prompt"

# 建立資料庫連線
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.text_factory = str  # 添加这行以确保正确处理中文
    return conn

# 推送檔案到遠端儲存庫
from flask import request, jsonify
from git import Repo, GitCommandError
import os

@app.route('/generate_ingredients_image', methods=['POST'])
def generate_ingredients_image():
    try:
        # 設定 recipes 目錄
        recipes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "recipes")
        
        data = request.get_json(force=True)  # 添加 force=True 确保正确解析 JSON
        prompt = data.get("image_prompt")
        titles = data.get("titles")
        # 把titles list轉成string, 並把逗號移除
        recipe_name = ", ".join(titles).replace(",", "")
        image_url = generate_image_with_comfyui(prompt, comfyui_api_url, recipe_name, workflow_path=IMAGE_MODEL)
        return jsonify({"image_url": image_url}), 200
    except Exception as e:
        return jsonify({"error": f"伺服器錯誤：{str(e)}"}), 500



@app.route('/get_historical_recipes', methods=['GET'])
def get_historical_recipes():
    try:
        # 設定 recipes 目錄
        recipes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "recipes")
        
        # 計算 7 天前的日期（包含今天）
        cutoff_date = datetime.datetime.now() - timedelta(days=UNIQUE_RECIPES_DAYS)
        
        # 儲存唯一菜名
        unique_recipes = set()
        
        # 遍歷 recipes 目錄
        if not os.path.exists(recipes_dir):
            return jsonify({"recipes": []}), 200
        
        for filename in os.listdir(recipes_dir):
            # 匹配檔案名稱格式: YYYY-MM-DD-HHMMSS_菜名
            match = re.match(r"(\d{4}-\d{2}-\d{2}-\d{6})_(.+)\.md$", filename)
            if match:
                timestamp_str, recipe_name = match.groups()
                try:
                    # 解析檔案的日期
                    file_date = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d-%H%M%S")
                    # 檢查是否在過去 7 天內
                    if file_date >= cutoff_date:
                        unique_recipes.add(recipe_name)
                except ValueError:
                    continue  # 無效日期格式，跳過
        
        return jsonify({"recipes": list(unique_recipes)}), 200
    
    except Exception as e:
        return jsonify({"error": f"伺服器錯誤：{str(e)}"}), 500
    
@app.route('/push-to-remote', methods=['POST'])
def push_to_remote():
    try:
        saved_files = request.get_json()['recipes']
        print(saved_files)

        repo_path = os.path.dirname(os.path.abspath(__file__))
        repo = Repo(repo_path)
        git = repo.git

        image_folder = os.path.join(repo_path, "static", "images", "recipes")
        markdown_folder = os.path.join("content", "recipes")

        added_files = []

        if repo.is_dirty(untracked_files=True):
            for filename in saved_files:
                # 加入 markdown 檔案
                md_path = os.path.join(markdown_folder, filename)
                if os.path.exists(md_path):
                    git.add(md_path)
                    added_files.append(md_path)
                
                # 推測圖片檔名並加入
                if "_" in filename:
                    image_name = filename.split("_", 1)[1].replace(".md", ".jpg")
                    image_path = os.path.join("static", "images", "recipes", image_name)
                    abs_image_path = os.path.join(repo_path, image_path)
                    if os.path.exists(abs_image_path):
                        git.add(image_path)
                        added_files.append(image_path)

            if added_files:
                commit_message = f"Add recipe markdown and image files: {', '.join(saved_files)}"
                git.commit(m=commit_message)
                git.push("origin", "master")
                return jsonify({
                    "message": "Recipes successfully converted to Markdown and pushed to remote",
                    "files": saved_files,
                    "images": [f.split("_", 1)[1].replace(".md", ".jpg") for f in saved_files]
                }), 200
            else:
                return jsonify({
                    "message": "No valid files found to push."
                }), 400

        else:
            return jsonify({
                "message": "nothing to push"
            }), 200

    except GitCommandError as e:
        return jsonify({
            "message": f"Git error: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "message": f"error: {str(e)}"
        }), 500



@app.route('/generate-recipe', methods=['POST'])
def generate_recipe():
    try:
        # 從請求中取得 LLM 回傳的 JSON
        data = request.json

        if 'recipes' not in data:
            return jsonify({"error": "Invalid data format, 'recipes' not found"}), 400
        
        recipe = data['recipes']
        
        # 轉換食譜為 markdown
        saved_files = []
        for entry in recipe:
            filename = recipe_to_md(entry)
            saved_files.append(filename)
    
        # 返回所有檔案名稱和推送結果
        return jsonify({
            "message": "Recipes successfully converted to Markdown and pushed to remote",
            "files": saved_files
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# 插入季節性食材資料
@app.route('/insert_seasonal_ingredients', methods=['POST'])
def insert_seasonal_ingredients():
    # 接收 JSON 請求
    data = request.get_json(force=True)  # 添加 force=True 确保正确解析 JSON
    seasonal_ingredients = data.get('seasonal_ingredients', [])

    conn = get_db()
    cursor = conn.cursor()

    # 插入數據
    for ingredient in seasonal_ingredients:
        cursor.execute("""
            INSERT INTO seasonal_ingredients (name, month_start, month_end, type)
            VALUES (?, ?, ?, ?)
        """, (ingredient['name'], ingredient['month_start'], ingredient['month_end'], ingredient['type']))

    conn.commit()
    conn.close()
    return jsonify({"status": "success"}), 200


# 創建當令食材資料表
def create_seasonal_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seasonal_ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT,
        month_start INTEGER,
        month_end INTEGER
    );
    """)
    conn.commit()
    conn.close()

def existing_seasonals():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM seasonal_ingredients")
    rows = cursor.fetchall()
    conn.close()
    return [str(row[0]).strip() for row in rows if row[0]]


def unique_crops():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT crop_name FROM product_transactions")
    results = cursor.fetchall()
    conn.close()
    return [str(row[0]).strip() for row in results if row[0]]


@app.route('/fetch_combined_data')
def fetch_combined_data():
    exist_seasonals = existing_seasonals()
    u_crops = unique_crops()
    new_crops = [crop for crop in u_crops if crop not in exist_seasonals]
    return jsonify({
        "new_crops": new_crops,
        "existing_seasonals": exist_seasonals
    })

# 抓取農產品交易資料並儲存
def fetch_and_store_data():
    today = datetime.datetime.today()
    roc_year = today.year - 1911
    date_str = f"{roc_year}.{today.month:02d}.{today.day:02d}"
    
    url = f"https://data.moa.gov.tw/api/v1/AgriProductsTransType/?Start_time={date_str}&End_time={date_str}"
    response = requests.get(url)
    data = json.loads(response.text)['Data']  # 強制將字串轉成 JSON 陣列

    conn = get_db()
    cursor = conn.cursor()

    for item in data:
        cursor.execute("""
            INSERT INTO product_transactions (
                trans_date, crop_code, crop_name, tc_type,
                market_code, market_name, upper_price, middle_price,
                lower_price, avg_price, trans_quantity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["TransDate"], item["CropCode"], item["CropName"], item["TcType"],
            item["MarketCode"], item["MarketName"], item["Upper_Price"], item["Middle_Price"],
            item["Lower_Price"], item["Avg_Price"], item["Trans_Quantity"]
        ))

    conn.commit()
    conn.close()

def get_seasonal_ingredients():
    now = datetime.datetime.now()
    current_month = now.month
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, type, month_start, month_end
        FROM seasonal_ingredients
    """)
    rows = cursor.fetchall()
    conn.close()

    def is_in_season(start, end, month):
        if start <= end:
            return start <= month <= end
        else:  # 跨年
            return month >= start or month <= end

    seasonal_today = [
        {"name": row[0], "type": row[1]}
        for row in rows
        if is_in_season(row[2], row[3], current_month)
    ]

    return seasonal_today

@app.route('/seasonal_top50', methods=['GET'])
def get_seasonal_top50():
    try:
        # 獲取 seasonal 參數，預設為 True
        seasonal = request.args.get('seasonal', 'true').lower() == 'true'

        # 獲取當季食材（僅在 seasonal=True 時需要）
        seasonal_ingredients = []
        seasonal_names = []
        if seasonal:
            seasonal_ingredients = get_seasonal_ingredients()
            if not seasonal_ingredients:
                return jsonify({"message": "今天沒有當季食材", "data": []}), 200
            seasonal_names = [item['name'] for item in seasonal_ingredients]

        # 獲取今天的日期
        now = datetime.datetime.now()
        roc_year = now.year - 1911
        today = f"{roc_year:03d}.{now.strftime('%m')}.{now.strftime('%d')}"
        two_days_ago = now - datetime.timedelta(days=1)
        two_days_ago_date = f"{roc_year:03d}.{two_days_ago.strftime('%m')}.{two_days_ago.strftime('%d')}"

        # 連接到資料庫
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()

            # 基礎 SQL 查詢，使用 ROW_NUMBER() 過濾重複 crop_name
            query = """
                WITH RankedCrops AS (
                    SELECT 
                        trans_date, 
                        crop_code, 
                        crop_name, 
                        tc_type, 
                        market_code, 
                        market_name, 
                        upper_price, 
                        middle_price, 
                        lower_price, 
                        avg_price, 
                        trans_quantity,
                        ROW_NUMBER() OVER (PARTITION BY crop_name ORDER BY trans_quantity DESC) as rn
                    FROM product_transactions
                    WHERE trans_quantity > (
                        SELECT trans_quantity
                        FROM product_transactions
                        ORDER BY trans_quantity
                        LIMIT 1
                        OFFSET (
                            SELECT CAST((COUNT(*) * 0.5) AS INTEGER)
                            FROM product_transactions
                        )
                    )
                    AND trans_date IN (?, ?)
                    {}
                )
                SELECT 
                    trans_date, 
                    crop_code, 
                    crop_name, 
                    tc_type, 
                    market_code, 
                    market_name, 
                    upper_price, 
                    middle_price, 
                    lower_price, 
                    avg_price, 
                    trans_quantity
                FROM RankedCrops
                WHERE rn = 1
                ORDER BY trans_quantity DESC
            """

            # 根據 seasonal 動態添加 crop_name 條件
            if seasonal:
                placeholders = ','.join(['?' for _ in seasonal_names])
                crop_name_condition = f"AND crop_name IN ({placeholders})"
                query = query.format(crop_name_condition)
                params = [today, two_days_ago_date] + seasonal_names
            else:
                query = query.format("")
                params = [today, two_days_ago_date]

            # 執行查詢
            print(query, params)
            cursor.execute(query, params)
            rows = cursor.fetchall()

        # 格式化結果
        results = [
            {
                "trans_date": row[0],
                "crop_code": row[1],
                "crop_name": row[2],
                "tc_type": row[3],
                "market_code": row[4],
                "market_name": row[5],
                "upper_price": row[6],
                "middle_price": row[7],
                "lower_price": row[8],
                "avg_price": row[9],
                "trans_quantity": row[10]
            }
            for row in rows
        ]

        return jsonify(results), 200

    except sqlite3.Error as e:
        return jsonify({"error": f"資料庫錯誤：{str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"伺服器錯誤：{str(e)}"}), 500


def process_llm_response(llm_response):
    cleaned_response = re.sub(r"<think>.*?</think>", "", llm_response, flags=re.DOTALL)
    cleaned_response = re.sub(r"\n+", "\n", cleaned_response).strip()
    json_block_match = re.search(r"```json\s*(\{[\s\S]*\})\s*", cleaned_response)
    if not json_block_match:
        raise ValueError("未找到 JSON 區塊，請確認 LLM 回傳格式")
    json_str = json_block_match.group(1)
    repaired_json_str = repair_json(json_str)
    try:
        parsed = json.loads(repaired_json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析錯誤：{e}")
    if "recipes" not in parsed or not isinstance(parsed["recipes"], list):
        raise ValueError("缺少 'recipes' 陣列或格式錯誤")
    return parsed

@app.route('/process-llm', methods=['POST'])
def handle_llm():
    data = request.get_json()
    llm_response = data.get("llmResponse")
    print('llm_response',llm_response)

    if not llm_response:
        return jsonify({"error": "缺少 llmResponse"}), 400

    try:
        processed = process_llm_response(llm_response)
        return jsonify(processed)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    

@app.route("/api/seasonal-today", methods=["GET"])
def seasonal_today_route():
    return jsonify(get_seasonal_ingredients())
    
@app.route('/')
def home():
    return "Flask爬蟲應用程式運行中"

@app.route('/fetch_data')
def fetch_data():
    fetch_and_store_data()
    return jsonify({"status": "成功抓取並儲存數據"})

if __name__ == '__main__':
    # create_seasonal_table()  # 初始化資料庫    
    for rule in app.url_map.iter_rules():
        print(f"{rule} -> {rule.endpoint}")
    app.run(host='0.0.0.0',debug=True)
