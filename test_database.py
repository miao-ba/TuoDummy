import psycopg2
import numpy as np

# 測試資料庫連接
try:
    conn = psycopg2.connect(
        host="localhost",
        database="quiz_db", 
        user="quiz_user",
        password="0000"
    )
    
    cur = conn.cursor()
    
    # 測試 pgvector
    cur.execute("SELECT '[1,2,3]'::vector;")
    result = cur.fetchone()
    print(f"向量測試成功: {result[0]}")
    
    # 測試向量相似度
    cur.execute("SELECT '[1,2,3]'::vector <-> '[3,2,1]'::vector;")
    distance = cur.fetchone()[0]
    print(f"向量距離: {distance}")
    
    conn.close()
    print("資料庫連接測試成功！")
    
except Exception as e:
    print(f"連接失敗: {e}")
