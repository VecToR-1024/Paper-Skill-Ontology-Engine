#!/usr/bin/env python3
"""Semantic Scholar API 封装 — 论文搜索与结构化提取

免费 API，无需密钥。用于论文定位阶段的 Gap 扫描。

API 文档：https://api.semanticscholar.org/api-docs/

返回值约定：
    search_papers 返回 (papers, status)
    status 为 "ok" | "rate_limited" | "api_error"
    调用方根据 status 决定：ok → 正常展示 / rate_limited → 提示降级 / api_error → 提示降级 WebSearch

用法：
    from semantic_scholar import search_papers, get_paper_detail

    papers, status = search_papers("transformer attention mechanism")
    detail = get_paper_detail("paper_id")
"""

import json
import sys
import time
import urllib.request
import urllib.parse
import ssl
from typing import Optional, Tuple

BASE_URL = "https://api.semanticscholar.org/graph/v1"
TIMEOUT = 15
RETRY_DELAY = 3
MAX_RETRIES = 2

# 请求的字段
SEARCH_FIELDS = [
    "paperId",
    "title",
    "year",
    "authors",
    "citationCount",
    "influentialCitationCount",
    "abstract",
    "venue",
    "publicationTypes",
    "openAccessPdf",
]

DETAIL_FIELDS = SEARCH_FIELDS + [
    "references",
    "citations",
    "tldr",
]


def _api_request(endpoint: str, params: dict) -> Tuple[Optional[dict], str]:
    """发送 API 请求，带重试

    Returns:
        (result_dict_or_None, status)
        status: "ok" | "rate_limited" | "api_error"
    """
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"

    ctx = ssl.create_default_context()
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
                if resp.status == 429:
                    return None, "rate_limited"
                return json.loads(resp.read().decode()), "ok"
        except urllib.error.HTTPError as e:
            if e.code == 429:
                return None, "rate_limited"
            if e.code == 404:
                return None, "not_found"
            print(f"  [API HTTP {e.code}] {e.reason}", file=sys.stderr)
            return None, "api_error"
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                print(f"  [API 错误] {type(e).__name__}: {e}", file=sys.stderr)
                return None, "api_error"


def search_papers(
    query: str,
    limit: int = 20,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    fields_of_study: Optional[list] = None,
) -> Tuple[list, str]:
    """搜索论文

    Args:
        query: 搜索关键词
        limit: 返回数量（默认 20）
        year_from: 起始年份
        year_to: 截止年份
        fields_of_study: 领域过滤（如 ["Computer Science"]）

    Returns:
        (papers, status) — status: "ok" | "rate_limited" | "api_error" | "no_results"
    """
    params = {
        "query": query,
        "limit": min(limit, 100),
        "fields": ",".join(SEARCH_FIELDS),
    }
    if year_from:
        params["year"] = f"{year_from}-{year_to or ''}"

    result, api_status = _api_request("paper/search", params)
    if api_status in ("rate_limited", "api_error"):
        return [], api_status

    if not result or "data" not in result:
        return [], "no_results"

    papers = result["data"]

    # 领域过滤
    if fields_of_study:
        papers = [
            p for p in papers
            if p.get("publicationTypes")
            and any(f in str(p.get("publicationTypes", [])) for f in fields_of_study)
        ]

    if not papers:
        return [], "no_results"

    return papers, "ok"


def get_paper_detail(paper_id: str) -> Tuple[Optional[dict], str]:
    """获取论文详细信息（含引用和参考文献列表）

    Returns:
        (result, status) — status: "ok" | "api_error" | "rate_limited" | "not_found"
    """
    params = {"fields": ",".join(DETAIL_FIELDS)}
    result, api_status = _api_request(f"paper/{paper_id}", params)
    if api_status != "ok":
        return None, api_status
    if not result:
        return None, "not_found"
    return result, "ok"


def search_recent(
    query: str,
    years_back: int = 2,
    limit: int = 15,
) -> Tuple[list, str]:
    """搜索近期论文（默认近 2 年）"""
    import datetime
    current_year = datetime.datetime.now().year
    return search_papers(
        query,
        limit=limit,
        year_from=current_year - years_back,
        year_to=current_year,
    )


def format_paper_entry(p: dict) -> str:
    """格式化单篇论文为一行引用"""
    title = p.get("title", "Untitled")
    year = p.get("year", "????")
    authors = p.get("authors", [])
    author_str = (
        authors[0]["name"].split()[-1] if authors else "Unknown"
    )
    if len(authors) > 1:
        author_str += " et al."
    citations = p.get("citationCount", 0)
    paper_id = p.get("paperId", "")

    return f"[{year}] {author_str} — *{title}* (cited {citations}) · {paper_id}"


def format_gap_report(
    query: str,
    papers: list[dict],
    status: str = "ok",
    max_display: int = 10,
) -> str:
    """生成 Gap 扫描结构化报告

    Args:
        query: 原始搜索词
        papers: search_papers 返回结果
        status: "ok" | "rate_limited" | "api_error" | "no_results"
        max_display: 最多展示 N 篇

    Returns:
        Markdown 格式的 Gap 扫描报告
    """
    if status == "rate_limited":
        return (
            f"### Gap 扫描：{query}\n\n"
            "⚠️ **Semantic Scholar API 限流 (429)**。\n"
            "建议：稍后重试，或降级使用 WebSearch 进行 Gap 扫描。\n"
            "（获取免费 API key 可提升限流：https://api.semanticscholar.org/）"
        )

    if status == "api_error":
        return (
            f"### Gap 扫描：{query}\n\n"
            "❌ **Semantic Scholar API 请求失败**。\n"
            "建议：降级使用 WebSearch 进行 Gap 扫描。\n"
            "检查：网络连接、API 服务状态（https://api.semanticscholar.org/）"
        )

    if status == "no_results" or not papers:
        return (
            f"### Gap 扫描：{query}\n\n"
            "未找到相关论文。请调整搜索词或扩大搜索范围。"
        )

    lines = [f"### Gap 扫描：{query}", ""]
    lines.append(f"共找到 {len(papers)} 篇论文，展示前 {min(max_display, len(papers))} 篇：\n")

    # 按引用数排序
    sorted_papers = sorted(
        papers, key=lambda p: p.get("citationCount", 0), reverse=True
    )

    for i, p in enumerate(sorted_papers[:max_display]):
        lines.append(f"{i+1}. {format_paper_entry(p)}")
        abstract = p.get("abstract", "")
        if abstract:
            abstract_short = abstract[:200] + "..." if len(abstract) > 200 else abstract
            lines.append(f"   _{abstract_short}_")
        lines.append("")

    # 统计信息
    years = [p.get("year") for p in papers if p.get("year")]
    avg_citations = (
        sum(p.get("citationCount", 0) for p in papers) / len(papers)
        if papers else 0
    )

    lines.append("---")
    lines.append(f"**统计**：{len(papers)} 篇 · 平均引用 {avg_citations:.0f}")
    if years:
        lines.append(f"年份范围：{min(years)}-{max(years)}")
    lines.append(f"来源：Semantic Scholar API")
    lines.append("")

    # Gap 提示
    lines.append("**💡 Gap 分析提示**（需人工判断）：")
    lines.append("- 检查近年论文的共同前提——是否有未被质疑的预设？")
    lines.append("- 对比阵营：不同论文的结论是否相互矛盾？")
    lines.append("- 领域空白：哪些方向缺实验/缺理论/缺跨领域验证？")

    return "\n".join(lines)


# ─── CLI ───────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 semantic_scholar.py <搜索词> [--recent] [--limit N]")
        print("      python3 semantic_scholar.py <paper_id> --detail")
        sys.exit(1)

    if "--detail" in sys.argv:
        paper_id = sys.argv[1]
        detail, status = get_paper_detail(paper_id)
        if status == "rate_limited":
            print("⚠️ API 限流 (429)，请稍后重试")
            sys.exit(1)
        elif status == "api_error":
            print("❌ API 请求失败")
            sys.exit(1)
        elif status == "not_found":
            print("未找到该论文")
            sys.exit(1)
        else:
            print(json.dumps(detail, indent=2, ensure_ascii=False))
        sys.exit(0)

    query = sys.argv[1]
    limit = 20
    recent = "--recent" in sys.argv

    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        limit = int(sys.argv[idx + 1])

    if recent:
        papers, status = search_recent(query, limit=limit)
    else:
        papers, status = search_papers(query, limit=limit)

    report = format_gap_report(query, papers, status)
    print(report)
