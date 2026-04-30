# Plan: Add X/Twitter as a Source in GitHub Actions Digests

## Problem

The weekly digest workflows only pull from Reddit and Hacker News. X/Twitter has strong
real-time signal — especially for developer workflows, indie builders, and AI tool launches —
that doesn't surface on Reddit for days or at all.

## Goal

Add X/Twitter as an active source in both the ecosystem and marketing digest jobs so the
synthesis includes cross-platform corroboration (Reddit + HN + X = stronger signal).

## What's needed

The engine already supports X via the vendored bird-search client. It just needs credentials:

- `AUTH_TOKEN` — your x.com `auth_token` cookie value
- `CT0` — your x.com `ct0` cookie value

Both are available from browser devtools on x.com (Application → Cookies).

## Plan

1. Extract `AUTH_TOKEN` and `CT0` from x.com browser cookies
2. Add both as GitHub Actions secrets (`AUTH_TOKEN`, `CT0`)
3. Add to both job env blocks in `.github/workflows/weekly-digest.yml`:
   ```yaml
   AUTH_TOKEN: ${{ secrets.AUTH_TOKEN }}
   CT0: ${{ secrets.CT0 }}
   ```
4. Update the plan JSON `sources` arrays to include `"x"`:
   ```json
   "sources": ["reddit", "hackernews", "x"]
   ```
5. Test with a manual workflow dispatch run

## Notes

- X cookies rotate periodically — if the digest stops pulling X results, refresh the secrets
- Ecosystem digest benefits more from X than marketing (developer/hacker signal is stronger on X)
- Marketing digest still benefits for AI tool launches and founder sharing workflows
