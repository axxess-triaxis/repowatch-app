"""The committed listing site must match the docs it is generated from."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _builder():
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_site_is_up_to_date(tmp_path: Path) -> None:
    _builder().build(tmp_path)
    for name in ("index.html", "privacy.html", "support.html"):
        fresh = (tmp_path / name).read_text("utf-8")
        committed = (ROOT / "site" / name).read_text("utf-8")
        assert fresh == committed, f"site/{name} is stale: run python scripts/build_site.py"


def test_privacy_page_carries_the_policy() -> None:
    body = (ROOT / "site" / "privacy.html").read_text("utf-8")
    assert "Effective 27 September 2026" in body
    assert "Triaxis Ventures Private Limited" in body
    assert 'href="/support"' in body


def test_markdown_subset() -> None:
    md = _builder().markdown
    out = md("# T\n\nA **b** `c<d>` [x](docs/privacy.md)\n\n- one\n- two\n\n| A | B |\n|---|---|\n| 1 | 2 |")
    assert "<h1>T</h1>" in out
    assert "<strong>b</strong>" in out and "<code>c&lt;d&gt;</code>" in out
    assert '<a href="/privacy">x</a>' in out
    assert "<ul><li>one</li><li>two</li></ul>" in out
    assert "<td>1</td><td>2</td>" in out
