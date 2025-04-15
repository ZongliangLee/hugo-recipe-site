from flask import Flask, jsonify, request
import sqlite3
import requests
import datetime
from flask_cors import CORS
import json
import re
from recipe_md import recipe_to_md  # 引入新的 module
from json_repair import repair_json
from git import Repo, GitCommandError
import os


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# DB 連線設定
DATABASE = 'market.db'

# 建立資料庫連線
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.text_factory = str  # 添加这行以确保正确处理中文
    return conn

# 推送檔案到遠端儲存庫
@app.route('/push-to-remote', methods=['POST'])
def push_to_remote():
    try:
        # 初始化 Git 倉庫
        saved_files = request.get_json()['recipes']
        print(saved_files)
        repo_path = os.path.dirname(os.path.abspath(__file__))
        repo = Repo(repo_path)
        git = repo.git

        # 確保工作目錄乾淨
        if repo.is_dirty(untracked_files=True):
            # 添加所有新生成的檔案
            for filename in saved_files:
                file_path = os.path.join("content/recipes", filename)
                print('file_path',file_path)
                git.add(file_path)

            # 提交
            commit_message = f"Add recipe markdown files: {', '.join(saved_files)}"
            git.commit(m=commit_message)

            # 推送
            git.push("origin", "master")
            return jsonify({
            "message": "Recipes successfully converted to Markdown and pushed to remote",
            "files": saved_files
            }), 200
            
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
    return [row[0] for row in rows]

def unique_crops():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT crop_name FROM product_transactions")
    results = cursor.fetchall()
    ## bob
    return [row[0] for row in results[0:200]]

@app.route('/fetch_combined_data')
def fetch_combined_data():
    # 1. 抓取現有的季節性作物
    exist_seasonals = existing_seasonals()
    # 3. 取得獨特的作物名稱
    u_crops = unique_crops()
    # 4. 過濾出新的作物（即不在現有季節性作物中的）
    new_crops = [crop for crop in u_crops if crop not in exist_seasonals and "甘藍" not in crop]

    # 組合並返回資料
    result = {
        "new_crops": new_crops,
        "existing_seasonals": exist_seasonals
    }
    
    return jsonify(result)

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
    conn = sqlite3.connect('market.db')
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

@app.route('/seasonal_top20', methods=['GET'])
def get_seasonal_top20():
    try:
        # 獲取今天當季食材
        seasonal_ingredients = get_seasonal_ingredients()
        if not seasonal_ingredients:
            return jsonify({"message": "今天沒有當季食材", "data": []}), 200

        # 提取當季食材名稱
        seasonal_names = [item['name'] for item in seasonal_ingredients]

        # 獲取今天的日期
        now = datetime.datetime.now()

        # 計算民國年（西元年 - 1911）
        roc_year = now.year - 1911

        # 格式化為 YYY.MM.DD（民國年.月.日）
        today = f"{roc_year:03d}.{now.strftime('%m')}.{now.strftime('%d')}"

        # 計算前兩天的日期
        two_days_ago = now - datetime.timedelta(days=2)
        two_days_ago_date = f"{roc_year:03d}.{two_days_ago.strftime('%m')}.{two_days_ago.strftime('%d')}"

        # 連接到資料庫
        conn = sqlite3.connect('market.db')
        cursor = conn.cursor()

        # 執行查詢，選取今天和前兩天當季且 trans_quantity 位於後10%的記錄
        query = """
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
            FROM product_transactions
            WHERE trans_quantity > (
                SELECT trans_quantity
                FROM product_transactions
                ORDER BY trans_quantity
                LIMIT 1
                OFFSET (
                    SELECT CAST((COUNT(*) * 0.8) AS INTEGER)
                    FROM product_transactions
                )
            )
            AND crop_name IN ({})
            AND trans_date IN (?, ?)  -- 查詢今天和前兩天的數據
            ORDER BY trans_quantity DESC
        """

        # 動態生成 IN 子句的佔位符
        placeholders = ','.join(['?' for _ in seasonal_names])
        query = query.format(placeholders)

        # 執行查詢，傳入 crop_name 清單和今天、前兩天的日期
        cursor.execute(query, seasonal_names + [today, two_days_ago_date])
        print(query)
        print(seasonal_names)
        print(today, two_days_ago_date)
        rows = cursor.fetchall()
        print(rows)
        conn.close()

        # 格式化結果
        raw_results = [
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

        # 去除重複的資料（根據所有欄位）
        seen = set()
        unique_results = []
        for item in raw_results:
            item_str = json.dumps(item, sort_keys=True)  # 轉為有順序的 JSON 字串當 key
            if item_str not in seen:
                seen.add(item_str)
                unique_results.append(item)

        return jsonify(unique_results), 200

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
