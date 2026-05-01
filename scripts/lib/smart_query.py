"""Claude-powered search query generation for platform-specific searches.

Uses claude-haiku to generate optimal queries for X and HackerNews given a
topic and date range. Falls back to caller-supplied default if ANTHROPIC_API_KEY
is not set or the API call fails. Results are cached in-process by topic+date.
"""

import json
import os
import re
from typing import Optional
from urllib.request import Request, urlopen

from . import log

# Strip any filter operators Claude adds despite prompt instructions
_OPERATOR_RE = re.compile(r'\b(since|until|min_faves|min_retweets|lang|filter|-filter):\S*', re.IGNORECASE)

_cache: dict[str, str] = {}

_X_PROMPT = """\
Generate a Twitter/X search query for the topic and date range below.
Output ONLY the raw query string — no explanation, no surrounding quotes.

Rules:
- Use OR-grouped quoted phrases: ("phrase one" OR "phrase two" OR "phrase three")
- Max 3 phrases, 1-3 words each
- Choose phrases people would actually tweet, not formal descriptions
- Known abbreviations (mcp, llm, gpt, rag, ai) count as 1-word phrases
- Do NOT include since:, min_faves:, lang:, or any other filters

Topic: {topic}
Date range: {from_date} to {to_date}"""

_HN_PROMPT = """\
Generate a Hacker News search query for the topic and date range below.
Output ONLY the raw query string — no explanation, no surrounding quotes.

Rules:
- Algolia uses AND matching, so fewer words = more results; max 3 words
- Use terms HN users write in post titles (technical, specific, lowercase)
- Prefer short abbreviations: mcp not "model context protocol", llm not "large language model"
- Do NOT include date filters or any operators

Topic: {topic}
Date range: {from_date} to {to_date}"""


def _call_claude(prompt: str) -> Optional[str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 80,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            raw = data["content"][0]["text"].strip()
            return _OPERATOR_RE.sub("", raw).strip() or None
    except Exception as e:
        log.debug(f"smart_query API call failed: {e}")
        return None


def build_x_query(topic: str, from_date: str, to_date: str) -> Optional[str]:
    """Return a Claude-generated X search expression, or None on failure."""
    key = f"x:{topic}:{from_date}"
    if key not in _cache:
        result = _call_claude(_X_PROMPT.format(topic=topic, from_date=from_date, to_date=to_date))
        if result:
            _cache[key] = result
    return _cache.get(key)


def build_hn_query(topic: str, from_date: str, to_date: str) -> Optional[str]:
    """Return a Claude-generated HN/Algolia query string, or None on failure."""
    key = f"hn:{topic}:{from_date}"
    if key not in _cache:
        result = _call_claude(_HN_PROMPT.format(topic=topic, from_date=from_date, to_date=to_date))
        if result:
            _cache[key] = result
    return _cache.get(key)
