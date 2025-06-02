# 智能答題系統 Docker 映像檔
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 設定環境變數
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 複製需求檔案並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案檔案
COPY . .

# 建立必要的目錄
RUN mkdir -p /app/media /app/staticfiles /app/logs

# 設定檔案權限
RUN chmod +x /app/start.sh 2>/dev/null || true

# 收集靜態檔案
RUN python manage.py collectstatic --noinput || true

# 暴露連接埠
EXPOSE 8000

# 建立啟動腳本
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "等待資料庫連接..."\n\
while ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do\n\
  echo "資料庫未就緒，等待 2 秒..."\n\
  sleep 2\n\
done\n\
\n\
echo "執行資料庫遷移..."\n\
python manage.py migrate\n\
\n\
echo "收集靜態檔案..."\n\
python manage.py collectstatic --noinput\n\
\n\
echo "啟動伺服器..."\n\
exec python manage.py runserver 0.0.0.0:8000\n\
' > /app/docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh

# 健康檢查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/ || exit 1

# 設定預設命令
CMD ["/app/docker-entrypoint.sh"]