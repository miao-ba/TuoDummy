-- 智能答題系統 資料庫初始化腳本
-- 此腳本在容器啟動時自動執行

-- 建立 pgvector 擴展
CREATE EXTENSION IF NOT EXISTS vector;

-- 建立索引優化查詢效能
-- 注意：這些索引會在 Django 遷移後建立

-- 設定 PostgreSQL 參數以優化向量搜索
ALTER SYSTEM SET shared_preload_libraries = 'vector';
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';

-- 重新載入設定
SELECT pg_reload_conf();

-- 建立資料庫使用者權限
GRANT ALL PRIVILEGES ON DATABASE quiz_db TO quiz_user;
GRANT ALL ON SCHEMA public TO quiz_user;

-- 顯示 pgvector 版本
SELECT vector_version();

-- 建立一個測試向量表以驗證功能
CREATE TABLE IF NOT EXISTS vector_test (
    id SERIAL PRIMARY KEY,
    test_vector vector(768),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 插入測試資料
INSERT INTO vector_test (test_vector) VALUES 
('[' || array_to_string(array(select random() from generate_series(1,768)), ',') || ']');

-- 測試向量距離計算
SELECT 
    'pgvector 測試成功' as status,
    vector_dims(test_vector) as dimensions,
    test_vector <-> test_vector as self_distance
FROM vector_test 
LIMIT 1;

-- 清理測試表
DROP TABLE IF EXISTS vector_test;

-- 輸出初始化完成訊息
DO $$ 
BEGIN 
    RAISE NOTICE '========================================';
    RAISE NOTICE '智能答題系統 資料庫初始化完成';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'pgvector 擴展已啟用';
    RAISE NOTICE '資料庫使用者權限已設定';
    RAISE NOTICE '效能參數已優化';
    RAISE NOTICE '========================================';
END $$;