#!/usr/bin/env python
"""
智能答題系統 - 系統測試腳本
用於測試各個組件是否正常工作
"""

import os
import sys
import django
from pathlib import Path

# 添加專案根目錄到 Python 路徑
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# 設定 Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_system.settings')
django.setup()

import json
import traceback
from django.contrib.auth.models import User
from django.test.utils import override_settings
from quiz.models import *
from quiz.utils import *
from quiz.rag_utils import *

class SystemTester:
    """系統測試類"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def test(self, test_name):
        """測試裝飾器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                print(f"\n🧪 測試: {test_name}")
                try:
                    result = func(*args, **kwargs)
                    print(f"✅ 通過: {test_name}")
                    self.passed += 1
                    self.results.append({"test": test_name, "status": "PASS", "error": None})
                    return result
                except Exception as e:
                    print(f"❌ 失敗: {test_name}")
                    print(f"   錯誤: {str(e)}")
                    self.failed += 1
                    self.results.append({"test": test_name, "status": "FAIL", "error": str(e)})
                    return None
            return wrapper
        return decorator
    
    @test("資料庫連接測試")
    def test_database_connection(self):
        """測試資料庫連接"""
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1, "資料庫查詢失敗"
        return True
    
    @test("pgvector 擴展測試")
    def test_pgvector_extension(self):
        """測試 pgvector 擴展是否可用"""
        from django.db import connection
        with connection.cursor() as cursor:
            # 檢查 pgvector 擴展
            cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
            result = cursor.fetchall()
            assert len(result) > 0, "pgvector 擴展未安裝"
            
            # 測試向量操作
            cursor.execute("SELECT '[1,2,3]'::vector;")
            vector_result = cursor.fetchone()
            assert vector_result is not None, "向量操作失敗"
        return True
    
    @test("Embedding 模型載入測試")
    def test_embedding_model(self):
        """測試 Embedding 模型是否能正常載入"""
        embedding_service = EmbeddingService()
        
        # 測試單個文本編碼
        text = "這是一個測試文本"
        embedding = embedding_service.encode(text)
        
        assert embedding is not None, "Embedding 生成失敗"
        assert len(embedding) == 768, f"Embedding 維度錯誤，期望 768，實際 {len(embedding)}"
        
        # 測試批量編碼
        texts = ["文本1", "文本2", "文本3"]
        embeddings = embedding_service.encode(texts)
        assert len(embeddings) == 3, "批量 Embedding 生成失敗"
        
        return True
    
    @test("Ollama 連接測試")
    def test_ollama_connection(self):
        """測試 Ollama 是否可用"""
        try:
            # 測試簡單的題目生成
            prompt = generate_prompt(1, "true_false", "easy", "測試內容")
            response = generate_questions_ollama(prompt)
            
            assert response is not None, "Ollama 回應為空"
            assert len(response) > 0, "Ollama 回應內容為空"
            
            # 嘗試解析 JSON
            questions = parse_questions(response)
            assert isinstance(questions, list), "題目解析失敗"
            
        except Exception as e:
            if "Connection" in str(e) or "refused" in str(e):
                print("   警告: Ollama 服務未運行，跳過此測試")
                return True
            else:
                raise e
        
        return True
    
    @test("模型功能測試")
    def test_models(self):
        """測試資料庫模型"""
        # 建立測試用戶
        user, created = User.objects.get_or_create(
            username='test_user',
            defaults={'email': 'test@example.com'}
        )
        
        # 測試知識庫建立
        kb = KnowledgeBase.objects.create(
            name="測試知識庫",
            summary="這是一個測試知識庫",
            content="這是測試內容，包含一些知識點。",
            user=user
        )
        
        assert kb.id is not None, "知識庫建立失敗"
        
        # 測試知識片段建立
        chunks = split_text(kb.content, chunk_size=50)
        assert len(chunks) > 0, "文本分割失敗"
        
        # 建立向量嵌入
        embedding_service = EmbeddingService()
        for i, chunk in enumerate(chunks):
            embedding = embedding_service.encode(chunk)
            KnowledgeChunk.objects.create(
                knowledge_base=kb,
                content=chunk,
                embedding=embedding.tolist(),
                chunk_index=i
            )
        
        # 驗證片段是否建立
        chunk_count = KnowledgeChunk.objects.filter(knowledge_base=kb).count()
        assert chunk_count > 0, "知識片段建立失敗"
        
        # 測試答題會話
        session = QuizSession.objects.create(
            user=user,
            quiz_type='custom',
            question_types='true_false',
            difficulty='easy',
            total_questions=1
        )
        session.knowledge_bases.add(kb)
        
        assert session.id is not None, "答題會話建立失敗"
        
        return True
    
    @test("RAG 檢索測試")
    def test_rag_functionality(self):
        """測試 RAG 檢索功能"""
        # 確保有測試資料
        user = User.objects.filter(username='test_user').first()
        if not user:
            return True  # 跳過，因為依賴前面的測試
        
        kb = KnowledgeBase.objects.filter(user=user).first()
        if not kb:
            return True  # 跳過，因為依賴前面的測試
        
        # 測試相似度搜尋
        query = "測試"
        results = search_similar_chunks(query, [kb.id], top_k=3)
        
        assert isinstance(results, list), "RAG 搜尋結果格式錯誤"
        
        if len(results) > 0:
            result = results[0]
            assert 'content' in result, "搜尋結果缺少內容欄位"
            assert 'similarity' in result, "搜尋結果缺少相似度欄位"
        
        # 測試內容獲取
        content = get_relevant_content([kb.id], 'true_false')
        assert isinstance(content, str), "相關內容獲取失敗"
        
        return True
    
    @test("工具函數測試")
    def test_utility_functions(self):
        """測試工具函數"""
        # 測試文本分割
        text = "這是第一句。這是第二句！這是第三句？"
        chunks = split_text(text, chunk_size=20)
        assert len(chunks) > 0, "文本分割失敗"
        
        # 測試提示詞生成
        prompt = generate_prompt(1, "true_false", "easy", "測試內容")
        assert "true_false" in prompt, "提示詞生成失敗"
        assert "easy" in prompt, "難度設定失敗"
        
        # 測試評分功能（模擬題目）
        mock_question = {
            'question_type': 'true_false',
            'options': [
                {'text': '正確', 'is_correct': True},
                {'text': '錯誤', 'is_correct': False}
            ],
            'answer_text': '正確',
            'explanation': '這是測試解釋'
        }
        
        score = grade_answer(mock_question, '正確')
        assert score == 100, f"評分錯誤，期望 100，實際 {score}"
        
        score = grade_answer(mock_question, '錯誤')
        assert score == 0, f"評分錯誤，期望 0，實際 {score}"
        
        return True
    
    def run_all_tests(self):
        """執行所有測試"""
        print("🚀 開始執行系統測試...")
        print("=" * 50)
        
        # 執行所有測試
        self.test_database_connection()
        self.test_pgvector_extension()
        self.test_embedding_model()
        self.test_ollama_connection()
        self.test_models()
        self.test_rag_functionality()
        self.test_utility_functions()
        
        # 清理測試資料
        self.cleanup_test_data()
        
        # 顯示結果
        self.show_results()
    
    def cleanup_test_data(self):
        """清理測試資料"""
        try:
            # 刪除測試用戶和相關資料
            test_user = User.objects.filter(username='test_user').first()
            if test_user:
                test_user.delete()
            print("\n🧹 測試資料清理完成")
        except Exception as e:
            print(f"\n⚠️  測試資料清理失敗: {e}")
    
    def show_results(self):
        """顯示測試結果"""
        print("\n" + "=" * 50)
        print("📊 測試結果總覽")
        print("=" * 50)
        
        total_tests = self.passed + self.failed
        success_rate = (self.passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"總測試數: {total_tests}")
        print(f"通過測試: {self.passed} ✅")
        print(f"失敗測試: {self.failed} ❌")
        print(f"成功率: {success_rate:.1f}%")
        
        if self.failed > 0:
            print("\n失敗的測試:")
            for result in self.results:
                if result['status'] == 'FAIL':
                    print(f"  ❌ {result['test']}: {result['error']}")
        
        print("\n" + "=" * 50)
        
        if self.failed == 0:
            print("🎉 所有測試通過！系統運行正常。")
        else:
            print("⚠️  有測試失敗，請檢查系統配置。")
        
        return self.failed == 0

def main():
    """主函數"""
    tester = SystemTester()
    success = tester.run_all_tests()
    
    # 根據測試結果設定退出碼
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()