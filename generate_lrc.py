"""
generate_lrc.py — AlbaFrancia FM
Stratégie :
  Si le MP3 a des paroles USLT :
    → Whisper transcrit librement pour obtenir les timecodes
    → Les timecodes sont distribués sur les lignes USLT (texte correct)
  Sinon :
    → Transcription libre Whisper

Compatible Python 3.8→3.13. Pas besoin de ffmpeg.
Usage :  python generate_lrc.py
"""

import subprocess, sys, re
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
MUSIC_DIR  = Path(__file__).parent / 'music'
MODEL_SIZE = 'medium'   # tiny | base | small | medium | large-v2 | large-v3
LANGUAGE   = 'sq'
OVERWRITE  = False
# ─────────────────────────────────────────────────────────────────────────────

def install(pkg):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '--quiet'])

for pkg, name in [('faster_whisper','faster-whisper'), ('mutagen','mutagen')]:
    try: __import__(pkg)
    except ImportError:
        print(f"Installation de {name}..."); install(name)

from faster_whisper import WhisperModel
from mutagen.id3 import ID3, ID3NoHeaderError

# ── Lecture USLT ──────────────────────────────────────────────────────────────
def read_uslt(mp3_path):
    """Retourne les lignes de paroles depuis USLT (sans timestamps LRC)."""
    try:
        tags = ID3(str(mp3_path))
        for key in tags.keys():
            if key.startswith('USLT'):
                raw = tags[key].text or ''
                lines = [re.sub(r'^\[\d+:\d+(?:\.\d+)?\]', '', l).strip()
                         for l in raw.splitlines()]
                lines = [l for l in lines if l]
                if lines:
                    return lines
    except (ID3NoHeaderError, Exception):
        pass
    return None

# ── Alignement paroles → timecodes ────────────────────────────────────────────
def align(lyric_lines, segments):
    """
    Distribue les timecodes Whisper sur les lignes de paroles.
    Filtre d'abord les segments vides/silences.
    """
    segs = [s for s in segments if s.text.strip()]
    if not segs:
        return []

    M = len(lyric_lines)
    N = len(segs)
    t_start = segs[0].start
    t_end   = segs[-1].end if hasattr(segs[-1],'end') else segs[-1].start + 4

    result = []
    for i, line in enumerate(lyric_lines):
        # Position proportionnelle dans les segments
        seg_idx = min(int(i / M * N), N - 1)
        t = segs[seg_idx].start
        result.append((t, line))
    return result

# ── LRC ───────────────────────────────────────────────────────────────────────
def fmt(t):
    m = int(t // 60); s = t % 60
    return f"[{m:02d}:{s:05.2f}]"

def to_lrc(pairs):
    return '\n'.join(f"{fmt(t)}{tx}" for t, tx in pairs)

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    mp3_files = sorted(MUSIC_DIR.glob('*.mp3'))
    if not mp3_files:
        print(f"Aucun MP3 trouvé dans {MUSIC_DIR}"); return

    print(f"\nChargement du modèle Whisper '{MODEL_SIZE}'...\n")

    import threading, time
    _cache = Path.home() / '.cache' / 'huggingface' / 'hub' / f'models--Systran--faster-whisper-{MODEL_SIZE}'
    def _mb():
        try: return sum(f.stat().st_size for f in _cache.rglob('*') if f.is_file()) / 1_048_576
        except: return 0.0
    _stop = threading.Event()
    def _spin():
        chars='|/-\\'; t0=time.time(); i=0
        while not _stop.is_set():
            sys.stdout.write(f'\r  {chars[i%4]}  {int(time.time()-t0)}s  —  cache: {_mb():.0f} Mo   ')
            sys.stdout.flush(); i+=1; _stop.wait(1)
        sys.stdout.write('\r'+' '*80+'\r')
    _t = threading.Thread(target=_spin, daemon=True); _t.start()

    model = WhisperModel(MODEL_SIZE, device='cpu', compute_type='int8')
    _stop.set(); _t.join()
    print("Modèle chargé.\n")

    total = len(mp3_files)
    done, skipped, errors = 0, 0, 0

    for i, mp3 in enumerate(mp3_files, 1):
        lrc_path = mp3.with_suffix('.lrc')
        if lrc_path.exists() and not OVERWRITE:
            print(f"[{i:02}/{total}] skip   {mp3.name}"); skipped += 1; continue

        lyric_lines = read_uslt(mp3)
        mode = f'USLT ({len(lyric_lines)} lignes)' if lyric_lines else 'libre'
        print(f"[{i:02}/{total}] ⏳  {mp3.name}  [{mode}]")

        try:
            # Transcription libre : pas de prompt, VAD off → timecodes bruts
            seg_gen, _ = model.transcribe(
                str(mp3),
                language=LANGUAGE,
                beam_size=5,
                vad_filter=False,
                condition_on_previous_text=False,
                temperature=0.0,
            )
            segments = list(seg_gen)
            print(f"        Whisper : {len(segments)} segments détectés")

            if lyric_lines:
                # Mode guidé : on utilise le texte USLT + les timecodes Whisper
                pairs = align(lyric_lines, segments)
                if pairs:
                    lrc_path.write_text(to_lrc(pairs), encoding='utf-8')
                    print(f"        ✓  {lrc_path.name}  ({len(pairs)} lignes alignées)")
                    done += 1
                else:
                    # Pas de segments Whisper → distribuer linéairement sur 3 min
                    fallback = [(i * 180 / len(lyric_lines), l)
                                for i, l in enumerate(lyric_lines)]
                    lrc_path.write_text(to_lrc(fallback), encoding='utf-8')
                    print(f"        ⚠  Fallback temporel ({len(lyric_lines)} lignes)")
                    done += 1
            else:
                # Mode libre : texte ET timecodes de Whisper
                if segments:
                    lrc_path.write_text(
                        '\n'.join(f"{fmt(s.start)}{s.text.strip()}" for s in segments),
                        encoding='utf-8')
                    print(f"        ✓  {lrc_path.name}  ({len(segments)} segments)")
                    done += 1
                else:
                    print(f"        ✗  Aucun segment détecté"); errors += 1

        except Exception as e:
            print(f"        ✗  ERREUR : {e}"); errors += 1

    print(f"\n── Terminé ──────────────────────────")
    print(f"  Générés  : {done}")
    print(f"  Ignorés  : {skipped}")
    print(f"  Erreurs  : {errors}")
    if done:
        print("\nÉtape suivante : vérifie quelques .lrc puis lance inject_lrc.py")

if __name__ == '__main__':
    main()
