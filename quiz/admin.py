from django.contrib import admin
from django.utils.html import format_html
from .models import *

@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    """知識庫管理"""
    list_display = ['name', 'user', 'summary_preview', 'content_length', 'chunks_count', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['name', 'summary', 'user__username']
    readonly_fields = ['content_preview', 'created_at']
    
    def summary_preview(self, obj):
        return obj.summary[:50] + '...' if len(obj.summary) > 50 else obj.summary
    summary_preview.short_description = '摘要'
    
    def content_length(self, obj):
        return f"{len(obj.content):,} 字"
    content_length.short_description = '內容長度'
    
    def chunks_count(self, obj):
        count = obj.chunks.count()
        return format_html(
            '<span style="color: {};">{} 個片段</span>',
            'green' if count > 0 else 'red',
            count
        )
    chunks_count.short_description = '知識片段'
    
    def content_preview(self, obj):
        preview = obj.content[:500] + '...' if len(obj.content) > 500 else obj.content
        return format_html('<pre style="white-space: pre-wrap;">{}</pre>', preview)
    content_preview.short_description = '內容預覽'
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('name', 'user', 'summary')
        }),
        ('內容', {
            'fields': ('content_preview',),
            'classes': ('collapse',)
        }),
        ('系統資訊', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    """知識片段管理"""
    list_display = ['knowledge_base', 'chunk_index', 'content_preview', 'embedding_dimension']
    list_filter = ['knowledge_base', 'knowledge_base__user']
    search_fields = ['content', 'knowledge_base__name']
    ordering = ['knowledge_base', 'chunk_index']
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = '內容片段'
    
    def embedding_dimension(self, obj):
        if obj.embedding:
            return f"{len(obj.embedding)} 維"
        return "無向量"
    embedding_dimension.short_description = '向量維度'
    
    readonly_fields = ['embedding_info']
    
    def embedding_info(self, obj):
        if obj.embedding:
            return format_html(
                '向量維度：{}<br>向量範例：{}...',
                len(obj.embedding),
                str(obj.embedding[:5])
            )
        return "無向量數據"
    embedding_info.short_description = '向量資訊'

@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    """答題會話管理"""
    list_display = ['user', 'quiz_type_display', 'total_questions', 'current_question', 
                    'score_display', 'status_display', 'created_at']
    list_filter = ['quiz_type', 'is_completed', 'difficulty', 'created_at']
    search_fields = ['user__username']
    readonly_fields = ['questions_preview', 'created_at', 'completed_at']
    filter_horizontal = ['knowledge_bases']
    
    def quiz_type_display(self, obj):
        colors = {'custom': 'blue', 'flashcard': 'green'}
        names = {'custom': '自定義', 'flashcard': '閃卡'}
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.quiz_type, 'black'),
            names.get(obj.quiz_type, obj.quiz_type)
        )
    quiz_type_display.short_description = '答題類型'
    
    def score_display(self, obj):
        if obj.score is not None:
            color = 'green' if obj.score >= 80 else 'orange' if obj.score >= 60 else 'red'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} 分</span>',
                color, obj.score
            )
        return '-'
    score_display.short_description = '分數'
    
    def status_display(self, obj):
        if obj.is_completed:
            return format_html('<span style="color: green;">✓ 已完成</span>')
        else:
            progress = (obj.current_question / obj.total_questions) * 100 if obj.total_questions > 0 else 0
            return format_html(
                '<span style="color: orange;">進行中 ({}%)</span>',
                int(progress)
            )
    status_display.short_description = '狀態'
    
    def questions_preview(self, obj):
        if obj.questions_data:
            return format_html(
                '<div style="max-height: 200px; overflow-y: auto;"><pre>{}</pre></div>',
                str(obj.questions_data)[:1000] + '...' if len(str(obj.questions_data)) > 1000 else str(obj.questions_data)
            )
        return "無題目資料"
    questions_preview.short_description = '題目資料'
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('user', 'quiz_type', 'knowledge_bases')
        }),
        ('答題設定', {
            'fields': ('question_types', 'difficulty', 'total_questions')
        }),
        ('進度狀態', {
            'fields': ('current_question', 'is_completed', 'score', 'created_at', 'completed_at')
        }),
        ('題目資料', {
            'fields': ('questions_preview',),
            'classes': ('collapse',)
        }),
    )

@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    """題目回答管理"""
    list_display = ['session_info', 'question_index', 'question_preview', 
                    'question_type', 'score_display', 'answered_at']
    list_filter = ['question_type', 'score', 'session__quiz_type', 'answered_at']
    search_fields = ['question_text', 'user_answer', 'session__user__username']
    ordering = ['-answered_at']
    
    def session_info(self, obj):
        return f"{obj.session.user.username} - {obj.session.get_quiz_type_display()}"
    session_info.short_description = '答題會話'
    
    def question_preview(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_preview.short_description = '題目內容'
    
    def score_display(self, obj):
        color = 'green' if obj.score == 100 else 'orange' if obj.score >= 60 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.score
        )
    score_display.short_description = '得分'
    
    readonly_fields = ['answer_comparison']
    
    def answer_comparison(self, obj):
        return format_html(
            '<div style="display: flex; gap: 20px;">'
            '<div><strong>使用者答案：</strong><br>{}</div>'
            '<div><strong>正確答案：</strong><br>{}</div>'
            '</div>',
            obj.user_answer or '未作答',
            obj.correct_answer
        )
    answer_comparison.short_description = '答案對比'

@admin.register(HistoryQuestion)
class HistoryQuestionAdmin(admin.ModelAdmin):
    """歷史題目管理"""
    list_display = ['user', 'knowledge_base_ids', 'question_hash', 'question_preview', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['user__username', 'question_hash']
    readonly_fields = ['question_preview_detail', 'created_at']
    
    def question_preview(self, obj):
        if obj.question_data and 'question_text' in obj.question_data:
            text = obj.question_data['question_text']
            return text[:50] + '...' if len(text) > 50 else text
        return "無題目內容"
    question_preview.short_description = '題目預覽'
    
    def question_preview_detail(self, obj):
        if obj.question_data:
            return format_html('<pre>{}</pre>', str(obj.question_data))
        return "無題目資料"
    question_preview_detail.short_description = '完整題目資料'

# 自定義管理介面標題
admin.site.site_header = "智能答題系統 管理後台"
admin.site.site_title = "智能答題系統"
admin.site.index_title = "系統管理"

# 自定義管理介面樣式
admin.site.site_url = "/"  # 查看網站連結

# 註冊自定義動作
def export_questions(modeladmin, request, queryset):
    """匯出題目資料"""
    import json
    from django.http import JsonResponse
    
    data = []
    for session in queryset:
        if session.questions_data:
            data.extend(session.questions_data)
    
    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})

export_questions.short_description = "匯出選中會話的題目資料"

def reset_quiz_progress(modeladmin, request, queryset):
    """重置答題進度"""
    count = 0
    for session in queryset:
        if not session.is_completed:
            session.current_question = 0
            session.answers.all().delete()  # 刪除已有答案
            session.save()
            count += 1
    
    modeladmin.message_user(request, f'已重置 {count} 個答題會話的進度')

reset_quiz_progress.short_description = "重置選中會話的答題進度"

# 添加自定義動作到相應的管理介面
QuizSessionAdmin.actions = [export_questions, reset_quiz_progress]