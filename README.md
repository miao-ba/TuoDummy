# 智能答題系統 🧠

基於 AI 的個性化學習平台，支援自定義題目生成和閃卡快速答題。

## ✨ 主要功能

- 🎯 **智能題目生成** - 基於知識庫內容自動生成多種類型題目
- 📱 **響應式設計** - 完美適配手機、平板和桌面設備
- 🔄 **閃卡答題** - Tinder 風格的快速學習模式
- 📚 **知識庫管理** - 上傳文本文件建立個人知識庫
- 🎨 **現代化界面** - 美觀的 UI 設計和流暢的動畫效果
- 📊 **學習統計** - 詳細的答題記錄和進度追蹤

## 🏗️ 技術架構

- **後端**: Django 4.2 + PostgreSQL + pgvector
- **前端**: Bootstrap 5 + 原生 JavaScript
- **AI 模型**: Ollama (本地部署) + Jina Embeddings
- **向量搜索**: pgvector 實現 RAG 檢索
- **容器化**: Docker + Docker Compose

## 🚀 快速開始

### 方法一：Docker Compose (推薦)

```bash
# 1. 克隆專案
git clone <repository-url>
cd quiz-system

# 2. 啟動所有服務
docker-compose up -d

# 3. 等待服務啟動完成
docker-compose logs -f web

# 4. 安裝 Ollama 模型
docker exec quiz_ollama ollama pull gemma3:4b

# 5. 建立管理員帳戶
docker exec -it quiz_web python manage.py createsuperuser

# 6. 訪問系統
open http://localhost:8000
```

### 方法二：本地安裝

#### 1. 環境準備

```bash
# 安裝 Python 3.8+
python3 --version

# 安裝 PostgreSQL 和 pgvector
# 詳見 database_setup.md
```

#### 2. 安裝依賴

```bash
# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安裝 Python 套件
pip install -r requirements.txt
```

#### 3. 設定環境變數

```bash
# 複製環境變數模板
cp .env.template .env

# 編輯 .env 檔案，設定資料庫連接資訊
nano .env
```

#### 4. 設定資料庫

```bash
# 建立資料庫
sudo -u postgres createdb quiz_db -O quiz_user

# 啟用 pgvector 擴展
sudo -u postgres psql quiz_db -c "CREATE EXTENSION vector;"
```

#### 5. 安裝 Ollama

```bash
# 安裝 Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 啟動服務
ollama serve

# 安裝模型 (新終端)
ollama pull gemma3:4b
```

#### 6. 初始化系統

```bash
# 執行自動化設定腳本
chmod +x start.sh
./start.sh
```

或手動執行：

```bash
# 執行資料庫遷移
python manage.py makemigrations
python manage.py migrate

# 建立管理員
python manage.py createsuperuser

# 收集靜態檔案
python manage.py collectstatic

# 啟動開發伺服器
python manage.py runserver
```

## 📖 使用指南

### 1. 系統概覽

訪問 `http://localhost:8000` 進入系統首頁。

### 2. 知識庫管理

#### 建立知識庫
1. 點擊「知識庫」→「新增」
2. 輸入知識庫名稱
3. 上傳 `.txt` 格式的文本文件
4. 系統自動生成摘要和向量索引

#### 管理知識庫
- 瀏覽：查看所有知識庫和摘要
- 查看：預覽知識庫內容
- 刪除：移除不需要的知識庫

### 3. 答題功能

#### 自定義題目
1. 選擇一個或多個知識庫
2. 選擇題目類型：
   - 選擇題 (multiple_choice)
   - 是非題 (true_false) 
   - 簡答題 (short_answer)
   - 論述題 (essay)
3. 設定難度等級 (簡單/中等/困難)
4. 選擇題目數量 (1-20 題)
5. 開始答題

#### 閃卡模式
1. 選擇知識庫
2. 設定難度和數量
3. 使用手勢或按鈕快速答題：
   - 左滑 / 左箭頭：錯誤
   - 右滑 / 右箭頭：正確

### 4. 查看結果

答題完成後可以：
- 查看總分和正確率
- 檢視每題的詳細解析
- 獲得個性化學習建議
- 在個人中心查看歷史記錄

## 🔧 系統測試

執行系統測試確保一切正常：

```bash
# 執行完整測試
python test_system.py

# 或在 Docker 中執行
docker exec quiz_web python test_system.py
```

## 🐛 常見問題

### Q: pgvector 安裝失敗
**A**: 確保已安裝 PostgreSQL 開發套件：
```bash
sudo apt install postgresql-server-dev-all
```

### Q: Ollama 連接失敗
**A**: 檢查 Ollama 服務是否運行：
```bash
curl http://localhost:11434/api/tags
```

### Q: 向量搜索緩慢
**A**: 建立向量索引：
```sql
CREATE INDEX ON quiz_knowledgechunk USING ivfflat (embedding vector_cosine_ops);
```

### Q: 記憶體不足
**A**: 調整 PostgreSQL 設定：
```conf
shared_buffers = 256MB
work_mem = 4MB
```

## 📊 效能優化

### 資料庫優化
```sql
-- 建立向量索引
CREATE INDEX quiz_embedding_idx ON quiz_knowledgechunk 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 優化查詢
ANALYZE quiz_knowledgechunk;
```

### 應用層優化
- 使用 Redis 快取頻繁查詢
- 調整批量處理大小
- 開啟 Django 查詢快取

## 🔒 安全設定

### 生產環境部署
1. 設定 `DEBUG=False`
2. 使用強密碼
3. 配置 HTTPS
4. 設定防火牆規則
5. 定期備份資料庫

## 🤝 貢獻指南

1. Fork 專案
2. 建立功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交變更 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 開啟 Pull Request

## 📝 版本歷史

- **v1.0.0** - 初始版本
  - 基本答題功能
  - 知識庫管理
  - RAG 檢索系統

## 📄 授權協議

本專案採用 MIT 授權協議 - 詳見 [LICENSE](LICENSE) 檔案

## 🙏 致謝

- [Django](https://djangoproject.com/) - Web 框架
- [PostgreSQL](https://postgresql.org/) - 資料庫
- [pgvector](https://github.com/pgvector/pgvector) - 向量擴展
- [Ollama](https://ollama.ai/) - 本地 AI 模型
- [Jina AI](https://jina.ai/) - 嵌入模型
- [Bootstrap](https://getbootstrap.com/) - 前端框架

## 📧 聯絡方式

如有問題或建議，請透過以下方式聯絡：
- 開啟 GitHub Issue
- 發送 Pull Request

---

**⭐ 如果這個專案對您有幫助，請給我們一個星星！**