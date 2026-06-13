# ============================================================
#  YouTube → MP3 İndirici  |  Render Flask Uygulaması
# ============================================================
#
#  Render Environment Variables:
#    YT_COOKIES  →  cookies.txt içeriğini buraya yapıştır
#
#  Start Command: gunicorn app:app --timeout 120
# ============================================================

import os
import re
import uuid
import time
import tempfile
import threading
from flask import Flask, request, jsonify, send_file, render_template_string

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

app = Flask(__name__)

# İndirilen dosyalar için klasör
DOWNLOAD_FOLDER = '/tmp/yt_mp3_temp'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ---------------------------------------------------------------
# 30 dakika sonra dosyaları otomatik sil
# ---------------------------------------------------------------
def cleanup_old_files():
    while True:
        try:
            now = time.time()
            for fname in os.listdir(DOWNLOAD_FOLDER):
                fpath = os.path.join(DOWNLOAD_FOLDER, fname)
                if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > 1800:
                    os.remove(fpath)
        except Exception:
            pass
        time.sleep(300)

cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

# ---------------------------------------------------------------
# Güvenli dosya adı
# ---------------------------------------------------------------
def safe_name(s):
    s = re.sub(r'[^\w\s\-]', '', s, flags=re.UNICODE)
    return s.strip()[:60] or 'audio'

# ---------------------------------------------------------------
# Çerez dosyası (Render env var'dan)
# ---------------------------------------------------------------
def get_cookies_file():
    content = os.environ.get('YT_COOKIES', '').strip()
    if not content:
        return None
    content = content.replace('\\n', '\n')
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.txt', delete=False, encoding='utf-8'
    )
    tmp.write(content)
    tmp.close()
    return tmp.name

# ---------------------------------------------------------------
# HTML Arayüz
# ---------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>YT → MP3</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:       #09090f;
      --surface:  #131320;
      --border:   #2a2a42;
      --accent:   #e8365d;
      --accent2:  #ff6b35;
      --text:     #eeeef5;
      --muted:    #6060a0;
      --success:  #2dd67a;
      --radius:   14px;
    }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'DM Sans', sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px 16px;
    }

    /* --- Arka plan ızgara deseni --- */
    body::before {
      content: '';
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(var(--border) 1px, transparent 1px),
        linear-gradient(90deg, var(--border) 1px, transparent 1px);
      background-size: 40px 40px;
      opacity: 0.25;
      pointer-events: none;
    }

    .card {
      position: relative;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 40px 36px;
      width: 100%;
      max-width: 540px;
      box-shadow: 0 24px 64px rgba(0,0,0,.55);
    }

    /* Kart üst kırmızı çizgi */
    .card::before {
      content: '';
      position: absolute;
      top: -1px; left: 20px; right: 20px;
      height: 3px;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      border-radius: 0 0 4px 4px;
    }

    h1 {
      font-size: 1.7rem;
      font-weight: 700;
      letter-spacing: -0.5px;
      margin-bottom: 6px;
    }
    h1 span { color: var(--accent); }

    .subtitle {
      font-size: 0.88rem;
      color: var(--muted);
      margin-bottom: 32px;
      line-height: 1.5;
    }

    label {
      display: block;
      font-size: 0.78rem;
      font-weight: 500;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-bottom: 8px;
    }

    .input-wrap {
      position: relative;
      margin-bottom: 18px;
    }

    input[type="url"] {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      color: var(--text);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      padding: 14px 48px 14px 16px;
      outline: none;
      transition: border-color .2s;
    }
    input[type="url"]::placeholder { color: var(--muted); }
    input[type="url"]:focus { border-color: var(--accent); }

    .paste-btn {
      position: absolute;
      right: 10px; top: 50%;
      transform: translateY(-50%);
      background: none;
      border: none;
      color: var(--muted);
      cursor: pointer;
      font-size: 1.1rem;
      padding: 4px;
      transition: color .2s;
    }
    .paste-btn:hover { color: var(--accent); }

    /* Format seçici */
    .format-row {
      display: flex;
      gap: 8px;
      margin-bottom: 22px;
    }
    .fmt-btn {
      flex: 1;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--muted);
      font-family: 'DM Sans', sans-serif;
      font-size: 0.82rem;
      font-weight: 500;
      padding: 10px 6px;
      cursor: pointer;
      transition: all .2s;
    }
    .fmt-btn.active {
      background: rgba(232,54,93,.12);
      border-color: var(--accent);
      color: var(--accent);
    }

    button#dlBtn {
      width: 100%;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border: none;
      border-radius: 10px;
      color: #fff;
      font-family: 'DM Sans', sans-serif;
      font-size: 1rem;
      font-weight: 700;
      padding: 16px;
      cursor: pointer;
      letter-spacing: .02em;
      transition: opacity .2s, transform .1s;
    }
    button#dlBtn:hover  { opacity: .88; transform: translateY(-1px); }
    button#dlBtn:active { transform: translateY(0); }
    button#dlBtn:disabled { opacity: .45; cursor: not-allowed; transform: none; }

    /* Dalga animasyonu */
    .waves {
      display: none;
      align-items: flex-end;
      justify-content: center;
      gap: 4px;
      height: 28px;
      margin: 18px 0 8px;
    }
    .waves.show { display: flex; }
    .waves span {
      display: block;
      width: 4px;
      background: linear-gradient(to top, var(--accent), var(--accent2));
      border-radius: 2px;
      animation: wave 1s ease-in-out infinite;
    }
    .waves span:nth-child(2)  { animation-delay: .1s; }
    .waves span:nth-child(3)  { animation-delay: .2s; }
    .waves span:nth-child(4)  { animation-delay: .3s; }
    .waves span:nth-child(5)  { animation-delay: .4s; }
    .waves span:nth-child(6)  { animation-delay: .3s; }
    .waves span:nth-child(7)  { animation-delay: .2s; }
    .waves span:nth-child(8)  { animation-delay: .1s; }
    @keyframes wave {
      0%, 100% { height: 6px; }
      50%       { height: 22px; }
    }

    #status {
      font-size: 0.85rem;
      color: var(--muted);
      text-align: center;
      min-height: 20px;
      margin-top: 14px;
    }
    #status.error   { color: var(--accent); }
    #status.success { color: var(--success); }

    .dl-link {
      display: none;
      margin-top: 18px;
      background: rgba(45, 214, 122, .1);
      border: 1px solid var(--success);
      border-radius: 10px;
      padding: 14px 18px;
      text-align: center;
    }
    .dl-link.show { display: block; }
    .dl-link a {
      color: var(--success);
      font-weight: 700;
      text-decoration: none;
      font-size: 0.95rem;
    }
    .dl-link a:hover { text-decoration: underline; }
    .dl-link small { display: block; color: var(--muted); font-size: 0.75rem; margin-top: 4px; }

    footer {
      margin-top: 24px;
      font-size: 0.75rem;
      color: var(--muted);
      text-align: center;
      line-height: 1.6;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>YT <span>→</span> Ses</h1>
    <p class="subtitle">YouTube linkini yapıştır, sesi telefona veya bilgisayara indir.</p>

    <label>YouTube Linki</label>
    <div class="input-wrap">
      <input type="url" id="urlInput" placeholder="https://youtube.com/watch?v=..." autocomplete="off">
      <button class="paste-btn" title="Yapıştır" onclick="pasteUrl()">📋</button>
    </div>

    <label>Format</label>
    <div class="format-row">
      <button class="fmt-btn active" onclick="setFmt(this,'mp3')">🎵 MP3</button>
      <button class="fmt-btn" onclick="setFmt(this,'m4a')">🍎 M4A</button>
      <button class="fmt-btn" onclick="setFmt(this,'opus')">🔊 OPUS</button>
    </div>

    <button id="dlBtn" onclick="startDownload()">⬇ İndir</button>

    <div class="waves" id="waves">
      <span></span><span></span><span></span><span></span>
      <span></span><span></span><span></span><span></span>
    </div>

    <div id="status"></div>

    <div class="dl-link" id="dlLink">
      <a id="dlAnchor" href="#" download>⬇ Dosyayı Kaydet</a>
      <small>Bağlantı 30 dakika geçerlidir.</small>
    </div>
  </div>

  <footer>
    Sadece kişisel kullanım için &mdash; telif hakkına saygı göster.
  </footer>

  <script>
    let selectedFmt = 'mp3';

    function setFmt(btn, fmt) {
      document.querySelectorAll('.fmt-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedFmt = fmt;
    }

    async function pasteUrl() {
      try {
        const text = await navigator.clipboard.readText();
        document.getElementById('urlInput').value = text;
      } catch {
        document.getElementById('urlInput').focus();
      }
    }

    function setStatus(msg, cls = '') {
      const el = document.getElementById('status');
      el.textContent = msg;
      el.className = cls;
    }

    async function startDownload() {
      const url = document.getElementById('urlInput').value.trim();
      if (!url) { setStatus('Lütfen bir YouTube linki gir.', 'error'); return; }

      const dlBtn  = document.getElementById('dlBtn');
      const waves  = document.getElementById('waves');
      const dlLink = document.getElementById('dlLink');

      dlBtn.disabled = true;
      waves.classList.add('show');
      dlLink.classList.remove('show');
      setStatus('Ses indiriliyor, lütfen bekle…');

      try {
        const res = await fetch('/api/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, format: selectedFmt })
        });
        const data = await res.json();

        if (!res.ok || data.error) {
          setStatus('Hata: ' + (data.error || 'Bilinmeyen bir sorun oluştu.'), 'error');
        } else {
          setStatus('Hazır! "' + data.title + '"', 'success');
          const anchor = document.getElementById('dlAnchor');
          anchor.href = '/api/file/' + data.file_id;
          anchor.download = data.title + '.' + selectedFmt;
          dlLink.classList.add('show');
        }
      } catch (e) {
        setStatus('Sunucuya ulaşılamadı: ' + e.message, 'error');
      } finally {
        dlBtn.disabled = false;
        waves.classList.remove('show');
      }
    }
  </script>
</body>
</html>"""


# ---------------------------------------------------------------
# API: İndir
# ---------------------------------------------------------------
@app.route('/api/download', methods=['POST'])
def api_download():
    if yt_dlp is None:
        return jsonify({'error': 'yt-dlp kurulu değil. pip install yt-dlp'}), 500

    body = request.get_json(force=True, silent=True) or {}
    url  = (body.get('url') or '').strip()
    fmt  = (body.get('format') or 'mp3').lower()

    if fmt not in ('mp3', 'm4a', 'opus', 'webm'):
        fmt = 'mp3'

    if not url:
        return jsonify({'error': 'URL boş.'}), 400

    file_id  = str(uuid.uuid4())
    out_tmpl = os.path.join(DOWNLOAD_FOLDER, f'{file_id}.%(ext)s')

    # Formatla eşleşen codec
    codec_map = {'mp3': 'mp3', 'm4a': 'm4a', 'opus': 'opus', 'webm': 'opus'}
    codec = codec_map[fmt]

    ydl_opts = {
        'format':          'bestaudio/best',
        'outtmpl':         out_tmpl,
        'quiet':           True,
        'no_warnings':     True,
        'postprocessors': [{
            'key':              'FFmpegExtractAudio',
            'preferredcodec':   codec,
            'preferredquality': '192',
        }],
    }

    # YouTube bot korumasını aşmak için çerezleri kullan
    cookies_file = get_cookies_file()
    if cookies_file:
        ydl_opts['cookiefile'] = cookies_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info  = ydl.extract_info(url, download=True)
            title = safe_name(info.get('title', 'ses'))
    except Exception as exc:
        # ffmpeg yoksa dönüşümsüz dene
        ydl_opts.pop('postprocessors', None)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info  = ydl.extract_info(url, download=True)
                title = safe_name(info.get('title', 'ses'))
                ext   = info.get('ext', 'webm')
                fmt   = ext
        except Exception as exc2:
            if cookies_file:
                try: os.remove(cookies_file)
                except: pass
            return jsonify({'error': str(exc2)}), 500
    finally:
        if cookies_file:
            try: os.remove(cookies_file)
            except: pass

    # İndirilen dosyayı bul
    found_path = None
    for ext_try in (fmt, 'mp3', 'm4a', 'opus', 'webm', 'ogg'):
        candidate = os.path.join(DOWNLOAD_FOLDER, f'{file_id}.{ext_try}')
        if os.path.exists(candidate):
            found_path = candidate
            fmt = ext_try
            break

    if not found_path:
        return jsonify({'error': 'Dosya oluşturulamadı.'}), 500

    # Title'ı uuid'e eşle (dosya servisinde kullanmak için)
    title_file = os.path.join(DOWNLOAD_FOLDER, f'{file_id}.title')
    with open(title_file, 'w', encoding='utf-8') as tf:
        tf.write(f'{title}||{fmt}')

    return jsonify({'file_id': file_id, 'title': title, 'format': fmt})


# ---------------------------------------------------------------
# API: Dosyayı sun
# ---------------------------------------------------------------
@app.route('/api/file/<file_id>')
def api_file(file_id):
    # Güvenlik: sadece UUID formatı
    if not re.fullmatch(r'[0-9a-f\-]{36}', file_id):
        return 'Geçersiz ID.', 400

    title_file = os.path.join(DOWNLOAD_FOLDER, f'{file_id}.title')
    title, fmt = 'ses', 'mp3'
    if os.path.exists(title_file):
        with open(title_file, encoding='utf-8') as tf:
            parts = tf.read().split('||')
            if len(parts) == 2:
                title, fmt = parts

    filepath = os.path.join(DOWNLOAD_FOLDER, f'{file_id}.{fmt}')
    if not os.path.exists(filepath):
        return 'Dosya bulunamadı veya süresi doldu.', 404

    mime_map = {'mp3': 'audio/mpeg', 'm4a': 'audio/mp4',
                'opus': 'audio/ogg',  'webm': 'audio/webm', 'ogg': 'audio/ogg'}
    mime = mime_map.get(fmt, 'audio/mpeg')

    return send_file(
        filepath,
        mimetype=mime,
        as_attachment=True,
        download_name=f'{title}.{fmt}'
    )


# ---------------------------------------------------------------
# Ana sayfa
# ---------------------------------------------------------------
@app.route('/')
def index():
    return render_template_string(HTML)


# ---------------------------------------------------------------
# Lokal test (PythonAnywhere'de gerekli değil)
# ---------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, port=5000)

