# Why the CLI Output Is So Good (and How to Replicate It in Email)

## The Two-Stage Pipeline

The quality of the CLI output comes from two distinct stages running back-to-back.

### Stage 1 - Python Engine (`render_compact`)

Outputs structured markdown with:
- Ranked clusters (up to 8) - each has the actual Reddit/HN post title, snippet, score, engagement count, source label
- The LLM reranker already scored every post 0-100 for relevance before this point, so only high-signal content survives
- An emoji footer with exact source counts (22 threads, 847 upvotes, etc.)
- A `# END OF last30days CANONICAL OUTPUT` boundary with explicit pass-through instructions to Claude

### Stage 2 - Claude Synthesis (SKILL.md voice contract)

Claude reads the structured engine output and writes the "What I learned" narrative following strict rules:
- Bold lead-in paragraphs, each one a theme extracted across multiple threads
- Specific citations pulled from the snippets ("52 comments", "109 pts", exact subreddit names)
- Cross-source corroboration - when Reddit AND HN independently cover the same story, Claude flags it as stronger signal
- KEY PATTERNS numbered list
- Engine footer passed through verbatim

## Why the GitHub Actions Email Is Weaker

Stage 2 never runs. The engine output goes straight to `email_digest.py`. The email shows raw cluster titles and snippets instead of the synthesized narrative.

## What Makes the Synthesis So Good

1. **Pre-filtered high-signal input**: The reranker uses an LLM to score every post before Claude sees anything. Claude gets the top 8 posts, not 60 raw ones.
2. **Cross-source corroboration**: When Reddit AND HN independently cover the same story (e.g., $1K video experiment + HN "AI Marketing BS Index"), Claude can call it out as stronger signal than single-source.
3. **Specific citable data**: Each cluster includes upvote counts, comment counts, subreddit names. Claude can say "52 comments" or "109 pts" with confidence.
4. **Strict voice contract**: SKILL.md rules (bold lead-ins, no em-dashes, no section headers, no trailing Sources block) prevent the output from turning into generic AI slop.
5. **cluster_mode: none**: Each post is its own cluster, so Claude sees 8 individual high-scoring posts with specific details rather than blended summaries.

## How to Replicate in Email

Pipe engine output through a Claude API call before sending:

```
engine output → Claude synthesis (voice contract prompt) → email_digest.py
```

The synthesis prompt needs to mirror SKILL.md rules:
- "What I learned:" prose label (no invented title)
- Bold lead-in paragraphs
- Cross-source citations with specifics
- KEY PATTERNS numbered list
- Engine footer passed through verbatim
- No em-dashes, no section headers, no trailing Sources block

See `digest-llm-synthesis.md` for the implementation plan.

## Reference

Sample output demonstrating target quality: `digests/ai-marketing-tools-sample-output.md`
