"""
CompanyAI Desktop Viewer
Kurumsal AI Asistanı — Masaüstü Uygulaması

Sunucudaki web arayüzünü native bir pencerede açar.
PyInstaller ile .exe olarak paketlenebilir.
"""

import webview
import threading
import time
import sys
import os
import subprocess
import urllib.request
import urllib.error
import ssl

# ── Sunucu Ayarları ──────────────────────────────────────
SERVER_ID = 1  # 1 = Sunucu 1 (LAN), 2 = Sunucu 2 (WAN)  ← build_all.py otomatik değiştirir

SERVERS = {
    1: {"url": "http://192.168.0.12",          "name": "Sunucu 1"},
    2: {"url": "https://88.246.13.23:2015",    "name": "Sunucu 2"},
}

# ── Ayarlar ──────────────────────────────────────────────
APP_TITLE = "CompanyAI — Kurumsal AI Asistanı"
APP_VERSION = "2.7.0"
SERVER_URL = SERVERS[SERVER_ID]["url"]
SERVER_NAME = SERVERS[SERVER_ID]["name"]
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820
MIN_WIDTH = 900
MIN_HEIGHT = 600
CHECK_INTERVAL = 2          # Sunucu kontrol aralığı (sn)
MAX_RETRIES = 0             # 0 = sınırsız deneme


# ── Yükleme / Hata HTML ─────────────────────────────────
LOADING_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        background: #0f1117;
        color: #e2e8f0;
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        height: 100vh; overflow: hidden;
    }
    .logo { font-size: 2.4rem; font-weight: 800; margin-bottom: 1.2rem; }
    .logo span { color: #6366f1; }
    .spinner {
        width: 44px; height: 44px;
        border: 3px solid #1e1e2e;
        border-top-color: #6366f1;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin-bottom: 1.5rem;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .status { color: #94a3b8; font-size: 0.95rem; margin-bottom: 0.3rem; }
    .sub { color: #475569; font-size: 0.8rem; }
    .dots::after {
        content: '';
        animation: dots 1.5s steps(4, end) infinite;
    }
    @keyframes dots {
        0%   { content: ''; }
        25%  { content: '.'; }
        50%  { content: '..'; }
        75%  { content: '...'; }
        100% { content: ''; }
    }
    .footer {
        position: absolute; bottom: 16px;
        display: flex; flex-direction: column; align-items: center; gap: 6px;
    }
    .sig { color: #334155; font-size: 0.65rem; letter-spacing: 0.25em; text-transform: uppercase; }
    .sig b { color: #475569; letter-spacing: 0.18em; font-weight: 500; }
    .ver {
        color: #475569; font-size: 0.65rem; font-family: monospace;
        padding: 2px 10px; border: 1px solid #1e293b; border-radius: 99px;
    }
</style>
</head>
<body>
    <div class="logo">Company<span>AI</span></div>
    <div class="spinner"></div>
    <p class="status">Sunucuya bağlanılıyor<span class="dots"></span></p>
    <p class="sub" id="timer"></p>
    <div class="footer">
        <span class="sig">Designed by <b>Murteza ALEMDAR</b></span>
        <span class="ver">v""" + APP_VERSION + """</span>
    </div>
    <script>
        var start = Date.now();
        setInterval(function() {
            var s = Math.floor((Date.now() - start) / 1000);
            document.getElementById('timer').textContent = s + ' saniye bekleniyor...';
        }, 1000);
    </script>
</body>
</html>
"""

ERROR_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        background: #0f1117; color: #e2e8f0;
        font-family: 'Segoe UI', system-ui, sans-serif;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        height: 100vh;
    }
    .icon { font-size: 3rem; margin-bottom: 1rem; }
    h2 { color: #f87171; margin-bottom: 0.5rem; }
    p { color: #94a3b8; font-size: 0.95rem; margin-bottom: 1.5rem; text-align: center; max-width: 400px; }
    .btn {
        padding: 0.6rem 2rem; background: #6366f1; color: white;
        border: none; border-radius: 8px; font-size: 0.95rem; cursor: pointer;
    }
    .btn:hover { background: #4f46e5; }
    .footer {
        position: absolute; bottom: 16px;
        display: flex; flex-direction: column; align-items: center; gap: 6px;
    }
    .sig { color: #334155; font-size: 0.65rem; letter-spacing: 0.25em; text-transform: uppercase; }
    .sig b { color: #475569; letter-spacing: 0.18em; font-weight: 500; }
</style>
</head>
<body>
    <div class="icon">⚠️</div>
    <h2>Sunucuya Ulaşılamıyor</h2>
    <p>CompanyAI sunucusu (""" + SERVER_URL + """) yanıt vermiyor.<br>
    Lütfen sunucunun çalıştığından ve ağ bağlantınızdan emin olun.</p>
    <button class="btn" onclick="location.reload()">Tekrar Dene</button>
    <div class="footer">
        <span class="sig">Designed by <b>Murteza ALEMDAR</b></span>
    </div>
</body>
</html>
"""


def create_desktop_shortcut():
    """İlk çalıştırmada masaüstüne kısayol oluştur (sadece Windows)"""
    try:
        if not getattr(sys, 'frozen', False):
            return  # Sadece exe olarak çalışırken
        if sys.platform != 'win32':
            return  # Sadece Windows'ta kısayol oluştur
        exe_path = os.path.abspath(sys.executable)
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_name = f"CompanyAI ({SERVER_NAME}).lnk"
        shortcut_path = os.path.join(desktop, shortcut_name)
        if os.path.exists(shortcut_path):
            return  # Zaten var
        ps = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$sc = $ws.CreateShortcut("{shortcut_path}"); '
            f'$sc.TargetPath = "{exe_path}"; '
            f'$sc.WorkingDirectory = "{os.path.dirname(exe_path)}"; '
            f'$sc.Description = "CompanyAI Kurumsal AI Asistanı — {SERVER_NAME}"; '
            f'$sc.IconLocation = "{exe_path},0"; '
            f'$sc.Save()'
        )
        subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass  # Kısayol oluşturulamazsa sessizce geç


def check_server(url: str, timeout: int = 5) -> str | None:
    """Sunucunun erişilebilir olup olmadığını kontrol et (HTTP/HTTPS)."""
    try:
        health = url.rstrip("/") + "/api/health"
        req = urllib.request.Request(health, method="GET")
        # Self-signed sertifika desteği (Sunucu 2 HTTPS)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        if resp.status == 200:
            return url
    except Exception:
        pass
    return None


def wait_and_navigate(window: webview.Window):
    """Arka planda sunucuyu kontrol et, hazır olunca yönlendir"""
    retries = 0
    while True:
        final_url = check_server(SERVER_URL)
        if final_url:
            # Sunucu hazır — ana sayfaya yönlendir
            try:
                window.load_url(final_url)
            except Exception:
                pass
            return

        retries += 1
        if MAX_RETRIES > 0 and retries >= MAX_RETRIES:
            try:
                window.load_html(ERROR_HTML)
            except Exception:
                pass
            return

        time.sleep(CHECK_INTERVAL)


def main():
    # İlk çalıştırmada masaüstüne kısayol oluştur
    create_desktop_shortcut()

    # Ana pencereyi oluştur (loading ekranıyla)
    window = webview.create_window(
        title=f"{APP_TITLE} — {SERVER_NAME}  v{APP_VERSION}",
        html=LOADING_HTML,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(MIN_WIDTH, MIN_HEIGHT),
        resizable=True,
        text_select=True,
        zoomable=True,
    )

    # Sunucu kontrolünü arka planda başlat
    bg_thread = threading.Thread(target=wait_and_navigate, args=(window,), daemon=True)

    def on_loaded():
        """Pencere yüklendiğinde sunucu kontrolünü başlat"""
        bg_thread.start()

    window.events.loaded += on_loaded

    # pywebview başlat (ana thread'de — Windows gereksinimi)
    webview.start(
        debug=("--debug" in sys.argv),
        private_mode=False,       # Cookie/session saklansın
    )


if __name__ == "__main__":
    main()
