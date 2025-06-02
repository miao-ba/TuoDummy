import json
import os
from ollama import chat, ChatResponse
from typing import List, Dict, Optional

def generate_prompt(count: int, question_types: str, difficulty: str, 
                   content: str, history: Optional[str] = None) -> str:
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
    
    requirements = f"""
    請根據內容生成 {count} 個題目，類型包括 {question_types}，難度為 {difficulty}。
    語言請使用台灣繁體中文，專有名詞可中英對照。
    題目數量嚴格限制為 {count} 個，類型僅限於 {question_types}。
    是非題選項文字僅能為「正確」與「錯誤」。
    """
    
    # 加入歷史題目避免重複
    history_prompt = f"\n# 歷史題目\n{history}\n" if history else ""
    if history:
        requirements += "\n生成新題目時不能與歷史題目重複。"
    
    return f"""
    # 內容
    {content}
    # 題目格式要求
    {format_template}
    請僅返回JSON格式的題目列表：
    [
    {{題目1}},
    {{題目2}}
    ]
    {history_prompt}
    {requirements}
    """

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
    return response.replace("```json", "").replace("```", "").strip()

def parse_questions(text: str) -> List[Dict]:
    """解析題目 JSON"""
    try:
        return json.loads(clean_json_response(text))
    except json.JSONDecodeError as e:
        raise Exception(f"JSON 解析失敗: {str(e)}")

def grade_answer(question: Dict, user_answer: str, model: str = "gemma3:4b") -> int:
    """自動評分（簡答題和論述題）"""
    if question['question_type'] in ['multiple_choice', 'true_false']:
        # 客觀題直接比對
        correct_option = next(opt for opt in question['options'] if opt['is_correct'])
        return 100 if user_answer.strip() == correct_option['text'] else 0
    
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
    
    請直接回答數字分數。
    """
    
    try:
        response: ChatResponse = chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.3}
        )
        # 提取數字分數
        score_text = response['message']['content'].strip()
        score = int(''.join(filter(str.isdigit, score_text)))
        return min(max(score, 0), 100)  # 限制在 0-100 範圍
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
        return response['message']['content'].strip()[:50]
    except:
        return "無法生成摘要"