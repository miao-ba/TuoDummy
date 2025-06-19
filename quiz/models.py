from django.db import models
from django.contrib.auth.models import User
from pgvector.django import VectorField
import json

class KnowledgeBase(models.Model):
    """知識庫模型"""
    name = models.CharField(max_length=200, verbose_name="知識庫名稱")
    summary = models.TextField(max_length=100, verbose_name="摘要")
    content = models.TextField(verbose_name="原始內容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="使用者")

    class Meta:
        verbose_name = "知識庫"
        verbose_name_plural = "知識庫"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

class KnowledgeChunk(models.Model):
    """知識片段模型（用於向量檢索）"""
    knowledge_base = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE, 
                                     related_name='chunks', verbose_name="所屬知識庫")
    content = models.TextField(verbose_name="片段內容")
    embedding = VectorField(dimensions=768, verbose_name="向量嵌入")  # jina-v2-base-zh 維度
    chunk_index = models.IntegerField(verbose_name="片段索引")

    class Meta:
        verbose_name = "知識片段"
        verbose_name_plural = "知識片段"
        indexes = [
            models.Index(fields=['knowledge_base', 'chunk_index']),
        ]

    def __str__(self):
        return f"{self.knowledge_base.name} - 片段 {self.chunk_index}"

class QuizSession(models.Model):
    """答題會話模型"""
    QUIZ_TYPES = [
        ('custom', '自定義題目'),
        ('flashcard', '閃卡'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="使用者")
    quiz_type = models.CharField(max_length=20, choices=QUIZ_TYPES, verbose_name="答題類型")
    knowledge_bases = models.ManyToManyField(KnowledgeBase, verbose_name="使用的知識庫")
    question_types = models.CharField(max_length=100, verbose_name="題目類型")  # 逗號分隔
    difficulty = models.CharField(max_length=20, verbose_name="難度")
    total_questions = models.IntegerField(verbose_name="總題數")
    current_question = models.IntegerField(default=0, verbose_name="當前題目索引")
    questions_data = models.JSONField(default=list, verbose_name="題目資料")  # 儲存生成的題目
    is_completed = models.BooleanField(default=False, verbose_name="是否完成")
    score = models.FloatField(null=True, blank=True, verbose_name="總分")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成時間")

    class Meta:
        verbose_name = "答題會話"
        verbose_name_plural = "答題會話"
        ordering = ['-created_at']

class QuestionAnswer(models.Model):
    """題目回答記錄"""
    session = models.ForeignKey(QuizSession, on_delete=models.CASCADE, 
                               related_name='answers', verbose_name="答題會話")
    question_index = models.IntegerField(verbose_name="題目索引")
    question_text = models.TextField(verbose_name="題目內容")
    question_type = models.CharField(max_length=20, verbose_name="題目類型")
    correct_answer = models.TextField(verbose_name="正確答案")
    user_answer = models.TextField(verbose_name="使用者答案")
    score = models.IntegerField(verbose_name="得分")  # 0-100
    answered_at = models.DateTimeField(auto_now_add=True, verbose_name="回答時間")

    class Meta:
        verbose_name = "題目回答"
        verbose_name_plural = "題目回答"
        unique_together = ['session', 'question_index']

class HistoryQuestion(models.Model):
    """歷史題目記錄（避免重複生成）"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="使用者")
    knowledge_base_ids = models.CharField(max_length=200, verbose_name="知識庫ID組合")
    question_hash = models.CharField(max_length=64, verbose_name="題目雜湊值")  # 題目內容的hash
    question_data = models.JSONField(verbose_name="題目資料")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    class Meta:
        verbose_name = "歷史題目"
        verbose_name_plural = "歷史題目"
        indexes = [
            models.Index(fields=['user', 'knowledge_base_ids']),
        ]
class AIModel(models.Model):
    """AI 模型配置"""
    MODEL_TYPES = [
        ('ollama', 'Ollama 本地模型'),
        ('gemini', 'Google Gemini'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="模型名稱")
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES, verbose_name="模型類型")
    model_id = models.CharField(max_length=100, verbose_name="模型ID")
    api_key = models.TextField(blank=True, null=True, verbose_name="API金鑰")
    base_url = models.URLField(blank=True, null=True, default="http://localhost:11434", verbose_name="基礎URL")
    is_active = models.BooleanField(default=True, verbose_name="是否啟用")
    is_available = models.BooleanField(default=False, verbose_name="是否可用")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="使用者")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")
    
    # 模型參數配置
    temperature = models.FloatField(default=0.7, verbose_name="溫度參數")
    max_tokens = models.IntegerField(default=4000, verbose_name="最大輸出長度")
    
    class Meta:
        verbose_name = "AI模型"
        verbose_name_plural = "AI模型"
        unique_together = ['user', 'model_id', 'model_type']
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.get_model_type_display()})"
    
    def test_connection(self):
        """測試模型連線"""
        try:
            if self.model_type == 'ollama':
                return self._test_ollama_connection()
            elif self.model_type == 'gemini':
                return self._test_gemini_connection()
            return False, "不支援的模型類型"
        except Exception as e:
            return False, str(e)
    
    def _test_ollama_connection(self):
        """測試 Ollama 連線"""
        try:
            from ollama import chat
            
            response = chat(
                model=self.model_id,
                messages=[{'role': 'user', 'content': 'test'}],
                options={'temperature': 0.1}
            )
            return True, "連線成功"
        except Exception as e:
            return False, f"Ollama 連線失敗: {str(e)}"
    
    def _test_gemini_connection(self):
        """測試 Gemini 連線"""
        try:
            from google import genai
            
            if not self.api_key:
                return False, "缺少 API 金鑰"
            
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model_id,
                contents="test"
            )
            return True, "連線成功"
        except Exception as e:
            return False, f"Gemini 連線失敗: {str(e)}"
    
    def generate_content(self, prompt):
        """生成內容"""
        if self.model_type == 'ollama':
            return self._generate_with_ollama(prompt)
        elif self.model_type == 'gemini':
            return self._generate_with_gemini(prompt)
        else:
            raise ValueError("不支援的模型類型")
    
    def _generate_with_ollama(self, prompt):
        """使用 Ollama 生成內容"""
        from ollama import chat
        
        response = chat(
            model=self.model_id,
            messages=[{'role': 'user', 'content': prompt}],
            options={
                'temperature': self.temperature,
                'max_tokens': self.max_tokens
            }
        )
        return response['message']['content']
    
    def _generate_with_gemini(self, prompt):
        """使用 Gemini 生成內容"""
        from google import genai
        
        if not self.api_key:
            raise ValueError("缺少 API 金鑰")
        
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model_id,
            contents=prompt
        )
        return response.text

class UserModelPreference(models.Model):
    """使用者模型偏好設定"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="使用者")
    default_model = models.ForeignKey(
        AIModel, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="預設模型"
    )
    auto_detect_models = models.BooleanField(default=True, verbose_name="自動偵測可用模型")
    
    class Meta:
        verbose_name = "使用者模型偏好"
        verbose_name_plural = "使用者模型偏好"

    def __str__(self):
        return f"{self.user.username} 的模型偏好"