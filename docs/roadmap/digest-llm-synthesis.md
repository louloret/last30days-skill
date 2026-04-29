# Plan: Add LLM Synthesis to GitHub Actions Email Digest

## Problem

Right now the GitHub Actions pipeline does `engine output → email` with no synthesis step. The "What I learned" narrative in the CLI sample is Claude reading the engine output and synthesizing themes - that happens in the interactive session, not in the Python engine itself.

## Goal

Make the digest email read like the CLI sample output - themes extracted across all 60+ threads, not just the top 8 cluster titles.

## Plan

1. Add `ANTHROPIC_API_KEY` as a GitHub Actions secret
2. Update `digest/email_digest.py` to optionally call Claude API - pass it the full engine output (all fetched threads, not just top N) and ask it to synthesize key themes in "What I learned" format
3. The email then includes the narrative + the raw thread list below it

## Reference: Sample CLI Output

See `digests/ai-marketing-tools-sample-output.md` for the target output quality.

Key elements to replicate:
- Bold-lead-in theme paragraphs ("Practitioners are exhausted by hype...")
- Cross-source synthesis (Reddit + HN + GitHub in same insight)
- Specific citations (subreddit names, upvote counts, thread titles)
- KEY PATTERNS numbered list
- Engine footer pass-through (source counts)

## Alternative (simpler, no API key needed)

Increase `cluster_limit` in `render_compact` from 8 to 12+ so more raw threads appear in the email. No synthesized insight, but more coverage. Good interim step.

## Notes

- `ANTHROPIC_API_KEY` already exists if user has Claude API access
- The synthesis prompt should mirror the last30days skill voice contract (bold lead-ins, no em-dashes, no section headers, no trailing Sources block)
- Input to Claude: full `--emit=compact` output (titles, snippets, scores, subreddit sources)
- Output: "What I learned" + KEY PATTERNS narrative, followed by raw cluster list
