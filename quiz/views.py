from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
import math
from .models import *
from .utils import *
from .rag_utils import *

def health_check(request):
    """健康檢查端點"""
    return HttpResponse("OK", content_type="text/plain")

def home(request):
    """首頁"""
    user_stats = {}
    
    # 如果用戶已登入，計算統計數據
    if request.user.is_authenticated:
        from django.db.models import Avg
        
        # 完成的答題數量
        user_stats['completed_quizzes'] = QuizSession.objects.filter(
            user=request.user, 
            is_completed=True
        ).count()
        
        # 知識庫數量
        user_stats['knowledge_bases'] = KnowledgeBase.objects.filter(
            user=request.user
        ).count()
        
        # 平均分數
        avg_score_result = QuizSession.objects.filter(
            user=request.user, 
            is_completed=True
        ).aggregate(avg_score=Avg('score'))
        
        user_stats['avg_score'] = avg_score_result['avg_score'] or 0
    
    return render(request, 'quiz/home.html', {'user_stats': user_stats})

@login_required
def custom_quiz_setup(request):
    """自定義題目設置"""
    if request.method == 'POST':
        # 獲取表單資料
        knowledge_base_ids = request.POST.getlist('knowledge_bases')
        question_types = ','.join(request.POST.getlist('question_types'))
        difficulty = request.POST.get('difficulty')
        total_questions = int(request.POST.get('total_questions', 5))
        
        # 建立答題會話
        session = QuizSession.objects.create(
            user=request.user,
            quiz_type='custom',
            question_types=question_types,
            difficulty=difficulty,
            total_questions=total_questions
        )
        session.knowledge_bases.set(knowledge_base_ids)
        
        # 生成題目
        try:
            generate_quiz_questions(session)
            return redirect('quiz_interface', session_id=session.id)
        except Exception as e:
            messages.error(request, f'題目生成失敗：{str(e)}')
            session.delete()
    
    # 獲取使用者的知識庫
    knowledge_bases = KnowledgeBase.objects.filter(user=request.user)
    context = {
        'knowledge_bases': knowledge_bases,
        'question_types': [
            ('multiple_choice', '選擇題'),
            ('true_false', '是非題'),
            ('short_answer', '簡答題'),
            ('essay', '論述題'),
        ],
        'difficulties': [
            ('easy', '簡單'),
            ('medium', '中等'),
            ('hard', '困難'),
        ]
    }
    return render(request, 'quiz/custom_quiz.html', context)

@login_required
def flashcard_setup(request):
    """閃卡設置"""
    if request.method == 'POST':
        knowledge_base_ids = request.POST.getlist('knowledge_bases')
        total_questions = int(request.POST.get('total_questions', 10))
        difficulty = request.POST.get('difficulty')
        
        session = QuizSession.objects.create(
            user=request.user,
            quiz_type='flashcard',
            question_types='true_false',  # 閃卡固定是非題
            difficulty=difficulty,
            total_questions=total_questions
        )
        session.knowledge_bases.set(knowledge_base_ids)
        
        try:
            generate_quiz_questions(session)
            return redirect('flashcard_interface', session_id=session.id)
        except Exception as e:
            messages.error(request, f'閃卡生成失敗：{str(e)}')
            session.delete()
    
    # 獲取使用者的知識庫
    knowledge_bases = KnowledgeBase.objects.filter(user=request.user)
    
    # 計算閃卡統計數據
    flashcard_stats = {}
    if request.user.is_authenticated:
        # 閃卡完成次數
        flashcard_stats['completed_count'] = QuizSession.objects.filter(
            user=request.user,
            quiz_type='flashcard',
            is_completed=True
        ).count()
        
        # 閃卡平均分數
        flashcard_avg = QuizSession.objects.filter(
            user=request.user,
            quiz_type='flashcard',
            is_completed=True
        ).aggregate(avg_score=models.Avg('score'))
        
        flashcard_stats['avg_score'] = flashcard_avg['avg_score'] or 0
        
        # 可用知識庫數量
        flashcard_stats['knowledge_bases'] = knowledge_bases.count()
    
    context = {
        'knowledge_bases': knowledge_bases,
        'flashcard_stats': flashcard_stats,
        'difficulties': [
            ('easy', '簡單'),
            ('medium', '中等'),
            ('hard', '困難'),
        ]
    }
    return render(request, 'quiz/flashcard_setup.html', context)

def generate_quiz_questions(session):
    """生成答題題目"""
    # 獲取相關內容
    kb_ids = list(session.knowledge_bases.values_list('id', flat=True))
    content = get_relevant_content(kb_ids, session.question_types)
    
    if not content:
        raise Exception("無法找到相關內容")
    
    # 獲取歷史題目
    history_data = get_history_questions(session.user, kb_ids)
    history_text = json.dumps(history_data) if history_data else None
    
    # 分批生成題目（每次最多10題）
    questions = []
    remaining = session.total_questions
    
    while remaining > 0:
        batch_size = min(remaining, 10)
        
        # 生成提示詞
        prompt = generate_prompt(
            count=batch_size,
            question_types=session.question_types,
            difficulty=session.difficulty,
            content=content,
            history=history_text
        )
        
        # 呼叫 LLM 生成
        response = generate_questions_ollama(prompt)
        batch_questions = parse_questions(response)
        
        questions.extend(batch_questions)
        remaining -= len(batch_questions)
        
        # 更新歷史記錄避免重複
        if history_text:
            history_text += json.dumps(batch_questions)
        else:
            history_text = json.dumps(batch_questions)
    
    # 儲存題目到會話
    session.questions_data = questions[:session.total_questions]
    session.save()
    
    # 儲存到歷史記錄
    save_history_questions(session.user, kb_ids, questions)

def save_history_questions(user, knowledge_base_ids, questions):
    """儲存歷史題目"""
    kb_ids_str = ','.join(map(str, sorted(knowledge_base_ids)))
    
    for question in questions:
        question_hash = generate_content_hash(question['question_text'])
        HistoryQuestion.objects.get_or_create(
            user=user,
            knowledge_base_ids=kb_ids_str,
            question_hash=question_hash,
            defaults={'question_data': question}
        )

@login_required
def quiz_interface(request, session_id):
    """答題介面"""
    session = get_object_or_404(QuizSession, id=session_id, user=request.user)
    
    if session.is_completed:
        return redirect('quiz_result', session_id=session.id)
    
    if request.method == 'POST':
        # 處理答題
        question_index = session.current_question
        user_answer = request.POST.get('answer', '').strip()
        
        if question_index < len(session.questions_data):
            question = session.questions_data[question_index]
            
            # 評分
            score = grade_answer(question, user_answer)
            
            # 儲存答案
            QuestionAnswer.objects.create(
                session=session,
                question_index=question_index,
                question_text=question['question_text'],
                question_type=question['question_type'],
                correct_answer=question['answer_text'],
                user_answer=user_answer,
                score=score
            )
            
            # 更新進度
            session.current_question += 1
            if session.current_question >= len(session.questions_data):
                # 答題完成
                session.is_completed = True
                session.completed_at = timezone.now()
                # 計算總分
                total_score = session.answers.aggregate(
                    avg_score=models.Avg('score')
                )['avg_score'] or 0
                session.score = round(total_score, 1)
            
            session.save()
            
            if session.is_completed:
                return redirect('quiz_result', session_id=session.id)
    
    # 取得當前題目
    current_question = None
    if session.current_question < len(session.questions_data):
        current_question = session.questions_data[session.current_question]
    
    context = {
        'session': session,
        'current_question': current_question,
        'question_number': session.current_question + 1,
        'total_questions': len(session.questions_data),
        'progress': (session.current_question / len(session.questions_data)) * 100
    }
    return render(request, 'quiz/quiz_interface.html', context)

@login_required
def flashcard_interface(request, session_id):
    """閃卡介面"""
    session = get_object_or_404(QuizSession, id=session_id, user=request.user)
    
    context = {
        'session': session,
        'questions': session.questions_data
    }
    return render(request, 'quiz/flashcard.html', context)

@csrf_exempt
@login_required
def flashcard_answer(request, session_id):
    """閃卡答題 API"""
    if request.method != 'POST':
        return JsonResponse({'error': '無效請求'}, status=400)
    
    session = get_object_or_404(QuizSession, id=session_id, user=request.user)
    data = json.loads(request.body)
    
    question_index = data.get('question_index')
    user_answer = data.get('answer')
    
    if question_index >= len(session.questions_data):
        return JsonResponse({'error': '題目不存在'}, status=400)
    
    question = session.questions_data[question_index]
    score = grade_answer(question, user_answer)
    
    # 儲存答案
    QuestionAnswer.objects.update_or_create(
        session=session,
        question_index=question_index,
        defaults={
            'question_text': question['question_text'],
            'question_type': question['question_type'],
            'correct_answer': question['answer_text'],
            'user_answer': user_answer,
            'score': score
        }
    )
    
    # 檢查是否全部完成
    answered_count = session.answers.count()
    if answered_count >= len(session.questions_data):
        session.is_completed = True
        session.completed_at = timezone.now()
        total_score = session.answers.aggregate(avg_score=models.Avg('score'))['avg_score'] or 0
        session.score = round(total_score, 1)
        session.save()
    
    return JsonResponse({
        'correct': score == 100,
        'score': score,
        'explanation': question.get('explanation', ''),
        'completed': session.is_completed
    })

@login_required
def quiz_result(request, session_id):
    """答題結果"""
    session = get_object_or_404(QuizSession, id=session_id, user=request.user)
    answers = session.answers.all().order_by('question_index')
    
    correct_count = answers.filter(score=100).count()
    total_count = answers.count()
    accuracy_rate = round((correct_count / total_count * 100), 1) if total_count > 0 else 0
    
    # 將題目資料與答案配對，方便模板使用
    answer_details = []
    for answer in answers:
        answer_data = {
            'answer': answer,
            'explanation': ''
        }
        
        # 從會話的題目資料中找到對應的解釋
        if (session.questions_data and 
            answer.question_index < len(session.questions_data)):
            question_data = session.questions_data[answer.question_index]
            answer_data['explanation'] = question_data.get('explanation', '暫無解析')
        
        answer_details.append(answer_data)
    
    context = {
        'session': session,
        'answer_details': answer_details,
        'correct_count': correct_count,
        'total_count': total_count,
        'accuracy_rate': accuracy_rate
    }
    return render(request, 'quiz/quiz_result.html', context)

@login_required
def knowledge_base_list(request):
    """知識庫列表 - 條列式視圖"""
    knowledge_bases = KnowledgeBase.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'knowledge_bases': knowledge_bases,
    }
    return render(request, 'quiz/knowledge_base_list.html', context)

@login_required
def knowledge_base_add(request):
    """新增知識庫 - 處理表單提交"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        uploaded_file = request.FILES.get('file')
        
        # 基本驗證
        if not name:
            messages.error(request, '請輸入知識庫名稱')
            return redirect('knowledge_base_list')
            
        if not uploaded_file:
            messages.error(request, '請選擇要上傳的檔案')
            return redirect('knowledge_base_list')
        
        # 檔案驗證
        if not uploaded_file.name.lower().endswith('.txt'):
            messages.error(request, '請上傳 .txt 格式的檔案')
            return redirect('knowledge_base_list')
            
        if uploaded_file.size > 10 * 1024 * 1024:  # 10MB
            messages.error(request, '檔案大小不能超過 10MB')
            return redirect('knowledge_base_list')
        
        try:
            # 讀取檔案內容
            content = uploaded_file.read().decode('utf-8')
            
            # 檢查是否已存在同名知識庫
            if KnowledgeBase.objects.filter(user=request.user, name=name).exists():
                messages.warning(request, f'知識庫「{name}」已存在，請使用其他名稱')
                return redirect('knowledge_base_list')
            
            # 生成摘要
            summary = generate_summary(content)
            
            # 建立知識庫
            kb = KnowledgeBase.objects.create(
                name=name,
                summary=summary,
                content=content,
                user=request.user
            )
            
            # 建立向量嵌入（在背景執行）
            try:
                chunk_count = create_embeddings(kb)
                messages.success(request, 
                    f'知識庫「{name}」建立成功！已建立 {chunk_count} 個知識片段，可用於題目生成。')
            except Exception as e:
                messages.warning(request, 
                    f'知識庫「{name}」建立成功，但向量索引建立失敗：{str(e)}。仍可使用基本功能。')
                
        except UnicodeDecodeError:
            messages.error(request, '檔案編碼錯誤，請確保檔案為 UTF-8 編碼的文本檔案')
        except Exception as e:
            messages.error(request, f'建立知識庫失敗：{str(e)}')
    
    return redirect('knowledge_base_list')

@login_required
def knowledge_base_delete(request, kb_id):
    """刪除知識庫"""
    kb = get_object_or_404(KnowledgeBase, id=kb_id, user=request.user)
    kb_name = kb.name
    kb.delete()
    messages.success(request, f'已刪除知識庫「{kb_name}」')
    return redirect('knowledge_base_list')

@login_required
def user_profile(request):
    """使用者個人頁面"""
    # 答題歷史
    quiz_sessions = QuizSession.objects.filter(
        user=request.user, 
        is_completed=True
    ).order_by('-completed_at')[:20]
    
    # 統計資料
    total_quizzes = quiz_sessions.count()
    avg_score = quiz_sessions.aggregate(
        avg=models.Avg('score')
    )['avg'] or 0
    
    context = {
        'quiz_sessions': quiz_sessions,
        'total_quizzes': total_quizzes,
        'avg_score': round(avg_score, 1)
    }
    return render(request, 'quiz/user_profile.html', context)