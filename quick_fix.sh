#!/bin/bash

# 快速修復資料庫遷移問題
echo "🚀 快速修復資料庫遷移問題..."

# 顏色設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() {
    echo -e "${BLUE}[步驟]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[成功]${NC} $1"
}

print_error() {
    echo -e "${RED}[錯誤]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[警告]${NC} $1"
}

# 檢查是否在正確目錄
if [ ! -f "manage.py" ]; then
    print_error "請在包含 manage.py 的目錄中執行此腳本"
    exit 1
fi

# 步驟 1: 檢查虛擬環境
print_step "檢查虛擬環境..."
if [ -d "venv" ]; then
    source venv/bin/activate
    print_success "虛擬環境已啟用"
else
    print_warning "未找到虛擬環境，使用系統 Python"
fi

# 步驟 2: 檢查 .env 檔案
print_step "檢查環境變數檔案..."
if [ ! -f ".env" ]; then
    if [ -f ".env.template" ]; then
        cp .env.template .env
        print_warning "已複製 .env.template 為 .env，請編輯資料庫設定"
    else
        print_error "找不到 .env 檔案，請先建立"
        exit 1
    fi
fi

# 步驟 3: 檢查資料庫連接
print_step "檢查資料庫連接..."
source .env 2>/dev/null || {
    print_error "無法載入 .env 檔案"
    exit 1
}

if ! pg_isready -h ${DB_HOST:-localhost} -p ${DB_PORT:-5432} &> /dev/null; then
    print_error "PostgreSQL 服務未運行，請先啟動："
    echo "  Ubuntu/Debian: sudo systemctl start postgresql"
    echo "  macOS: brew services start postgresql"
    echo "  Docker: docker-compose up -d db"
    exit 1
fi

# 步驟 4: 檢查資料庫是否存在
print_step "檢查資料庫是否存在..."
if ! PGPASSWORD=$DB_PASSWORD psql -h ${DB_HOST:-localhost} -U $DB_USER -d $DB_NAME -c "SELECT 1;" &> /dev/null; then
    print_warning "資料庫不存在，嘗試建立..."
    
    # 嘗試建立資料庫
    if PGPASSWORD=$DB_PASSWORD createdb -h ${DB_HOST:-localhost} -U $DB_USER $DB_NAME 2>/dev/null; then
        print_success "資料庫建立成功"
    else
        print_error "無法建立資料庫，請手動執行："
        echo "  sudo -u postgres createdb $DB_NAME -O $DB_USER"
        exit 1
    fi
fi

# 步驟 5: 檢查 pgvector 擴展
print_step "檢查 pgvector 擴展..."
if ! PGPASSWORD=$DB_PASSWORD psql -h ${DB_HOST:-localhost} -U $DB_USER -d $DB_NAME -c "SELECT * FROM pg_extension WHERE extname = 'vector';" | grep -q vector; then
    print_warning "pgvector 擴展未啟用，嘗試啟用..."
    
    if PGPASSWORD=$DB_PASSWORD psql -h ${DB_HOST:-localhost} -U $DB_USER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;" &> /dev/null; then
        print_success "pgvector 擴展已啟用"
    else
        print_warning "無法啟用 pgvector 擴展，請手動執行或檢查是否已安裝"
    fi
fi

# 步驟 6: 清理舊的遷移檔案
print_step "清理舊的遷移檔案..."
if [ -d "quiz/migrations" ]; then
    # 保留 __init__.py，刪除其他遷移檔案
    find quiz/migrations -name "*.py" ! -name "__init__.py" -delete
    print_success "舊遷移檔案已清理"
fi

# 確保 migrations 目錄存在
mkdir -p quiz/migrations
touch quiz/migrations/__init__.py

# 步驟 7: 建立新的遷移檔案
print_step "建立新的遷移檔案..."
if python manage.py makemigrations quiz; then
    print_success "遷移檔案建立成功"
else
    print_error "建立遷移檔案失敗"
    exit 1
fi

# 步驟 8: 執行資料庫遷移
print_step "執行資料庫遷移..."
if python manage.py migrate; then
    print_success "資料庫遷移完成"
else
    print_error "資料庫遷移失敗"
    exit 1
fi

# 步驟 9: 驗證資料表
print_step "驗證資料表..."
tables_to_check="quiz_knowledgebase quiz_knowledgechunk quiz_quizsession quiz_questionanswer quiz_historyquestion"

for table in $tables_to_check; do
    if PGPASSWORD=$DB_PASSWORD psql -h ${DB_HOST:-localhost} -U $DB_USER -d $DB_NAME -c "SELECT 1 FROM $table LIMIT 1;" &> /dev/null; then
        print_success "資料表 $table 存在且可訪問"
    else
        print_error "資料表 $table 不存在或無法訪問"
    fi
done

# 步驟 10: 建立超級使用者（可選）
print_step "檢查管理員帳戶..."
if python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(is_superuser=True).exists())" 2>/dev/null | grep -q True; then
    print_success "管理員帳戶已存在"
else
    echo ""
    print_warning "沒有管理員帳戶，是否要建立一個？(y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        python manage.py createsuperuser
    fi
fi

# 完成
echo ""
echo "=========================================="
print_success "資料庫修復完成！"
echo "=========================================="
echo "現在可以啟動伺服器："
echo "  python manage.py runserver"
echo ""
echo "或使用完整啟動腳本："
echo "  ./start.sh"
echo "=========================================="