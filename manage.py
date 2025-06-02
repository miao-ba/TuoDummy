#!/usr/bin/env python
"""Django 的命令列工具，用於管理任務。"""
import os
import sys

if __name__ == '__main__':
    # 設定 Django 設定模組的環境變數
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_system.settings')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "無法導入 Django。您確定已安裝且在 PYTHONPATH 環境變數中可用嗎？ "
            "您是否忘記啟用虛擬環境？"
        ) from exc
    
    # 執行命令列參數
    execute_from_command_line(sys.argv)