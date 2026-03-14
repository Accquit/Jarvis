# actions/web_search.py
# MARK XXX — Web Search
# Primary: Tavily Search API (AI-Optimized Synthesized Responses)
# Fallback: DuckDuckGo (ddgs)

import json
import sys
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

def _get_api_keys() -> dict:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _tavily_search(query: str) -> str:
    import requests
    keys = _get_api_keys()
    api_key = keys.get("tavily_api_key")
    
    if not api_key:
        raise ValueError("Tavily API key not found in config.")

    # We use advanced depth and include_answer to get a highly detailed summary
    # synthesized from the top 5 websites by Tavily's backend LLMs directly via REST API.
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": 5
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    
    answer = data.get("answer", "")
    if answer:
        return f"Synthesized Answer:\n{answer}"
        
    # Fallback to formatting raw results if no direct answer is provided
    results = data.get("results", [])
    if not results:
        raise ValueError("Empty response from Tavily")
        
    formatted = []
    for r in results:
        formatted.append(f"Source ({r.get('url')}):\n{r.get('content')}\n")
    return "\n".join(formatted[:3])

def _ddg_search(query: str, max_results: int = 6) -> list:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title":   r.get("title", ""),
                "snippet": r.get("body", ""),
                "url":     r.get("href", ""),
            })
    return results

def _format_ddg(query: str, results: list) -> str:
    if not results:
        return f"No results found for: {query}"
    lines = [f"Basic Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        lines.append("")
    return "\n".join(lines).strip()

def web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode", "search").lower()
    items  = params.get("items", [])

    if not query and not items:
        return "Please provide a search query, sir."

    if items and mode != "compare":
        mode = "compare"
        query = f"Compare {', '.join(items)}"

    if player:
        player.write_log(f"[Search] {query}")

    print(f"[WebSearch] 🔍 Query: {query!r}")

    try:
        print("[WebSearch] 🌐 Tavily Advanced Agent Search...")
        try:
            result = _tavily_search(query)
            print("[WebSearch] ✅ Tavily OK.")
            return result
        except Exception as e:
            print(f"[WebSearch] ⚠️ Tavily failed ({e}), trying DDG fallback...")
            results = _ddg_search(query)
            result  = _format_ddg(query, results)
            print(f"[WebSearch] ✅ DDG: {len(results)} results.")
            return result

    except Exception as e:
        print(f"[WebSearch] ❌ Failed: {e}")
        return f"Search failed entirely, sir: {e}"