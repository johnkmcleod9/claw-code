"""
WebFetchTool — Fetch a URL, convert to readable text, and optionally answer a prompt.

Ported from rust/crates/tools/src/lib.rs execute_web_fetch().
Uses httpx for fetching + basic HTML-to-text extraction.
"""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlparse

import httpx

from .base import Tool, ToolContext, ToolResult

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

MAX_CONTENT_LENGTH = 100_000  # ~100KB of text


def _html_to_text(html: str) -> str:
    """Convert HTML to readable plain text. Simple but effective."""
    # Remove script and style blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert common block elements to newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|h[1-6]|li|tr|blockquote|pre)>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<(p|div|h[1-6]|li|tr|blockquote|pre)[^>]*>", "", text, flags=re.IGNORECASE)

    # Convert headers with markdown-style markers
    for level in range(1, 7):
        prefix = "#" * level
        text = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            rf"\n\n{prefix} \1\n\n",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Extract link text with URL
    text = re.sub(
        r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        r"[\2](\1)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Convert lists
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)

    # Code blocks
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<pre[^>]*>(.*?)</pre>", r"\n```\n\1\n```\n", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    text = unescape(text)

    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))

    return text.strip()


def _extract_title(html: str) -> str:
    """Extract page title from HTML."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if match:
        return unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
    return ""


class WebFetchTool(Tool):
    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch a URL and convert it to readable text. "
            "Use this to read documentation, blog posts, API references, or any web page. "
            "Optionally provide a prompt to focus on specific information."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "format": "uri",
                    "description": "URL to fetch",
                },
                "prompt": {
                    "type": "string",
                    "description": "Optional: what to look for in the page content",
                },
            },
            "required": ["url"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        url = args.get("url", "")
        prompt = args.get("prompt", "")

        if not url:
            return ToolResult(success=False, output="", error="url is required")

        # Basic URL validation
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ToolResult(success=False, output="", error=f"Invalid URL scheme: {parsed.scheme}")

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
                timeout=30.0,
            ) as client:
                resp = await client.get(url)

                content_type = resp.headers.get("content-type", "")
                final_url = str(resp.url)
                status = resp.status_code

                if status >= 400:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"HTTP {status} fetching {url}",
                    )

                # Handle non-HTML content
                if "text/html" not in content_type and "text/plain" not in content_type:
                    return ToolResult(
                        success=True,
                        output=f"Fetched {url} → {final_url}\nContent-Type: {content_type}\nSize: {len(resp.content)} bytes\n(Non-text content, cannot extract readable text)",
                    )

                html = resp.text
                title = _extract_title(html)
                text = _html_to_text(html)

                # Truncate if too long
                if len(text) > MAX_CONTENT_LENGTH:
                    text = text[:MAX_CONTENT_LENGTH] + f"\n\n... (truncated, {len(text)} total chars)"

                # Build output
                parts = []
                parts.append(f"# {title}" if title else f"# {final_url}")
                parts.append(f"URL: {final_url}")
                if prompt:
                    parts.append(f"Focus: {prompt}")
                parts.append("")
                parts.append(text)

                return ToolResult(
                    success=True,
                    output="\n".join(parts),
                    metadata={"url": final_url, "status": status, "title": title},
                )

        except httpx.TimeoutException:
            return ToolResult(success=False, output="", error=f"Timeout fetching {url}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Fetch failed: {e}")
