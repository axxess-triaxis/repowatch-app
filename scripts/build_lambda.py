"""Assemble build/lambda/: the App code plus its dependencies, for Lambda on arm64.

Run before `cdk synth` / `cdk deploy`:

    python scripts/build_lambda.py

Binary dependencies (cryptography, cffi) are fetched as prebuilt Linux arm64
wheels for the Lambda Python runtime, so this works on Windows or macOS with no
Docker. RepoWatch itself is pure Python and is installed from its pinned
commit without dependencies (it has none).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "lambda"
PYTHON_VERSION = "3.13"
PLATFORMS = ("manylinux_2_28_aarch64", "manylinux2014_aarch64", "manylinux_2_34_aarch64")


def pip(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--target", str(OUT), *args], check=True)


def main() -> None:
    requirements = [
        line.strip() for line in (ROOT / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    binary = [r for r in requirements if not r.startswith("repowatch")]
    source = [r for r in requirements if r.startswith("repowatch")]

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)

    platform_flags = [flag for p in PLATFORMS for flag in ("--platform", p)]
    pip(*platform_flags, "--implementation", "cp", "--python-version", PYTHON_VERSION,
        "--only-binary=:all:", *binary)
    pip("--no-deps", *source)

    shutil.copytree(ROOT / "src" / "repowatch_app", OUT / "repowatch_app",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.rmtree(OUT / "bin", ignore_errors=True)  # console-script shims, unused on Lambda
    for junk in OUT.glob("**/__pycache__"):
        shutil.rmtree(junk)
    print(f"Built {OUT} ({sum(1 for _ in OUT.rglob('*') if _.is_file())} files)")


if __name__ == "__main__":
    main()
