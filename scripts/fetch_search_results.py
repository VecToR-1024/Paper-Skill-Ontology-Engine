from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml


SEMANTIC_SCHOLAR_SEARCH_FIELDS = [
    "paperId",
    "title",
    "authors",
    "year",
    "venue",
    "abstract",
    "url",
    "externalIds",
    "citationCount",
    "influentialCitationCount",
    "publicationDate",
]

OPENALEX_SELECT_FIELDS = [
    "id",
    "doi",
    "display_name",
    "title",
    "publication_year",
    "authorships",
    "primary_location",
    "host_venue",
    "abstract_inverted_index",
    "relevance_score",
    "cited_by_count",
]

Opener = Callable[..., Any]


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def compact_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item is not None)
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def first_text(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            text = compact_text(item)
            if text:
                return text
        return None
    return compact_text(value)


def strip_tags(value: Any) -> str | None:
    text = compact_text(value)
    if not text:
        return None
    return compact_text(re.sub(r"<[^>]+>", " ", text))


def normalize_doi(value: Any) -> str | None:
    text = compact_text(value)
    if not text:
        return None
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    return text


def strip_arxiv_version(value: Any) -> str | None:
    text = compact_text(value)
    if not text:
        return None
    text = text.rsplit("/", 1)[-1]
    return re.sub(r"v\d+$", "", text)


def author_names(authors: Any) -> str | None:
    if not isinstance(authors, list):
        return None
    names: list[str] = []
    for author in authors:
        if isinstance(author, dict):
            name = compact_text(author.get("name") or author.get("display_name"))
        else:
            name = compact_text(author)
        if name:
            names.append(name)
    return "; ".join(names) or None


def openalex_author_names(authorships: Any) -> str | None:
    if not isinstance(authorships, list):
        return None
    names: list[str] = []
    for authorship in authorships:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author")
        if isinstance(author, dict):
            name = compact_text(author.get("display_name"))
            if name:
                names.append(name)
    return "; ".join(names) or None


def year_from_date_parts(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    date_parts = value.get("date-parts")
    if (
        isinstance(date_parts, list)
        and date_parts
        and isinstance(date_parts[0], list)
        and date_parts[0]
    ):
        try:
            return int(date_parts[0][0])
        except (TypeError, ValueError):
            return None
    return None


def year_from_iso(value: Any) -> int | None:
    text = compact_text(value)
    if not text:
        return None
    match = re.match(r"(\d{4})", text)
    return int(match.group(1)) if match else None


def venue_from_openalex(item: dict[str, Any]) -> str | None:
    primary_location = item.get("primary_location")
    if isinstance(primary_location, dict):
        source = primary_location.get("source")
        if isinstance(source, dict):
            venue = compact_text(source.get("display_name"))
            if venue:
                return venue
    host_venue = item.get("host_venue")
    if isinstance(host_venue, dict):
        return compact_text(host_venue.get("display_name"))
    return None


def reconstruct_openalex_abstract(index: Any) -> str | None:
    if not isinstance(index, dict):
        return None
    positions: list[tuple[int, str]] = []
    for word, offsets in index.items():
        if not isinstance(offsets, list):
            continue
        for offset in offsets:
            try:
                positions.append((int(offset), str(word)))
            except (TypeError, ValueError):
                continue
    if not positions:
        return None
    return " ".join(word for _, word in sorted(positions))


def request_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
    opener: Opener = urllib.request.urlopen,
) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "*/*",
            "User-Agent": "research-paper-suite/0.1",
            **(headers or {}),
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"HTTP {error.code} from search provider: {error.reason}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"network error from search provider: {error.reason}") from error


def request_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    data = request_bytes(url, headers=headers, timeout=timeout, opener=opener)
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("search provider returned non-object JSON")
    return parsed


def normalize_semantic_scholar(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    items = data.get("data")
    if not isinstance(items, list):
        return rows
    for item in items:
        if not isinstance(item, dict):
            continue
        title = compact_text(item.get("title"))
        if not title:
            continue
        external_ids = item.get("externalIds") if isinstance(item.get("externalIds"), dict) else {}
        row: dict[str, Any] = {
            "provider_work_id": compact_text(item.get("paperId")),
            "title": title,
            "authors": author_names(item.get("authors")),
            "year": item.get("year") if isinstance(item.get("year"), int) else None,
            "venue": compact_text(item.get("venue")),
            "doi": normalize_doi(external_ids.get("DOI")),
            "arxiv_id": strip_arxiv_version(external_ids.get("ArXiv")),
            "uri": compact_text(item.get("url")),
            "abstract": compact_text(item.get("abstract")),
            "citation_count": item.get("citationCount"),
            "influential_citation_count": item.get("influentialCitationCount"),
            "publication_date": compact_text(item.get("publicationDate")),
        }
        rows.append({key: value for key, value in row.items() if value not in (None, "")})
    return rows


def normalize_crossref(data: dict[str, Any]) -> list[dict[str, Any]]:
    message = data.get("message")
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = first_text(item.get("title"))
        if not title:
            continue
        authors = []
        for author in item.get("author") or []:
            if not isinstance(author, dict):
                continue
            given = compact_text(author.get("given"))
            family = compact_text(author.get("family"))
            name = " ".join(part for part in (given, family) if part)
            if name:
                authors.append(name)
        year = (
            year_from_date_parts(item.get("issued"))
            or year_from_date_parts(item.get("published-print"))
            or year_from_date_parts(item.get("published-online"))
        )
        row: dict[str, Any] = {
            "provider_work_id": normalize_doi(item.get("DOI")),
            "title": title,
            "authors": "; ".join(authors) or None,
            "year": year,
            "venue": first_text(item.get("container-title")),
            "doi": normalize_doi(item.get("DOI")),
            "uri": compact_text(item.get("URL")),
            "abstract": strip_tags(item.get("abstract")),
            "score": item.get("score") if isinstance(item.get("score"), (int, float)) else None,
            "type": compact_text(item.get("type")),
        }
        rows.append({key: value for key, value in row.items() if value not in (None, "")})
    return rows


def normalize_openalex(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = data.get("results")
    if not isinstance(items, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = compact_text(item.get("display_name") or item.get("title"))
        if not title:
            continue
        row: dict[str, Any] = {
            "provider_work_id": compact_text(item.get("id")),
            "title": title,
            "authors": openalex_author_names(item.get("authorships")),
            "year": item.get("publication_year") if isinstance(item.get("publication_year"), int) else None,
            "venue": venue_from_openalex(item),
            "doi": normalize_doi(item.get("doi")),
            "uri": compact_text(item.get("doi") or item.get("id")),
            "abstract": reconstruct_openalex_abstract(item.get("abstract_inverted_index")),
            "score": item.get("relevance_score") if isinstance(item.get("relevance_score"), (int, float)) else None,
            "citation_count": item.get("cited_by_count"),
        }
        rows.append({key: value for key, value in row.items() if value not in (None, "")})
    return rows


def normalize_arxiv(feed_bytes: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(feed_bytes)
    atom = {"atom": "http://www.w3.org/2005/Atom"}
    rows: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", atom):
        title = compact_text(entry.findtext("atom:title", default="", namespaces=atom))
        if not title:
            continue
        entry_id = compact_text(entry.findtext("atom:id", default="", namespaces=atom))
        arxiv_id = strip_arxiv_version(entry_id)
        authors = [
            compact_text(author.findtext("atom:name", default="", namespaces=atom))
            for author in entry.findall("atom:author", atom)
        ]
        link = None
        for link_node in entry.findall("atom:link", atom):
            if link_node.get("rel") == "alternate" or link is None:
                link = link_node.get("href")
        row: dict[str, Any] = {
            "provider_work_id": arxiv_id,
            "title": title,
            "authors": "; ".join(author for author in authors if author) or None,
            "year": year_from_iso(entry.findtext("atom:published", default="", namespaces=atom)),
            "venue": "arXiv",
            "arxiv_id": arxiv_id,
            "uri": compact_text(link or entry_id),
            "abstract": compact_text(entry.findtext("atom:summary", default="", namespaces=atom)),
        }
        rows.append({key: value for key, value in row.items() if value not in (None, "")})
    return rows


def semantic_scholar_url(query: str, limit: int, offset: int, year_from: int | None, year_to: int | None) -> str:
    params: dict[str, Any] = {
        "query": query,
        "limit": min(limit, 100),
        "offset": max(offset, 0),
        "fields": ",".join(SEMANTIC_SCHOLAR_SEARCH_FIELDS),
    }
    if year_from and year_to:
        params["year"] = f"{year_from}-{year_to}"
    elif year_from:
        params["year"] = f"{year_from}-"
    elif year_to:
        params["year"] = f"-{year_to}"
    return "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)


def crossref_url(query: str, limit: int, offset: int, mailto: str | None) -> str:
    params: dict[str, Any] = {
        "query.bibliographic": query,
        "rows": min(limit, 100),
        "offset": max(offset, 0),
    }
    if mailto:
        params["mailto"] = mailto
    return "https://api.crossref.org/works?" + urllib.parse.urlencode(params)


def openalex_url(
    query: str,
    limit: int,
    page: int,
    mailto: str | None,
    year_from: int | None,
    year_to: int | None,
) -> str:
    params: dict[str, Any] = {
        "search": query,
        "per_page": min(limit, 100),
        "page": max(page, 1),
        "select": ",".join(OPENALEX_SELECT_FIELDS),
    }
    filters: list[str] = []
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filters.append(f"to_publication_date:{year_to}-12-31")
    if filters:
        params["filter"] = ",".join(filters)
    if mailto:
        params["mailto"] = mailto
    return "https://api.openalex.org/works?" + urllib.parse.urlencode(params)


def arxiv_url(query: str, limit: int, offset: int) -> str:
    search_query = query if ":" in query else f"all:{query}"
    params = {
        "search_query": search_query,
        "start": max(offset, 0),
        "max_results": min(limit, 2000),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    return "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)


def fetch_search_results(
    *,
    provider: str,
    query: str,
    limit: int,
    offset: int = 0,
    page: int = 1,
    year_from: int | None = None,
    year_to: int | None = None,
    mailto: str | None = None,
    timeout: int = 20,
    api_key_env: str | None = "SEMANTIC_SCHOLAR_API_KEY",
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    provider = provider.lower().replace("-", "_")
    if provider == "semantic_scholar":
        url = semantic_scholar_url(query, limit, offset, year_from, year_to)
        headers = {"Accept": "application/json"}
        if api_key_env:
            api_key = os.environ.get(api_key_env)
            if api_key:
                headers["x-api-key"] = api_key
        rows = normalize_semantic_scholar(request_json(url, headers=headers, timeout=timeout, opener=opener))
    elif provider == "crossref":
        url = crossref_url(query, limit, offset, mailto)
        rows = normalize_crossref(request_json(url, headers={"Accept": "application/json"}, timeout=timeout, opener=opener))
    elif provider == "openalex":
        url = openalex_url(query, limit, page, mailto, year_from, year_to)
        rows = normalize_openalex(request_json(url, headers={"Accept": "application/json"}, timeout=timeout, opener=opener))
    elif provider == "arxiv":
        url = arxiv_url(query, limit, offset)
        rows = normalize_arxiv(request_bytes(url, timeout=timeout, opener=opener))
    else:
        raise ValueError(f"unsupported provider: {provider}")

    parameters: dict[str, Any] = {
        "limit": limit,
        "offset": offset,
    }
    if provider == "openalex":
        parameters["page"] = page
    if year_from is not None:
        parameters["year_from"] = year_from
    if year_to is not None:
        parameters["year_to"] = year_to
    if mailto:
        parameters["mailto_supplied"] = True
    if provider == "semantic_scholar" and api_key_env and os.environ.get(api_key_env):
        parameters["api_key_env_supplied"] = api_key_env

    return {
        "provider": provider,
        "query": query,
        "searched_at": now_iso(),
        "status": "succeeded",
        "parameters": parameters,
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch scholarly search results and write an import_search_results-compatible YAML file."
    )
    parser.add_argument("provider", choices=["semantic_scholar", "crossref", "openalex", "arxiv"])
    parser.add_argument("query")
    parser.add_argument("--out", required=True, help="Output search-results YAML path.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0, help="Offset/start for providers that support it.")
    parser.add_argument("--page", type=int, default=1, help="OpenAlex page number.")
    parser.add_argument("--year-from", type=int)
    parser.add_argument("--year-to", type=int)
    parser.add_argument("--mailto", help="Optional polite-pool contact for Crossref/OpenAlex; not written to output.")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument(
        "--api-key-env",
        default="SEMANTIC_SCHOLAR_API_KEY",
        help="Environment variable containing a Semantic Scholar API key; the key itself is never written.",
    )
    args = parser.parse_args()

    result = fetch_search_results(
        provider=args.provider,
        query=args.query,
        limit=args.limit,
        offset=args.offset,
        page=args.page,
        year_from=args.year_from,
        year_to=args.year_to,
        mailto=args.mailto,
        timeout=args.timeout,
        api_key_env=args.api_key_env,
    )
    out_path = Path(args.out).resolve()
    write_yaml(out_path, result)
    print(f"provider: {result['provider']}")
    print(f"query: {result['query']}")
    print(f"results: {len(result['results'])}")
    print(f"search results file: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
