# PostgreSQL + pgvector 安裝指南

本指南將協助您安裝和設定 PostgreSQL 資料庫以及 pgvector 擴展，用於智能答題系統。

## 系統需求

- Ubuntu 20.04+ / macOS 10.15+ / Windows 10+
- Python 3.8+
- 至少 4GB 可用磁碟空間

## 一、安裝 PostgreSQL

### Ubuntu/Debian 系統

```bash
# 更新系統套件
sudo apt update

# 安裝 PostgreSQL
sudo apt install postgresql postgresql-contrib postgresql-server-dev-all

# 啟動 PostgreSQL 服務
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 建立資料庫使用者
sudo -u postgres createuser --interactive --pwprompt quiz_user

# 建立資料庫
sudo -u postgres createdb quiz_db -O quiz_user
```

### macOS 系統

```bash
# 使用 Homebrew 安裝
brew install postgresql

# 啟動 PostgreSQL 服務
brew services start postgresql

# 建立資料庫和使用者
psql postgres
CREATE USER quiz_user WITH PASSWORD 'your_password';
CREATE DATABASE quiz_db OWNER quiz_user;
GRANT ALL PRIVILEGES ON DATABASE quiz_db TO quiz_user;
\q
```

### Windows 系統

1. 前往 [PostgreSQL 官網](https://www.postgresql.org/download/windows/) 下載安裝程式
2. 執行安裝程式，記住設定的密碼
3. 開啟 pgAdmin 或命令列工具
4. 建立資料庫和使用者：

```sql
CREATE USER quiz_user WITH PASSWORD 'your_password';
CREATE DATABASE quiz_db OWNER quiz_user;
GRANT ALL PRIVILEGES ON DATABASE quiz_db TO quiz_user;
```

## 二、安裝 pgvector 擴展

### 方法一：從源碼編譯（推薦）

```bash
# 安裝編譯工具
sudo apt install build-essential git

# 下載 pgvector 源碼
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector

# 編譯和安裝
make
sudo make install

# 重啟 PostgreSQL
sudo systemctl restart postgresql
```

### 方法二：使用套件管理器（Ubuntu）

```bash
# 添加 pgvector 倉庫
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -cs)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list

# 更新並安裝
sudo apt update
sudo apt install postgresql-15-pgvector
```

### macOS 使用 Homebrew

```bash
# 安裝 pgvector
brew install pgvector

# 重啟 PostgreSQL
brew services restart postgresql
```

## 三、在資料庫中啟用 pgvector

連接到您的資料庫並啟用擴展：

```bash
# 連接到資料庫
psql -h localhost -U quiz_user -d quiz_db

# 在資料庫中執行
CREATE EXTENSION IF NOT EXISTS vector;

# 驗證安裝
SELECT * FROM pg_extension WHERE extname = 'vector';

# 測試向量功能
SELECT '[1,2,3]'::vector;

# 離開
\q
```

## 四、設定環境變數

建立 `.env` 檔案：

```env
# 資料庫設定
DB_NAME=quiz_db
DB_USER=quiz_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Django 設定
SECRET_KEY=your_secret_key_here
DEBUG=True

# Ollama 模型設定
OLLAMA_MODEL=gemma3:4b
```

## 五、驗證安裝

執行以下 Python 腳本驗證連接：

```python
import psycopg2
import numpy as np

# 測試資料庫連接
try:
    conn = psycopg2.connect(
        host="localhost",
        database="quiz_db", 
        user="quiz_user",
        password="your_password"
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
```

## 六、常見問題解決

### 問題1：pgvector 安裝失敗

```bash
# 確認 PostgreSQL 版本
psql --version

# 確認開發套件已安裝
sudo apt install postgresql-server-dev-all

# 重新編譯
cd pgvector
make clean
make
sudo make install
```

### 問題2：權限不足

```bash
# 給予使用者完整權限
sudo -u postgres psql
ALTER USER quiz_user CREATEDB;
ALTER USER quiz_user SUPERUSER;
\q
```

### 問題3：連接被拒絕

編輯 PostgreSQL 設定檔：

```bash
# 找到設定檔位置
sudo -u postgres psql -c "SHOW config_file;"

# 編輯 postgresql.conf
sudo nano /etc/postgresql/*/main/postgresql.conf

# 修改監聽地址
listen_addresses = 'localhost'

# 編輯 pg_hba.conf
sudo nano /etc/postgresql/*/main/pg_hba.conf

# 添加本地連接規則
local   all             quiz_user                               md5
host    all             quiz_user       127.0.0.1/32            md5

# 重啟服務
sudo systemctl restart postgresql
```

## 七、效能優化建議

### 調整 PostgreSQL 設定

```bash
# 編輯 postgresql.conf
sudo nano /etc/postgresql/*/main/postgresql.conf
```

建議設定：

```conf
# 記憶體設定
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB

# 向量索引優化
maintenance_work_mem = 512MB

# 連接設定
max_connections = 100
```

### 建立向量索引

```sql
-- 在應用程式部署後建立索引以提升查詢效能
CREATE INDEX ON quiz_knowledgechunk USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

## 八、備份與還原

### 資料庫備份

```bash
# 備份整個資料庫
pg_dump -h localhost -U quiz_user quiz_db > quiz_backup.sql

# 只備份資料
pg_dump -h localhost -U quiz_user --data-only quiz_db > quiz_data.sql
```

### 資料庫還原

```bash
# 還原資料庫
psql -h localhost -U quiz_user quiz_db < quiz_backup.sql
```

## 九、安全設定

### 1. 修改預設密碼

```sql
ALTER USER quiz_user WITH PASSWORD 'new_strong_password';
```

### 2. 限制網路存取

```bash
# 編輯 pg_hba.conf，只允許必要的連接
sudo nano /etc/postgresql/*/main/pg_hba.conf
```

### 3. 啟用 SSL

```conf
# 在 postgresql.conf 中
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
```

完成以上步驟後，您的 PostgreSQL + pgvector 環境就設定完成了！