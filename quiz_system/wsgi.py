"""
Django 的 WSGI 設定檔 - 智能答題系統

本檔案包含 WSGI 可調用物件，作為 Django 專案的 WSGI 應用程式。

WSGI 伺服器使用此檔案來為您的專案提供服務。
"""

import os
from django.core.wsgi import get_wsgi_application

# 設定 Django 設定模組
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_system.settings')

# 取得 WSGI 應用程式
application = get_wsgi_application()