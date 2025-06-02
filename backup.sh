#!/bin/bash

# 智能答題系統 資料備份腳本
# 用於定期備份資料庫和重要檔案

set -e

# 載入環境變數
if [ -f ".env" ]; then
    source .env
else
    echo "錯誤：找不到 .env 檔案"
    exit 1
fi

# 顏色設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 輔助函數
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 設定備份目錄
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="quiz_backup_$DATE"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

# 建立備份目錄
create_backup_dir() {
    log_info "建立備份目錄..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        log_success "備份目錄建立完成: $BACKUP_DIR"
    fi
    
    mkdir -p "$BACKUP_PATH"
    log_success "本次備份目錄: $BACKUP_PATH"
}

# 備份資料庫
backup_database() {
    log_info "開始備份資料庫..."
    
    # 設定資料庫連接參數
    DB_HOST=${DB_HOST:-localhost}
    DB_PORT=${DB_PORT:-5432}
    DB_NAME=${DB_NAME:-quiz_db}
    DB_USER=${DB_USER:-quiz_user}
    
    # 檢查資料庫連接
    if ! PGPASSWORD=$DB_PASSWORD pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; then
        log_error "無法連接到資料庫"
        return 1
    fi
    
    # 執行完整備份
    log_info "執行完整資料庫備份..."
    PGPASSWORD=$DB_PASSWORD pg_dump \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        --no-password \
        --verbose \
        --create \
        --clean \
        > "$BACKUP_PATH/database_full.sql"
    
    # 執行資料備份（無結構）
    log_info "執行資料備份..."
    PGPASSWORD=$DB_PASSWORD pg_dump \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        --no-password \
        --data-only \
        --inserts \
        > "$BACKUP_PATH/database_data.sql"
    
    # 執行結構備份（無資料）
    log_info "執行結構備份..."
    PGPASSWORD=$DB_PASSWORD pg_dump \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        --no-password \
        --schema-only \
        > "$BACKUP_PATH/database_schema.sql"
    
    log_success "資料庫備份完成"
}

# 備份媒體檔案
backup_media() {
    log_info "備份媒體檔案..."
    
    if [ -d "./media" ]; then
        tar -czf "$BACKUP_PATH/media_files.tar.gz" -C . media/
        log_success "媒體檔案備份完成"
    else
        log_warning "媒體目錄不存在，跳過媒體備份"
    fi
}

# 備份設定檔案
backup_config() {
    log_info "備份設定檔案..."
    
    # 建立設定檔案目錄
    mkdir -p "$BACKUP_PATH/config"
    
    # 備份重要設定檔案
    config_files=(
        ".env.template"
        "requirements.txt"
        "docker-compose.yml"
        "Dockerfile"
        "nginx.conf"
        "init.sql"
    )
    
    for file in "${config_files[@]}"; do
        if [ -f "$file" ]; then
            cp "$file" "$BACKUP_PATH/config/"
            log_info "已備份: $file"
        fi
    done
    
    log_success "設定檔案備份完成"
}

# 備份日誌檔案
backup_logs() {
    log_info "備份日誌檔案..."
    
    if [ -d "./logs" ]; then
        tar -czf "$BACKUP_PATH/log_files.tar.gz" -C . logs/
        log_success "日誌檔案備份完成"
    else
        log_warning "日誌目錄不存在，跳過日誌備份"
    fi
}

# 生成備份資訊
generate_backup_info() {
    log_info "生成備份資訊..."
    
    cat > "$BACKUP_PATH/backup_info.txt" << EOF
智能答題系統 備份資訊
====================

備份時間: $(date)
備份版本: $BACKUP_NAME
系統資訊: $(uname -a)

資料庫資訊:
- 主機: $DB_HOST
- 連接埠: $DB_PORT  
- 資料庫: $DB_NAME
- 使用者: $DB_USER

備份內容:
- 完整資料庫: database_full.sql
- 資料備份: database_data.sql
- 結構備份: database_schema.sql
- 媒體檔案: media_files.tar.gz
- 設定檔案: config/
- 日誌檔案: log_files.tar.gz

還原指令:
psql -h $DB_HOST -U $DB_USER -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
psql -h $DB_HOST -U $DB_USER -d postgres < database_full.sql

注意事項:
1. 還原前請確保目標環境已安裝 pgvector 擴展
2. 還原後需要重新啟動應用程式服務
3. 媒體檔案需要手動解壓到正確位置
EOF
    
    log_success "備份資訊已生成"
}

# 壓縮備份檔案
compress_backup() {
    log_info "壓縮備份檔案..."
    
    cd "$BACKUP_DIR"
    tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME/"
    
    # 檢查壓縮檔案大小
    compressed_size=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
    log_success "備份檔案已壓縮: ${BACKUP_NAME}.tar.gz ($compressed_size)"
    
    # 刪除未壓縮的目錄
    rm -rf "$BACKUP_NAME/"
    
    cd - > /dev/null
}

# 清理舊備份
cleanup_old_backups() {
    log_info "清理舊備份檔案..."
    
    # 保留最近 7 天的備份
    find "$BACKUP_DIR" -name "quiz_backup_*.tar.gz" -mtime +7 -delete
    
    # 列出剩餘備份
    remaining_backups=$(find "$BACKUP_DIR" -name "quiz_backup_*.tar.gz" | wc -l)
    log_success "已清理舊備份，剩餘 $remaining_backups 個備份檔案"
}

# 檢查磁碟空間
check_disk_space() {
    log_info "檢查磁碟空間..."
    
    available_space=$(df . | awk 'NR==2 {print $4}')
    required_space=1048576  # 1GB in KB
    
    if [ "$available_space" -lt "$required_space" ]; then
        log_warning "磁碟空間不足，建議清理舊備份"
    else
        available_gb=$((available_space / 1048576))
        log_success "可用磁碟空間: ${available_gb}GB"
    fi
}

# 主備份函數
perform_backup() {
    log_info "開始執行備份作業..."
    echo "========================================"
    
    # 檢查先決條件
    check_disk_space
    
    # 執行備份步驟
    create_backup_dir
    backup_database
    backup_media
    backup_config
    backup_logs
    generate_backup_info
    compress_backup
    cleanup_old_backups
    
    echo "========================================"
    log_success "備份作業完成！"
    log_info "備份位置: $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
}

# 還原功能
restore_backup() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        echo "使用方式: $0 restore <backup_file.tar.gz>"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_error "備份檔案不存在: $backup_file"
        exit 1
    fi
    
    log_warning "這將覆蓋現有資料，是否繼續？"
    read -p "輸入 'yes' 確認還原: " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "還原作業已取消"
        exit 0
    fi
    
    log_info "開始還原備份..."
    
    # 解壓備份檔案
    local restore_dir="/tmp/quiz_restore_$$"
    mkdir -p "$restore_dir"
    tar -xzf "$backup_file" -C "$restore_dir"
    
    # 找到備份目錄
    local backup_content=$(find "$restore_dir" -name "quiz_backup_*" -type d | head -1)
    
    if [ -z "$backup_content" ]; then
        log_error "無效的備份檔案格式"
        rm -rf "$restore_dir"
        exit 1
    fi
    
    # 還原資料庫
    log_info "還原資料庫..."
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d postgres < "$backup_content/database_full.sql"
    
    # 還原媒體檔案
    if [ -f "$backup_content/media_files.tar.gz" ]; then
        log_info "還原媒體檔案..."
        tar -xzf "$backup_content/media_files.tar.gz"
    fi
    
    # 清理臨時檔案
    rm -rf "$restore_dir"
    
    log_success "還原完成！請重新啟動應用程式"
}

# 主程式
main() {
    case "${1:-backup}" in
        "backup")
            perform_backup
            ;;
        "restore")
            restore_backup "$2"
            ;;
        "list")
            log_info "可用備份檔案:"
            ls -la "$BACKUP_DIR"/quiz_backup_*.tar.gz 2>/dev/null || echo "沒有找到備份檔案"
            ;;
        "help")
            echo "智能答題系統 備份工具"
            echo ""
            echo "使用方式:"
            echo "  $0 backup           - 執行完整備份"
            echo "  $0 restore <file>   - 從備份還原"
            echo "  $0 list             - 列出可用備份"
            echo "  $0 help             - 顯示此說明"
            ;;
        *)
            log_error "未知的命令: $1"
            echo "使用 '$0 help' 查看可用命令"
            exit 1
            ;;
    esac
}

# 腳本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi