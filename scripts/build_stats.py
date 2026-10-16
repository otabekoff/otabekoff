#!/usr/bin/env python3
"""
Builds cards/stats.svg and cards/languages.svg from the GitHub GraphQL API.

A self-generated replacement for the shared github-readme-stats service: no external server,
no rate-limited images. Runs in the same weekly workflow as the project cards.

Usage:  GITHUB_TOKEN=... python scripts/build_stats.py
"""

import html
import json
import os
import urllib.request

LOGIN = "otabekoff"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_DIR = os.path.join(ROOT, "cards")
FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'
W, H = 400, 214

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      contributionCalendar { totalContributions }
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
    }
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 20) { edges { size node { name color } } }
      }
    }
  }
}
"""


def graphql(variables):
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise SystemExit(payload["errors"])
    return payload["data"]["user"]


def card(title, subtitle, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<foreignObject x="0" y="0" width="{W}" height="{H}">
<div xmlns="http://www.w3.org/1999/xhtml" style='box-sizing:border-box;width:{W}px;height:{H}px;padding:16px 20px;font-family:{FONT};background:#161b22;border:1px solid #30363d;border-radius:12px;color:#e6edf3;-webkit-font-smoothing:antialiased'>
<div style="font-size:15px;font-weight:600">{html.escape(title)}</div>
<div style="font-size:12px;color:#9198a1;margin-top:2px">{html.escape(subtitle)}</div>
{body}
</div>
</foreignObject>
</svg>
"""


def main():
    user, nodes, after = None, [], None
    while True:
        page = graphql({"login": LOGIN, "after": after})
        user = user or page
        nodes += page["repositories"]["nodes"]
        info = page["repositories"]["pageInfo"]
        if not info["hasNextPage"]:
            break
        after = info["endCursor"]

    cc = user["contributionsCollection"]
    stars = sum(n["stargazerCount"] for n in nodes)
    figures = [
        (cc["contributionCalendar"]["totalContributions"], "contributions"),
        (cc["totalCommitContributions"], "commits"),
        (cc["totalPullRequestContributions"], "pull requests"),
        (cc["totalIssueContributions"], "issues"),
        (user["repositories"]["totalCount"], "public repositories"),
        (stars, "stars earned"),
    ]
    cells = "".join(
        f'<div><div style="font-size:24px;font-weight:600;line-height:1.1">{value:,}</div>'
        f'<div style="font-size:12px;color:#9198a1;margin-top:3px">{label}</div></div>'
        for value, label in figures)
    stats = card("GitHub activity", "Last 12 months · refreshed weekly",
                 f'<div style="margin-top:16px;display:grid;grid-template-columns:repeat(3,1fr);row-gap:16px;column-gap:8px">{cells}</div>')

    totals = {}
    for repo in nodes:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            entry = totals.setdefault(name, [0, edge["node"]["color"] or "#8b949e"])
            entry[0] += edge["size"]
    ranked = sorted(totals.items(), key=lambda kv: kv[1][0], reverse=True)
    grand = sum(v[0] for _, v in ranked) or 1
    top = ranked[:8]
    other = 1.0 - sum(v[0] for _, v in top) / grand

    bar = "".join(f'<span style="width:{v[0] / grand * 100:.2f}%;background:{v[1]}"></span>' for _, v in top)
    if other > 0.001:
        bar += f'<span style="width:{other * 100:.2f}%;background:#30363d"></span>'
    legend = "".join(
        f'<div style="display:flex;align-items:center;gap:7px;font-size:12.5px;white-space:nowrap">'
        f'<span style="width:9px;height:9px;border-radius:50%;background:{v[1]};flex:none"></span>'
        f'<span style="overflow:hidden;text-overflow:ellipsis">{html.escape(name)}</span>'
        f'<span style="color:#9198a1;margin-left:auto">{v[0] / grand * 100:.1f}%</span></div>'
        for name, v in top)
    languages = card("Most used languages", "By code size across public repositories",
                     f'<div style="margin-top:14px;display:flex;height:8px;border-radius:4px;overflow:hidden;gap:2px">{bar}</div>'
                     f'<div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr;row-gap:9px;column-gap:24px">{legend}</div>')

    os.makedirs(CARDS_DIR, exist_ok=True)
    for name, svg in (("stats.svg", stats), ("languages.svg", languages)):
        with open(os.path.join(CARDS_DIR, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
    print("stats:", ", ".join(f"{label} {value}" for value, label in figures))
    print("languages:", ", ".join(f"{n} {v[0] / grand * 100:.1f}%" for n, v in top))


if __name__ == "__main__":
    main()
