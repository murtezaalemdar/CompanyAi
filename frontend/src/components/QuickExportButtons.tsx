import { useState } from 'react'
import { Download, FileSpreadsheet, FileText, Presentation, Loader2, Check, ChevronDown, ChevronUp } from 'lucide-react'

interface ExportFormat {
    key: string
    label: string
    icon: any
    color: string
}

const FORMATS: ExportFormat[] = [
    { key: 'excel', label: 'Excel', icon: FileSpreadsheet, color: 'text-green-400 hover:bg-green-500/10 border-green-500/20' },
    { key: 'pdf', label: 'PDF', icon: FileText, color: 'text-red-400 hover:bg-red-500/10 border-red-500/20' },
    { key: 'pptx', label: 'PowerPoint', icon: Presentation, color: 'text-orange-400 hover:bg-orange-500/10 border-orange-500/20' },
    { key: 'word', label: 'Word', icon: FileText, color: 'text-blue-400 hover:bg-blue-500/10 border-blue-500/20' },
]

export default function QuickExportButtons({ content }: { content: string }) {
    const [expanded, setExpanded] = useState(false)
    const [loading, setLoading] = useState<string | null>(null)
    const [done, setDone] = useState<string | null>(null)

    const handleExport = async (format: string) => {
        setLoading(format)
        try {
            const token = localStorage.getItem('token')
            
            // 1. Export dosyası oluştur
            const genResponse = await fetch('/api/export/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    content: content,
                    format: format,
                    title: 'Rapor',
                }),
            })
            
            if (!genResponse.ok) throw new Error('Export oluşturulamadı')
            const data = await genResponse.json()
            
            if (!data.success || !data.download_url) {
                throw new Error(data.error || 'Export başarısız')
            }
            
            // 2. Dosyayı indir
            const dlResponse = await fetch(data.download_url, {
                headers: { Authorization: `Bearer ${token}` },
            })
            
            if (!dlResponse.ok) throw new Error('İndirme başarısız')
            
            const blob = await dlResponse.blob()
            const url = window.URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = data.filename
            document.body.appendChild(a)
            a.click()
            window.URL.revokeObjectURL(url)
            document.body.removeChild(a)
            
            setDone(format)
            setTimeout(() => setDone(null), 2500)
        } catch (err) {
            console.error('Quick export error:', err)
        } finally {
            setLoading(null)
        }
    }

    return (
        <div className="mt-2">
            <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-1 text-[11px] text-dark-500 hover:text-dark-300 transition-colors"
            >
                <Download className="w-3 h-3" />
                <span>Farklı formatta indir</span>
                {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>

            {expanded && (
                <div className="flex flex-wrap gap-1.5 mt-1.5 animate-in slide-in-from-top-1 duration-200">
                    {FORMATS.map((fmt) => {
                        const Icon = fmt.icon
                        const isLoading = loading === fmt.key
                        const isDone = done === fmt.key
                        return (
                            <button
                                key={fmt.key}
                                onClick={() => handleExport(fmt.key)}
                                disabled={isLoading}
                                className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium
                                    border bg-dark-800/50 transition-all duration-150
                                    ${isDone ? 'border-green-500/40 text-green-400' : fmt.color}
                                    disabled:opacity-50 disabled:cursor-not-allowed
                                `}
                            >
                                {isLoading ? (
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                ) : isDone ? (
                                    <Check className="w-3 h-3" />
                                ) : (
                                    <Icon className="w-3 h-3" />
                                )}
                                {fmt.label}
                            </button>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
