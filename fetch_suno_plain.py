"""
fetch_suno_plain.py — AlbaFrancia FM
Récupère les paroles brutes depuis Suno pour les pistes 8 à 32.
Écrit du texte pur (sans timestamps) dans les .lrc — prêt pour MiniLyrics.

Les 7 premiers fichiers (01-001 à 01-007) ne sont JAMAIS touchés.

Utilisation : lance 03-Fetch Plain LRC.bat
"""

import re, json, sys, os
from pathlib import Path
from urllib import request, error

MUSIC_DIR  = Path(__file__).parent / 'music'
API_BASE   = 'https://studio-api.prod.suno.com'
START_TRACK = 1   # ignorer les pistes 1–7 (faites manuellement)


# ── Numéro de piste dans le nom de fichier ────────────────────────────────────
def track_num(path):
    """Ex: '01-008 Titre.mp3' → 8"""
    m = re.match(r'\d+-(\d+)', path.stem)
    return int(m.group(1)) if m else 999


# ── ID Suno depuis les tags ID3 ───────────────────────────────────────────────
def get_song_id(mp3_path):
    try:
        from mutagen.id3 import ID3
        tags = ID3(str(mp3_path))
        # WOAS : https://suno.com/song/{uuid}
        for key in tags.keys():
            if key.startswith('WOAS'):
                m = re.search(r'/song/([0-9a-f\-]{36})', tags[key].url or '')
                if m:
                    return m.group(1)
        # Fallback COMM
        for key in tags.keys():
            if key.startswith('COMM'):
                txt = tags[key].text or ''
                if isinstance(txt, list):
                    txt = ' '.join(txt)
                m = re.search(r'\bid=([0-9a-f\-]{36})', txt)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


# ── Appel API ─────────────────────────────────────────────────────────────────
def fetch_aligned(song_id, token):
    url = f'{API_BASE}/api/gen/{song_id}/aligned_lyrics/v2/'
    req = request.Request(url, headers={
        'Authorization': token if token.startswith('Bearer ') else f'Bearer {token}',
        'Accept':        'application/json',
        'Origin':        'https://suno.com',
        'Referer':       f'https://suno.com/song/{song_id}',
        'User-Agent':    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    r = request.urlopen(req, timeout=15)
    return json.loads(r.read().decode('utf-8'))


# ── Nettoyage : supprime tout ce qui est entre [ et ] ─────────────────────────
def strip_brackets(text):
    return re.sub(r'\[.*?\]', '', text).strip()


# ── Extraction des paroles en texte pur ───────────────────────────────────────
def extract_plain(data):
    lines = []

    if not isinstance(data, dict):
        return None

    # Priorité 1 : aligned_lyrics
    al = data.get('aligned_lyrics', [])
    if isinstance(al, str):
        try:
            al = json.loads(al)
        except Exception:
            al = []

    for item in (al or []):
        if not isinstance(item, dict):
            continue
        raw = (item.get('text') or item.get('line') or '').strip()
        txt = strip_brackets(raw)
        if txt:
            lines.append(txt)

    if lines:
        return '\n'.join(lines)

    # Priorité 2 : aligned_words → regroupe par saut de ligne
    cur = []
    for w in data.get('aligned_words', []):
        word = re.sub(r'\[.*?\]', '', w.get('word', ''))
        if '\n' in word:
            cur.append(word.rstrip('\n'))
            txt = ''.join(cur).strip()
            if txt:
                lines.append(txt)
            cur = []
        else:
            cur.append(word)
    if cur:
        txt = ''.join(cur).strip()
        if txt:
            lines.append(txt)

    return '\n'.join(lines) if lines else None


# ── Token Suno ────────────────────────────────────────────────────────────────
def get_token():
    print('┌──────────────────────────────────────────────────────┐')
    print('│  Token Suno requis                                   │')
    print('└──────────────────────────────────────────────────────┘')
    print()
    print('  1. Va sur suno.com dans ton navigateur (connecté)')
    print('  2. F12 → onglet "Console"')
    print('  3. Colle cette commande et appuie sur Entrée :')
    print()
    print('     Clerk.session.getToken().then(t => console.log("Bearer " + t))')
    print()
    print('  4. Copie le token affiché (Bearer eyJ...)')
    print()
    return input('  Token : ').strip()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    # Vérifie mutagen
    try:
        import mutagen
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'mutagen', '--quiet'])

    # Fichiers MP3 à partir de la piste START_TRACK
    all_mp3 = sorted(MUSIC_DIR.glob('*.mp3'))
    mp3_files = [f for f in all_mp3 if track_num(f) >= START_TRACK]

    if not mp3_files:
        print(f'Aucun MP3 >= piste {START_TRACK} dans {MUSIC_DIR}')
        return

    print(f'{len(mp3_files)} fichiers à traiter (pistes {START_TRACK}+)')
    print(f'Les pistes 1–{START_TRACK - 1} sont ignorées.')
    print()

    # Token
    token = os.environ.get('SUNO_TOKEN', '').strip()
    if token:
        print('Token lu depuis SUNO_TOKEN (env).')
    else:
        token = get_token()

    if not token:
        print('Token vide, abandon.')
        return
    if not token.startswith('Bearer '):
        token = 'Bearer ' + token

    # Traitement
    total = len(mp3_files)
    done = errors = 0

    for i, mp3 in enumerate(mp3_files, 1):
        lrc = mp3.with_suffix('.lrc')
        song_id = get_song_id(mp3)

        if not song_id:
            print(f'[{i:02}/{total}] ✗  Pas d\'ID Suno : {mp3.name}')
            errors += 1
            continue

        print(f'[{i:02}/{total}] ⏳  {mp3.name}', end=' ', flush=True)

        try:
            data  = fetch_aligned(song_id, token)
            plain = extract_plain(data)

            if plain:
                lrc.write_text(plain, encoding='utf-8')
                line_count = plain.count('\n') + 1
                print(f'✓  ({line_count} lignes)')
                done += 1
            else:
                print(f'⚠  Aucune parole trouvée (clés: {list(data.keys())})')
                errors += 1

        except error.HTTPError as e:
            if e.code == 401:
                print('✗  TOKEN EXPIRÉ')
                print(f'\n   Relance le script avec un nouveau token.')
                break
            elif e.code == 403:
                print('✗  Accès refusé (403) — chanson privée ?')
                errors += 1
            else:
                body = e.read().decode()[:120]
                print(f'✗  HTTP {e.code}: {body}')
                errors += 1
        except Exception as e:
            print(f'✗  {type(e).__name__}: {e}')
            errors += 1

    print()
    print('── Terminé ──────────────────────')
    print(f'  ✓  Écrits  : {done}')
    print(f'  ✗  Erreurs : {errors}')
    if done:
        print()
        print('  Les .lrc sont prêts — ouvre-les dans MiniLyrics pour ajouter les timestamps.')

if __name__ == '__main__':
    main()
