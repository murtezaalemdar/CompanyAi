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
import urllib.request
import urllib.error

# ── Ayarlar ──────────────────────────────────────────────
APP_TITLE = "CompanyAI — Kurumsal AI Asistanı"
APP_VERSION = "2.6.0"
SERVER_URL = "http://192.168.0.12"
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
    .status { color: #94a3b8; font-size: 0.95rem; }
    .status.error { color: #f87171; }
    .retry-btn {
        margin-top: 1.2rem; padding: 0.6rem 1.8rem;
        background: #6366f1; color: white; border: none;
        border-radius: 8px; font-size: 0.95rem; cursor: pointer;
        display: none;
    }
    .retry-btn:hover { background: #4f46e5; }
    .version {
        position: absolute; bottom: 16px;
        color: #475569; font-size: 0.75rem;
    }
</style>
</head>
<body>
    <div class="logo">Company<span>AI</span></div>
    <div class="spinner" id="spinner"></div>
    <p class="status" id="status">Sunucuya bağlanılıyor...</p>
    <button class="retry-btn" id="retryBtn" onclick="location.reload()">Tekrar Dene</button>
    <div class="version">v""" + APP_VERSION + """</div>
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
</style>
</head>
<body>
    <div class="icon">⚠️</div>
    <h2>Sunucuya Ulaşılamıyor</h2>
    <p>CompanyAI sunucusu (""" + SERVER_URL + """) yanıt vermiyor.<br>
    Lütfen sunucunun çalıştığından ve ağ bağlantınızdan emin olun.</p>
    <button class="btn" onclick="location.reload()">Tekrar Dene</button>
</body>
</html>
"""


def check_server(url: str, timeout: int = 5) -> bool:
    """Sunucunun erişilebilir olup olmadığını kontrol et"""
    try:
        req = urllib.request.Request(url + "/api/health", method="GET")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status == 200
    except Exception:
        return False


def wait_and_navigate(window: webview.Window):
    """Arka planda sunucuyu kontrol et, hazır olunca yönlendir"""
    retries = 0
    while True:
        if check_server(SERVER_URL):
            # Sunucu hazır — ana sayfaya yönlendir
            try:
                window.load_url(SERVER_URL)
            except Exception:
                pass
            return

        retries += 1
        if MAX_RETRIES > 0 and retries >= MAX_RETRIES:
            # Maksimum deneme aşıldı — hata göster
            try:
                window.load_html(ERROR_HTML)
            except Exception:
                pass
            return

        time.sleep(CHECK_INTERVAL)


def main():
    # Ana pencereyi oluştur (loading ekranıyla)
    window = webview.create_window(
        title=f"{APP_TITLE}  v{APP_VERSION}",
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
