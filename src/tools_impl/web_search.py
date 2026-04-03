"""
WebSearchTool — Search the web and return cited results.

Ported from rust/crates/tools/src/lib.rs execute_web_search().
Uses DuckDuckGo HTML search (no API key needed) with fallback to Google.
"""
from __future__ import annotations

import asyncio
import re
import urllib.parse
from html import unescape
from typing import Any

import httpx

from .base import Tool, ToolContext, ToolResult

# User-Agent to get proper HTML results
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _extract_ddg_hits(html: str) -> list[dict[str, str]]:
    """Extract search results from DuckDuckGo HTML."""
    hits = []
    # DuckDuckGo results pattern
    for match in re.finditer(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    ):
        url = match.group(1)
        title = re.sub(r"<[^>]+>", "", match.group(2)).strip()

        # DuckDuckGo wraps URLs in a redirect
        if "uddg=" in url:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            url = parsed.get("uddg", [url])[0]

        if url.startswith("http") and title:
            hits.append({"url": url, "title": unescape(title)})

    return hits


def _extract_google_hits(html: str) -> list[dict[str, str]]:
    """Extract search results from Google HTML."""
    hits = []
    for match in re.finditer(
        r'<a[^>]+href="(https?://[^"]+)"[^>]*><h3[^>]*>(.*?)</h3>',
        html,
        re.DOTALL,
    ):
        url = match.group(1)
        title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        if not any(d in url for d in ["google.com", "googleapis.com"]):
            hits.append({"url": url, "title": unescape(title)})
    return hits


def _extract_snippets(html: str, hits: list[dict[str, str]]) -> list[dict[str, str]]:
    """Try to extract snippets near the result links."""
    # DuckDuckGo snippet pattern
    snippets = re.findall(
        r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )
    for i, snippet in enumerate(snippets):
        if i < len(hits):
            hits[i]["snippet"] = re.sub(r"<[^>]+>", "", unescape(snippet)).strip()

    return hits


def _dedupe(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    """Remove duplicate URLs."""
    seen = set()
    result = []
    for hit in hits:
        url = hit["url"].rstrip("/")
        if url not in seen:
            seen.add(url)
            result.append(hit)
    return result


async def _search(query: str, allowed_domains: list[str] | None = None,
                  blocked_domains: list[str] | None = None) -> list[dict[str, str]]:
    """Perform web search, trying DuckDuckGo then Google."""
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=15.0,
    ) as client:
        hits = []

        # Try DuckDuckGo first
        try:
            ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
            resp = await client.get(ddg_url)
            if resp.status_code == 200:
                hits = _extract_ddg_hits(resp.text)
                hits = _extract_snippets(resp.text, hits)
        except Exception:
            pass

        # Fallback to Google if DDG fails
        if not hits:
            try:
                google_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}&num=10"
                resp = await client.get(google_url)
                if resp.status_code == 200:
                    hits = _extract_google_hits(resp.text)
            except Exception:
                pass

        # Domain filtering
        if allowed_domains:
            allowed = [d.lower() for d in allowed_domains]
            hits = [h for h in hits if any(d in h["url"].lower() for d in allowed)]
        if blocked_domains:
            blocked = [d.lower() for d in blocked_domains]
            hits = [h for h in hits if not any(d in h["url"].lower() for d in blocked)]

        hits = _dedupe(hits)
        return hits[:8]


class WebSearchTool(Tool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for current information and return cited results. "
            "Use this to find documentation, look up error messages, or research topics."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                    "minLength": 2,
                },
                "allowed_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Only include results from these domains",
                },
                "blocked_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Exclude results from these domains",
                },
            },
            "required": ["query"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        query = args.get("query", "")
        if not query or len(query) < 2:
            return ToolResult(success=False, output="", error="query must be at least 2 characters")

        try:
            hits = await _search(
                query,
                allowed_domains=args.get("allowed_domains"),
                blocked_domains=args.get("blocked_domains"),
            )

            if not hits:
                return ToolResult(
                    success=True,
                    output=f'No web search results matched the query "{query}".',
                )

            lines = [f'Search results for "{query}". Include a Sources section in the final answer.\n']
            for hit in hits:
                lines.append(f"- [{hit['title']}]({hit['url']})")
                if hit.get("snippet"):
                    lines.append(f"  {hit['snippet']}")

            return ToolResult(success=True, output="\n".join(lines))

        except Exception as e:
            return ToolResult(success=False, output="", error=f"Search failed: {e}")
