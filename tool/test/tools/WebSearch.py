"""
WebSearch 工具实现
使用 Tavily API 进行网页搜索
"""

import json
import os
from urllib.request import Request, urlopen

TAVILY_API_KEY = "tvly-your-api-key-here"
TAVILY_URL = "https://api.tavily.com/search"


def execute(query: str, max_results: int = 5, include_answer: bool = True, **kwargs) -> str:
    """
    执行网页搜索
    参数:
        query: 搜索查询字符串
        max_results: 最大结果数 (默认 5)
        include_answer: 是否包含 AI 生成的答案摘要 (默认 True)
    返回: 格式化的搜索结果文本
    """
    if not query or not query.strip():
        return "错误：搜索查询不能为空。"

    # 参数类型转换（工具调用传来可能是字符串）
    try:
        max_results = int(max_results)
    except (ValueError, TypeError):
        max_results = 5
    max_results = min(max(max_results, 1), 10)
    try:
        include_answer = bool(include_answer) if not isinstance(include_answer, bool) else include_answer
    except (ValueError, TypeError):
        pass

    body = json.dumps({
        "api_key": TAVILY_API_KEY,
        "query": query.strip(),
        "max_results": min(max(int(max_results), 1), 10),
        "include_answer": bool(include_answer),
        "search_depth": "basic",
    }).encode("utf-8")

    req = Request(TAVILY_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        resp = urlopen(req, timeout=30)
        data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return f"搜索失败: {type(e).__name__} - {e}"

    lines = []

    # Answer summary
    if include_answer and data.get("answer"):
        lines.append(f"摘要: {data['answer']}")
        lines.append("")

    # Search results
    results = data.get("results", [])
    if not results:
        return "未找到相关结果。"

    lines.append(f"搜索结果 ({len(results)}):")
    for i, r in enumerate(results[:max_results], 1):
        title = r.get("title", "无标题")
        url = r.get("url", "")
        content = r.get("content", "")
        # 截断过长内容
        if len(content) > 200:
            content = content[:200] + "..."
        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   URL: {url}")
        lines.append(f"   {content}")
        lines.append("")

    return "\n".join(lines).strip()
