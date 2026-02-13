import { useState, useRef, useCallback } from 'react'
import DOMPurify from 'dompurify'
import {
    BarChart3,
    Upload,
    FileSpreadsheet,
    Search,
    TrendingUp,
    PieChart,
    Table2,
    Lightbulb,
    FileText,
    Loader2,
    CheckCircle,
    XCircle,
    ChevronDown,
    Send,
    Trash2,
    Download,
    Info,
    AlertTriangle,
    GitBranch,
    Activity,
    Target,
    Layers,
    ShieldCheck,
} from 'lucide-react'
import { analyzeApi } from '../services/api'

// ──────────────────────────────────────────────
// TİP TANIMLARI
// ──────────────────────────────────────────────
interface DataInfo {
    rows?: number
    cols?: number
    type?: string
    chars?: number
    words?: number
    lines?: number
    is_tabular?: boolean
    numeric_columns?: string[]
    categorical_columns?: string[]
    date_columns?: string[]
    has_missing?: boolean
    missing_summary?: Record<string, number>
    columns?: string[]
    available_analyses?: string[]
    sample_data?: Record<string, any>[]
    sheets?: string[]
}

interface AnalysisResult {
    answer: string
    analysis_type: string
    filename: string
    processing_time_ms: number
    data_info?: any
}

// ──────────────────────────────────────────────
// ANALİZ TİPLERİ
// ──────────────────────────────────────────────
const ANALYSIS_TYPES = [
    { value: 'full', label: 'Tam Analiz', icon: BarChart3, description: 'Pivot + İstatistik + Trend + Tavsiye', color: 'text-blue-400' },
    { value: 'pivot', label: 'Pivot Tablo', icon: Table2, description: 'Özet tablo ve çapraz analiz', color: 'text-purple-400' },
    { value: 'trend', label: 'Trend Analizi', icon: TrendingUp, description: 'Zaman bazlı trend ve yönelim', color: 'text-green-400' },
    { value: 'compare', label: 'Karşılaştırma', icon: PieChart, description: 'Grup bazlı karşılaştırma', color: 'text-orange-400' },
    { value: 'summary', label: 'Özet', icon: FileText, description: 'Hızlı özet rapor', color: 'text-cyan-400' },
    { value: 'recommend', label: 'Tavsiye', icon: Lightbulb, description: 'Aksiyon önerileri ve tavsiyeler', color: 'text-yellow-400' },
    { value: 'report', label: 'Rapor', icon: FileSpreadsheet, description: 'Profesyonel rapor formatı', color: 'text-rose-400' },
    { value: 'anomaly', label: 'Anomali Tespiti', icon: AlertTriangle, description: 'Aykırı değer ve anomali tarama', color: 'text-red-400' },
    { value: 'correlation', label: 'Korelasyon', icon: GitBranch, description: 'Değişkenler arası ilişki analizi', color: 'text-indigo-400' },
    { value: 'distribution', label: 'Dağılım', icon: Activity, description: 'Veri dağılım profili ve istatistik', color: 'text-teal-400' },
    { value: 'forecast', label: 'Tahminleme', icon: Target, description: 'Gelecek dönem projeksiyonu', color: 'text-amber-400' },
    { value: 'pareto', label: 'Pareto / ABC', icon: Layers, description: '80/20 kuralı ve ABC sınıflandırması', color: 'text-pink-400' },
    { value: 'quality', label: 'Veri Kalitesi', icon: ShieldCheck, description: 'Eksik, tekrar ve tutarlılık denetimi', color: 'text-emerald-400' },
    // ── CEO-Tier Analiz Tipleri (v3.8.0) ──
    { value: 'profitability', label: 'Karlılık', icon: TrendingUp, description: 'Ürün/müşteri bazlı net kârlılık analizi', color: 'text-green-300', ceo: true },
    { value: 'bottleneck', label: 'Darboğaz', icon: AlertTriangle, description: 'Operasyonel tıkanıklık ve verimlilik tespiti', color: 'text-orange-300', ceo: true },
    { value: 'executive', label: 'Sağlık Skoru', icon: Activity, description: 'Şirket sağlık endeksi (0-100)', color: 'text-cyan-300', ceo: true },
    { value: 'benchmark', label: 'Kıyaslama', icon: Target, description: 'Sektörel benchmark ve rekabet analizi', color: 'text-violet-300', ceo: true },
]

export default function Analyze() {
    // ── STATE ──
    const [file, setFile] = useState<File | null>(null)
    const [analysisType, setAnalysisType] = useState('full')
    const [question, setQuestion] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [isDiscovering, setIsDiscovering] = useState(false)
    const [dataInfo, setDataInfo] = useState<DataInfo | null>(null)
    const [result, setResult] = useState<AnalysisResult | null>(null)
    const [queryInput, setQueryInput] = useState('')
    const [queryResult, setQueryResult] = useState<string | null>(null)
    const [isQuerying, setIsQuerying] = useState(false)
    const [streamingText, setStreamingText] = useState('')
    const [error, setError] = useState<string | null>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const resultRef = useRef<HTMLDivElement>(null)

    // ── DOSYA YÜKLE & KEŞFİ ──
    const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0]
        if (!selectedFile) return

        setFile(selectedFile)
        setResult(null)
        setQueryResult(null)
        setError(null)
        setDataInfo(null)

        // Dosya yapısını keşfet
        setIsDiscovering(true)
        try {
            const info = await analyzeApi.discover(selectedFile)
            setDataInfo(info)
        } catch (err: any) {
            console.error('Discover error:', err)
            // Keşif başarısız olsa da dosya seçili kalsın
            setDataInfo(null)
        } finally {
            setIsDiscovering(false)
        }
    }, [])

    // ── ANALİZ BAŞLAT ──
    const handleAnalyze = useCallback(async () => {
        if (!file) return

        setIsLoading(true)
        setError(null)
        setResult(null)
        setStreamingText('')

        try {
            // Streaming analiz
            const response = await analyzeApi.uploadAndAnalyzeStream(file, analysisType, question || undefined)

            if (!response.ok) {
                const errData = await response.json().catch(() => ({ detail: 'Bilinmeyen hata' }))
                throw new Error(errData.detail || `HTTP ${response.status}`)
            }

            const reader = response.body?.getReader()
            if (!reader) throw new Error('Stream bulunamadı')

            const decoder = new TextDecoder()
            let fullText = ''
            let analysisInfo: any = {}

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                const chunk = decoder.decode(value, { stream: true })
                const lines = chunk.split('\n')

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue
                    try {
                        const data = JSON.parse(line.slice(6))

                        if (data.data_info) {
                            analysisInfo = data
                        } else if (data.token) {
                            fullText += data.token
                            setStreamingText(fullText)
                        } else if (data.done) {
                            setResult({
                                answer: fullText,
                                analysis_type: data.analysis_type || analysisType,
                                filename: analysisInfo.filename || file.name,
                                processing_time_ms: data.processing_time_ms || 0,
                                data_info: analysisInfo.data_info,
                            })
                        } else if (data.error) {
                            throw new Error(data.error)
                        }
                    } catch (parseErr) {
                        // JSON parse hatası - devam et
                    }
                }
            }

            // Stream bittiyse ama result set edilmediyse
            if (fullText && !result) {
                setResult({
                    answer: fullText,
                    analysis_type: analysisType,
                    filename: file.name,
                    processing_time_ms: 0,
                })
            }

            // Sonuca scroll
            setTimeout(() => {
                resultRef.current?.scrollIntoView({ behavior: 'smooth' })
            }, 300)

        } catch (err: any) {
            console.error('Analyze error:', err)
            setError(err.message || 'Analiz sırasında bir hata oluştu')

            // Streaming başarısız olursa normal API dene
            try {
                const normalResult = await analyzeApi.uploadAndAnalyze(file, analysisType, question || undefined)
                setResult(normalResult)
                setError(null)
            } catch {
                // İkisi de başarısız
            }
        } finally {
            setIsLoading(false)
        }
    }, [file, analysisType, question])

    // ── DOĞAL DİL SORGU ──
    const handleQuery = useCallback(async () => {
        if (!queryInput.trim()) return

        setIsQuerying(true)
        setQueryResult(null)
        try {
            const res = await analyzeApi.query(queryInput)
            setQueryResult(res.answer || res.value?.toString() || 'Sonuç bulunamadı')
        } catch (err: any) {
            setQueryResult(`Hata: ${err.message || 'Sorgu yapılamadı'}`)
        } finally {
            setIsQuerying(false)
        }
    }, [queryInput])

    // ── TEMİZLE ──
    const handleClear = () => {
        setFile(null)
        setDataInfo(null)
        setResult(null)
        setStreamingText('')
        setQueryResult(null)
        setError(null)
        setQuestion('')
        setQueryInput('')
        if (fileInputRef.current) fileInputRef.current.value = ''
    }

    // ── MARKDOWN → basit HTML dönüştürücü ──
    const renderMarkdown = (text: string) => {
        const html = text
            .replace(/### (.*)/g, '<h3 class="text-lg font-bold text-white mt-4 mb-2">$1</h3>')
            .replace(/## (.*)/g, '<h2 class="text-xl font-bold text-white mt-5 mb-2">$1</h2>')
            .replace(/# (.*)/g, '<h1 class="text-2xl font-bold text-white mt-6 mb-3">$1</h1>')
            .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/^- (.*)/gm, '<li class="ml-4 text-dark-200">• $1</li>')
            .replace(/^\d+\. (.*)/gm, '<li class="ml-4 text-dark-200">$1</li>')
            .replace(/\|(.+)\|/g, (match) => {
                const cells = match.split('|').filter(c => c.trim())
                if (cells.every(c => /^[-:]+$/.test(c.trim()))) return ''
                return '<tr>' + cells.map(c => `<td class="border border-dark-600 px-3 py-1.5 text-sm">${c.trim()}</td>`).join('') + '</tr>'
            })
            .replace(/\n/g, '<br/>')
        // DOMPurify ile XSS koruması
        return DOMPurify.sanitize(html, {
            ALLOWED_TAGS: ['h1','h2','h3','strong','em','li','tr','td','br','table','tbody','thead','th','ul','ol','p','span','div','code','pre'],
            ALLOWED_ATTR: ['class'],
        })
    }

    return (
        <div className="max-w-7xl mx-auto space-y-6">
            {/* BAŞLIK */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <BarChart3 className="w-7 h-7 text-blue-400" />
                        Doküman Analiz Merkezi
                    </h1>
                    <p className="text-dark-400 mt-1">
                        Excel, CSV, PDF, Word dosyalarınızı yükleyip detaylı analiz edin
                    </p>
                </div>
                {file && (
                    <button
                        onClick={handleClear}
                        className="px-4 py-2 bg-dark-800 text-dark-300 rounded-lg hover:bg-dark-700 flex items-center gap-2 transition"
                    >
                        <Trash2 className="w-4 h-4" />
                        Temizle
                    </button>
                )}
            </div>

            {/* 1. DOSYA YÜKLEME ALANI */}
            <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Upload className="w-5 h-5 text-blue-400" />
                    Dosya Seç
                </h2>

                <div className="flex items-center gap-4">
                    <input
                        ref={fileInputRef}
                        type="file"
                        onChange={handleFileSelect}
                        accept=".xlsx,.xls,.csv,.json,.tsv,.pdf,.docx,.doc,.txt,.rtf,.odt,.pptx"
                        className="flex-1 file:mr-4 file:py-2.5 file:px-5 file:rounded-lg file:border-0
                            file:text-sm file:font-semibold file:bg-blue-500/10 file:text-blue-400
                            hover:file:bg-blue-500/20 file:cursor-pointer text-dark-300 text-sm
                            cursor-pointer bg-dark-900/50 rounded-lg border border-dark-600
                            focus:outline-none focus:border-blue-500"
                    />

                    {isDiscovering && (
                        <div className="flex items-center gap-2 text-blue-400 text-sm">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span>Keşfediliyor...</span>
                        </div>
                    )}
                </div>

                {/* Dosya Bilgisi */}
                {file && !isDiscovering && dataInfo && (
                    <div className="mt-4 bg-dark-900/50 rounded-lg p-4 border border-dark-600">
                        <div className="flex items-start justify-between">
                            <div>
                                <h3 className="text-white font-medium flex items-center gap-2">
                                    <FileSpreadsheet className="w-4 h-4 text-green-400" />
                                    {file.name}
                                    <span className="text-xs bg-dark-700 px-2 py-0.5 rounded text-dark-300">
                                        {(file.size / 1024).toFixed(1)} KB
                                    </span>
                                </h3>
                            </div>
                            {dataInfo.is_tabular && (
                                <div className="flex items-center gap-3 text-sm">
                                    <span className="text-dark-400">{dataInfo.rows} satır</span>
                                    <span className="text-dark-500">•</span>
                                    <span className="text-dark-400">{dataInfo.cols} sütun</span>
                                </div>
                            )}
                        </div>

                        {/* Sütun Bilgileri */}
                        {dataInfo.is_tabular && (
                            <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
                                {dataInfo.numeric_columns && dataInfo.numeric_columns.length > 0 && (
                                    <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
                                        <div className="text-xs font-medium text-blue-400 mb-1">Sayısal Sütunlar</div>
                                        <div className="flex flex-wrap gap-1">
                                            {dataInfo.numeric_columns.map(c => (
                                                <span key={c} className="text-xs bg-blue-500/10 text-blue-300 px-2 py-0.5 rounded">
                                                    {c}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {dataInfo.categorical_columns && dataInfo.categorical_columns.length > 0 && (
                                    <div className="bg-purple-500/5 border border-purple-500/20 rounded-lg p-3">
                                        <div className="text-xs font-medium text-purple-400 mb-1">Kategorik Sütunlar</div>
                                        <div className="flex flex-wrap gap-1">
                                            {dataInfo.categorical_columns.map(c => (
                                                <span key={c} className="text-xs bg-purple-500/10 text-purple-300 px-2 py-0.5 rounded">
                                                    {c}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {dataInfo.date_columns && dataInfo.date_columns.length > 0 && (
                                    <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-3">
                                        <div className="text-xs font-medium text-green-400 mb-1">Tarih Sütunları</div>
                                        <div className="flex flex-wrap gap-1">
                                            {dataInfo.date_columns.map(c => (
                                                <span key={c} className="text-xs bg-green-500/10 text-green-300 px-2 py-0.5 rounded">
                                                    {c}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Sample Data Preview */}
                        {dataInfo.sample_data && dataInfo.sample_data.length > 0 && (
                            <details className="mt-3">
                                <summary className="text-xs text-dark-400 cursor-pointer hover:text-dark-300 flex items-center gap-1">
                                    <ChevronDown className="w-3 h-3" />
                                    Örnek Veri (ilk 5 satır)
                                </summary>
                                <div className="mt-2 overflow-x-auto">
                                    <table className="min-w-full text-xs">
                                        <thead>
                                            <tr>
                                                {Object.keys(dataInfo.sample_data[0]).map(key => (
                                                    <th key={key} className="px-3 py-1.5 text-left text-dark-400 border-b border-dark-600 font-medium">
                                                        {key}
                                                    </th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {dataInfo.sample_data.map((row, i) => (
                                                <tr key={i} className="hover:bg-dark-700/30">
                                                    {Object.values(row).map((val, j) => (
                                                        <td key={j} className="px-3 py-1.5 text-dark-300 border-b border-dark-700/50">
                                                            {val != null ? String(val) : '-'}
                                                        </td>
                                                    ))}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </details>
                        )}
                    </div>
                )}
            </div>

            {/* 2. ANALİZ TİPİ SEÇİMİ */}
            {file && (
                <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
                    <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <BarChart3 className="w-5 h-5 text-purple-400" />
                        Analiz Tipi Seçin
                    </h2>

                    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-7 gap-3">
                        {ANALYSIS_TYPES.filter(t =>
                            !t.ceo && (!dataInfo?.available_analyses || dataInfo.available_analyses.includes(t.value))
                        ).map(type => (
                            <button
                                key={type.value}
                                onClick={() => setAnalysisType(type.value)}
                                className={`p-3 rounded-xl border transition text-left ${
                                    analysisType === type.value
                                        ? 'bg-blue-500/10 border-blue-500/40 ring-1 ring-blue-500/30'
                                        : 'bg-dark-900/50 border-dark-600 hover:border-dark-500'
                                }`}
                            >
                                <type.icon className={`w-5 h-5 ${type.color} mb-2`} />
                                <div className="text-sm font-medium text-white">{type.label}</div>
                                <div className="text-xs text-dark-400 mt-0.5">{type.description}</div>
                            </button>
                        ))}
                    </div>

                    {/* CEO-Tier Analiz Tipleri */}
                    <div className="mt-4 pt-4 border-t border-dark-700">
                        <div className="text-xs font-semibold text-amber-400/80 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                            👑 C-Level Stratejik Analiz
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            {ANALYSIS_TYPES.filter(t => t.ceo).map(type => (
                                <button
                                    key={type.value}
                                    onClick={() => setAnalysisType(type.value)}
                                    className={`p-3 rounded-xl border transition text-left ${
                                        analysisType === type.value
                                            ? 'bg-amber-500/10 border-amber-500/40 ring-1 ring-amber-500/30'
                                            : 'bg-dark-900/50 border-amber-900/30 hover:border-amber-700/40'
                                    }`}
                                >
                                    <type.icon className={`w-5 h-5 ${type.color} mb-2`} />
                                    <div className="text-sm font-medium text-white">{type.label}</div>
                                    <div className="text-xs text-dark-400 mt-0.5">{type.description}</div>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Ek Soru */}
                    <div className="mt-4">
                        <label className="block text-sm text-dark-400 mb-2">
                            Özel soru veya talep (opsiyonel)
                        </label>
                        <div className="flex gap-3">
                            <input
                                type="text"
                                value={question}
                                onChange={e => setQuestion(e.target.value)}
                                placeholder="Örn: Satış trendi nasıl? Hangi ürün en çok satılmış?"
                                className="flex-1 bg-dark-900/50 border border-dark-600 rounded-lg px-4 py-2.5 text-white
                                    placeholder-dark-500 focus:outline-none focus:border-blue-500 text-sm"
                                onKeyDown={e => e.key === 'Enter' && handleAnalyze()}
                            />
                            <button
                                onClick={handleAnalyze}
                                disabled={isLoading}
                                className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-500
                                    disabled:opacity-50 disabled:cursor-not-allowed font-medium flex items-center gap-2 transition"
                            >
                                {isLoading ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        Analiz Ediliyor...
                                    </>
                                ) : (
                                    <>
                                        <BarChart3 className="w-4 h-4" />
                                        Analiz Et
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 3. HATA MESAJI */}
            {error && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-start gap-3">
                    <XCircle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
                    <div>
                        <div className="text-red-400 font-medium">Analiz Hatası</div>
                        <div className="text-red-300/80 text-sm mt-1">{error}</div>
                    </div>
                </div>
            )}

            {/* 4. SONUÇ ALANI */}
            {(streamingText || result) && (
                <div ref={resultRef} className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                            <CheckCircle className="w-5 h-5 text-green-400" />
                            Analiz Sonucu
                            {result && (
                                <span className="text-xs bg-dark-700 px-2 py-0.5 rounded text-dark-400 ml-2">
                                    {result.processing_time_ms}ms
                                </span>
                            )}
                        </h2>
                        {result?.answer && (
                            <button
                                onClick={() => {
                                    navigator.clipboard.writeText(result.answer)
                                }}
                                className="text-dark-400 hover:text-white text-sm flex items-center gap-1 transition"
                            >
                                <Download className="w-4 h-4" /> Kopyala
                            </button>
                        )}
                    </div>

                    {/* Analiz metni */}
                    <div className="prose prose-invert max-w-none">
                        <div
                            className="text-dark-200 text-sm leading-relaxed whitespace-pre-wrap"
                            dangerouslySetInnerHTML={{
                                __html: renderMarkdown(result?.answer || streamingText)
                            }}
                        />
                    </div>

                    {/* Yükleniyor indicator */}
                    {isLoading && (
                        <div className="flex items-center gap-2 mt-4 text-blue-400 text-sm">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            AI analiz ediyor...
                        </div>
                    )}
                </div>
            )}

            {/* 5. DOĞAL DİL SORGU (Veri yüklendikten sonra) */}
            {dataInfo?.is_tabular && (result || streamingText) && (
                <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
                    <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <Search className="w-5 h-5 text-cyan-400" />
                        Veriye Soru Sor
                    </h2>
                    <p className="text-dark-400 text-sm mb-3 flex items-center gap-1">
                        <Info className="w-3.5 h-3.5" />
                        Türkçe doğal dil ile veriyi sorgulayın. Örn: "toplam satış nedir?", "en yüksek fiyatlı ürün hangisi?"
                    </p>

                    <div className="flex gap-3">
                        <input
                            type="text"
                            value={queryInput}
                            onChange={e => setQueryInput(e.target.value)}
                            placeholder="Verinize sorunuzu yazın..."
                            className="flex-1 bg-dark-900/50 border border-dark-600 rounded-lg px-4 py-2.5 text-white
                                placeholder-dark-500 focus:outline-none focus:border-cyan-500 text-sm"
                            onKeyDown={e => e.key === 'Enter' && handleQuery()}
                        />
                        <button
                            onClick={handleQuery}
                            disabled={isQuerying || !queryInput.trim()}
                            className="px-5 py-2.5 bg-cyan-600 text-white rounded-lg hover:bg-cyan-500
                                disabled:opacity-50 disabled:cursor-not-allowed font-medium flex items-center gap-2 transition"
                        >
                            {isQuerying ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                <Send className="w-4 h-4" />
                            )}
                            Sorgula
                        </button>
                    </div>

                    {queryResult && (
                        <div className="mt-4 bg-dark-900/50 border border-dark-600 rounded-lg p-4">
                            <div
                                className="text-dark-200 text-sm whitespace-pre-wrap"
                                dangerouslySetInnerHTML={{ __html: renderMarkdown(queryResult) }}
                            />
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
