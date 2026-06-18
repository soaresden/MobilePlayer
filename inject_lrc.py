"""
inject_lrc.py — AlbaFrancia FM
Injecte les fichiers .lrc dans les tags ID3 USLT des MP3 de suno/.
À lancer après generate_lrc.py.

Usage :  python inject_lrc.py
"""

import subprocess, sys
from pathlib import Path

def install(pkg):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '--quiet'])

try:
    from mutagen.id3 import ID3, USLT, ID3NoHeaderError
except ImportError:
    install('mutagen')
    from mutagen.id3 import ID3, USLT, ID3NoHeaderError

SUNO_DIR = Path(__file__).parent / 'music'

def main():
    lrc_files = sorted(SUNO_DIR.glob('*.lrc'))
    if not lrc_files:
        print("Aucun .lrc trouvé dans suno/ — lance d'abord generate_lrc.py")
        return

    total = len(lrc_files)
    done, errors = 0, 0

    for i, lrc in enumerate(lrc_files, 1):
        mp3 = lrc.with_suffix('.mp3')
        if not mp3.exists():
            print(f"[{i:02}/{total}] skip  {lrc.name}  (pas de MP3 correspondant)")
            continue

        try:
            lyrics = lrc.read_text(encoding='utf-8')
            try:
                tags = ID3(str(mp3))
            except ID3NoHeaderError:
                tags = ID3()

            # Supprimer les anciens USLT puis injecter
            tags.delall('USLT')
            tags.add(USLT(encoding=3, lang='sqi', desc='', text=lyrics))
            tags.save(str(mp3), v2_version=3)

            print(f"[{i:02}/{total}] ✓  {mp3.name}")
            done += 1
        except Exception as e:
            print(f"[{i:02}/{total}] ✗  {mp3.name}  ERREUR : {e}")
            errors += 1

    print(f"\n── Terminé ──────────────────────────")
    print(f"  Injectés : {done}")
    print(f"  Erreurs  : {errors}")

if __name__ == '__main__':
    main()
