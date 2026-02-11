"""
CompanyAI — Tüm Platformlar İçin İkon + Splash Üretici
Kullanım: python scripts/generate_icons.py

Üretir:
  - Android: mipmap-{mdpi..xxxhdpi}/ic_launcher.png + ic_launcher_round.png + ic_launcher_foreground.png
  - iOS: AppIcon-512@2x.png (1024x1024)
  - macOS: desktop/icon.icns (via PNG)
  - Windows: desktop/icon.ico
  - Splash: Android drawable + iOS Assets splash
"""

import os
import sys
import math

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow gerekli: pip install Pillow")
    sys.exit(1)

# ── Ayarlar ──────────────────────────────────────────────
BG_COLOR = "#0f1117"          # Koyu arka plan
ACCENT_COLOR = "#6366f1"      # Mor vurgu (indigo-500)
TEXT_COLOR = "#e2e8f0"         # Açık metin
APP_TEXT = "C"                 # İkon üzerindeki harf
ICON_SIZE = 1024              # Kaynak boyut (sonra resize)

# Proje kökü
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ── Yardımcılar ──────────────────────────────────────────

def get_font(size: int):
    """Sistemdeki ilk uygun kalın fontu bul"""
    font_candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/SFPro-Bold.otf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for fp in font_candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def create_base_icon(size: int = ICON_SIZE) -> Image.Image:
    """CompanyAI markası ile kare ikon oluştur"""
    img = Image.new("RGBA", (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Arka plan gradient efekti (üstten alta hafif açılma)
    for y in range(size):
        alpha = int(8 + (y / size) * 12)
        draw.line([(0, y), (size, y)], fill=(99, 102, 241, alpha))

    # Mor daire (merkez)
    margin = int(size * 0.15)
    circle_bbox = [margin, margin, size - margin, size - margin]
    draw.ellipse(circle_bbox, fill=ACCENT_COLOR)

    # İç kısımda daha koyu halka efekti
    inner_margin = int(size * 0.18)
    inner_bbox = [inner_margin, inner_margin, size - inner_margin, size - inner_margin]
    draw.ellipse(inner_bbox, fill="#5558e6")

    # "C" harfi (bold, beyaz)
    font_size = int(size * 0.48)
    font = get_font(font_size)
    bbox = draw.textbbox((0, 0), APP_TEXT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2 - int(size * 0.03)
    draw.text((tx, ty), APP_TEXT, fill="white", font=font)

    # "AI" alt yazısı
    ai_size = int(size * 0.14)
    ai_font = get_font(ai_size)
    ai_bbox = draw.textbbox((0, 0), "AI", font=ai_font)
    ai_tw = ai_bbox[2] - ai_bbox[0]
    ai_tx = (size - ai_tw) // 2
    ai_ty = ty + th - int(size * 0.02)
    draw.text((ai_tx, ai_ty), "AI", fill="#c7d2fe", font=ai_font)

    return img


def create_round_icon(base: Image.Image) -> Image.Image:
    """Yuvarlak ikon (Android round)"""
    size = base.size[0]
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, size, size], fill=255)
    result = base.copy()
    result.putalpha(mask)
    return result


def create_foreground_icon(size: int = ICON_SIZE) -> Image.Image:
    """Android adaptive icon foreground (sadece logo, şeffaf arka plan)"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Adaptive icon'da safe zone %66 — logo merkeze
    safe_margin = int(size * 0.17)
    circle_bbox = [safe_margin, safe_margin, size - safe_margin, size - safe_margin]
    draw.ellipse(circle_bbox, fill=ACCENT_COLOR)

    inner_margin = int(size * 0.20)
    inner_bbox = [inner_margin, inner_margin, size - inner_margin, size - inner_margin]
    draw.ellipse(inner_bbox, fill="#5558e6")

    # "C" harfi
    font_size = int(size * 0.38)
    font = get_font(font_size)
    bbox = draw.textbbox((0, 0), APP_TEXT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2 - int(size * 0.02)
    draw.text((tx, ty), APP_TEXT, fill="white", font=font)

    # "AI"
    ai_size = int(size * 0.11)
    ai_font = get_font(ai_size)
    ai_bbox = draw.textbbox((0, 0), "AI", font=ai_font)
    ai_tw = ai_bbox[2] - ai_bbox[0]
    ai_tx = (size - ai_tw) // 2
    ai_ty = ty + th - int(size * 0.015)
    draw.text((ai_tx, ai_ty), "AI", fill="#c7d2fe", font=ai_font)

    return img


def create_splash(width: int, height: int) -> Image.Image:
    """Splash screen — karanlık arka plan + logo"""
    img = Image.new("RGBA", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # "CompanyAI" yazısı
    font_size = int(min(width, height) * 0.07)
    font = get_font(font_size)

    text = "Company"
    ai_text = "AI"

    # "Company" ölç
    c_bbox = draw.textbbox((0, 0), text, font=font)
    c_tw = c_bbox[2] - c_bbox[0]

    # "AI" ölç  
    ai_bbox = draw.textbbox((0, 0), ai_text, font=font)
    ai_tw = ai_bbox[2] - ai_bbox[0]

    total_w = c_tw + ai_tw
    start_x = (width - total_w) // 2
    y = height // 2 - int(font_size * 0.6)

    draw.text((start_x, y), text, fill=TEXT_COLOR, font=font)
    draw.text((start_x + c_tw, y), ai_text, fill=ACCENT_COLOR, font=font)

    # Alt imza
    sig_size = int(min(width, height) * 0.02)
    sig_font = get_font(sig_size)
    sig_text = "Designed by Murteza ALEMDAR"
    sig_bbox = draw.textbbox((0, 0), sig_text, font=sig_font)
    sig_tw = sig_bbox[2] - sig_bbox[0]
    draw.text(((width - sig_tw) // 2, height - int(height * 0.08)), sig_text, fill="#334155", font=sig_font)

    return img


def save_resized(img: Image.Image, path: str, size: tuple):
    """Resize + PNG olarak kaydet"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    resized = img.resize(size, Image.LANCZOS)
    resized.save(path, "PNG")
    print(f"  ✓ {path} ({size[0]}x{size[1]})")


def main():
    print("\n══════════════════════════════════════════════")
    print("  CompanyAI — İkon & Splash Üretici")
    print("══════════════════════════════════════════════\n")

    # Kaynak ikonları üret
    base_icon = create_base_icon(1024)
    round_icon = create_round_icon(base_icon)
    foreground = create_foreground_icon(1024)

    # ── Android Mipmap İkonları ──────────────────────────
    print("[1/6] Android ikonları...")
    android_res = os.path.join(ROOT, "frontend", "android", "app", "src", "main", "res")
    android_sizes = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }
    for folder, size in android_sizes.items():
        d = os.path.join(android_res, folder)
        save_resized(base_icon, os.path.join(d, "ic_launcher.png"), (size, size))
        save_resized(round_icon, os.path.join(d, "ic_launcher_round.png"), (size, size))
        save_resized(foreground, os.path.join(d, "ic_launcher_foreground.png"), (size, size))

    # ── Android Splash ───────────────────────────────────
    print("\n[2/6] Android splash ekranları...")
    splash_landscape = {
        "drawable-land-mdpi": (480, 320),
        "drawable-land-hdpi": (800, 480),
        "drawable-land-xhdpi": (1280, 720),
        "drawable-land-xxhdpi": (1600, 960),
        "drawable-land-xxxhdpi": (1920, 1280),
    }
    splash_portrait = {
        "drawable-port-mdpi": (320, 480),
        "drawable-port-hdpi": (480, 800),
        "drawable-port-xhdpi": (720, 1280),
        "drawable-port-xxhdpi": (960, 1600),
        "drawable-port-xxxhdpi": (1280, 1920),
    }
    # Varsayılan splash
    default_splash = create_splash(480, 800)
    save_resized(default_splash, os.path.join(android_res, "drawable", "splash.png"), (480, 800))

    for folder, (w, h) in splash_landscape.items():
        splash = create_splash(w, h)
        save_resized(splash, os.path.join(android_res, folder, "splash.png"), (w, h))

    for folder, (w, h) in splash_portrait.items():
        splash = create_splash(w, h)
        save_resized(splash, os.path.join(android_res, folder, "splash.png"), (w, h))

    # ── iOS App Icon ─────────────────────────────────────
    print("\n[3/6] iOS app ikonu...")
    ios_icon_dir = os.path.join(ROOT, "frontend", "ios", "App", "App",
                                 "Assets.xcassets", "AppIcon.appiconset")
    save_resized(base_icon, os.path.join(ios_icon_dir, "AppIcon-512@2x.png"), (1024, 1024))

    # ── iOS Splash ───────────────────────────────────────
    print("\n[4/6] iOS splash ekranları...")
    ios_splash_dir = os.path.join(ROOT, "frontend", "ios", "App", "App",
                                   "Assets.xcassets", "Splash.imageset")
    ios_splash = create_splash(2732, 2732)
    save_resized(ios_splash, os.path.join(ios_splash_dir, "splash-2732x2732.png"), (2732, 2732))
    save_resized(ios_splash, os.path.join(ios_splash_dir, "splash-2732x2732-1.png"), (2732, 2732))
    save_resized(ios_splash, os.path.join(ios_splash_dir, "splash-2732x2732-2.png"), (2732, 2732))

    # ── Windows .ico ─────────────────────────────────────
    print("\n[5/6] Windows ikon (.ico)...")
    ico_path = os.path.join(ROOT, "desktop", "icon.ico")
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_images = [base_icon.resize(s, Image.LANCZOS) for s in ico_sizes]
    ico_images[0].save(ico_path, format="ICO", sizes=ico_sizes, append_images=ico_images[1:])
    print(f"  ✓ {ico_path}")

    # ── macOS .icns (via PNG — gerçek icns dönüşümü macOS'ta yapılır) ──
    print("\n[6/6] macOS ikon (PNG → .icns macOS'ta dönüştürülür)...")
    mac_icon_png = os.path.join(ROOT, "desktop", "icon_1024.png")
    base_icon.save(mac_icon_png, "PNG")
    print(f"  ✓ {mac_icon_png} (macOS'ta: iconutil veya sips ile .icns'e dönüştür)")

    # Android arka plan rengini güncelle
    bg_xml_path = os.path.join(android_res, "values", "ic_launcher_background.xml")
    with open(bg_xml_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write('<resources>\n')
        f.write(f'    <color name="ic_launcher_background">{BG_COLOR}</color>\n')
        f.write('</resources>\n')
    print(f"\n  ✓ Android ikon arka planı → {BG_COLOR}")

    print("\n══════════════════════════════════════════════")
    print("  ✅ Tüm ikonlar ve splash ekranları üretildi!")
    print("  Sonraki: npx cap sync (frontend klasöründe)")
    print("══════════════════════════════════════════════\n")


if __name__ == "__main__":
    main()
