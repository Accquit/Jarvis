import sys
import json
import uuid
import re
from pathlib import Path
from collections import Counter
import math

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
DB_FILE = BASE_DIR / "memory" / "vector_db.json"

def _load_db() -> list[dict]:
    if not DB_FILE.exists():
        return []
    try:
        data = json.loads(DB_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[VectorMemory] ⚠️ Load error: {e}")
        return []

def _save_db(data: list[dict]):
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    DB_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _tokenize(text: str) -> list[str]:
    # Simple word tokenization, lowercase, remove punctuation
    words = re.findall(r'\b\w+\b', text.lower())
    # Exclude very common stop words to improve search relevance
    stop_words = {"the", "is", "at", "which", "on", "a", "an", "and", "or", "in", "to", "of", "it", "that", "this", "for", "with", "as", "by"}
    return [w for w in words if w not in stop_words]

def add_memory(text: str):
    """Adds a semantic memory to the local JSON database."""
    if not text or not text.strip():
        return
    
    db = _load_db()
    memory_id = str(uuid.uuid4())
    tokens = _tokenize(text)
    
    # Don't add if it's identical or super similar to the last one
    if db and len(db[-1]["text"]) > 10 and text in db[-1]["text"]:
        return

    db.append({
        "id": memory_id,
        "text": text,
        "tokens": tokens,
        "source": "conversation"
    })
    
    _save_db(db)
    print(f"[VectorMemory] 🧠 Embedded and saved: {text[:50]}...")

def search_memory(query: str, n_results: int = 3) -> list[str]:
    """Searches the database using a basic TF-IDF / BM25 style keyword overlap scoring."""
    if not query or not query.strip():
        return []
        
    db = _load_db()
    if not db:
        return []
        
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    # Calculate basic term frequencies across documents
    doc_freq = Counter()
    for doc in db:
        unique_tokens = set(doc.get("tokens", []))
        for token in unique_tokens:
            doc_freq[token] += 1
            
    num_docs = len(db)
    
    # Score documents
    scored_docs = []
    for doc in db:
        doc_tokens = doc.get("tokens", [])
        if not doc_tokens: continue
            
        doc_len = len(doc_tokens)
        score = 0.0
        
        # Calculate TF-IDF score for this document
        for q_term in query_tokens:
            tf = doc_tokens.count(q_term) / doc_len if doc_len > 0 else 0
            # IDF: log( total_docs / doc_freq[q_term] )
            df = doc_freq[q_term]
            idf = math.log(num_docs / df) if df > 0 else 0
            
            score += tf * idf
            
        # Boost score slightly if there are exact word overlaps
        exact_matches = sum(1 for q in query_tokens if q in doc_tokens)
        score += (exact_matches * 0.5)

        if score > 0:
            scored_docs.append((score, doc["text"]))
            
    # Sort by score descending
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    
    # Return top N text results
    top_results = [text for score, text in scored_docs[:n_results]]
    
    if top_results:
        print(f"[VectorMemory] 🔍 Found {len(top_results)} memories for query: '{query}'")
        
    return top_results
