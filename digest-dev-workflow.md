# Weekly Digest — Dev & Debug Workflow

## How the digest runs

Two GitHub Actions jobs fire every Monday at 8am UTC (or manually via workflow_dispatch):

- **AI Ecosystem Digest** — covers claude code, MCP servers, AI developer tools
- **AI Marketing Digest** — covers AI marketing tools, video, growth automation

Each job:
1. Fetches the subscriber list from a private GitHub repo
2. Runs `scripts/last30days.py` with a hardcoded plan JSON (sources: Reddit, X, HN)
3. Pipes the compact research output through `digest/email_digest.py`
4. Claude Haiku synthesizes the output into a narrative
5. Resend delivers the email to subscribers

Workflow file: `.github/workflows/weekly-digest.yml`
Runs on: `louloret/last30days-skill` (fork), branch `custom`

---

## Sources and how they search

| Source | Search approach | Key constraint |
|--------|----------------|----------------|
| Reddit | Semantic full-text, multiple subreddits | Highest recall, uses ScrapeCreators API |
| X (Bird) | Claude-generated OR phrases: `("claude code" OR "ai agent")` | `min_faves:3 -filter:replies`, requires AUTH_TOKEN + CT0 |
| HackerNews | Claude-generated Algolia query (1-3 words) | Always available, free Algolia API |

Claude Haiku generates the search queries for X and HN at runtime via `scripts/lib/smart_query.py`. Falls back to `extract_core_subject` if ANTHROPIC_API_KEY is missing.

---

## Checking logs

```bash
# List recent runs
gh run list --repo louloret/last30days-skill --limit=5

# View key log lines from a run
gh run view <RUN_ID> --repo louloret/last30days-skill --log | grep -E "\[HN\]|\[Bird\]|Research complete"
```

Key lines to watch:
- `[Bird] Searching: ...` — shows the X query Claude generated
- `[HN] Searching for '...'` — shows the HN query Claude generated
- `[HN] Found N stories` — Algolia hit count before filtering
- `✓ Research complete` — final per-source counts

---

## Triggering a test run

```bash
gh workflow run weekly-digest.yml \
  --repo louloret/last30days-skill \
  --ref custom \
  -f test_mode=true
```

`test_mode=true` sends only to `RESEND_TO` (your email) instead of the full subscriber list.

---

## Making changes

All changes go on the `custom` branch of `louloret/last30days-skill`. The upstream public repo is `mvanhorn/last30days-skill`.

```bash
# Edit → commit → push → retrigger
git add <files>
git commit -m "..."
git push origin custom

gh workflow run weekly-digest.yml --repo louloret/last30days-skill --ref custom -f test_mode=true
```

---

## Email sections

The digest email renders two GitHub repo sections (requires `--terms`):

| Section | Source | Ranking |
|---------|--------|---------|
| 🌟 Trending GitHub Repos | Repos created within `--trending-days` (default 7), sorted by stars | Newest repos gaining the most stars |
| 🔥 Top GitHub Repos | All-time top repos by topic, top 10 | `log10(stars) × 3 + recency` blend |

Pass `--trending-days` to `email_digest.py` to match the digest window (e.g. `--trending-days 14` for the marketing digest).

---

## Key files

| File | Purpose |
|------|---------|
| `.github/workflows/weekly-digest.yml` | Job definitions, plan JSON, subscriber fetch |
| `scripts/lib/smart_query.py` | Claude-generated X and HN queries |
| `scripts/lib/bird_x.py` | X search via vendored bird-search.mjs |
| `scripts/lib/hackernews.py` | HN search via Algolia |
| `scripts/lib/planner.py` | Source priority, weights, quick-mode limits |
| `digest/email_digest.py` | Claude synthesis + Resend delivery |

---

## Source weights (product intent)

| Source | Effective weight | Notes |
|--------|-----------------|-------|
| Reddit | 2.5 | Most trusted, deliberate discussion |
| YouTube | 1.8 | Rarely returns results without yt-dlp |
| HackerNews | 1.0 | Baseline, good technical signal |
| X | 0.7 | Reduced — tends toward hype |

Quick-mode priority order: `reddit → hackernews → x` (limit 3)

---

## Secrets required

| Secret | Used by |
|--------|---------|
| `RESEND_API_KEY` | Email delivery |
| `RESEND_TO` | Test-mode recipient |
| `ANTHROPIC_API_KEY` | Smart query generation + email synthesis |
| `AUTH_TOKEN` + `CT0` | X/Bird search (Twitter session cookies) |
| `SCRAPECREATORS_API_KEY` | Reddit (ScrapeCreators backup) |
| `GH_SUBSCRIBERS_TOKEN` | Fetching subscriber list from private repo |
