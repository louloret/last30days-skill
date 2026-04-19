#!/usr/bin/env python3
"""Send digest via Resend as HTML. Usage: script | python3 email_digest.py --terms term1 term2"""

import argparse
import json
import math
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
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
    return env

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

def repos_to_html(repos):
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
        "<h2>🔥 Top GitHub Repos</h2>"
        "<table style='border-collapse:collapse;width:100%;font-size:14px;font-family:-apple-system,sans-serif;'>"
        f"{rows}"
        "</table>"
    )

def build_html(subject, body_text, repos):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:680px;margin:0 auto;padding:24px;color:#24292e;line-height:1.6;">
<h1 style="border-bottom:2px solid #e1e4e8;padding-bottom:12px;font-size:1.4em;">{subject}</h1>
{txt_to_html(body_text)}
{repos_to_html(repos)}
<hr>
<p style="color:#999;font-size:11px;">AI Digest · <a href="https://github.com/louloret/last30days-skill" style="color:#999;">last30days</a></p>
</body></html>"""

# ── Send ─────────────────────────────────────────────────────────────────────

def send(api_key, to, subject, text_body, html_body):
    payload = json.dumps({
        "from": "AI Digest <onboarding@resend.dev>",
        "to": [to],
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }).encode()
    req = Request("https://api.resend.com/emails", data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "python-urllib/3.13",
    }, method="POST")
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        print(f"Resend error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", nargs="*", default=[], help="GitHub search terms for repo section")
    args = parser.parse_args()

    env = load_env()
    api_key = env.get("RESEND_API_KEY")
    to      = env.get("RESEND_TO")
    if not api_key or not to:
        print("ERROR: RESEND_API_KEY and RESEND_TO must be set in ~/.config/last30days/.env", file=sys.stderr)
        sys.exit(1)

    body = sys.stdin.read()
    if not body.strip():
        print("ERROR: empty digest body.", file=sys.stderr); sys.exit(1)

    first_line = body.splitlines()[0].strip().strip("=").strip()
    subject = first_line if first_line else f"AI Digest · {datetime.now().strftime('%Y-%m-%d')}"

    repos = fetch_top_repos(args.terms) if args.terms else []
    html  = build_html(subject, body, repos)
    result = send(api_key, to, subject, body, html)
    print(f"Sent: {result.get('id', 'ok')} → {to}")

if __name__ == "__main__":
    main()
