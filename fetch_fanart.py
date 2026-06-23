#!/usr/bin/env python3
"""
Fetch top-scored solo safe-rated fan art from Danbooru for each T-doll and
download it to fanart_images/. Falls back to the official CG in doll_images/
when Danbooru returns nothing or only video files.

Writes image_manifest.json:
  {
    "AK-47":     {"tag": "ak-47_(girls'_frontline)", "url": "https://...",
                  "local": "fanart_images/AK-47.jpg", "source": "danbooru"},
    "RareGirl":  {"tag": null, "url": null,
                  "local": "doll_images/RareGirl.png", "source": "local_cg"},
  }

Resume-safe: skips any doll whose local file already exists on disk.
"""

import json
import re
import time
import urllib.request
import urllib.parse
from html import unescape
from pathlib import Path

from tqdm import tqdm

DANBOORU_LOGIN   = "Binary489"
DANBOORU_API_KEY = "MgUFvCiFUT4yVH6WvxfEKCUU"

PROFILES_DIR  = Path("profiles")
CG_DIR        = Path("doll_images")
FANART_DIR    = Path("fanart_images")
MANIFEST_PATH = Path("image_manifest.json")

WIKI_URL = "https://danbooru.donmai.us/wiki_pages/list_of_girls%27_frontline_characters"

# Seconds between Danbooru API calls.
DELAY = 2.0

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

NEGATIVE_TAGS = "-swimsuit -underwear_only -head_out_of_frame"

# Profile stem -> Danbooru tag, for names that don't match the wiki directly.
OVERRIDES: dict[str, str] = {
    "AK-74M":         "ak74m_(girls'_frontline)",
    "Boys AT Rifle":  "boys_(girls'_frontline)",
    "CZ 100":         "cz100_(girls'_frontline)",
    "Carcano M91_38": "carcano_m91/38_(girls'_frontline)",
    "Mondragon":      "mondragon_m1908_(girls'_frontline)",
    "PzB 39":         "pzb39_(girls'_frontline)",
    "SIG CROSS":      "sig_cross_(girls'_frontline)",
    "SSG 3000":       "ssg3000_(girls'_frontline)",
    "Stevens M520":   "stevens_520_(girls'_frontline)",
    "Stevens M620":   "stevens_620_(girls'_frontline)",
    "ZiP .22":        "zip.22_(girls'_frontline)",
    "Steyr ACR":      "s-acr_(girls'_frontline)",
    "Type 56":        "type_56_carbine_(girls'_frontline)",
    "Supernova":      "nova_(girls'_frontline)",
}


def fetch_wiki_map() -> dict[str, str]:
    """Scrape the Danbooru GFL wiki page → {display_name: danbooru_tag}."""
    req = urllib.request.Request(
        WIKI_URL, headers={"User-Agent": "tdoll-quiz-builder/1.0 (personal project)"}
    )
    with urllib.request.urlopen(req) as r:
        html = r.read().decode("utf-8")
    body = re.search(r'id="wiki-page-body"[^>]*>(.*)', html, re.DOTALL).group(1)
    links = re.findall(
        r'href="/wiki_pages/([^"]+%28girls%27_frontline%29[^"]*)"[^>]*>([^<]+)</a>',
        body,
    )
    return {
        unescape(display.strip()): urllib.parse.unquote(slug)
        for slug, display in links
    }


def danbooru_top(tag: str) -> str | None:
    """Return the URL of the top solo safe post for tag, or None."""
    params = urllib.parse.urlencode({
        "tags":    f"{tag} solo order:score rating:safe {NEGATIVE_TAGS}",
        "limit":   1,
        "login":   DANBOORU_LOGIN,
        "api_key": DANBOORU_API_KEY,
    })
    req = urllib.request.Request(
        f"https://danbooru.donmai.us/posts.json?{params}",
        headers={"User-Agent": "tdoll-quiz-builder/1.0 (personal project)"},
    )
    with urllib.request.urlopen(req) as r:
        posts = json.loads(r.read())
    if not posts:
        return None
    p = posts[0]
    url = p.get("large_file_url") or p.get("file_url") or ""
    ext = Path(url).suffix.lower()
    return url if ext in IMAGE_EXTS else None


def download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "tdoll-quiz-builder/1.0 (personal project)"}
        )
        with urllib.request.urlopen(req) as r:
            dest.write_bytes(r.read())
        return True
    except Exception as e:
        tqdm.write(f"  download failed: {e}")
        return False


def find_local_cg(name: str) -> str | None:
    """Find the official CG PNG for this doll, tolerating _ / - / space differences."""
    normalized = name.lower().replace(" ", "_").replace("-", "_")
    for p in CG_DIR.iterdir():
        if p.stem.lower().replace("-", "_") == normalized:
            return str(p)
    return None


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


def local_path_for(name: str, url: str) -> Path:
    ext = Path(url).suffix.lower() or ".jpg"
    return FANART_DIR / f"{name}{ext}"


def already_done(name: str, manifest: dict) -> bool:
    entry = manifest.get(name)
    if not entry:
        return False
    local = entry.get("local")
    if not local:
        return False
    # CG fallbacks point into doll_images/ which already exists; Danbooru
    # downloads need the file to actually be present.
    if entry["source"] == "local_cg":
        return True
    return Path(local).exists()


def main() -> None:
    FANART_DIR.mkdir(exist_ok=True)

    print("Fetching Danbooru wiki tag map...")
    wiki_map = fetch_wiki_map()
    print(f"  {len(wiki_map)} entries found.\n")

    manifest = load_manifest()
    doll_names = sorted(p.stem for p in PROFILES_DIR.glob("*.md"))
    remaining = [n for n in doll_names if not already_done(n, manifest)]

    skipped = len(doll_names) - len(remaining)
    if skipped:
        print(f"Resuming — {skipped}/{len(doll_names)} dolls already done.\n")

    for name in tqdm(remaining, unit="doll"):
        tag = OVERRIDES.get(name) or wiki_map.get(name)

        if tag is None:
            local = find_local_cg(name)
            manifest[name] = {"tag": None, "url": None, "local": local, "source": "local_cg"}
            tqdm.write(f"{name}: no tag — CG fallback")
            save_manifest(manifest)
            continue

        try:
            url = danbooru_top(tag)
        except Exception as e:
            tqdm.write(f"{name}: API error ({e}) — CG fallback")
            local = find_local_cg(name)
            manifest[name] = {"tag": tag, "url": None, "local": local, "source": "local_cg"}
            save_manifest(manifest)
            time.sleep(DELAY)
            continue

        if url:
            dest = local_path_for(name, url)
            if download(url, dest):
                manifest[name] = {"tag": tag, "url": url, "local": str(dest), "source": "danbooru"}
            else:
                local = find_local_cg(name)
                manifest[name] = {"tag": tag, "url": url, "local": local, "source": "local_cg"}
                tqdm.write(f"{name}: download failed — CG fallback")
        else:
            local = find_local_cg(name)
            manifest[name] = {"tag": tag, "url": None, "local": local, "source": "local_cg"}
            tqdm.write(f"{name}: no safe solo posts — CG fallback")

        save_manifest(manifest)
        time.sleep(DELAY)

    total    = len(doll_names)
    danbooru = sum(1 for v in manifest.values() if v["source"] == "danbooru")
    local_cg = sum(1 for v in manifest.values() if v["source"] == "local_cg")
    no_image = sum(1 for v in manifest.values() if not v.get("local"))

    print(f"\nDone. {total} dolls total.")
    print(f"  Danbooru fan art : {danbooru}")
    print(f"  Local CG         : {local_cg}")
    if no_image:
        print(f"  No image at all  : {no_image}")
    print(f"\nManifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
