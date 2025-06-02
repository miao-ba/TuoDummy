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