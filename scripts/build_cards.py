#!/usr/bin/env python3
"""
Builds the project cards (cards/*.svg) and the "Projects" section of README.md.

Each card is a self-contained SVG: GitHub shows README images through a sandboxed <img>,
so the thumbnail is embedded as a data URI and the text is laid out with HTML inside a
<foreignObject>. The font is set on the card element itself (there is no <body> inside a
foreignObject, so a `body { font-family }` rule would silently fall back to serif).

Usage:  python scripts/build_cards.py        (set GITHUB_TOKEN to avoid API rate limits)
"""

import base64
import html
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

from PIL import Image

OWNER = "otabekoff"
REPOS = [
    "voice-frame-pro",
    "book-craft",
    "joinery",
    "preview-cam",
    "mitti",
    "jojavoy-chikki",
    "nodets",
    "senbrua",
    "rust-jobqueue",
    "ombor",
    "realchat",
    "power-calculator",
    "universaltools",
    "CopyAsMarkdown",
    "MahalliyBaza",  # renamed to "ombor"; duplicates are skipped
]

CARD_W, CARD_H, THUMB_H = 400, 352, 200
FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'
LANG_COLOURS = {
    "C++": "#f34b7d", "C": "#555555", "Rust": "#dea584", "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a", "Dart": "#00b4ab", "Python": "#3572a5", "Vue": "#41b883",
    "HTML": "#e34c26", "CSS": "#663399", "Go": "#00add8", "Shell": "#89e051",
}
# Used when a repository has neither a description nor a prose paragraph in its README
FALLBACK_DESCRIPTIONS = {
    "CopyAsMarkdown": "Copy text and paste it as Markdown.",
}
SKIP_IMAGE = re.compile(r"shields\.io|badgen|badge|/actions/workflows/|github-readme-stats|vercel\.app/api|"
                        r"\.svg(\?|$)|emoji|gravatar|avatars\.githubusercontent", re.I)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
CARDS_DIR = os.path.join(ROOT, "cards")
THUMBS_DIR = os.path.join(ROOT, "thumbnails")  # optional <repo>.svg/.png/.jpg overrides, 2:1
START, END = "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->"


def fetch(url, accept=None, raw=False):
    headers = {"User-Agent": "profile-cards"}
    if accept:
        headers["Accept"] = accept
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        data = response.read()
    return data if raw else data.decode("utf-8", "replace")


def readme_text(full_name):
    try:
        return fetch(f"https://api.github.com/repos/{full_name}/readme", "application/vnd.github.raw")
    except Exception:
        return ""


def resolve(url, full_name, branch):
    url = html.unescape(url.strip().strip("<>"))
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        m = re.match(r"https://github\.com/([^/]+/[^/]+)/(?:blob|raw)/(.+)", url)
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}" if m else url
    return f"https://raw.githubusercontent.com/{full_name}/{branch}/{urllib.parse.quote(url.lstrip('./'))}"


def thumbnail(readme, full_name, branch):
    """First real screenshot in the README, cropped to the card's header, as a JPEG data URI."""
    candidates = re.findall(r"!\[[^\]]*\]\(\s*([^)\s]+)", readme) + re.findall(r"<img[^>]+src=[\"']([^\"']+)", readme, re.I)
    for candidate in candidates:
        url = resolve(candidate, full_name, branch)
        if SKIP_IMAGE.search(url):
            continue
        try:
            image = Image.open(io.BytesIO(fetch(url, raw=True)))
            image.seek(0)
            image = image.convert("RGB")
        except Exception:
            continue
        if image.width < 320 or image.height < 160:
            continue  # logos and icons make poor headers

        # Cover-crop to the header's aspect, keeping the top of screenshots
        target = CARD_W / THUMB_H
        if image.width / image.height > target:
            w = int(image.height * target)
            image = image.crop(((image.width - w) // 2, 0, (image.width - w) // 2 + w, image.height))
        else:
            image = image.crop((0, 0, image.width, int(image.width / target)))
        image = image.resize((CARD_W * 2, THUMB_H * 2), Image.LANCZOS)

        out = io.BytesIO()
        image.save(out, "JPEG", quality=72, optimize=True, progressive=True)
        return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()
    return None


def local_thumbnail(slug):
    """A hand-picked header from thumbnails/, preferred over README screenshots."""
    for ext in ("svg", "png", "jpg", "jpeg", "webp"):
        path = os.path.join(THUMBS_DIR, f"{slug}.{ext}")
        if not os.path.exists(path):
            continue
        if ext == "svg":
            with open(path, "rb") as f:
                return "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode()
        image = Image.open(path).convert("RGB").resize((CARD_W * 2, THUMB_H * 2), Image.LANCZOS)
        out = io.BytesIO()
        image.save(out, "JPEG", quality=80, optimize=True, progressive=True)
        return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()
    return None


def generated_cover(name, language):
    """Cover for repos without a screenshot: language-tinted gradient, dot grid, project name."""
    accent = LANG_COLOURS.get(language, "#8b949e")
    size = 44 if len(name) <= 12 else (36 if len(name) <= 16 else 30)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W}" height="{THUMB_H}" viewBox="0 0 {CARD_W} {THUMB_H}">
<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{accent}" stop-opacity=".55"/><stop offset=".6" stop-color="#161b22"/><stop offset="1" stop-color="#0d1117"/></linearGradient>
<pattern id="p" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#ffffff" fill-opacity=".07"/></pattern>
</defs>
<rect width="100%" height="100%" fill="url(#g)"/><rect width="100%" height="100%" fill="url(#p)"/>
<text x="24" y="{THUMB_H - 34}" font-family='{FONT.replace('"', "")}' font-size="{size}" font-weight="700" fill="#ffffff" letter-spacing="-0.5">{html.escape(name)}</text>
<rect x="24" y="{THUMB_H - 22}" width="40" height="4" rx="2" fill="{accent}"/>
</svg>"""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def summary(readme):
    """First prose paragraph of a README, for repos without a description."""
    for block in re.split(r"\n\s*\n", re.sub(r"<!--.*?-->", "", readme, flags=re.S)):
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)|<[^>]+>|`", "", block)
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text).strip()
        if text and not text.startswith(("#", "|", "-", "*", ">")) and len(text) > 30:
            return " ".join(text.split())
    return ""


def card_svg(repo, image):
    language = repo.get("language") or ""
    colour = LANG_COLOURS.get(language, "#8b949e")
    description = html.escape(repo["description"] or "")
    stars = repo.get("stargazers_count", 0)
    lang_html = (f'<span style="display:inline-flex;align-items:center;gap:6px"><span style="width:10px;height:10px;'
                 f'border-radius:50%;background:{colour};display:inline-block"></span>{html.escape(language)}</span>') if language else "<span></span>"
    star_icon = ('<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 16 16" fill="#9198a1" style="vertical-align:-2px">'
                 '<path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"/></svg>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W}" height="{CARD_H}" viewBox="0 0 {CARD_W} {CARD_H}">
<foreignObject x="0" y="0" width="{CARD_W}" height="{CARD_H}">
<div xmlns="http://www.w3.org/1999/xhtml" style='box-sizing:border-box;width:{CARD_W}px;height:{CARD_H}px;font-family:{FONT};background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;display:flex;flex-direction:column;-webkit-font-smoothing:antialiased'>
<img src="{image}" width="{CARD_W}" height="{THUMB_H}" style="display:block;width:{CARD_W}px;height:{THUMB_H}px;object-fit:cover;border-bottom:1px solid #30363d" alt=""/>
<div style="flex:1;display:flex;flex-direction:column;padding:14px 18px 14px">
<div style="font-size:21px;font-weight:600;color:#e6edf3;line-height:1.25;letter-spacing:-0.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{html.escape(repo["name"])}</div>
<div style="margin-top:7px;font-size:13.5px;line-height:1.45;color:#9198a1;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden">{description}</div>
<div style="margin-top:auto;display:flex;justify-content:space-between;align-items:center;font-size:12.5px;color:#9198a1">{lang_html}<span>{star_icon} {stars}</span></div>
</div>
</div>
</foreignObject>
</svg>
"""


def main():
    os.makedirs(CARDS_DIR, exist_ok=True)
    seen, items = set(), []

    for name in REPOS:
        repo = json.loads(fetch(f"https://api.github.com/repos/{OWNER}/{name}"))
        if repo["full_name"].lower() in seen:
            print(f"skip   {name} (same repository as {repo['name']})")
            continue
        seen.add(repo["full_name"].lower())

        readme = readme_text(repo["full_name"])
        if not repo.get("description"):
            repo["description"] = summary(readme) or FALLBACK_DESCRIPTIONS.get(repo["name"], "")

        slug = repo["name"].lower()
        image = local_thumbnail(slug)
        source = "custom"
        if image is None:
            image = thumbnail(readme, repo["full_name"], repo.get("default_branch", "main"))
            source = "readme" if image else "cover"
        print(f"{source:7} {repo['name']}")
        image = image or generated_cover(repo["name"], repo.get("language"))

        with open(os.path.join(CARDS_DIR, f"{slug}.svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(card_svg(repo, image))
        items.append((repo, slug))

    links = "\n".join(
        f'<a href="{repo["html_url"]}"><img src="cards/{slug}.svg" width="32%" '
        f'alt="{html.escape(repo["name"])}: {html.escape(repo["description"] or "")}"/></a>'
        for repo, slug in items)
    # Blank lines matter: a Markdown HTML block runs until the next blank line, so without
    # them the heading after the section is swallowed and shown as raw text
    section = f'{START}\n\n<p align="center">\n{links}\n</p>\n\n{END}'

    with open(README, encoding="utf-8") as f:
        text = f.read()
    if START not in text:
        sys.exit(f"README.md has no {START} … {END} markers")
    text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: section, text, flags=re.S)
    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


if __name__ == "__main__":
    main()
