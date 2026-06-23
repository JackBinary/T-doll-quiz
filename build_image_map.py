#!/usr/bin/env python3
"""
Build image_manifest.json mapping each T-doll to their official CG.

Tries in order:
  1. Local file in doll_images/
  2. IOPWiki full-size CG (downloaded to doll_images/)
  3. null
"""

import json
import re
import urllib.request
import urllib.parse
from pathlib import Path

PROFILES_DIR  = Path("profiles")
CG_DIR        = Path("doll_images")
MANIFEST_PATH = Path("image_manifest.json")


def alnum(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def find_local_cg(name: str) -> str | None:
    doll_key = alnum(name)
    exact = skin_variant = cg_prefix = None

    for p in CG_DIR.iterdir():
        base = p.stem.split("_(")[0]
        cg_key = alnum(base)

        if cg_key == doll_key:
            return str(p)
        if skin_variant is None and cg_key.startswith(doll_key) and len(doll_key) >= 2:
            skin_variant = str(p)
        if cg_prefix is None and doll_key.startswith(cg_key) and len(cg_key) >= 4:
            cg_prefix = str(p)

    return skin_variant or cg_prefix


def fetch_iopwiki_cg(name: str) -> str | None:
    """Download the full-size CG from IOPWiki into doll_images/ and return the path."""
    wiki_name = name.replace(' ', '_')
    page_url = f'https://iopwiki.com/wiki/{urllib.parse.quote(wiki_name)}'
    req = urllib.request.Request(
        page_url, headers={'User-Agent': 'tdoll-quiz-builder/1.0 (personal project)'}
    )
    try:
        with urllib.request.urlopen(req) as r:
            html = r.read().decode('utf-8')
    except Exception as e:
        print(f"  {name}: IOPWiki page error — {e}")
        return None

    base_file = wiki_name + '.png'
    m = re.search(
        r'/images/thumb/([a-f0-9]+/[a-f0-9]+)/' + re.escape(base_file) + r'/\d+px-',
        html, re.IGNORECASE
    )
    if not m:
        print(f"  {name}: no CG found on IOPWiki")
        return None

    img_url = f'https://iopwiki.com/images/{m.group(1)}/{base_file}'
    dest = CG_DIR / base_file

    try:
        req = urllib.request.Request(
            img_url, headers={'User-Agent': 'tdoll-quiz-builder/1.0 (personal project)'}
        )
        with urllib.request.urlopen(req) as r:
            dest.write_bytes(r.read())
        print(f"  {name}: downloaded from IOPWiki → {dest}")
        return str(dest)
    except Exception as e:
        print(f"  {name}: IOPWiki download failed — {e}")
        return None


def main() -> None:
    manifest = {}
    missing = []

    for profile in sorted(PROFILES_DIR.glob("*.md")):
        name = profile.stem
        local = find_local_cg(name)

        if local is None:
            print(f"Fetching IOPWiki CG for: {name}")
            local = fetch_iopwiki_cg(name)

        if local:
            manifest[name] = {"local": local, "source": "local_cg"}
        else:
            manifest[name] = {"local": None, "source": "local_cg"}
            missing.append(name)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    print(f"\n{len(manifest)} dolls mapped.")
    if missing:
        print(f"{len(missing)} still missing:")
        for name in missing:
            print(f"  {name}")
    else:
        print("All dolls have a CG.")


if __name__ == "__main__":
    main()
