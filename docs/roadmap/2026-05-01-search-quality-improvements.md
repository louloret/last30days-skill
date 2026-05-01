# Search Quality Improvements — 2026-05-01

## Summary

Session focused on diagnosing and fixing why X and HackerNews weren't producing results in the weekly digest GitHub Actions workflow, then improving search quality across both sources.

---

## Bugs Fixed

### HackerNews — 3 layered bugs

1. **Algolia AND-matching too many words** — `extract_core_subject` was called without `max_words=3`, so "mcp server model context protocol" returned 0 Algolia hits. Fixed: cap to 3 words.

2. **`_title_matches_query` AND semantics** — required ALL query words in the title. "claude code ai agent" → 0 of 13 hits passed. Fixed: OR semantics (any word matches).

3. **HN excluded from quick product runs** — `QUICK_SOURCE_PRIORITY["product"]` listed HN at position 5 with a limit of 3. YouTube, Reddit, X filled the top 3, HN never reached. Fixed: reordered to `[reddit, hackernews, x, youtube, tiktok]` so CI consistently selects reddit + hackernews + x.

### X / Bird — silent errors

- Bird outputs error JSON to stdout on failure, not stderr. Code only read stderr → errors were completely invisible. Fixed: parse stdout for JSON error.

### HN logs invisible in CI

- `_log` in hackernews.py used `tty_only=True` (default). GH Actions stderr is not a TTY so all HN logs were suppressed. Bird, Reddit, YouTube all used `tty_only=False`. Fixed to match.

### Email digest — footer dropped by token limit

- Claude Haiku was instructed to copy the `✅ All agents reported back!` footer verbatim. With `max_tokens=1024`, longer synthesis bodies (ecosystem digest) exhausted the budget before reaching the footer. Marketing digest fit; ecosystem didn't.
- Fixed two ways: bump `max_tokens` 1024→3000, and deterministically extract + reattach the footer from the original `render_compact` output if Claude dropped it.

---

## Quality Improvements

### X / Bird — engagement filtering

- Added `min_faves:{N} -filter:replies` to every Bird search query at the API level. Drops low-engagement tweets and replies before they return. Thresholds: quick=3, default=5, deep=10.
- Added engagement-aware relevance scoring in `parse_bird_response`: blends keyword match (50%) + position rank (30%) + log-scaled engagement boost from likes (up to +0.2). Previously was pure keyword overlap.

### Source weights — product intent

- Boosted Reddit: +1.5 bonus (was +1.2) → effective weight 2.5
- Reduced X: −0.3 penalty (was 0) → effective weight 0.7
- HN left at baseline (1.0)
- Rationale: Reddit has deliberate discussion, X tends toward hype.

### Claude-powered query generation (`smart_query.py`)

- New module that calls Claude Haiku to generate platform-optimal search queries given a topic and date range.
- **For X**: generates OR-grouped quoted phrases — `("claude code" OR "claude agent" OR "claude AI")` instead of literal AND matching all words.
- **For HN**: generates concise 1-3 word Algolia queries, preferring abbreviations — `claude code agent` instead of `claude code ai agent`.
- In-process cache by topic+date avoids duplicate API calls per run.
- Graceful fallback to `extract_core_subject` if ANTHROPIC_API_KEY missing or call fails.
- Sanitizes Claude's output to strip any filter operators (since:, until:, min_faves:) that Claude adds despite prompt instructions.

---

## Commits (chronological)

| Commit | Description |
|--------|-------------|
| `3de96a2` | fix(hackernews): OR semantics in title filter + Algolia max_words=3 |
| `6b6570b` | fix(planner): add hackernews to product quick priority, bump limit 2→3 |
| `83b73f5` | fix(planner): prioritize hackernews over youtube for product quick mode |
| `ab37c8f` | feat(bird_x): min_faves filter + engagement-weighted relevance scoring |
| `f1fb8e3` | fix(email_digest): deterministically reattach footer dropped by token limit |
| `898a8f2` | fix(hackernews): enable CI logging (tty_only=False) |
| `8807c14` | tune(planner): keep hackernews at baseline weight for product intent |
| `e634169` | tune(planner): boost reddit/HN, reduce x weight for product intent |
| `9e10148` | feat(bird_x): OR-grouped phrases upfront (superseded by smart_query) |
| `abf8ac5` | feat(smart_query): Claude-generated queries for X and HackerNews |
| `02f7036` | fix(smart_query): strip date/filter operators from Claude output |
| `bdddd93` | tune(email_digest): bump synthesis max_tokens to 3000 |

---

## Known tradeoff — X engagement scoring (not yet addressed)

OR queries cast a wider net, bringing in more keyword-matching tweets that happen to be low-engagement. The old AND query was accidentally restrictive in a way that favored established, talked-about content.

The engagement boost is also too weak. The formula `min(0.2, math.log1p(likes) / 50)` only gives a max +0.2 boost, while content match is weighted at 0.5. A tweet with 3 likes and good keyword match beats a 500-like tweet with moderate keyword match:

- 3 likes, great keyword match: `0.5*1.0 + 0.3*1.0 + 0.03 = 0.83`
- 500 likes, decent match: `0.5*0.6 + 0.3*0.9 + 0.12 = 0.69`

The content score dominates, so likes barely move the needle. Two potential fixes (deferred — current output looks clean enough):

- Bump `min_faves` quick: 3 → 10 (filter more aggressively at the API level)
- Strengthen engagement formula: `min(0.3, math.log1p(likes) / 25)` and shift blend weights to give engagement more influence

---

## Result

Both weekly digest jobs (ecosystem + marketing) now consistently produce:
- Reddit: 6 threads
- X: 6 posts (OR-grouped smart queries, min_faves filtered)
- HN: 1-6 stories (Claude-optimized Algolia queries)
- `✅ All agents reported back!` footer present in both emails
