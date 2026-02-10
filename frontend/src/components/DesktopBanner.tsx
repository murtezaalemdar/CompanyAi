import { useState, useEffect } from 'react'
import { Monitor, X, Download } from 'lucide-react'

/**
 * Masaüstü uygulama indirme banner'ı.
 * Sadece normal tarayıcıda gösterilir (pywebview içinde GİZLENİR).
 * Kullanıcı kapattığında 7 gün boyunca tekrar gösterilmez.
 */
export default function DesktopBanner() {
    const [visible, setVisible] = useState(false)

    useEffect(() => {
        // pywebview içinde mi? (pencere özelliğini kontrol et)
        if ((window as any).pywebview) return

        // Kullanıcı daha önce kapatmış mı?
        const dismissed = localStorage.getItem('desktop_banner_dismissed')
        if (dismissed) {
            const ts = parseInt(dismissed, 10)
            const sevenDays = 7 * 24 * 60 * 60 * 1000
            if (Date.now() - ts < sevenDays) return
        }

        setVisible(true)
    }, [])

    const handleDismiss = () => {
        setVisible(false)
        localStorage.setItem('desktop_banner_dismissed', Date.now().toString())
    }

    if (!visible) return null

    return (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 w-[92%] max-w-md animate-slide-up">
            <div className="bg-dark-900/95 backdrop-blur-lg border border-primary-500/30 rounded-2xl shadow-2xl shadow-primary-500/10 px-4 py-3.5 flex items-center gap-3">
                {/* Icon */}
                <div className="shrink-0 w-10 h-10 bg-primary-500/15 rounded-xl flex items-center justify-center">
                    <Monitor className="w-5 h-5 text-primary-400" />
                </div>

                {/* Text */}
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-white leading-tight">
                        Masaüstü Uygulaması
                    </p>
                    <p className="text-[11px] text-dark-400 mt-0.5">
                        Daha hızlı erişim için CompanyAI'ı masaüstünüze yükleyin
                    </p>
                </div>

                {/* Download Button */}
                <button
                    onClick={() => window.open('/downloads/CompanyAI.exe', '_blank')}
                    className="shrink-0 flex items-center gap-1.5 bg-primary-600 hover:bg-primary-500 text-white text-xs font-semibold px-3.5 py-2 rounded-xl transition-colors cursor-pointer"
                >
                    <Download className="w-3.5 h-3.5" />
                    İndir
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
