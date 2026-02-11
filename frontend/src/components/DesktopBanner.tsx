import { useState, useEffect } from 'react'
import { Monitor, X, Download, Smartphone, Laptop } from 'lucide-react'

type PlatformInfo = {
    platform: 'windows' | 'macos' | 'android' | 'ios'
    title: string
    description: string
    icon: typeof Monitor
    downloadUrl: string | null
    buttonText: string
}

function detectPlatform(): PlatformInfo | null {
    const ua = navigator.userAgent

    // Capacitor veya pywebview içindeyse banner gösterme
    if ((window as any).pywebview || (window as any).Capacitor || ua.includes('CompanyAI-Mobile')) {
        return null
    }

    // iOS (iPhone/iPad/iPod veya iPad masquerading as Mac)
    if (/iPhone|iPad|iPod/i.test(ua) || (navigator.maxTouchPoints > 1 && /Macintosh/i.test(ua))) {
        return {
            platform: 'ios',
            title: 'iOS Uygulaması',
            description: 'CompanyAI\'ı iPhone\'unuza yükleyin — daha hızlı erişim',
            icon: Smartphone,
            downloadUrl: null, // App Store linki eklenecek
            buttonText: 'Yakında',
        }
    }

    // Android
    if (/Android/i.test(ua)) {
        return {
            platform: 'android',
            title: 'Android Uygulaması',
            description: 'CompanyAI\'ı telefonunuza yükleyin — daha hızlı erişim',
            icon: Smartphone,
            downloadUrl: null, // Play Store linki eklenecek
            buttonText: 'Yakında',
        }
    }

    // macOS (gerçek Mac, iOS değil)
    if (/Macintosh|Mac OS/i.test(ua)) {
        return {
            platform: 'macos',
            title: 'macOS Uygulaması',
            description: 'CompanyAI\'ı Mac\'inize yükleyin — native deneyim',
            icon: Laptop,
            downloadUrl: '/downloads/CompanyAI.app.zip',
            buttonText: 'İndir',
        }
    }

    // Windows (varsayılan)
    return {
        platform: 'windows',
        title: 'Masaüstü Uygulaması',
        description: 'Daha hızlı erişim için CompanyAI\'ı masaüstünüze yükleyin',
        icon: Monitor,
        downloadUrl: '/downloads/CompanyAI.exe',
        buttonText: 'İndir',
    }
}

/**
 * Platform-duyarlı uygulama indirme banner'ı.
 * - Windows  → .exe indir
 * - macOS    → .app indir
 * - Android  → "Yakında" (Play Store linki eklenecek)
 * - iOS      → "Yakında" (App Store linki eklenecek)
 * - pywebview / Capacitor içinde → GİZLENİR
 * Kullanıcı kapattığında 7 gün boyunca tekrar gösterilmez.
 */
export default function DesktopBanner() {
    const [visible, setVisible] = useState(false)
    const [info, setInfo] = useState<PlatformInfo | null>(null)

    useEffect(() => {
        const detected = detectPlatform()
        if (!detected) return

        // Kullanıcı daha önce kapatmış mı? (platform bazlı key)
        const key = `app_banner_dismissed_${detected.platform}`
        const dismissed = localStorage.getItem(key)
        if (dismissed) {
            const ts = parseInt(dismissed, 10)
            const sevenDays = 7 * 24 * 60 * 60 * 1000
            if (Date.now() - ts < sevenDays) return
        }

        setInfo(detected)
        setVisible(true)
    }, [])

    const handleDismiss = () => {
        setVisible(false)
        if (info) {
            localStorage.setItem(`app_banner_dismissed_${info.platform}`, Date.now().toString())
        }
    }

    const handleAction = () => {
        if (info?.downloadUrl) {
            window.open(info.downloadUrl, '_blank')
        }
    }

    if (!visible || !info) return null

    const IconComponent = info.icon

    return (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 w-[92%] max-w-md animate-slide-up">
            <div className="bg-dark-900/95 backdrop-blur-lg border border-primary-500/30 rounded-2xl shadow-2xl shadow-primary-500/10 px-4 py-3.5 flex items-center gap-3">
                {/* Icon */}
                <div className="shrink-0 w-10 h-10 bg-primary-500/15 rounded-xl flex items-center justify-center">
                    <IconComponent className="w-5 h-5 text-primary-400" />
                </div>

                {/* Text */}
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-white leading-tight">
                        {info.title}
                    </p>
                    <p className="text-[11px] text-dark-400 mt-0.5">
                        {info.description}
                    </p>
                </div>

                {/* Action Button */}
                <button
                    onClick={handleAction}
                    disabled={!info.downloadUrl}
                    className={`shrink-0 flex items-center gap-1.5 text-white text-xs font-semibold px-3.5 py-2 rounded-xl transition-colors ${
                        info.downloadUrl
                            ? 'bg-primary-600 hover:bg-primary-500 cursor-pointer'
                            : 'bg-dark-700 text-dark-400 cursor-default'
                    }`}
                >
                    {info.downloadUrl && <Download className="w-3.5 h-3.5" />}
                    {info.buttonText}
                </button>

                {/* Close */}
                <button
                    onClick={handleDismiss}
                    className="shrink-0 p-1 text-dark-500 hover:text-dark-300 transition-colors"
                    title="Kapat"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>
        </div>
    )
}
