from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_search_results as fetcher  # noqa: E402


class FakeResponse:
    def __init__(self, data: bytes, status: int = 200) -> None:
        self.data = data
        self.status = status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.data


class FakeOpener:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.requests: list[Any] = []

    def __call__(self, request: Any, timeout: int) -> FakeResponse:
        self.requests.append(request)
        if isinstance(self.payload, bytes):
            return FakeResponse(self.payload)
        return FakeResponse(json.dumps(self.payload).encode("utf-8"))


class FetchSearchResultsTests(unittest.TestCase):
    def test_semantic_scholar_fetch_normalizes_paper_metadata(self) -> None:
        opener = FakeOpener(
            {
                "data": [
                    {
                        "paperId": "S2-001",
                        "title": "Attention Is All You Need",
                        "authors": [{"name": "Ashish Vaswani"}, {"name": "Noam Shazeer"}],
                        "year": 2017,
                        "venue": "NeurIPS",
                        "abstract": "A transformer architecture based on attention.",
                        "url": "https://www.semanticscholar.org/paper/S2-001",
                        "externalIds": {"DOI": "10.5555/3295222.3295349", "ArXiv": "1706.03762"},
                        "citationCount": 10000,
                    }
                ]
            }
        )

        result = fetcher.fetch_search_results(
            provider="semantic_scholar",
            query="attention transformer",
            limit=1,
            opener=opener,
            api_key_env=None,
        )

        self.assertEqual(result["provider"], "semantic_scholar")
        self.assertEqual(result["parameters"]["limit"], 1)
        self.assertEqual(result["results"][0]["provider_work_id"], "S2-001")
        self.assertEqual(result["results"][0]["title"], "Attention Is All You Need")
        self.assertEqual(result["results"][0]["authors"], "Ashish Vaswani; Noam Shazeer")
        self.assertEqual(result["results"][0]["doi"], "10.5555/3295222.3295349")
        self.assertEqual(result["results"][0]["arxiv_id"], "1706.03762")
        self.assertEqual(result["results"][0]["citation_count"], 10000)
        self.assertIn("graph/v1/paper/search", opener.requests[0].full_url)

    def test_openalex_inverted_index_abstract_is_rebuilt(self) -> None:
        data = {
            "results": [
                {
                    "id": "https://openalex.org/W123",
                    "doi": "https://doi.org/10.1000/example",
                    "display_name": "A Study of Memes",
                    "publication_year": 2024,
                    "relevance_score": 42.5,
                    "abstract_inverted_index": {"internet": [0], "memes": [1], "spread": [2]},
                    "authorships": [
                        {"author": {"display_name": "Limor Shifman"}},
                        {"author": {"display_name": "Ryan Milner"}},
                    ],
                    "primary_location": {"source": {"display_name": "Journal of Internet Culture"}},
                }
            ]
        }

        rows = fetcher.normalize_openalex(data)

        self.assertEqual(rows[0]["provider_work_id"], "https://openalex.org/W123")
        self.assertEqual(rows[0]["doi"], "10.1000/example")
        self.assertEqual(rows[0]["title"], "A Study of Memes")
        self.assertEqual(rows[0]["authors"], "Limor Shifman; Ryan Milner")
        self.assertEqual(rows[0]["venue"], "Journal of Internet Culture")
        self.assertEqual(rows[0]["abstract"], "internet memes spread")
        self.assertEqual(rows[0]["score"], 42.5)

    def test_arxiv_atom_feed_is_normalized(self) -> None:
        feed = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <title>Attention Is All You Need</title>
    <summary>Transformer sequence transduction models.</summary>
    <published>2017-06-12T17:57:34Z</published>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <link href="http://arxiv.org/abs/1706.03762v7" rel="alternate" type="text/html"/>
  </entry>
</feed>
"""

        rows = fetcher.normalize_arxiv(feed)

        self.assertEqual(rows[0]["provider_work_id"], "1706.03762")
        self.assertEqual(rows[0]["arxiv_id"], "1706.03762")
        self.assertEqual(rows[0]["title"], "Attention Is All You Need")
        self.assertEqual(rows[0]["authors"], "Ashish Vaswani; Noam Shazeer")
        self.assertEqual(rows[0]["year"], 2017)
        self.assertEqual(rows[0]["venue"], "arXiv")
        self.assertEqual(rows[0]["uri"], "http://arxiv.org/abs/1706.03762v7")


if __name__ == "__main__":
    unittest.main()
