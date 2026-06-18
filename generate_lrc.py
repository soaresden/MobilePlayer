"""
generate_lrc.py — AlbaFrancia FM
Transcrit les MP3 albanais (suno/) avec faster-whisper et génère les fichiers .lrc synchronisés.
Compatible Python 3.8 → 3.13.

Usage :  python generate_lrc.py
Prérequis : Python 3.8+  (ffmpeg PAS nécessaire — faster-whisper lit les MP3 directement)
"""

import subprocess, sys
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
SUNO_DIR   = Path(__file__).parent / 'music'
MODEL_SIZE = 'medium'      # tiny | base | small | medium | large-v2 | large-v3
LANGUAGE   = 'sq'          # albanais
OVERWRITE  = False         # True = re-générer même si .lrc existe déjà
# ─────────────────────────────────────────────────────────────────────────────

def install(pkg):
    print(f"  → installation de {pkg}...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '--quiet'])

# Vérifier/installer faster-whisper
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Installation de faster-whisper (première fois seulement)...")
    install('faster-whisper')
    from faster_whisper import WhisperModel

def seconds_to_lrc(t: float) -> str:
    """Convertit des secondes en timestamp LRC [mm:ss.xx]"""
    m = int(t // 60)
    s = t % 60
    return f"[{m:02d}:{s:05.2f}]"

def segments_to_lrc(segments) -> str:
    lines = []
    for seg in segments:
        ts = seconds_to_lrc(seg.start)
        lines.append(f"{ts}{seg.text.strip()}")
    return "\n".join(lines)

def main():
    mp3_files = sorted(SUNO_DIR.glob('*.mp3'))
    if not mp3_files:
        print(f"Aucun MP3 trouvé dans {SUNO_DIR}")
        return

    print(f"\nChargement du modèle Whisper '{MODEL_SIZE}'...")
    print("(le modèle se télécharge la première fois, ~1.4 Go pour 'medium')\n")
    # device='cpu' fonctionne partout ; passe 'cuda' si tu as un GPU NVIDIA
    model = WhisperModel(MODEL_SIZE, device='cpu', compute_type='int8')

    total = len(mp3_files)
    done, skipped, errors = 0, 0, 0

    for i, mp3 in enumerate(mp3_files, 1):
        lrc = mp3.with_suffix('.lrc')

        if lrc.exists() and not OVERWRITE:
            print(f"[{i:02}/{total}] skip  {mp3.name}")
            skipped += 1
            continue

        print(f"[{i:02}/{total}] ⏳    {mp3.name}")
        try:
            segments, info = model.transcribe(
                str(mp3),
                language=LANGUAGE,
                beam_size=5,
                vad_filter=True,   # ignore les silences / parties instrumentales
            )
            lrc_content = segments_to_lrc(segments)
            lrc.write_text(lrc_content, encoding='utf-8')
            print(f"         ✓    {lrc.name}")
            done += 1
        except Exception as e:
            print(f"         ✗    ERREUR : {e}")
            errors += 1

    print(f"\n── Terminé ─────────────────────────────")
    print(f"  Générés  : {done}")
    print(f"  Ignorés  : {skipped}  (déjà existants)")
    print(f"  Erreurs  : {errors}")

    if done > 0:
        print("\nÉtape suivante : lance inject_lrc.py pour injecter les .lrc dans les tags ID3.")

if __name__ == '__main__':
    main()
