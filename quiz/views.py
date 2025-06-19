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
import requests
from django.views.decorators.http import require_http_methods
from .models import AIModel, UserModelPreference
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
            generate_questions_with_model(session)
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
            generate_questions_with_model(session)
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

class OllamaClient:
    """Ollama 客戶端"""
    
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
    
    def get_models(self):
        """獲取可用的模型清單"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            else:
                print(f"Ollama API 回應錯誤: {response.status_code}")
                return []
        except requests.exceptions.ConnectionError:
            print("無法連接到 Ollama 服務，請確認服務是否運行")
            return []
        except requests.exceptions.Timeout:
            print("Ollama API 回應超時")
            return []
        except Exception as e:
            print(f"獲取 Ollama 模型清單時發生錯誤: {e}")
            return []
    
    def test_model(self, model_name):
        """測試模型是否可用"""
        try:
            payload = {
                "model": model_name,
                "prompt": "test",
                "stream": False
            }
            response = requests.post(
                f"{self.base_url}/api/generate", 
                json=payload, 
                timeout=30
            )
            return response.status_code == 200
        except Exception as e:
            print(f"測試 Ollama 模型 {model_name} 時發生錯誤: {e}")
            return False

@login_required
def model_management(request):
    """模型管理頁面"""
    user_models = AIModel.objects.filter(user=request.user)
    
    # 獲取使用者偏好
    preference, created = UserModelPreference.objects.get_or_create(user=request.user)
    
    # 獲取可用的 Ollama 模型
    ollama_client = OllamaClient()
    available_ollama_models = ollama_client.get_models()
    
    context = {
        'user_models': user_models,
        'preference': preference,
        'available_ollama_models': available_ollama_models,
    }
    return render(request, 'quiz/model_management.html', context)

@login_required
@require_http_methods(["POST"])
def add_model(request):
    """新增模型"""
    model_type = request.POST.get('model_type')
    model_name = request.POST.get('model_name')
    model_id = request.POST.get('model_id')
    api_key = request.POST.get('api_key', '')
    base_url = request.POST.get('base_url', '')
    temperature = float(request.POST.get('temperature', 0.7))
    
    try:
        # 檢查模型是否已存在
        if AIModel.objects.filter(
            user=request.user, 
            model_id=model_id, 
            model_type=model_type
        ).exists():
            messages.error(request, f'模型 {model_id} 已存在')
            return redirect('model_management')
        
        # 設定預設 base_url
        if model_type == 'ollama' and not base_url:
            base_url = "http://localhost:11434"
        
        # 建立模型
        model = AIModel.objects.create(
            user=request.user,
            name=model_name,
            model_type=model_type,
            model_id=model_id,
            api_key=api_key if api_key else None,
            base_url=base_url if base_url else None,
            temperature=temperature
        )
        
        # 測試連線
        success, message = model.test_connection()
        model.is_available = success
        model.save()
        
        if success:
            messages.success(request, f'模型 {model_name} 新增成功並測試通過')
            
            # 如果是第一個可用模型，設為預設
            preference, created = UserModelPreference.objects.get_or_create(user=request.user)
            if not preference.default_model:
                preference.default_model = model
                preference.save()
                messages.info(request, f'已將 {model_name} 設為預設模型')
        else:
            messages.warning(request, f'模型 {model_name} 新增成功但連線測試失敗: {message}')
            
    except Exception as e:
        messages.error(request, f'新增模型失敗: {str(e)}')
    
    return redirect('model_management')

@login_required
@csrf_exempt
def test_model_connection(request, model_id):
    """測試模型連線 API"""
    if request.method != 'POST':
        return JsonResponse({'error': '無效的請求方法'}, status=405)
    
    try:
        model = get_object_or_404(AIModel, id=model_id, user=request.user)
        success, message = model.test_connection()
        
        # 更新可用狀態
        model.is_available = success
        model.save()
        
        return JsonResponse({
            'success': success,
            'message': message,
            'model_name': model.name
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def set_default_model(request, model_id):
    """設定預設模型"""
    try:
        model = get_object_or_404(AIModel, id=model_id, user=request.user)
        
        if not model.is_available:
            messages.error(request, '無法將不可用的模型設為預設')
            return redirect('model_management')
        
        preference, created = UserModelPreference.objects.get_or_create(user=request.user)
        preference.default_model = model
        preference.save()
        
        messages.success(request, f'已將 {model.name} 設為預設模型')
        
    except Exception as e:
        messages.error(request, f'設定預設模型失敗: {str(e)}')
    
    return redirect('model_management')

@login_required
def delete_model(request, model_id):
    """刪除模型"""
    try:
        model = get_object_or_404(AIModel, id=model_id, user=request.user)
        model_name = model.name
        
        # 如果是預設模型，清除預設設定
        preference = UserModelPreference.objects.filter(user=request.user).first()
        if preference and preference.default_model == model:
            preference.default_model = None
            preference.save()
            messages.info(request, '已清除預設模型設定')
        
        model.delete()
        messages.success(request, f'已刪除模型 {model_name}')
        
    except Exception as e:
        messages.error(request, f'刪除模型失敗: {str(e)}')
    
    return redirect('model_management')

@csrf_exempt
def get_available_ollama_models():
    """獲取可用的 Ollama 模型（使用新的方式）"""
    ollama_client = OllamaClient()
    return ollama_client.get_models()

@login_required
@csrf_exempt
def fetch_ollama_models_api(request):
    """獲取 Ollama 模型 API"""
    if request.method != 'POST':
        return JsonResponse({'error': '無效的請求方法'}, status=405)
    
    try:
        data = json.loads(request.body)
        base_url = data.get('base_url', 'http://localhost:11434')
        
        ollama_client = OllamaClient(base_url)
        models = ollama_client.get_models()
        
        if models:
            return JsonResponse({
                'success': True,
                'models': models,
                'message': f'成功獲取 {len(models)} 個模型'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Ollama 服務未運行或沒有可用模型'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'error': '無效的 JSON 格式'}, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
@csrf_exempt
def fetch_gemini_models(request):
    """獲取 Gemini 可用模型 API"""
    if request.method != 'POST':
        return JsonResponse({'error': '無效的請求方法'}, status=405)
    
    try:
        data = json.loads(request.body)
        api_key = data.get('api_key')
        
        if not api_key:
            return JsonResponse({'error': '缺少 API 金鑰'}, status=400)
        
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # 嘗試獲取模型列表
        try:
            # 使用常見的 Gemini 模型列表，因為API可能不提供模型列表
            common_models = [
                'gemini-1.5-flash',
                'gemini-1.5-pro',
                'gemini-2.0-flash-exp',
                'gemini-1.5-flash-8b'
            ]
            
            # 測試第一個模型來驗證 API 金鑰
            test_response = client.models.generate_content(
                model=common_models[0],
                contents="test"
            )
            
            return JsonResponse({
                'success': True,
                'models': common_models,
                'message': 'API 金鑰驗證成功'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'API 金鑰驗證失敗: {str(e)}'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': '無效的 JSON 格式'}, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

# 修改現有的題目生成函數以支援模型選擇
def get_user_default_model(user):
    """獲取使用者的預設模型"""
    try:
        preference = UserModelPreference.objects.get(user=user)
        if preference.default_model and preference.default_model.is_available:
            return preference.default_model
    except UserModelPreference.DoesNotExist:
        pass
    
    # 如果沒有預設模型，返回第一個可用的模型
    available_model = AIModel.objects.filter(
        user=user, 
        is_available=True
    ).first()
    
    return available_model

def generate_questions_with_model(session, model=None):
    """使用指定模型生成題目"""
    if not model:
        model = get_user_default_model(session.user)
        
    if not model:
        # 如果沒有可用的模型，使用傳統方式
        return generate_quiz_questions_fallback(session)
    
    # 獲取相關內容
    kb_ids = list(session.knowledge_bases.values_list('id', flat=True))
    content = get_relevant_content(kb_ids, session.question_types)
    
    if not content:
        raise Exception("無法找到相關內容")
    
    print(f"使用模型 {model.name} 生成 {session.total_questions} 個題目")
    
    # 批量生成題目
    questions = []
    remaining = session.total_questions
    temp_history = []
    
    while remaining > 0:
        batch_size = min(remaining, 10)
        print(f"生成批次：{batch_size} 題，剩餘：{remaining} 題")
        
        # 生成提示詞
        prompt = generate_prompt(
            count=batch_size,
            question_types=session.question_types,
            difficulty=session.difficulty,
            content=content,
            history=temp_history
        )
        
        try:
            # 使用指定模型生成
            response = model.generate_content(prompt)
            batch_questions = parse_questions(response)
            
            if not batch_questions:
                raise Exception("本批次無法生成有效題目")
            
            print(f"本批次生成 {len(batch_questions)} 個題目")
            
            questions.extend(batch_questions)
            temp_history.extend([{
                'question_text': q['question_text'],
                'question_type': q['question_type']
            } for q in batch_questions])
            
            remaining -= len(batch_questions)
            
            if len(temp_history) > 20:
                temp_history = temp_history[-20:]
                
        except Exception as e:
            print(f"批次生成失敗：{str(e)}")
            if batch_size > 1:
                batch_size = max(1, batch_size // 2)
                continue
            else:
                raise Exception(f"使用模型 {model.name} 生成題目失敗: {str(e)}")
    
    # 儲存題目
    final_questions = questions[:session.total_questions]
    session.questions_data = final_questions
    session.save()
    
    print(f"使用 {model.name} 成功生成 {len(final_questions)} 個題目")
    
    return final_questions

def generate_quiz_questions_fallback(session):
    """備用的題目生成方式（當沒有可用模型時）"""
    # 使用原來的 ollama 客戶端方式
    from ollama import chat, ChatResponse
    
    # 獲取相關內容
    kb_ids = list(session.knowledge_bases.values_list('id', flat=True))
    content = get_relevant_content(kb_ids, session.question_types)
    
    if not content:
        raise Exception("無法找到相關內容")
    
    print(f"使用備用方式生成 {session.total_questions} 個題目")
    
    # 生成提示詞
    prompt = generate_prompt(
        count=session.total_questions,
        question_types=session.question_types,
        difficulty=session.difficulty,
        content=content
    )
    
    try:
        # 使用 ollama 客戶端
        response: ChatResponse = chat(
            model="gemma3:4b",  # 預設模型
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.7}
        )
        
        questions = parse_questions(response['message']['content'])
        
        if not questions:
            raise Exception("無法生成有效題目")
        
        # 儲存題目
        session.questions_data = questions[:session.total_questions]
        session.save()
        
        print(f"備用方式成功生成 {len(session.questions_data)} 個題目")
        
    except Exception as e:
        raise Exception(f"備用方式生成題目失敗: {str(e)}")
    
    return session.questions_data
def save_history_questions(user, knowledge_base_ids, questions):
    """儲存歷史題目（用於統計，不影響生成邏輯）"""
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
    
    if session.is_completed:
        return redirect('quiz_result', session_id=session.id)
    
    # 檢查題目資料是否存在
    if not session.questions_data:
        messages.error(request, '找不到題目資料，請重新生成')
        return redirect('flashcard_setup')
    
    context = {
        'session': session,
        'questions': session.questions_data,  # 直接傳遞原始資料，讓模板處理
        'questions_json': json.dumps(session.questions_data, ensure_ascii=False)  # 額外提供 JSON 字串
    }
    return render(request, 'quiz/flashcard.html', context)

@csrf_exempt
@login_required
def flashcard_answer(request, session_id):
    """閃卡答題 API"""
    if request.method != 'POST':
        return JsonResponse({'error': '無效請求'}, status=400)
    
    session = get_object_or_404(QuizSession, id=session_id, user=request.user)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '無效的 JSON 格式'}, status=400)
    
    question_index = data.get('question_index')
    user_answer = data.get('answer')
    
    if question_index is None or question_index >= len(session.questions_data):
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