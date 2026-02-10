import { useState } from 'react'
import { Download, FileSpreadsheet, FileText, Presentation, File, Check, Loader2 } from 'lucide-react'

interface ExportData {
    type: 'export'
    file_id: string
    filename: string
    format: string
    format_label: string
    format_icon: string
    download_url: string
}

const FORMAT_STYLES: Record<string, { bg: string; border: string; icon: any; color: string }> = {
    excel: {
        bg: 'from-green-500/10 to-green-600/5',
        border: 'border-green-500/30',
        icon: FileSpreadsheet,
        color: 'text-green-400',
    },
    pdf: {
        bg: 'from-red-500/10 to-red-600/5',
        border: 'border-red-500/30',
        icon: FileText,
        color: 'text-red-400',
    },
    pptx: {
        bg: 'from-orange-500/10 to-orange-600/5',
        border: 'border-orange-500/30',
        icon: Presentation,
        color: 'text-orange-400',
    },
    word: {
        bg: 'from-blue-500/10 to-blue-600/5',
        border: 'border-blue-500/30',
        icon: FileText,
        color: 'text-blue-400',
    },
    csv: {
        bg: 'from-teal-500/10 to-teal-600/5',
        border: 'border-teal-500/30',
        icon: File,
        color: 'text-teal-400',
    },
}

export default function ExportCard({ data }: { data: ExportData }) {
    const [downloading, setDownloading] = useState(false)
    const [downloaded, setDownloaded] = useState(false)

    const style = FORMAT_STYLES[data.format] || FORMAT_STYLES.pdf
    const IconComponent = style.icon

    const handleDownload = async () => {
        setDownloading(true)
        try {
            const token = localStorage.getItem('token')
            const response = await fetch(data.download_url, {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            })

            if (!response.ok) {
                throw new Error('İndirme başarısız')
            }

            const blob = await response.blob()
            const url = window.URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = data.filename
            document.body.appendChild(a)
            a.click()
            window.URL.revokeObjectURL(url)
            document.body.removeChild(a)

            setDownloaded(true)
            setTimeout(() => setDownloaded(false), 3000)
        } catch (err) {
            console.error('Export download error:', err)
        } finally {
            setDownloading(false)
        }
    }

    return (
        <div className={`w-full max-w-md my-3 rounded-xl border ${style.border} bg-gradient-to-r ${style.bg} backdrop-blur-sm overflow-hidden`}>
            <div className="px-4 py-3 flex items-center gap-3">
                {/* Format ikonu */}
                <div className={`w-10 h-10 rounded-lg bg-dark-800/50 flex items-center justify-center ${style.color}`}>
                    <IconComponent className="w-5 h-5" />
                </div>

                {/* Dosya bilgisi */}
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-dark-200 truncate">
                        {data.filename}
                    </p>
                    <p className="text-xs text-dark-400">
                        {data.format_icon} {data.format_label} dosyası hazır
                    </p>
                </div>

                {/* İndir butonu */}
                <button
                    onClick={handleDownload}
                    disabled={downloading}
                    className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200
                        ${downloaded
                            ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                            : 'bg-dark-700/80 text-dark-200 hover:bg-dark-600 hover:text-white border border-dark-600'
                        }
                        disabled:opacity-50 disabled:cursor-not-allowed
                    `}
                >
                    {downloading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    ) : downloaded ? (
                        <Check className="w-4 h-4" />
                    ) : (
                        <Download className="w-4 h-4" />
                    )}
                    {downloading ? 'İndiriliyor...' : downloaded ? 'İndirildi' : 'İndir'}
                </button>
            </div>
        </div>
    )
}
