#!/usr/bin/env python3
"""
AlbaFrancia FM - LRC Translator  (French -> Albanian / shqip)
--------------------------------------------------------------
- Renames each music/*.lrc  to  music/*.lrcsource  (original backup)
- Translates every lyric line (keeps timestamps intact)
- Saves the Albanian version as music/*.lrc

Usage:  python translate_lrc.py
Requires: pip install deep-translator
"""
import os, re, shutil, time, sys

# ── Auto-install dependency ──────────────────────────────────────────────────
try:
    from deep_translator import GoogleTranslator
except ImportError:
    print("Installing deep-translator...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "deep-translator", "--break-system-packages", "-q"])
    from deep_translator import GoogleTranslator

translator = GoogleTranslator(source="fr", target="sq")

# ── Regex patterns ───────────────────────────────────────────────────────────
TIME_TAG   = re.compile(r"^(\[[\d:.]+\])(.*)")          # [mm:ss.xx] text
META_TAG   = re.compile(r"^\[[a-zA-Z]+:.*\]$")          # [ar:], [ti:], etc.

# ── Helpers ──────────────────────────────────────────────────────────────────
def translate(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    try:
        result = translator.translate(text)
        return result if result else text
    except Exception as e:
        print(f"    ⚠  {e}")
        return text

def process_file(path: str):
    backup = path + "source"

    if os.path.exists(backup):
        print(f"  [skip] {os.path.basename(path)}  (already translated)")
        return

    print(f"  {os.path.basename(path)}")

    # Back up original
    shutil.copy2(path, backup)

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw_lines = f.read().splitlines()

    out_lines = []
    for raw in raw_lines:
        if not raw.strip() or META_TAG.match(raw):
            out_lines.append(raw)          # keep empty / metadata lines
            continue

        m = TIME_TAG.match(raw)
        if m:
            tag, text = m.group(1), m.group(2).strip()
            if text:
                tr = translate(text)
                out_lines.append(f"{tag}{tr}")
                time.sleep(0.15)           # gentle rate-limit
            else:
                out_lines.append(raw)
        else:
            out_lines.append(raw)          # non-lyric lines unchanged

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    music_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lrc")

    lrc_files = sorted([
        os.path.join(music_dir, f)
        for f in os.listdir(music_dir)
        if f.lower().endswith(".lrc")
    ])

    if not lrc_files:
        print("No .lrc files found in lrc/")
        return

    print(f"Found {len(lrc_files)} .lrc file(s) — translating FR → Albanian\n")
    for path in lrc_files:
        process_file(path)

    print(f"\nDone!  Originals saved as .lrcsource")

if __name__ == "__main__":
    main()
