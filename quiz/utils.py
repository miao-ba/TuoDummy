import json
import os
from ollama import chat, ChatResponse
from typing import List, Dict, Optional

def generate_prompt(count: int, question_types: str, difficulty: str, 
                   content: str, history: Optional[List[Dict]] = None) -> str:
    """生成題目的提示詞"""
    # 題目格式模板
    format_template = """
    ## 選擇題 (multiple_choice)
    {
    "question_text": "問題內容",
    "question_type": "multiple_choice", 
    "options": [
        {"text": "選項A", "is_correct": true},
        {"text": "選項B", "is_correct": false},
        {"text": "選項C", "is_correct": false},
        {"text": "選項D", "is_correct": false}
    ],
    "answer_text": "正確答案解釋",
    "explanation": "詳細解釋"
    }
    ## 是非題 (true_false)
    {
    "question_text": "問題內容（是非判斷）",
    "question_type": "true_false",
    "options": [
        {"text": "正確", "is_correct": true},
        {"text": "錯誤", "is_correct": false}
    ],
    "answer_text": "正確或錯誤", 
    "explanation": "詳細解釋"
    }
    ## 簡答題 (short_answer)
    {
    "question_text": "問題內容",
    "question_type": "short_answer",
    "answer_text": "參考答案",
    "explanation": "詳細解釋"
    }
    ## 論述題 (essay)
    {
    "question_text": "問題內容", 
    "question_type": "essay",
    "answer_text": "參考答案框架",
    "explanation": "評分要點"
    }
    """
    
    # 基本要求
    requirements = f"""
    請根據內容生成 {count} 個題目，類型包括 {question_types}，難度為 {difficulty}。
    語言請使用台灣繁體中文，專有名詞可中英對照。
    題目數量嚴格限制為 {count} 個，類型僅限於 {question_types}。
    是非題選項文字僅能為「正確」與「錯誤」。
    """
    
    # 歷史題目避重複（僅在有歷史題目時才加入）
    history_section = ""
    if history and len(history) > 0:
        history_section = f"""
        
        # 已生成的題目（請避免重複類似內容）
        {json.dumps(history, ensure_ascii=False, indent=2)}
        
        重要：請確保新生成的題目與上述歷史題目內容不重複。
        """
        requirements += "\n生成新題目時必須與歷史題目的內容和主題有所不同。"
    
    # 組合完整提示詞
    prompt = f"""
    # 學習內容
    {content}
    
    # 題目格式要求
    以下是各種題型的JSON格式範例：
    {format_template}
    
    # 生成要求
    {requirements}
    {history_section}
    
    請嚴格按照上述格式，僅返回JSON格式的題目列表：
    [
    {{題目1}},
    {{題目2}},
    ...
    ]
    """
    
    return prompt

def generate_questions_ollama(prompt: str, model: str = "gemma3:4b") -> str:
    """使用 Ollama 生成題目"""
    try:
        response: ChatResponse = chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.7}
        )
        return response['message']['content']
    except Exception as e:
        raise Exception(f"Ollama 生成失敗: {str(e)}")

def clean_json_response(response: str) -> str:
    """清理回應格式"""
    # 移除可能的 markdown 標記
    response = response.replace("```json", "").replace("```", "").strip()
    
    # 移除可能的前後文字說明，只保留 JSON 陣列部分
    start_idx = response.find('[')
    end_idx = response.rfind(']')
    
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        response = response[start_idx:end_idx+1]
    
    return response

def parse_questions(text: str) -> List[Dict]:
    """解析題目 JSON"""
    try:
        cleaned_text = clean_json_response(text)
        questions = json.loads(cleaned_text)
        
        # 驗證題目格式
        validated_questions = []
        for q in questions:
            if validate_question_format(q):
                validated_questions.append(q)
        
        return validated_questions
    except json.JSONDecodeError as e:
        raise Exception(f"JSON 解析失敗: {str(e)}")

def validate_question_format(question: Dict) -> bool:
    """驗證題目格式是否正確"""
    required_fields = ['question_text', 'question_type', 'answer_text', 'explanation']
    
    # 檢查必要欄位
    for field in required_fields:
        if field not in question:
            return False
    
    # 檢查選擇題和是非題的選項格式
    if question['question_type'] in ['multiple_choice', 'true_false']:
        if 'options' not in question or not isinstance(question['options'], list):
            return False
        
        # 確保有正確答案
        has_correct = any(opt.get('is_correct', False) for opt in question['options'])
        if not has_correct:
            return False
    
    return True

def grade_answer(question: Dict, user_answer: str, model: str = "gemma3:4b") -> int:
    """自動評分（簡答題和論述題）"""
    if question['question_type'] in ['multiple_choice', 'true_false']:
        # 客觀題直接比對
        correct_option = next((opt for opt in question['options'] if opt['is_correct']), None)
        if correct_option:
            return 100 if user_answer.strip() == correct_option['text'] else 0
        return 0
    
    # 主觀題使用 LLM 評分
    prompt = f"""
    請為以下回答評分（0-100分）：
    
    問題：{question['question_text']}
    標準答案：{question['answer_text']}
    學生回答：{user_answer}
    
    評分標準：
    - 完全正確：90-100分
    - 大部分正確：70-89分  
    - 部分正確：50-69分
    - 略有相關：30-49分
    - 完全錯誤：0-29分
    
    請直接回答數字分數，不要其他說明。
    """
    
    try:
        response: ChatResponse = chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.3}
        )
        # 提取數字分數
        score_text = response['message']['content'].strip()
        # 使用正則表達式提取數字
        import re
        numbers = re.findall(r'\d+', score_text)
        if numbers:
            score = int(numbers[0])
            return min(max(score, 0), 100)  # 限制在 0-100 範圍
        return 50  # 如果無法提取數字，給予中等分數
    except:
        return 50  # 評分失敗時給予中等分數

def generate_summary(content: str, model: str = "gemma3:4b") -> str:
    """生成知識庫摘要"""
    prompt = f"""
    請為以下內容生成50字以內的摘要，使用台灣繁體中文：
    
    {content[:1000]}...
    
    摘要：
    """
    
    try:
        response: ChatResponse = chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.5}
        )
        summary = response['message']['content'].strip()
        # 限制字數
        return summary[:50] if len(summary) > 50 else summary
    except:
        return "無法生成摘要"