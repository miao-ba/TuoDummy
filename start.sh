#!/bin/bash

# 智能答題系統 啟動腳本
# 作者：AI Assistant
# 用途：自動化部署和啟動整個系統

set -e  # 遇到錯誤立即退出

# 顏色代碼
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 輔助函數
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查必要的命令是否存在
check_requirements() {
    print_status "檢查系統需求..."
    
    local missing_commands=()
    
    for cmd in python3 pip3 psql; do
        if ! command -v $cmd &> /dev/null; then
            missing_commands+=($cmd)
        fi
    done
    
    if [ ${#missing_commands[@]} -ne 0 ]; then
        print_error "缺少必要的命令: ${missing_commands[*]}"
        echo "請先安裝以下軟體："
        echo "- Python 3.8+"
        echo "- PostgreSQL"
        echo "- pip3"
        exit 1
    fi
    
    print_success "系統需求檢查通過"
}

# 建立虛擬環境
setup_venv() {
    print_status "設定 Python 虛擬環境..."
    
    if [ ! -d ".venv" ]; then
        python3 -m venv venv
        print_success "虛擬環境建立完成"
    else
        print_warning "虛擬環境已存在，跳過建立"
    fi
    
    # 啟用虛擬環境
    source .venv/bin/activate || {
        print_error "無法啟用虛擬環境"
        exit 1
    }
    
    print_success "虛擬環境已啟用"
}

# 安裝 Python 套件
install_packages() {
    print_status "安裝 Python 套件..."
    
    # 升級 pip
    pip install --upgrade pip
    
    # 安裝套件
    pip install -r requirements.txt
    
    print_success "Python 套件安裝完成"
}

# 檢查並設定環境變數
setup_environment() {
    print_status "設定環境變數..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.template" ]; then
            cp .env.template .env
            print_warning "已複製 .env.template 為 .env，請編輯其中的設定"
            print_warning "特別注意資料庫密碼和 SECRET_KEY"
        else
            print_error "找不到 .env.template 檔案"
            exit 1
        fi
    else
        print_success "環境變數檔案已存在"
    fi
}

# 檢查資料庫連接
check_database() {
    print_status "檢查資料庫連接..."
    
    # 載入環境變數
    source .env 2>/dev/null || {
        print_error "無法載入 .env 檔案"
        exit 1
    }
    
    # 檢查 PostgreSQL 是否運行
    if ! pg_isready -h ${DB_HOST:-localhost} -p ${DB_PORT:-5432} &> /dev/null; then
        print_error "PostgreSQL 服務未運行，請先啟動資料庫服務"
        echo "Ubuntu/Debian: sudo systemctl start postgresql"
        echo "macOS: brew services start postgresql"
        exit 1
    fi
    
    # 檢查資料庫是否存在
    if ! PGPASSWORD=$DB_PASSWORD psql -h ${DB_HOST:-localhost} -U $DB_USER -d $DB_NAME -c "SELECT 1;" &> /dev/null; then
        print_warning "資料庫連接失敗，請檢查 .env 中的資料庫設定"
        print_status "嘗試建立資料庫..."
        
        # 嘗試建立資料庫
        sudo -u postgres createdb $DB_NAME -O $DB_USER 2>/dev/null || {
            print_error "無法建立資料庫，請手動建立或檢查權限"
            exit 1
        }
    fi
    
    print_success "資料庫連接正常"
}

# 檢查 pgvector 擴展
check_pgvector() {
    print_status "檢查 pgvector 擴展..."
    
    source .env
    
    # 檢查 pgvector 是否安裝
    if ! PGPASSWORD=$DB_PASSWORD psql -h ${DB_HOST:-localhost} -U $DB_USER -d $DB_NAME -c "SELECT * FROM pg_extension WHERE extname = 'vector';" | grep -q vector; then
        print_warning "pgvector 擴展未啟用，嘗試自動啟用..."
        
        # 嘗試啟用 pgvector
        PGPASSWORD=$DB_PASSWORD psql -h ${DB_HOST:-localhost} -U $DB_USER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
            print_error "無法啟用 pgvector 擴展"
            echo "請參考 database_setup.md 手動安裝 pgvector"
            exit 1
        }
    fi
    
    print_success "pgvector 擴展已啟用"
}

# 執行資料庫遷移
run_migrations() {
    print_status "執行資料庫遷移..."
    
    # 建立遷移檔案
    python manage.py makemigrations
    
    # 執行遷移
    python manage.py migrate
    
    print_success "資料庫遷移完成"
}

# 建立超級使用者
create_superuser() {
    print_status "檢查管理員帳戶..."
    
    # 檢查是否已有超級使用者
    if python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(is_superuser=True).exists())" | grep -q True; then
        print_success "管理員帳戶已存在"
    else
        print_status "建立管理員帳戶..."
        echo "請輸入管理員資訊："
        python manage.py createsuperuser
        print_success "管理員帳戶建立完成"
    fi
}

# 收集靜態檔案
collect_static() {
    print_status "收集靜態檔案..."
    
    python manage.py collectstatic --noinput
    
    print_success "靜態檔案收集完成"
}

# 檢查 Ollama 是否運行
check_ollama() {
    print_status "檢查 Ollama 服務..."
    
    if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
        print_warning "Ollama 服務未運行"
        echo "請先安裝並啟動 Ollama："
        echo "1. 安裝：curl -fsSL https://ollama.ai/install.sh | sh"
        echo "2. 啟動：ollama serve"
        echo "3. 安裝模型：ollama pull gemma3:4b"
        
        read -p "是否繼續啟動系統？(y/N): " continue_without_ollama
        if [[ ! $continue_without_ollama =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "Ollama 服務運行正常"
        
        # 檢查模型是否存在
        source .env
        if ! ollama list | grep -q ${OLLAMA_MODEL:-gemma3:4b}; then
            print_warning "Ollama 模型 ${OLLAMA_MODEL:-gemma3:4b} 未安裝"
            echo "正在安裝模型，這可能需要幾分鐘..."
            ollama pull ${OLLAMA_MODEL:-gemma3:4b} || {
                print_warning "模型安裝失敗，請手動安裝"
            }
        fi
    fi
}

# 啟動開發伺服器
start_server() {
    print_status "啟動開發伺服器..."
    
    # 檢查埠號是否被佔用
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
        print_warning "埠號 8000 已被佔用"
        read -p "是否使用其他埠號？(輸入埠號或按 Enter 使用 8001): " port
        port=${port:-8001}
    else
        port=8000
    fi
    
    print_success "系統啟動完成！"
    echo "===========================================" 
    echo "  智能答題系統已成功啟動"
    echo "==========================================="
    echo "訪問地址: http://localhost:$port"
    echo "管理後台: http://localhost:$port/admin"
    echo ""
    echo "按 Ctrl+C 停止伺服器"
    echo "=========================================="
    
    # 啟動伺服器
    python manage.py runserver 0.0.0.0:$port
}

# 主函數
main() {
    echo "=========================================="
    echo "      智能答題系統 - 啟動腳本"
    echo "=========================================="
    echo ""
    
    # 檢查是否在正確的目錄
    if [ ! -f "manage.py" ]; then
        print_error "請在包含 manage.py 的目錄中執行此腳本"
        exit 1
    fi
    
    # 執行各個步驟
    check_requirements
    setup_venv
    install_packages
    setup_environment
    check_database
    check_pgvector
    run_migrations
    create_superuser
    collect_static
    check_ollama
    start_server
}

# 腳本入口點
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi