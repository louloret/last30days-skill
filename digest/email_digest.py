#!/usr/bin/env python3
"""Send digest via Gmail SMTP as HTML. Usage: script | python3 email_digest.py --terms term1 term2"""

import argparse
import json
import math
import os
import re
import smtplib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ENV_FILE = Path.home() / ".config" / "last30days" / ".env"

def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    for key in ("GMAIL_APP_PASSWORD", "RESEND_TO", "ANTHROPIC_API_KEY"):
        if key not in env and key in os.environ:
            env[key] = os.environ[key]
    return env

def load_subscribers(path):
    lines = Path(path).read_text().splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]

# ── Claude synthesis ─────────────────────────────────────────────────────────

_SYNTHESIS_PROMPT = (
    "You are synthesizing research engine output into a digest narrative. Follow these rules exactly.\n\n"
    "Output format:\n"
    "1. Start with `What I learned:` on its own line — nothing above it, no title\n"
    "2. Write bold-lead-in paragraphs: each opens with **Bold theme** followed by supporting detail "
    "with specific citations (subreddit names, upvote counts, comment counts, thread titles)\n"
    "3. When Reddit AND Hacker News independently cover the same story, call it out as stronger signal\n"
    "4. Write the prose label `KEY PATTERNS from the research:` followed by a numbered list\n"
    "5. Copy the engine emoji-tree footer block (between `---` lines, starting with "
    "`✅ All agents reported back!`) verbatim at the end\n\n"
    "Non-negotiable rules:\n"
    "- No em-dashes or en-dashes; use ` - ` (hyphen with spaces) instead\n"
    "- No ## or ### section headers in the body\n"
    "- No Sources block, References block, or trailing URL lists at the end\n"
    "- Cite specific data from the engine output: upvote counts, comment counts, subreddit names, thread titles\n\n"
    "Engine output to synthesize:\n"
)


def _extract_footer(body: str) -> str | None:
    """Pull the ✅ footer block out of render_compact output so we can reattach it after synthesis."""
    match = re.search(r'---\n✅ All agents reported back!.*?---', body, re.DOTALL)
    return match.group(0) if match else None


def synthesize(text, api_key):
    if not api_key:
        return None
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 3000,
        "messages": [{"role": "user", "content": _SYNTHESIS_PROMPT + text}],
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
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    except Exception as e:
        print(f"Synthesis skipped: {e}", file=sys.stderr)
        return None


# ── GitHub repo fetching ────────────────────────────────────────────────────

def gh_fetch(query, sort):
    q = query.replace(" ", "+")
    url = f"https://api.github.com/search/repositories?q={q}&sort={sort}&per_page=20"
    req = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-digest/1.0",
    })
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("items", [])
    except Exception:
        return []

def recency(pushed_at):
    days = (datetime.now(timezone.utc) -
            datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))).days
    return 5 if days <= 7 else 4 if days <= 30 else 3 if days <= 90 else 2 if days <= 365 else 1

def fmt_age(pushed_at):
    days = (datetime.now(timezone.utc) -
            datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))).days
    if days == 0: return "today"
    if days == 1: return "1 day ago"
    if days < 7: return f"{days} days ago"
    if days < 14: return "1 week ago"
    if days < 30: return f"{days // 7} weeks ago"
    if days < 60: return "1 month ago"
    return f"{days // 30} months ago"

def fetch_top_repos(terms, top_n=10):
    queries = [(t, s) for t in terms for s in ("stars", "updated")]
    all_items = {}
    with ThreadPoolExecutor(max_workers=max(len(queries), 1)) as pool:
        futures = {pool.submit(gh_fetch, t, s): (t, s) for t, s in queries}
        for f in as_completed(futures):
            for item in f.result():
                fn = item["full_name"]
                if fn not in all_items:
                    all_items[fn] = item
    return sorted(all_items.values(),
                  key=lambda r: math.log10(r["stargazers_count"] + 1) * 3 + recency(r["pushed_at"]),
                  reverse=True)[:top_n]

def fetch_trending_repos(terms, days=7, top_n=5):
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    all_items = {}
    for term in terms:
        q = f"{term}+created:>{cutoff}"
        for item in gh_fetch(q, "stars"):
            fn = item["full_name"]
            if fn not in all_items:
                all_items[fn] = item
    return sorted(all_items.values(),
                  key=lambda r: r["stargazers_count"],
                  reverse=True)[:top_n]

# ── HTML conversion ─────────────────────────────────────────────────────────

def _inline(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(.+?)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r'(?<!["\(=])(https?://\S+)', r'<a href="\1">\1</a>', text)
    return text

def txt_to_html(text):
    lines, out, in_list = text.splitlines(), [], False
    for line in lines:
        if any(x in line for x in ["END OF last30days CANONICAL OUTPUT", "Pass through the lines", "LAW 1 overrides"]):
            break
        if line.strip() == "---":
            if in_list: out.append("</ul>"); in_list = False
            out.append("<hr>"); continue
        if line.startswith("### "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h3>{_inline(line[4:])}</h3>"); continue
        if line.startswith("## "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h2>{_inline(line[3:])}</h2>"); continue
        if line.startswith("# "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h1 style='font-size:1.2em;color:#444;'>{_inline(line[2:])}</h1>"); continue
        if line.startswith("> "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<blockquote style='border-left:3px solid #e1e4e8;margin:4px 0;padding:4px 12px;color:#586069;'>{_inline(line[2:])}</blockquote>"); continue
        if re.match(r"^[-*] ", line) or re.match(r"^\d+\. ", line):
            if not in_list: out.append("<ul>"); in_list = True
            content = re.sub(r"^[-*] |^\d+\. ", "", line)
            out.append(f"<li>{_inline(content)}</li>"); continue
        if not line.strip():
            if in_list: out.append("</ul>"); in_list = False
            out.append("<br>"); continue
        if in_list: out.append("</ul>"); in_list = False
        out.append(f"<p>{_inline(line)}</p>")
    if in_list: out.append("</ul>")
    return "\n".join(out)

def repos_to_md(repos, title):
    if not repos:
        return ""
    lines = [f"\n## {title}\n", "| # | Repo | Stars | Last Push |", "|---|------|-------|-----------|"]
    for i, r in enumerate(repos, 1):
        desc = (r.get("description") or "")[:80]
        lines.append(f"| {i} | [{r['full_name']}]({r['html_url']}) [{desc}] | ★ {r['stargazers_count']:,} | {fmt_age(r['pushed_at'])} |")
    return "\n".join(lines) + "\n"

def repos_to_html(repos, title="🔥 Top GitHub Repos"):
    if not repos:
        return ""
    rows = ""
    for i, r in enumerate(repos, 1):
        desc = (r.get("description") or "")[:100]
        rows += (
            f"<tr style='border-bottom:1px solid #f0f0f0;'>"
            f"<td style='padding:8px 6px;color:#999;width:24px;'>{i}</td>"
            f"<td style='padding:8px 6px;'>"
            f"<a href='{r['html_url']}' style='color:#0366d6;font-weight:bold;text-decoration:none;'>{r['full_name']}</a>"
            f"<br><span style='color:#586069;font-size:12px;'>{desc}</span></td>"
            f"<td style='padding:8px 6px;white-space:nowrap;color:#586069;'>★ {r['stargazers_count']:,}</td>"
            f"<td style='padding:8px 6px;white-space:nowrap;color:#999;font-size:12px;'>{fmt_age(r['pushed_at'])}</td>"
            f"</tr>"
        )
    return (
        f"<h2>{title}</h2>"
        "<table style='border-collapse:collapse;width:100%;font-size:14px;font-family:-apple-system,sans-serif;'>"
        f"{rows}"
        "</table>"
    )

def build_html(subject, body_text, trending_repos, top_repos, trending_days=7):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:680px;margin:0 auto;padding:24px;color:#24292e;line-height:1.6;">
<h1 style="border-bottom:2px solid #e1e4e8;padding-bottom:12px;font-size:1.4em;">{subject}</h1>
{txt_to_html(body_text)}
{repos_to_html(trending_repos, title=f"🌟 Trending GitHub Repos (last {trending_days} days)")}
{repos_to_html(top_repos)}
<hr>
<p style="color:#999;font-size:11px;">AI Digest · <a href="https://github.com/louloret/last30days-skill" style="color:#999;">last30days</a></p>
</body></html>"""

# ── Send ─────────────────────────────────────────────────────────────────────

GMAIL_USER = "luisgrowthhack@gmail.com"

def send(gmail_password, to, subject, text_body, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"AI Digest <{GMAIL_USER}>"
    msg["To"] = to
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_USER, gmail_password)
            server.sendmail(GMAIL_USER, to, msg.as_string())
    except Exception as e:
        print(f"Gmail error: {e}", file=sys.stderr)
        sys.exit(1)
    return {"id": "ok"}

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", nargs="*", default=[], help="GitHub search terms for repo section")
    parser.add_argument("--trending-days", type=int, default=7, help="Window for trending repos (default: 7)")
    parser.add_argument("--subscribers-file", help="Path to subscribers list (one email per line)")
    parser.add_argument("--save-md", help="Write the emailed markdown body to this file path")
    args = parser.parse_args()

    env = load_env()
    api_key = env.get("GMAIL_APP_PASSWORD")
    if not api_key:
        print("ERROR: GMAIL_APP_PASSWORD must be set", file=sys.stderr)
        sys.exit(1)

    if args.subscribers_file:
        recipients = load_subscribers(args.subscribers_file)
        if not recipients:
            print("ERROR: subscribers file is empty", file=sys.stderr)
            sys.exit(1)
    else:
        to = env.get("RESEND_TO")
        if not to:
            print("ERROR: RESEND_TO must be set or --subscribers-file provided", file=sys.stderr)
            sys.exit(1)
        recipients = [to]

    body = sys.stdin.read()
    if not body.strip():
        print("ERROR: empty digest body.", file=sys.stderr); sys.exit(1)

    first_line = body.splitlines()[0].strip().strip("=").strip()
    subject = first_line if first_line else f"AI Digest · {datetime.now().strftime('%Y-%m-%d')}"

    anthropic_key = env.get("ANTHROPIC_API_KEY")
    footer = _extract_footer(body)
    synthesized = synthesize(body, anthropic_key)
    if synthesized:
        print("Synthesis: ok", file=sys.stderr)
        if footer and "✅ All agents reported back!" not in synthesized:
            synthesized = synthesized.rstrip() + "\n\n" + footer + "\n"
    display_body = synthesized if synthesized else body

    trending = fetch_trending_repos(args.terms, days=args.trending_days) if args.terms else []
    top_repos = fetch_top_repos(args.terms) if args.terms else []
    html  = build_html(subject, display_body, trending, top_repos, trending_days=args.trending_days)
    for recipient in recipients:
        result = send(api_key, recipient, subject, display_body, html)
        print(f"Sent: {result.get('id', 'ok')} → {recipient}")

    if args.save_md:
        md = display_body
        if trending:
            md += repos_to_md(trending, f"🌟 Trending GitHub Repos (last {args.trending_days} days)")
        if top_repos:
            md += repos_to_md(top_repos, "🔥 Top GitHub Repos")
        Path(args.save_md).write_text(md, encoding="utf-8")
        print(f"Saved: {args.save_md}", file=sys.stderr)

if __name__ == "__main__":
    main()
