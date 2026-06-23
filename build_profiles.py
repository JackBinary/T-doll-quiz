#!/usr/bin/env python3
"""
Fetch T-doll quotes from IOP Wiki and generate personality profiles
using a local llama.cpp server (Gemma 4 12B).

Resumable: skips dolls that already have a profile or a quotes cache.
Run: python3 build_profiles.py
"""

import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Config ─────────────────────────────────────────────────────────────────

WIKI_BASE    = "https://iopwiki.com/wiki"
LLM_URL      = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL    = "/home/jgarland/llama-models/gemma-4-12b-it-qat-q4_0.gguf"

QUOTES_DIR   = Path("quotes")
PROFILES_DIR = Path("profiles")

FETCH_DELAY  = 0.4   # seconds between wiki requests
LLM_TIMEOUT  = 120   # seconds

# ── T-doll list (418 GFL originals, extras/collabs excluded) ───────────────

DOLLS = [
    "43M","6P62","93R","9A-91","A-545","A-91","AA-12","AAT-52","ACR","ADS",
    "AEK-999","AK-12","AK-15","AK-47","AK-74M","AK-74U","AK-Alfa","AN-94",
    "APC556","APC9K","AR-18","AR-57","AR70","ART556","ARX-160","AS Val",
    "ASh-12.7","AUG","AUG Para","Ak 5","Ameli","Astra Revolver","BM59",
    "Ballista","Beowulf","Beretta Model 38","Boys AT Rifle","Bren","Bren Ten",
    "C-93","C-MS","C14","C96","CAR","CAWS","CF05","CM901","CMR-30","CR-21",
    "CZ 100","CZ-805","CZ2000","CZ52","CZ75","Carcano M1891","Carcano M91/38",
    "Chauchat","Chiappa Triple Crown","Colt M1851N","Colt Revolver","Colt Walker",
    "Contender","Cx4 Storm","DP-12","DP28","DSR-50","De Lisle","Defender",
    "Derringer","Desert Eagle","EF88","EM-2","EVO 3","Erma","F1","F2000","FAL",
    "FAMAS","FARA 83","FG42","FM24","FMG-9","FN-49","FNC","FNP-9","FO-12",
    "FP-6","FX-05","Falcon","Fedorov","Five-seveN","G11","G28","G3","G36",
    "G36C","G41","G43","GM6 Lynx","GSh-18","Galil","General Liu","Gepard M1",
    "Glock 17","Grizzly MkV","HK21","HK23","HK33","HK416","HK433","HK45",
    "HK512","HP-35","HS.50","HS2000","HSM10","HTI","Hanyang Type 88","Hecate II",
    "Hi-Point C9","Honey Badger","Howa Type 64","Howa Type 89","IA2","IDW",
    "INSAS","IWS 2000","JS 9","JS05","Jatimatic","Jericho","K11","K2","K3",
    "K31","K5","K7","KAC-PDW","KGP-9","KH2002","KLIN","KS-23","KSG","KSVK",
    "Kar98k","Kolibri","Kord","L85A1","LAMG","LR-300","LS26","LTLX 7000",
    "LWMMG","Lee-Enfield","Lewis","Liberator","Lusa","M&P9","M1 Garand","M1014",
    "M110","M12","M14","M16A1","M1887","M1895 CB","M1897","M1911","M1918",
    "M1919A4","M1A1","M200","M21","M240L","M249 SAW","M26-MASS","M2HB","M3",
    "M327","M37","M4 SOPMOD II","M4A1","M500","M590","M6 ASW","M60","M82",
    "M82A1","M870","M887","M9","M950A","M99","MAC-10","MAG-7","MAS-38","MAT-49",
    "MDR","MG15","MG3","MG338","MG34","MG36","MG4","MG42","MG5","MK3A1",
    "MP-443","MP-446","MP-448","MP40","MP41","MP5","MP7","MPK","MPL","MSBS",
    "MT-9","Magal","Makarov","Martini-Henry","Maxim 9","Micro Uzi","Mini-14",
    "Mk 12","Mk.18","Mk23","Mk46","Mk48","Model L","Mondragon","Mosin-Nagant",
    "Mx4 Storm","NS2000","NTW-20","NZ75","Nagant Revolver","Negev","OBR",
    "OTs-12","OTs-14","OTs-39","OTs-44","Owen","P08","P10C","P2000","P22",
    "P226","P290","P30","P38","P50","P7","P90","P99","PA-15","PK","PKP",
    "PM-06","PM-9","PM1910","PP-19","PP-19-01","PP-2000","PP-90","PPD-40",
    "PPK","PPQ","PPS-43","PPSh-41","PSG-1","PSM","PTRD","Px4 Storm","Python",
    "PzB 39","QBU-191","QBU-88","QBZ-191","QSB-91","R5","R93","RFB","RMB-93",
    "RO635","RPD","RPK-16","RPK-203","RT-20","Rex Alpha","Rex Zero 1","Rhino",
    "Ribeyrolles","S.A.T.8","SAF","SAR-21","SCAR-H","SCAR-L","SCR","SCW",
    "SIG CROSS","SIG M400","SIG MCX","SIG-510","SIG-556","SL8","SM-1","SP9",
    "SPAS-12","SPAS-15","SPP-1","SPR A3G","SR-2","SR-3MP","SRS","SSG 3000",
    "SSG 69","SSG M1","ST AR-15","SUB-2000","SV-98","SVCh","SVD","SVT-38",
    "Saiga 308","Saiga-12","Savage 99","Serdyukov","Shipka","Simonov","Six12",
    "Skorpion","Spectre M4","Spitfire","Springfield","StG-940","StG44",
    "Sten MkII","Sterling","Stevens M520","Stevens M620","Steyr ACR",
    "Steyr Scout","Suomi","Super SASS","Super-Shorty","Supernova","T-5000",
    "T-CMS","T65","T77","T91","TAC-50","TAR-21","TEC-9","TF-Q","TKB-408",
    "TMP","TPS","TS12","Tabuk","Thompson","Thunder","Tokarev","Type 03",
    "Type 100","Type 4","Type 56","Type 56-1","Type 59","Type 62","Type 63",
    "Type 64","Type 79","Type 80","Type 81 Carbine","Type 82","Type 88",
    "Type 92","Type 95","Type 97","Type 97 Shotgun","UKM-2000","UMP40",
    "UMP45","UMP9","USAS-12","USP Compact","UTS-15","Unica 6","V-PM5","VHS",
    "VP1915","VP70","VP9","VRB","VSK-94","Vector","Vepr","Vigneron M2","WA2000",
    "WKp","Webley","Welrod MkII","X95","XCR","XM3","XM556","XM8","Z-62",
    "ZB-26","Zas M21","Zas M76","ZiP .22","m45","wz.29","wz.63",
]

# ── Extraction ─────────────────────────────────────────────────────────────

SKIP_LABELS = {"Dialogue", "Chinese", "Japanese", "Korean", "English"}


def extract_english_quotes(html: str) -> str:
    """Parse 5-column quote tables (label | ZH | JP | KO | EN)."""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", {"id": "mw-content-text"}) or soup

    lines = []
    for table in content.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 5:
                continue
            label   = cells[0].get_text(strip=True)
            english = cells[4].get_text(separator=" ", strip=True)
            if label in SKIP_LABELS or not english:
                continue
            lines.append(f"[{label}] {english}")

    return "\n".join(lines)


def fetch_quotes(name: str) -> str | None:
    slug = name.replace(" ", "_").replace("/", "%2F")
    url = f"{WIKI_BASE}/{slug}/Quotes"
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; tdoll-profiler/1.0)"},
            timeout=15,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return extract_english_quotes(r.text)
    except Exception as e:
        print(f"  [fetch error] {name}: {e}")
        return None


# ── LLM ────────────────────────────────────────────────────────────────────

PROFILE_SYSTEM = """\
You are writing personality profiles for a quiz that matches players to Girls' Frontline T-dolls.
The quiz must find the *best* match, not just a good-enough one — so profiles need to be
discriminating: they should capture what makes each doll distinctly herself, not generic traits
that could apply to many characters.

Write each profile in this exact markdown format:

## [Name]

**Summary:** 2-3 sentences. Concrete personality, not vague adjectives. Include her dominant
emotional register, how she relates to the Commander, and one specific behavioral pattern.

**Traits:**
- [4-6 traits, each phrased as a behavior or tendency, not a single adjective.
  E.g. "Deflects compliments with self-deprecating jokes" not just "humble"]

**Communication style:** One sentence on tone, register, and any speech patterns.

**What sets her apart:** One sentence on what makes her distinct from other dolls —
especially any who might seem similar at first glance.
"""


def generate_profile(name: str, quotes: str) -> str:
    prompt = (
        f"Here are the in-game quotes for the T-doll named {name}.\n\n"
        f"{quotes}\n\n"
        f"Write a personality profile for {name} following the format in your instructions."
    )
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": PROFILE_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.65,
        "max_tokens": 600,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    r = requests.post(LLM_URL, json=payload, timeout=LLM_TIMEOUT)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    # Gemma 4 thinking model: final answer is in content, reasoning in reasoning_content
    return (msg.get("content") or msg.get("reasoning_content") or "").strip()


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    QUOTES_DIR.mkdir(exist_ok=True)
    PROFILES_DIR.mkdir(exist_ok=True)

    total   = len(DOLLS)
    done    = 0
    skipped = 0
    errors  = []

    for i, name in enumerate(DOLLS, 1):
        safe_name    = re.sub(r'[<>:"/\\|?*]', "_", name)
        profile_path = PROFILES_DIR / f"{safe_name}.md"
        quotes_path  = QUOTES_DIR   / f"{safe_name}.txt"

        if profile_path.exists():
            skipped += 1
            continue

        print(f"[{i}/{total}] {name}", end="", flush=True)

        # Step 1: quotes (cache or fetch)
        if quotes_path.exists():
            quotes = quotes_path.read_text(encoding="utf-8")
            print(" (cached)", end="", flush=True)
        else:
            quotes = fetch_quotes(name)
            time.sleep(FETCH_DELAY)
            if quotes and len(quotes) > 30:
                quotes_path.write_text(quotes, encoding="utf-8")
            else:
                quotes = None

        if not quotes or len(quotes) < 30:
            print(" -> no quotes, skipping")
            profile_path.write_text(f"## {name}\n\n*No quotes available.*\n", encoding="utf-8")
            skipped += 1
            continue

        # Step 2: generate profile
        try:
            profile = generate_profile(name, quotes)
            profile_path.write_text(profile + "\n", encoding="utf-8")
            done += 1
            print(" ok")
        except Exception as e:
            print(f" ERROR: {e}")
            errors.append((name, str(e)))

    print(f"\nDone. {done} profiles written, {skipped} skipped, {len(errors)} errors.")
    if errors:
        print("Errors:")
        for name, err in errors:
            print(f"  {name}: {err}")


if __name__ == "__main__":
    main()
