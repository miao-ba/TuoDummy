import torch
import numpy as np
from transformers import AutoModel
from django.conf import settings
from django.db import connection
from .models import KnowledgeBase, KnowledgeChunk
import hashlib
import re
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    """向量嵌入服務"""
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._model is None:
            try:
                # 載入 Jina 嵌入模型
                self._model = AutoModel.from_pretrained(
                    settings.EMBEDDING_MODEL,
                    trust_remote_code=True,
                    torch_dtype=torch.bfloat16
                )
                logger.info("Embedding 模型載入成功")
            except Exception as e:
                logger.error(f"Embedding 模型載入失敗: {e}")
                self._model = None
    
    def encode(self, texts):
        """文本轉向量"""
        if self._model is None:
            logger.warning("Embedding 模型未載入，返回預設向量")
            # 返回預設向量（768維度的零向量）
            if isinstance(texts, str):
                return np.zeros(768, dtype=np.float32)
            else:
                return np.zeros((len(texts), 768), dtype=np.float32)
        
        if isinstance(texts, str):
            texts = [texts]
        
        try:
            with torch.no_grad():
                embeddings = self._model.encode(texts)
                
            # 確保返回 numpy 數組
            if torch.is_tensor(embeddings):
                embeddings = embeddings.cpu().numpy()
            
            # 確保數據類型為 float32
            embeddings = embeddings.astype(np.float32)
            
            return embeddings if len(texts) > 1 else embeddings[0]
        except Exception as e:
            logger.error(f"文本編碼失敗: {e}")
            # 返回預設向量
            if len(texts) == 1:
                return np.zeros(768, dtype=np.float32)
            else:
                return np.zeros((len(texts), 768), dtype=np.float32)

def split_text(text, chunk_size=500, overlap=50):
    """文本分割成片段"""
    sentences = re.split(r'[。！？\n]', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        if len(current_chunk) + len(sentence) < chunk_size:
            current_chunk += sentence + "。"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + "。"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return [chunk for chunk in chunks if len(chunk) > 10]  # 過濾太短的片段

def create_embeddings(knowledge_base):
    """為知識庫建立向量嵌入"""
    try:
        embedding_service = EmbeddingService()
        
        # 分割文本
        chunks = split_text(knowledge_base.content)
        
        if not chunks:
            logger.warning(f"知識庫 {knowledge_base.name} 沒有有效的文本片段")
            return 0
        
        # 刪除舊的嵌入
        KnowledgeChunk.objects.filter(knowledge_base=knowledge_base).delete()
        
        # 建立新的嵌入
        chunk_objects = []
        successful_chunks = 0
        
        for i, chunk_text in enumerate(chunks):
            try:
                # 生成向量
                embedding = embedding_service.encode(chunk_text)
                
                # 確保向量是正確的格式
                if embedding is not None and len(embedding) == 768:
                    # 轉換為 Python list 格式儲存
                    embedding_list = embedding.tolist()
                    
                    chunk_objects.append(KnowledgeChunk(
                        knowledge_base=knowledge_base,
                        content=chunk_text,
                        embedding=embedding_list,
                        chunk_index=i
                    ))
                    successful_chunks += 1
                else:
                    logger.warning(f"片段 {i} 的向量生成失敗，使用預設向量")
                    # 使用零向量作為預設
                    default_embedding = [0.0] * 768
                    
                    chunk_objects.append(KnowledgeChunk(
                        knowledge_base=knowledge_base,
                        content=chunk_text,
                        embedding=default_embedding,
                        chunk_index=i
                    ))
                    
            except Exception as e:
                logger.error(f"處理片段 {i} 時發生錯誤: {e}")
                # 跳過有問題的片段
                continue
        
        # 批量儲存
        if chunk_objects:
            KnowledgeChunk.objects.bulk_create(chunk_objects)
            logger.info(f"成功建立 {len(chunk_objects)} 個知識片段，其中 {successful_chunks} 個有有效向量")
            return len(chunk_objects)
        else:
            logger.error("沒有成功建立任何知識片段")
            return 0
            
    except Exception as e:
        logger.error(f"建立向量嵌入失敗: {e}")
        return 0

def search_similar_chunks(query, knowledge_base_ids, top_k=5):
    """搜尋相似的知識片段"""
    try:
        embedding_service = EmbeddingService()
        
        # 將查詢轉換為向量
        query_embedding = embedding_service.encode(query)
        
        # 確保向量為正確格式
        if query_embedding is None or len(query_embedding) == 0:
            logger.warning("查詢向量生成失敗，返回空結果")
            return []
        
        # 轉換為列表格式用於 PostgreSQL
        query_vector_list = query_embedding.tolist()
        
        # 使用 pgvector 進行相似度搜尋
        with connection.cursor() as cursor:
            # 修正的 SQL 查詢，確保向量類型匹配
            cursor.execute("""
                SELECT qkc.content, qkc.knowledge_base_id, 
                       (qkc.embedding <-> %s::vector) as distance
                FROM quiz_knowledgechunk qkc
                WHERE qkc.knowledge_base_id = ANY(%s)
                ORDER BY qkc.embedding <-> %s::vector
                LIMIT %s
            """, [query_vector_list, knowledge_base_ids, query_vector_list, top_k])
            
            results = cursor.fetchall()
        
        return [{
            'content': row[0],
            'knowledge_base_id': row[1],
            'similarity': max(0, 1 - row[2])  # 距離轉相似度，確保非負
        } for row in results]
        
    except Exception as e:
        logger.error(f"向量搜尋失敗: {e}")
        # 返回基於文本的備用搜尋
        return fallback_text_search(query, knowledge_base_ids, top_k)

def fallback_text_search(query, knowledge_base_ids, top_k=5):
    """備用文本搜尋（當向量搜尋失敗時）"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT qkc.content, qkc.knowledge_base_id, 
                       CASE 
                           WHEN qkc.content ILIKE %s THEN 0.9
                           WHEN qkc.content ILIKE %s THEN 0.7
                           ELSE 0.5
                       END as similarity
                FROM quiz_knowledgechunk qkc
                WHERE qkc.knowledge_base_id = ANY(%s)
                AND (qkc.content ILIKE %s OR qkc.content ILIKE %s)
                ORDER BY similarity DESC
                LIMIT %s
            """, [
                f'%{query}%',  # 完全匹配
                f'%{query[:len(query)//2]}%',  # 部分匹配
                knowledge_base_ids,
                f'%{query}%',
                f'%{query[:len(query)//2]}%',
                top_k
            ])
            
            results = cursor.fetchall()
        
        return [{
            'content': row[0],
            'knowledge_base_id': row[1],
            'similarity': row[2]
        } for row in results]
        
    except Exception as e:
        logger.error(f"備用文本搜尋也失敗: {e}")
        return []

def get_relevant_content(knowledge_base_ids, question_types, max_chunks=10):
    """獲取相關內容用於題目生成"""
    # 根據題目類型建立查詢
    type_queries = {
        'multiple_choice': '選擇題 概念 定義',
        'true_false': '判斷 對錯 是非',
        'short_answer': '簡答 解釋 說明',
        'essay': '論述 分析 評論'
    }
    
    all_chunks = []
    for q_type in question_types.split(','):
        q_type = q_type.strip()
        if q_type in type_queries:
            query = type_queries[q_type]
            chunks = search_similar_chunks(query, knowledge_base_ids, top_k=3)
            all_chunks.extend(chunks)
    
    # 去重並限制數量
    seen_content = set()
    unique_chunks = []
    for chunk in all_chunks:
        if chunk['content'] not in seen_content:
            seen_content.add(chunk['content'])
            unique_chunks.append(chunk)
            if len(unique_chunks) >= max_chunks:
                break
    
    return '\n\n'.join([chunk['content'] for chunk in unique_chunks])

def generate_content_hash(content):
    """生成內容雜湊值"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def get_history_questions(user, knowledge_base_ids):
    """獲取歷史題目避免重複"""
    from .models import HistoryQuestion
    
    kb_ids_str = ','.join(map(str, sorted(knowledge_base_ids)))
    history_questions = HistoryQuestion.objects.filter(
        user=user,
        knowledge_base_ids=kb_ids_str
    ).order_by('-created_at')[:20]  # 最近20題
    
    return [hq.question_data for hq in history_questions]