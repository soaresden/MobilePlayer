"""
fetch_suno_lrc.py — AlbaFrancia FM
Télécharge les paroles alignées (timestampées) depuis l'API Suno
et génère des fichiers .lrc dans music/

Prérequis : ton token Bearer Suno (copié depuis les DevTools du navigateur)

  Comment obtenir le token :
  1. Ouvre suno.com dans ton navigateur (connecté)
  2. F12 → onglet "Network" (Réseau)
  3. Filtre par : studio-api.prod.suno.com
  4. Clique sur n'importe quelle requête → Headers → Request Headers
  5. Copie la valeur du header "Authorization" (commence par "Bearer eyJ...")
  6. Colle-la ici quand le script te le demande
"""

import re, json, sys, os
from pathlib import Path
from urllib import request, error
from urllib.parse import urlparse

MUSIC_DIR   = Path(__file__).parent / 'music'
API_BASE    = 'https://studio-api.prod.suno.com'
OVERWRITE   = True    # True pour écraser les .lrc existants

# ── Lecture du WOAS tag (lien Suno) ──────────────────────────────────────────
def get_song_id(mp3_path):
    """Extrait l'ID Suno depuis le tag WOAS du MP3."""
    try:
        from mutagen.id3 import ID3, ID3NoHeaderError
        tags = ID3(str(mp3_path))
        # WOAS : https://suno.com/song/{uuid}
        for key in tags.keys():
            if key.startswith('WOAS'):
                url = tags[key].url
                m = re.search(r'/song/([0-9a-f\-]{36})', url)
                if m:
                    return m.group(1)
        # Fallback : COMM avec champ id=
        for key in tags.keys():
            if key.startswith('COMM'):
                txt = tags[key].text or ''
                m = re.search(r'\bid=([0-9a-f\-]{36})', txt)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None

# ── Appel API ─────────────────────────────────────────────────────────────────
def fetch_aligned_lyrics(song_id, token):
    """Appelle /api/gen/{clip_id}/aligned_lyrics/v2/ et retourne les données."""
    url = f'{API_BASE}/api/gen/{song_id}/aligned_lyrics/v2/'
    req = request.Request(url, headers={
        'Authorization': token if token.startswith('Bearer ') else f'Bearer {token}',
        'Accept':        'application/json',
        'Origin':        'https://suno.com',
        'Referer':       f'https://suno.com/song/{song_id}',
        'User-Agent':    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    try:
        r = request.urlopen(req, timeout=15)
        return json.loads(r.read().decode('utf-8'))
    except error.HTTPError as e:
        body = e.read().decode()[:200]
        raise RuntimeError(f'HTTP {e.code}: {body}')

# ── Conversion aligned_lyrics → LRC ──────────────────────────────────────────
def aligned_to_lrc(data):
    """
    Convertit la réponse API en texte LRC.
    La réponse contient typiquement :
      - data['aligned_lyrics'] : liste de {start_time_ms, end_time_ms, text}
      - ou data['hookLyrics'] / data['lines'] selon la version
    """
    lines = []

    if not isinstance(data, dict):
        return None, f"Structure inattendue : {type(data)}"

    # ── Priorité 1 : aligned_lyrics (ligne complète avec timestamp) ───────────
    al = data.get('aligned_lyrics', [])
    if isinstance(al, str):
        try: al = json.loads(al)
        except Exception: al = []

    for item in (al or []):
        if not isinstance(item, dict): continue
        txt = (item.get('text') or item.get('line') or '').strip()
        # Si le texte commence par [mm:ss], c'est le vrai timestamp → on l'extrait
        m = re.match(r'^(\[(\d{1,2}):(\d{2})(?:\.(\d+))?\])(.*)', txt)
        if m:
            mins, secs, dec = int(m.group(2)), int(m.group(3)), m.group(4) or '0'
            t   = mins * 60 + secs + int(dec) / (10 ** len(dec))
            txt = m.group(5).strip()
        else:
            t = item.get('start_s') or item.get('start_time_ms', 0) / 1000
        if txt:
            lines.append(f'[{int(t//60):02d}:{t%60:05.2f}]{txt}')

    if lines:
        return '\n'.join(lines), None

    # ── Priorité 2 : aligned_words → regroupe par sauts de ligne ─────────────
    words = data.get('aligned_words', [])
    cur_t, cur_words = None, []

    for w in words:
        word = w.get('word', '')
        t_s  = w.get('start_s', 0)

        # Cas spécial : timestamp LRC embarqué dans le mot (ex: "[00:08.40]Po ")
        m = re.match(r'^(\[\d{1,2}:\d{2}\.\d+\])(.*)', word)
        if m:
            if cur_t is not None and cur_words:
                txt = ''.join(cur_words).strip()
                if txt: lines.append(f'{cur_t}{txt}')
            cur_t    = m.group(1)
            cur_words = [m.group(2)]
            continue

        # Premier mot de la ligne courante
        if cur_t is None:
            m2 = int(t_s // 60); s2 = t_s % 60
            cur_t = f'[{m2:02d}:{s2:05.2f}]'

        # Saut de ligne si le mot contient \n
        if '\n' in word:
            cur_words.append(word.rstrip('\n'))
            txt = ''.join(cur_words).strip()
            if txt: lines.append(f'{cur_t}{txt}')
            cur_t, cur_words = None, []
        else:
            cur_words.append(word)

    # Flush dernier groupe
    if cur_t and cur_words:
        txt = ''.join(cur_words).strip()
        if txt: lines.append(f'{cur_t}{txt}')

    if lines:
        return '\n'.join(lines), None

    return None, f"Aucune donnée exploitable (clés: {list(data.keys())})"

# ── Fallback : USLT + durée uniforme ─────────────────────────────────────────
def uslt_fallback(mp3_path, duration_s=None):
    """Génère LRC depuis USLT si pas de réponse API."""
    try:
        from mutagen.id3 import ID3, ID3NoHeaderError
        from mutagen.mp3 import MP3
        tags  = ID3(str(mp3_path))
        audio = MP3(str(mp3_path))
        dur   = duration_s or audio.info.length

        lyric_lines = []
        for key in tags.keys():
            if key.startswith('USLT'):
                raw = tags[key].text or ''
                lyric_lines = [re.sub(r'^\[\d+:\d+(?:\.\d+)?\]', '', l).strip()
                               for l in raw.splitlines()]
                lyric_lines = [l for l in lyric_lines if l]
                break
        if not lyric_lines:
            return None

        lrc_lines = []
        for i, txt in enumerate(lyric_lines):
            t = i / len(lyric_lines) * dur
            m = int(t // 60); s = t % 60
            lrc_lines.append(f'[{m:02d}:{s:05.2f}]{txt}')
        return '\n'.join(lrc_lines)
    except Exception:
        return None

# ── Récupération automatique du token via presse-papier ──────────────────────
def read_clipboard():
    """Lit le presse-papier Windows sans dépendance externe."""
    try:
        import ctypes
        CF_UNICODETEXT = 13
        ctypes.windll.user32.OpenClipboard(0)
        handle = ctypes.windll.user32.GetClipboardData(CF_UNICODETEXT)
        if handle:
            result = ctypes.wstring_at(handle)
            ctypes.windll.user32.CloseClipboard()
            return result.strip()
        ctypes.windll.user32.CloseClipboard()
    except Exception:
        pass
    return ''

def get_token_via_browser():
    print('┌──────────────────────────────────────────────────────┐')
    print('│  Récupération du token Suno                          │')
    print('└──────────────────────────────────────────────────────┘')
    print()
    print('  1. Va sur suno.com dans ton navigateur (connecté)')
    print('  2. F12 → onglet "Console"')
    print('  3. Colle cette commande et appuie sur Entrée :')
    print()
    print('     Clerk.session.getToken().then(t => console.log("Bearer " + t))')
    print()
    print('  4. Le token s\'affiche dans la console (Bearer eyJ...)')
    print('  5. Copie-le et colle-le ici')
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

    mp3_files = sorted(MUSIC_DIR.glob('*.mp3'))
    if not mp3_files:
        print(f'Aucun MP3 trouvé dans {MUSIC_DIR}')
        return

    # ── Token ────────────────────────────────────────────────────────────────
    token_env = os.environ.get('SUNO_TOKEN', '')
    if token_env:
        token = token_env.strip()
        print(f'Token lu depuis SUNO_TOKEN (env).')
    else:
        token = get_token_via_browser()

    if not token:
        print('Token vide, abandon.')
        return

    if not token.startswith('Bearer '):
        token = 'Bearer ' + token

    # ── Traitement ───────────────────────────────────────────────────────────
    total = len(mp3_files)
    done, skipped, errors, fallbacks = 0, 0, 0, 0

    for i, mp3 in enumerate(mp3_files, 1):
        lrc_path = mp3.with_suffix('.lrc')

        if lrc_path.exists() and not OVERWRITE:
            print(f'[{i:02}/{total}] skip   {mp3.name}')
            skipped += 1
            continue

        song_id = get_song_id(mp3)
        if not song_id:
            print(f'[{i:02}/{total}] ✗  Pas de WOAS : {mp3.name}')
            errors += 1
            continue

        print(f'[{i:02}/{total}] ⏳  {mp3.name}  [{song_id[:8]}...]', end=' ', flush=True)

        try:
            data = fetch_aligned_lyrics(song_id, token)
            lrc_text, err = aligned_to_lrc(data)

            if lrc_text:
                lrc_path.write_text(lrc_text, encoding='utf-8')
                line_count = lrc_text.count('\n') + 1
                print(f'✓ ({line_count} lignes)')
                done += 1
            else:
                print(f'⚠  API OK mais structure inconnue ({err})')
                # Debug : affiche la réponse brute
                print(f'       Réponse : {json.dumps(data)[:200]}')
                # Fallback USLT
                fb = uslt_fallback(mp3)
                if fb:
                    lrc_path.write_text(fb, encoding='utf-8')
                    print(f'       → Fallback USLT écrit')
                    fallbacks += 1
                else:
                    errors += 1

        except RuntimeError as e:
            msg = str(e)
            if '401' in msg:
                print(f'✗  TOKEN EXPIRÉ — recolle un nouveau token')
                print(f'\n   Interruption (401 sur {mp3.name})')
                break
            elif '403' in msg:
                print(f'✗  Accès refusé (403) — chanson privée ?')
                errors += 1
            else:
                print(f'✗  {msg[:80]}')
                errors += 1
        except Exception as e:
            print(f'✗  {type(e).__name__}: {e}')
            errors += 1

    print(f'\n── Terminé ──────────────────────')
    print(f'  ✓  API Suno  : {done}')
    print(f'  ⚠  Fallback  : {fallbacks}')
    print(f'  →  Ignorés   : {skipped}')
    print(f'  ✗  Erreurs   : {errors}')
    if done or fallbacks:
        print('\nÉtape suivante : vérifie quelques .lrc puis lance inject_lrc.py')

if __name__ == '__main__':
    main()
