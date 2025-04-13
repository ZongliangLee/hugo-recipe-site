import sqlite3
import datetime
import requests
import json

# 建立 DB 連線
conn = sqlite3.connect("market.db")
cursor = conn.cursor()

# # 建立 table
# cursor.execute("""
# CREATE TABLE IF NOT EXISTS product_transactions (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     trans_date TEXT,
#     crop_code TEXT,
#     crop_name TEXT,
#     tc_type TEXT,
#     market_code TEXT,
#     market_name TEXT,
#     upper_price REAL,
#     middle_price REAL,
#     lower_price REAL,
#     avg_price REAL,
#     trans_quantity REAL,
#     created_at DATETIME DEFAULT CURRENT_TIMESTAMP
# );
# """)

# 擷取今天的資料
today = datetime.datetime.today()
roc_year = today.year - 1911
date_str = f"{roc_year}.{today.month:02d}.{today.day:02d}"
url = f"https://data.moa.gov.tw/api/v1/AgriProductsTransType/?Start_time={date_str}&End_time={date_str}"

resp = requests.get(url)
data = json.loads(resp.text)['Data']  # 強制將字串轉成 JSON 陣列

# 寫入資料
for item in data:
    print("處理中：", item)  # 看看 item 是不是字典
    cursor.execute("""
        INSERT INTO product_transactions (
            trans_date, crop_code, crop_name, tc_type,
            market_code, market_name,
            upper_price, middle_price, lower_price,
            avg_price, trans_quantity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item["TransDate"], item["CropCode"], item["CropName"], item["TcType"],
        item["MarketCode"], item["MarketName"],
        item["Upper_Price"], item["Middle_Price"], item["Lower_Price"],
        item["Avg_Price"], item["Trans_Quantity"]
    ))

conn.commit()
conn.close()

print("✅ 資料已寫入 SQLite 資料庫")
