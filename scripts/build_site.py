"""Build the public listing site (landing, privacy, support) into ``site/``.

The Markdown in ``README.md`` and ``docs/`` stays the single source of truth; this
renders it to static HTML for the GitHub Marketplace listing URLs, served by
Vercel (see ``vercel.json``). Standard library only. Run after editing the docs:

    python scripts/build_site.py

``tests/test_site.py`` fails if ``site/`` is out of date with the docs.
"""

from __future__ import annotations

import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
REPO_URL = "https://github.com/axxess-triaxis/repowatch-app"

# Links between docs become site paths; other repo-relative links go to GitHub.
LINK_MAP = {
    "docs/privacy.md": "/privacy",
    "docs/support.md": "/support",
    "README.md": "/",
}


def _link(url: str) -> str:
    if url in LINK_MAP:
        return LINK_MAP[url]
    if re.match(r"^[a-z]+://", url) or url.startswith(("#", "mailto:")):
        return url
    return f"{REPO_URL}/blob/main/{url}"


def inline(text: str) -> str:
    """Escape, then apply code spans, links, bold and bare URLs."""
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        s = html.escape(part, quote=False)
        s = re.sub(
            r"\[([^\]]+)\]\(([^)\s]+)\)",
            lambda m: f'<a href="{html.escape(_link(m.group(2)))}">{m.group(1)}</a>',
            s,
        )
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(
            r'(?<!["=>])(https://[^\s<)]+[^\s<).,;:])',
            lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>',
            s,
        )
        out.append(s)
    return "".join(out)


def markdown(md: str) -> str:
    """Render the Markdown subset used in these docs to HTML."""
    lines = md.splitlines()
    out: list[str] = []
    para: list[str] = []
    i = 0

    def flush() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            flush()
            i += 1
            continue
        if m := re.match(r"^(#{1,3}) (.+)$", line):
            flush()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue
        if line.startswith("- "):
            flush()
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{inline(lines[i][2:].strip())}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[1:] if not set("".join(r)) <= set("-: ")]
            thead = "".join(f"<th>{inline(c)}</th>" for c in head)
            tbody = "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body
            )
            out.append(f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>")
            continue
        if line.startswith("!["):
            flush()
            i += 1
            continue  # images are placed by the page template
        para.append(line.strip())
        i += 1
    flush()
    return "\n".join(out)


def landing_markdown() -> str:
    """README from the top up to (not including) the Architecture section."""
    readme = (ROOT / "README.md").read_text("utf-8")
    cut = readme.find("\n## Architecture")
    return readme if cut < 0 else readme[:cut]


CSS = """
:root{--navy:#0A0F1E;--shield:#111A33;--gold:#F2B544;--cream:#E9E4D2;--wordmark:#9A6A0D;
--bg:#F4F1E9;--ink:#1a1d24;--muted:#5a5f6b;--rule:#ddd6c6}
*{box-sizing:border-box}html,body{margin:0}
body{font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);background:var(--bg)}
header{background:var(--navy);color:var(--cream)}
.bar{max-width:880px;margin:0 auto;padding:14px 16px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.bar img{width:40px;height:40px;border-radius:8px}
.bar b{font-size:18px;color:#fff;letter-spacing:.01em}
nav{margin-left:auto;display:flex;gap:18px;flex-wrap:wrap}
nav a{color:var(--cream);text-decoration:none;font-size:15px}
nav a:hover,nav a[aria-current]{color:var(--gold)}
.hero{background:var(--shield);border-bottom:3px solid var(--gold)}
.hero img{display:block;width:100%;max-width:880px;margin:0 auto;height:auto}
main{max-width:880px;margin:0 auto;padding:28px 16px 48px}
h1{font-size:30px;line-height:1.2;margin:0 0 14px}h2{font-size:21px;margin:32px 0 8px}
h3{font-size:17px;margin:22px 0 6px}
a{color:var(--wordmark)}a:hover{color:var(--navy)}
code{font:14px ui-monospace,Consolas,monospace;background:#e8e2d3;padding:1px 5px;border-radius:4px}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:15px;display:block;overflow-x:auto}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
th{background:#ebe5d6}
ul{padding-left:22px}li{margin:3px 0}
footer{border-top:1px solid var(--rule);color:var(--muted);font-size:14px}
footer div{max-width:880px;margin:0 auto;padding:16px}
"""


def page(title: str, body: str, current: str, hero: bool = False) -> str:
    def nav(href: str, label: str) -> str:
        cur = ' aria-current="page"' if href == current else ""
        return f'<a href="{href}"{cur}>{label}</a>'

    banner = (
        '<div class="hero"><img src="/assets/repowatch-banner.png" '
        'alt="RepoWatch: repo governance, audit, vigilance" width="2000" height="1050"></div>'
        if hero
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="RepoWatch GitHub App: weekly governance audits for AI-assisted teams, posted as one GitHub issue.">
<link rel="icon" type="image/png" href="/assets/repowatch-logo-200.png">
<style>{CSS}</style>
</head>
<body>
<header><div class="bar">
<img src="/assets/repowatch-logo-200.png" alt="" width="40" height="40"><b>RepoWatch</b>
<nav>{nav("/", "Overview")}{nav("/privacy", "Privacy")}{nav("/support", "Support")}<a href="{REPO_URL}">GitHub</a></nav>
</div></header>
{banner}
<main>
{body}
</main>
<footer><div>RepoWatch GitHub App &middot; operated by Triaxis Ventures Private Limited &middot;
<a href="/privacy">Privacy policy</a> &middot; <a href="/support">Support</a> &middot;
<a href="{REPO_URL}">Source</a></div></footer>
</body>
</html>
"""


def build(out: Path = SITE) -> None:
    shutil.rmtree(out, ignore_errors=True)
    (out / "assets").mkdir(parents=True)
    for name in ("repowatch-logo-200.png", "repowatch-banner.png"):
        shutil.copy2(ROOT / "docs" / "assets" / name, out / "assets" / name)
    pages = {
        "index.html": ("RepoWatch GitHub App", landing_markdown(), "/", True),
        "privacy.html": (
            "RepoWatch: Privacy Policy",
            (ROOT / "docs" / "privacy.md").read_text("utf-8"),
            "/privacy",
            False,
        ),
        "support.html": (
            "RepoWatch: Support",
            (ROOT / "docs" / "support.md").read_text("utf-8"),
            "/support",
            False,
        ),
    }
    for name, (title, md, current, hero) in pages.items():
        (out / name).write_text(page(title, markdown(md), current, hero), "utf-8", newline="\n")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else SITE)
    print(f"built {SITE}")
