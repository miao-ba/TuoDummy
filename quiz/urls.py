from django.urls import path
from . import views

urlpatterns = [
    # 首頁
    path('', views.home, name='home'),
    
    # 健康檢查
    path('health/', views.health_check, name='health_check'),
    
    # 答題系統
    path('quiz/custom/', views.custom_quiz_setup, name='custom_quiz_setup'),
    path('quiz/flashcard/', views.flashcard_setup, name='flashcard_setup'),
    path('quiz/<int:session_id>/', views.quiz_interface, name='quiz_interface'),
    path('flashcard/<int:session_id>/', views.flashcard_interface, name='flashcard_interface'),
    path('flashcard/<int:session_id>/answer/', views.flashcard_answer, name='flashcard_answer'),
    path('quiz/<int:session_id>/result/', views.quiz_result, name='quiz_result'),
    
    # 知識庫管理
    path('knowledge/', views.knowledge_base_list, name='knowledge_base_list'),
    path('knowledge/add/', views.knowledge_base_add, name='knowledge_base_add'),
    path('knowledge/<int:kb_id>/delete/', views.knowledge_base_delete, name='knowledge_base_delete'),
    
    # 使用者
    path('profile/', views.user_profile, name='user_profile'),
    
    # 模型管理
    path('models/', views.model_management, name='model_management'),
    path('models/add/', views.add_model, name='add_model'),
    path('model/<int:model_id>/test/', views.test_model_connection, name='test_model_connection'),
    path('model/<int:model_id>/default/', views.set_default_model, name='set_default_model'),
    path('model/<int:model_id>/delete/', views.delete_model, name='delete_model'),
    path('api/gemini/models/', views.fetch_gemini_models, name='fetch_gemini_models'),
]