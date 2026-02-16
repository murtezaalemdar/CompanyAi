import { useState, useEffect, useRef, useCallback } from 'react'
import {
    Cpu, Zap, Leaf, SlidersHorizontal, Save, Loader2,
    CheckCircle, AlertCircle, RotateCcw, Gauge, MemoryStick,
    MonitorSpeaker, Download, Trash2, ArrowRightLeft, ChevronDown,
    ChevronUp, HardDrive, X, Activity
} from 'lucide-react'
import { adminApi } from '../services/api'
import clsx from 'clsx'

// ── Tipler ──
interface PerformanceProfile {
    mode: string
    gpu_percent: number
    cpu_percent: number
    ram_percent: number
    calculated_params?: {
        num_gpu: number
        num_thread: number
        num_ctx: number
        num_batch: number
        gpu_layers_display: number
    }
    live_config?: Record<string, number>
    total_model_layers?: number
    active_model?: string
    presets?: Record<string, { gpu_percent: number; cpu_percent: number; ram_percent: number }>
    applied_at?: string
}

// ── Preset Tanımları ──
const PRESETS = [
    {
        key: 'full',
        label: 'Tam Performans',
        desc: 'Tüm kaynaklar maksimum',
        icon: Zap,
        color: 'from-orange-500 to-red-500',
        borderColor: 'border-orange-500',
        textColor: 'text-orange-400',
        bgColor: 'bg-orange-500/10',
    },
    {
        key: 'balanced',
        label: 'Dengeli',
        desc: 'Orta seviye kaynak kullanımı',
        icon: Gauge,
        color: 'from-blue-500 to-cyan-500',
        borderColor: 'border-blue-500',
        textColor: 'text-blue-400',
        bgColor: 'bg-blue-500/10',
    },
    {
        key: 'eco',
        label: 'Eko Mod',
        desc: 'Minimum kaynak, sessiz çalışma',
        icon: Leaf,
        color: 'from-green-500 to-emerald-500',
        borderColor: 'border-green-500',
        textColor: 'text-green-400',
        bgColor: 'bg-green-500/10',
    },
]

// ── Dikey Bar Slider ──
interface VerticalBarProps {
    value: number
    onChange: (val: number) => void
    label: string
    icon: React.ReactNode
    color: string        // tailwind gradient: "from-X to-Y"
    glowColor: string    // shadow color
    detail?: string      // alt bilgi
    disabled?: boolean
}

function VerticalBar({ value, onChange, label, icon, color, glowColor, detail, disabled }: VerticalBarProps) {
    const barRef = useRef<HTMLDivElement>(null)
    const isDragging = useRef(false)

    const calcPercent = useCallback((clientY: number) => {
        if (!barRef.current) return value
        const rect = barRef.current.getBoundingClientRect()
        const y = clientY - rect.top
        const pct = Math.round(Math.max(0, Math.min(100, ((rect.height - y) / rect.height) * 100)))
        return pct
    }, [value])

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        if (disabled) return
        e.preventDefault()
        isDragging.current = true
        const pct = calcPercent(e.clientY)
        onChange(pct)
    }, [disabled, calcPercent, onChange])

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDragging.current) return
            const pct = calcPercent(e.clientY)
            onChange(pct)
        }
        const handleMouseUp = () => {
            isDragging.current = false
        }

        // Touch events
        const handleTouchMove = (e: TouchEvent) => {
            if (!isDragging.current) return
            e.preventDefault()
            const pct = calcPercent(e.touches[0].clientY)
            onChange(pct)
        }
        const handleTouchEnd = () => {
            isDragging.current = false
        }

        window.addEventListener('mousemove', handleMouseMove)
        window.addEventListener('mouseup', handleMouseUp)
        window.addEventListener('touchmove', handleTouchMove, { passive: false })
        window.addEventListener('touchend', handleTouchEnd)

        return () => {
            window.removeEventListener('mousemove', handleMouseMove)
            window.removeEventListener('mouseup', handleMouseUp)
            window.removeEventListener('touchmove', handleTouchMove)
            window.removeEventListener('touchend', handleTouchEnd)
        }
    }, [calcPercent, onChange])

    const handleTouchStart = useCallback((e: React.TouchEvent) => {
        if (disabled) return
        e.preventDefault()
        isDragging.current = true
        const pct = calcPercent(e.touches[0].clientY)
        onChange(pct)
    }, [disabled, calcPercent, onChange])

    // Bar renkleri
    const getBarGradient = () => {
        if (value >= 80) return `bg-gradient-to-t ${color}`
        if (value >= 50) return `bg-gradient-to-t ${color} opacity-80`
        if (value >= 20) return `bg-gradient-to-t ${color} opacity-60`
        return `bg-gradient-to-t ${color} opacity-40`
    }

    return (
        <div className="flex flex-col items-center gap-3 select-none">
            {/* Yüzde değeri */}
            <div className={clsx(
                'text-2xl font-bold tabular-nums transition-colors duration-300',
                value >= 80 ? 'text-white' : value >= 50 ? 'text-dark-200' : 'text-dark-400'
            )}>
                {value}%
            </div>

            {/* Bar container */}
            <div
                ref={barRef}
                className={clsx(
                    'relative w-16 h-52 bg-dark-800/80 rounded-2xl border border-dark-600/50 overflow-hidden',
                    !disabled && 'cursor-ns-resize hover:border-dark-500',
                    disabled && 'opacity-50 cursor-not-allowed'
                )}
                onMouseDown={handleMouseDown}
                onTouchStart={handleTouchStart}
            >
                {/* Dolum */}
                <div
                    className={clsx(
                        'absolute bottom-0 left-0 right-0 rounded-b-2xl transition-all duration-150 ease-out',
                        getBarGradient()
                    )}
                    style={{
                        height: `${value}%`,
                        boxShadow: value > 10 ? `0 0 20px ${glowColor}` : 'none',
                    }}
                />

                {/* Sürükleme tutamacı */}
                {!disabled && (
                    <div
                        className="absolute left-1 right-1 h-2 rounded-full bg-white/90 shadow-lg shadow-black/30 transition-all duration-150 pointer-events-none"
                        style={{ bottom: `calc(${value}% - 4px)` }}
                    >
                        <div className="absolute inset-0 rounded-full bg-white animate-pulse opacity-40" />
                    </div>
                )}

                {/* Grid çizgileri */}
                {[25, 50, 75].map(line => (
                    <div
                        key={line}
                        className="absolute left-2 right-2 border-t border-dark-600/30 pointer-events-none"
                        style={{ bottom: `${line}%` }}
                    />
                ))}
            </div>

            {/* Etiket */}
            <div className="flex flex-col items-center gap-1">
                <div className="flex items-center gap-1.5">
                    {icon}
                    <span className="text-sm font-medium text-dark-200">{label}</span>
                </div>
                {detail && (
                    <span className="text-xs text-dark-500 text-center max-w-[80px]">{detail}</span>
                )}
            </div>
        </div>
    )
}


// ── Model Bilgi Tipleri ──
interface OllamaModel {
    name: string
    size?: number
    size_label: string
    modified_at?: string
    family?: string
    parameter_size?: string
    quantization?: string
}

interface AvailableModel {
    name: string
    size_label: string
    desc: string
    installed: boolean
    fit?: 'full' | 'partial'
    fit_label?: string
    vram_gb?: number
}

interface HardwareInfo {
    total_vram_gb: number
    gpu_count: number
    gpu_names: string[]
}

interface PullProgress {
    status: string
    completed?: number
    total?: number
}

// ── Ana Bileşen ──
export default function PerformanceTuning() {
    const [profile, setProfile] = useState<PerformanceProfile | null>(null)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

    // Slider değerleri
    const [gpuPct, setGpuPct] = useState(100)
    const [cpuPct, setCpuPct] = useState(100)
    const [ramPct, setRamPct] = useState(100)
    const [activeMode, setActiveMode] = useState('auto')

    // Model yönetim state'leri
    const [modelPanelOpen, setModelPanelOpen] = useState(false)
    const [installedModels, setInstalledModels] = useState<OllamaModel[]>([])
    const [availableModels, setAvailableModels] = useState<AvailableModel[]>([])
    const [activeModelName, setActiveModelName] = useState('')
    const [settingsModel, setSettingsModel] = useState('')
    const [modelsLoading, setModelsLoading] = useState(false)
    const [pulling, setPulling] = useState(false)
    const [pullingModel, setPullingModel] = useState('')
    const [pullProgress, setPullProgress] = useState<PullProgress | null>(null)
    const [pullPercent, setPullPercent] = useState(0)
    const [switching, setSwitching] = useState(false)
    const [deleting, setDeleting] = useState<string | null>(null)
    const [hardware, setHardware] = useState<HardwareInfo | null>(null)
    const [tps, setTps] = useState<number | null>(null)
    const [tpsLoading, setTpsLoading] = useState(false)
    const pullCancelRef = useRef<(() => void) | null>(null)

    // TPS ölç
    const loadTps = useCallback(async () => {
        setTpsLoading(true)
        try {
            const data = await adminApi.getOllamaTps()
            setTps(data.tps ?? null)
        } catch {
            setTps(null)
        } finally {
            setTpsLoading(false)
        }
    }, [])

    // Profil yükle
    useEffect(() => {
        loadProfile()
        loadTps()
    }, [])

    const loadProfile = async () => {
        setLoading(true)
        try {
            const data = await adminApi.getPerformanceProfile()
            setProfile(data)
            setGpuPct(data.gpu_percent ?? 100)
            setCpuPct(data.cpu_percent ?? 100)
            setRamPct(data.ram_percent ?? 100)
            setActiveMode(data.mode ?? 'auto')
        } catch {
            // İlk kurulumda profil olmayabilir
            setProfile(null)
        } finally {
            setLoading(false)
        }
    }

    // Model listesini yükle
    const loadModels = async () => {
        setModelsLoading(true)
        try {
            const data = await adminApi.getOllamaModels()
            setInstalledModels(data.installed || [])
            setAvailableModels(data.available || [])
            setActiveModelName(data.active_model || '')
            setSettingsModel(data.settings_model || '')
            if (data.hardware) setHardware(data.hardware)
        } catch (err) {
            setMessage({ type: 'error', text: 'Model listesi yüklenemedi' })
        } finally {
            setModelsLoading(false)
        }
    }

    // Model paneli açıldığında listele
    useEffect(() => {
        if (modelPanelOpen) {
            loadModels()
        }
    }, [modelPanelOpen])

    // Model indir
    const handlePullModel = (modelName: string) => {
        if (pulling) return
        setPulling(true)
        setPullingModel(modelName)
        setPullProgress(null)
        setPullPercent(0)
        setMessage(null)

        const cancel = adminApi.pullOllamaModel(
            modelName,
            (data) => {
                setPullProgress(data)
                if (data.completed && data.total && data.total > 0) {
                    setPullPercent(Math.round((data.completed / data.total) * 100))
                }
            },
            () => {
                setPulling(false)
                setPullingModel('')
                setPullProgress(null)
                setPullPercent(0)
                setMessage({ type: 'success', text: `${modelName} başarıyla indirildi!` })
                loadModels()
            },
            (err) => {
                setPulling(false)
                setPullingModel('')
                setPullProgress(null)
                setPullPercent(0)
                setMessage({ type: 'error', text: `İndirme hatası: ${err}` })
            },
        )
        pullCancelRef.current = cancel
    }

    // İndirmeyi iptal et
    const handleCancelPull = () => {
        if (pullCancelRef.current) {
            pullCancelRef.current()
            pullCancelRef.current = null
        }
        setPulling(false)
        setPullingModel('')
        setPullProgress(null)
        setPullPercent(0)
    }

    // Model değiştir
    const handleSwitchModel = async (modelName: string) => {
        if (switching) return
        setSwitching(true)
        setMessage(null)

        try {
            const result = await adminApi.switchOllamaModel(modelName)
            if (result.success) {
                setMessage({ type: 'success', text: `Model değiştirildi: ${result.new_model} (${result.total_layers} katman)` })
                setActiveModelName(result.active_model || modelName)
                await loadModels()
                await loadProfile() // profili yeniden yükle (katman sayısı vb.)
            }
        } catch (err: any) {
            const detail = err?.response?.data?.detail || err.message || 'Model değiştirilemedi'
            setMessage({ type: 'error', text: detail })
        } finally {
            setSwitching(false)
        }
    }

    // Model sil
    const handleDeleteModel = async (modelName: string) => {
        if (deleting) return
        if (!confirm(`"${modelName}" modelini silmek istediğinize emin misiniz?`)) return
        setDeleting(modelName)
        setMessage(null)

        try {
            const result = await adminApi.deleteOllamaModel(modelName)
            if (result.success) {
                setMessage({ type: 'success', text: `${modelName} silindi` })
                await loadModels()
            }
        } catch (err: any) {
            const detail = err?.response?.data?.detail || err.message || 'Model silinemedi'
            setMessage({ type: 'error', text: detail })
        } finally {
            setDeleting(null)
        }
    }

    // Preset uygula
    const applyPreset = (presetKey: string) => {
        const presets: Record<string, { gpu: number; cpu: number; ram: number }> = {
            full: { gpu: 100, cpu: 100, ram: 100 },
            balanced: { gpu: 65, cpu: 50, ram: 60 },
            eco: { gpu: 30, cpu: 25, ram: 30 },
        }
        const p = presets[presetKey]
        if (!p) return
        setGpuPct(p.gpu)
        setCpuPct(p.cpu)
        setRamPct(p.ram)
        setActiveMode(presetKey)
        setMessage(null)
    }

    // Slider değiştiğinde mode'u custom yap
    const handleGpuChange = (val: number) => {
        setGpuPct(val)
        setActiveMode('custom')
        setMessage(null)
    }
    const handleCpuChange = (val: number) => {
        setCpuPct(val)
        setActiveMode('custom')
        setMessage(null)
    }
    const handleRamChange = (val: number) => {
        setRamPct(val)
        setActiveMode('custom')
        setMessage(null)
    }

    // Kaydet ve uygula
    const handleSave = async () => {
        setSaving(true)
        setMessage(null)
        try {
            const result = await adminApi.updatePerformanceProfile({
                mode: activeMode,
                gpu_percent: gpuPct,
                cpu_percent: cpuPct,
                ram_percent: ramPct,
            })
            setProfile(prev => ({
                ...prev,
                ...result.profile,
                calculated_params: result.applied_params,
                live_config: result.live_config,
            }))
            setMessage({ type: 'success', text: 'Performans profili başarıyla uygulandı!' })
        } catch (err: any) {
            setMessage({ type: 'error', text: err.response?.data?.detail || 'Profil uygulanırken hata oluştu.' })
        } finally {
            setSaving(false)
        }
    }

    // Otomatik moda sıfırla
    const handleReset = async () => {
        setSaving(true)
        setMessage(null)
        try {
            const result = await adminApi.updatePerformanceProfile({
                mode: 'auto',
                gpu_percent: 100,
                cpu_percent: 100,
                ram_percent: 100,
            })
            setGpuPct(100)
            setCpuPct(100)
            setRamPct(100)
            setActiveMode('auto')
            setProfile(prev => ({
                ...prev,
                ...result.profile,
                calculated_params: result.applied_params,
                live_config: result.live_config,
            }))
            setMessage({ type: 'success', text: 'Otomatik moda sıfırlandı.' })
        } catch (err: any) {
            setMessage({ type: 'error', text: err.response?.data?.detail || 'Sıfırlama hatası.' })
        } finally {
            setSaving(false)
        }
    }

    // Hesaplanan parametreleri göster
    const getParamDetail = () => {
        // Client-side yaklaşık hesaplama (backend ile sync)
        const totalLayers = profile?.total_model_layers ?? 81
        const gpuLayers = gpuPct >= 95 ? totalLayers : gpuPct <= 5 ? 0 : Math.round(totalLayers * gpuPct / 100)
        const ctxMin = 2048, ctxMax = 32768
        const numCtx = Math.round(((ctxMax - ctxMin) * ramPct / 100 + ctxMin) / 256) * 256

        return { gpuLayers, numCtx }
    }

    const params = getParamDetail()

    if (loading) {
        return (
            <div className="card">
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin text-primary-500" />
                    <span className="ml-3 text-dark-400">Performans profili yükleniyor...</span>
                </div>
            </div>
        )
    }

    // Mode label
    const modeLabels: Record<string, string> = {
        auto: 'Otomatik',
        full: 'Tam Performans',
        balanced: 'Dengeli',
        eco: 'Eko Mod',
        custom: 'Özel Ayar',
    }

    // Değişiklik var mı?
    const hasChanges = profile ? (
        gpuPct !== (profile.gpu_percent ?? 100) ||
        cpuPct !== (profile.cpu_percent ?? 100) ||
        ramPct !== (profile.ram_percent ?? 100) ||
        activeMode !== (profile.mode ?? 'auto')
    ) : true

    return (
        <div className="card">
            {/* Başlık */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
                        <SlidersHorizontal className="w-5 h-5 text-purple-400" />
                    </div>
                    <div>
                        <h3 className="text-lg font-medium text-white">Performans Ayarları</h3>
                        <p className="text-xs text-dark-400">
                            GPU, CPU ve RAM kaynak kullanımını ayarlayın
                        </p>
                    </div>
                </div>
                <div className={clsx(
                    'px-3 py-1 rounded-full text-xs font-medium border',
                    activeMode === 'full' && 'text-orange-400 border-orange-500/30 bg-orange-500/10',
                    activeMode === 'balanced' && 'text-blue-400 border-blue-500/30 bg-blue-500/10',
                    activeMode === 'eco' && 'text-green-400 border-green-500/30 bg-green-500/10',
                    activeMode === 'custom' && 'text-purple-400 border-purple-500/30 bg-purple-500/10',
                    activeMode === 'auto' && 'text-dark-300 border-dark-600 bg-dark-800',
                )}>
                    {modeLabels[activeMode] ?? activeMode}
                </div>
            </div>

            {/* Preset Butonları */}
            <div className="grid grid-cols-3 gap-3 mb-8">
                {PRESETS.map(preset => {
                    const Icon = preset.icon
                    const isActive = activeMode === preset.key
                    return (
                        <button
                            key={preset.key}
                            onClick={() => applyPreset(preset.key)}
                            disabled={saving}
                            className={clsx(
                                'relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200',
                                isActive
                                    ? `${preset.borderColor} ${preset.bgColor} shadow-lg`
                                    : 'border-dark-600 hover:border-dark-500 bg-dark-900/30'
                            )}
                        >
                            {isActive && (
                                <div className="absolute top-2 right-2">
                                    <CheckCircle className={clsx('w-4 h-4', preset.textColor)} />
                                </div>
                            )}
                            <div className={clsx(
                                'w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br',
                                preset.color,
                                'bg-opacity-20'
                            )}>
                                <Icon className="w-5 h-5 text-white" />
                            </div>
                            <span className={clsx(
                                'text-sm font-medium',
                                isActive ? preset.textColor : 'text-dark-300'
                            )}>
                                {preset.label}
                            </span>
                            <span className="text-xs text-dark-500">{preset.desc}</span>
                        </button>
                    )
                })}
            </div>

            {/* Dikey Bar Slider'lar */}
            <div className="bg-dark-800/30 rounded-2xl border border-dark-700/50 p-6 mb-6">
                <div className="text-center mb-4">
                    <span className="text-xs text-dark-500 uppercase tracking-wider">Kaynak Ayarları — Barları sürükleyerek ayarlayın</span>
                </div>
                <div className="flex justify-center items-end gap-10 sm:gap-16">
                    <VerticalBar
                        value={gpuPct}
                        onChange={handleGpuChange}
                        label="GPU"
                        icon={<MonitorSpeaker className="w-4 h-4 text-orange-400" />}
                        color="from-orange-500 to-amber-500"
                        glowColor="rgba(249,115,22,0.3)"
                        detail={`${params.gpuLayers} katman`}
                        disabled={saving}
                    />
                    <VerticalBar
                        value={cpuPct}
                        onChange={handleCpuChange}
                        label="CPU"
                        icon={<Cpu className="w-4 h-4 text-blue-400" />}
                        color="from-blue-500 to-cyan-500"
                        glowColor="rgba(59,130,246,0.3)"
                        detail="Thread sayısı"
                        disabled={saving}
                    />
                    <VerticalBar
                        value={ramPct}
                        onChange={handleRamChange}
                        label="RAM"
                        icon={<MemoryStick className="w-4 h-4 text-green-400" />}
                        color="from-green-500 to-emerald-500"
                        glowColor="rgba(34,197,94,0.3)"
                        detail={`ctx: ${(params.numCtx / 1024).toFixed(0)}K`}
                        disabled={saving}
                    />
                </div>
            </div>

            {/* ═══ Model Yönetimi ═══ */}
            <div className="mb-6">
                {/* Aktif Model Bilgisi + Açma Butonu */}
                <button
                    onClick={() => setModelPanelOpen(!modelPanelOpen)}
                    className="w-full flex items-center justify-between gap-3 px-4 py-3 rounded-xl bg-dark-800/60 border border-dark-700/50 hover:border-dark-600 transition-colors group"
                >
                    <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-dark-400">Model:</span>
                            <span className="text-sm font-medium text-white">
                                {profile?.active_model || settingsModel || '—'}
                            </span>
                        </div>
                        {profile?.total_model_layers && (
                            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-dark-700/50">
                                <span className="text-[10px] text-dark-400">Katman:</span>
                                <span className="text-xs font-medium text-white">{profile.total_model_layers}</span>
                            </div>
                        )}
                    </div>
                    <div className="flex items-center gap-2 text-dark-400 group-hover:text-white transition-colors">
                        <span className="text-xs">Model Yönetimi</span>
                        {modelPanelOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </div>
                </button>

                {/* Model Yönetim Paneli */}
                {modelPanelOpen && (
                    <div className="mt-3 rounded-xl border border-dark-700/50 bg-dark-800/30 overflow-hidden">
                        {/* İndirme Progress Bar */}
                        {pulling && (
                            <div className="px-4 py-3 border-b border-dark-700/50 bg-gradient-to-r from-blue-500/5 to-purple-500/5">
                                <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                        <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                                        <span className="text-sm text-white font-medium">{pullingModel}</span>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-xs text-dark-400">
                                            {pullProgress?.status === 'downloading' && pullProgress.completed && pullProgress.total
                                                ? `${(pullProgress.completed / 1024 / 1024 / 1024).toFixed(1)} / ${(pullProgress.total / 1024 / 1024 / 1024).toFixed(1)} GB`
                                                : pullProgress?.status || 'Başlatılıyor...'}
                                        </span>
                                        <button
                                            onClick={handleCancelPull}
                                            className="p-1 rounded-lg hover:bg-dark-700 text-dark-400 hover:text-red-400 transition-colors"
                                            title="İptal"
                                        >
                                            <X className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                </div>
                                {/* Progress Bar */}
                                <div className="w-full h-2.5 rounded-full bg-dark-700 overflow-hidden">
                                    <div
                                        className="h-full rounded-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-300 ease-out relative"
                                        style={{ width: `${pullPercent}%` }}
                                    >
                                        <div className="absolute inset-0 bg-white/20 animate-pulse rounded-full" />
                                    </div>
                                </div>
                                <div className="flex justify-between mt-1">
                                    <span className="text-[10px] text-dark-500">İndiriliyor</span>
                                    <span className="text-xs font-medium text-blue-400">{pullPercent}%</span>
                                </div>
                            </div>
                        )}

                        {modelsLoading ? (
                            <div className="flex items-center justify-center py-8">
                                <Loader2 className="w-5 h-5 text-dark-400 animate-spin" />
                            </div>
                        ) : (
                            <>
                                {/* Yüklü Modeller */}
                                <div className="px-4 pt-3 pb-2">
                                    <div className="flex items-center justify-between mb-2">
                                        <h4 className="text-xs font-semibold text-dark-300 uppercase tracking-wider flex items-center gap-2">
                                            <HardDrive className="w-3.5 h-3.5" />
                                            Yüklü Modeller
                                        </h4>
                                        <button
                                            onClick={loadModels}
                                            disabled={modelsLoading}
                                            className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] text-dark-400 hover:text-white hover:bg-dark-700 border border-dark-700/50 hover:border-dark-600 transition-colors disabled:opacity-40"
                                            title="Listeyi yenile"
                                        >
                                            <RotateCcw className={clsx('w-3 h-3', modelsLoading && 'animate-spin')} />
                                            Güncelle
                                        </button>
                                    </div>
                                    {installedModels.length === 0 ? (
                                        <p className="text-xs text-dark-500 py-2">Henüz model bulunamadı</p>
                                    ) : (
                                        <div className="space-y-1.5">
                                            {installedModels.map(m => {
                                                const isActive = m.name === activeModelName || m.name === settingsModel
                                                return (
                                                    <div
                                                        key={m.name}
                                                        className={clsx(
                                                            'flex items-center justify-between px-3 py-2 rounded-lg border transition-colors',
                                                            isActive
                                                                ? 'border-green-500/30 bg-green-500/5'
                                                                : 'border-dark-700/40 bg-dark-800/40 hover:border-dark-600'
                                                        )}
                                                    >
                                                        <div className="flex items-center gap-2.5 min-w-0">
                                                            {isActive && <div className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" />}
                                                            <div className="min-w-0">
                                                                <span className="text-sm text-white font-medium block truncate">{m.name}</span>
                                                                <span className="text-[10px] text-dark-500">
                                                                    {m.size_label}
                                                                    {m.parameter_size ? ` • ${m.parameter_size}` : ''}
                                                                    {m.quantization ? ` • ${m.quantization}` : ''}
                                                                </span>
                                                            </div>
                                                        </div>
                                                        <div className="flex items-center gap-1.5 flex-shrink-0">
                                                            {isActive ? (
                                                                <span className="text-[10px] text-green-400 font-medium px-2 py-0.5 rounded bg-green-500/10">
                                                                    Aktif
                                                                </span>
                                                            ) : (
                                                                <>
                                                                    <button
                                                                        onClick={() => handleSwitchModel(m.name)}
                                                                        disabled={switching || pulling}
                                                                        className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] text-blue-400 hover:bg-blue-500/10 border border-blue-500/20 hover:border-blue-500/40 transition-colors disabled:opacity-40"
                                                                        title="Bu modele geç"
                                                                    >
                                                                        {switching ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowRightLeft className="w-3 h-3" />}
                                                                        Geç
                                                                    </button>
                                                                    <button
                                                                        onClick={() => handleDeleteModel(m.name)}
                                                                        disabled={!!deleting || pulling}
                                                                        className="p-1 rounded-lg text-dark-500 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40"
                                                                        title="Sil"
                                                                    >
                                                                        {deleting === m.name ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                                                                    </button>
                                                                </>
                                                            )}
                                                        </div>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    )}
                                </div>

                                {/* İndirilebilir Modeller */}
                                <div className="px-4 pt-3 pb-3 border-t border-dark-700/30">
                                    <div className="flex items-center justify-between mb-2">
                                        <h4 className="text-xs font-semibold text-dark-300 uppercase tracking-wider flex items-center gap-2">
                                            <Download className="w-3.5 h-3.5" />
                                            İndirilebilir Modeller
                                        </h4>
                                        <div className="flex items-center gap-2">
                                            {hardware && (
                                                <span className="text-[10px] text-dark-500 px-2 py-0.5 rounded bg-dark-700/50">
                                                    {hardware.gpu_count > 0
                                                        ? `${hardware.gpu_count}x GPU • ${hardware.total_vram_gb} GB VRAM`
                                                        : 'CPU Only'
                                                    }
                                                </span>
                                            )}
                                            <button
                                                onClick={loadModels}
                                                disabled={modelsLoading}
                                                className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] text-dark-400 hover:text-white hover:bg-dark-700 border border-dark-700/50 hover:border-dark-600 transition-colors disabled:opacity-40"
                                                title="Listeyi yenile"
                                            >
                                                <RotateCcw className={clsx('w-3 h-3', modelsLoading && 'animate-spin')} />
                                                Güncelle
                                            </button>
                                        </div>
                                    </div>
                                    <div className="space-y-1.5">
                                        {availableModels.map(m => (
                                            <div
                                                key={m.name}
                                                className={clsx(
                                                    'flex items-center justify-between px-3 py-2 rounded-lg border transition-colors',
                                                    m.fit === 'full'
                                                        ? 'border-dark-700/40 bg-dark-800/40 hover:border-dark-600'
                                                        : 'border-yellow-500/20 bg-yellow-500/5 hover:border-yellow-500/30'
                                                )}
                                            >
                                                <div className="flex items-center gap-2 min-w-0">
                                                    {/* Uyumluluk göstergesi */}
                                                    <div className={clsx(
                                                        'w-1.5 h-1.5 rounded-full flex-shrink-0',
                                                        m.fit === 'full' ? 'bg-green-500' : 'bg-yellow-500'
                                                    )} title={m.fit_label || ''} />
                                                    <div className="min-w-0">
                                                        <span className="text-sm text-white font-medium block truncate">{m.name}</span>
                                                        <span className="text-[10px] text-dark-500">
                                                            {m.size_label} • {m.desc}
                                                            {m.fit === 'partial' && (
                                                                <span className="text-yellow-400 ml-1">• Kısmi offload</span>
                                                            )}
                                                        </span>
                                                    </div>
                                                </div>
                                                <div className="flex-shrink-0 ml-2">
                                                    {m.installed ? (
                                                        <span className="flex items-center gap-1 text-[10px] text-green-400 px-2 py-0.5 rounded bg-green-500/10">
                                                            <CheckCircle className="w-3 h-3" />
                                                            Yüklü
                                                        </span>
                                                    ) : (
                                                        <button
                                                            onClick={() => handlePullModel(m.name)}
                                                            disabled={pulling}
                                                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] text-purple-400 hover:bg-purple-500/10 border border-purple-500/20 hover:border-purple-500/40 transition-colors disabled:opacity-40"
                                                        >
                                                            {pulling && pullingModel === m.name
                                                                ? <Loader2 className="w-3 h-3 animate-spin" />
                                                                : <Download className="w-3 h-3" />
                                                            }
                                                            İndir
                                                        </button>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                )}
            </div>

            {/* Canlı Parametreler */}
            {profile?.live_config && (
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
                    {[
                        { label: 'GPU Katman', value: profile.live_config.num_gpu === 99 ? 'Otomatik' : String(profile.live_config.num_gpu ?? '-'), sub: 'num_gpu' },
                        { label: 'CPU Thread', value: String(profile.live_config.num_thread ?? '-'), sub: 'num_thread' },
                        { label: 'Context', value: profile.live_config.num_ctx ? `${(profile.live_config.num_ctx / 1024).toFixed(0)}K` : '-', sub: 'num_ctx' },
                        { label: 'Batch', value: String(profile.live_config.num_batch ?? '-'), sub: 'num_batch' },
                    ].map(item => (
                        <div key={item.sub} className="bg-dark-800/50 rounded-xl p-3 border border-dark-700/50 text-center">
                            <p className="text-dark-400 text-xs mb-1">{item.label}</p>
                            <p className="text-white font-semibold text-lg">{item.value}</p>
                            <p className="text-dark-600 text-[10px] font-mono">{item.sub}</p>
                        </div>
                    ))}
                    {/* TPS — Donanım bazlı dinamik */}
                    <div
                        className="bg-dark-800/50 rounded-xl p-3 border border-dark-700/50 text-center cursor-pointer hover:border-dark-600 transition-colors group relative"
                        onClick={() => !tpsLoading && loadTps()}
                        title="Tıklayarak yeniden ölç"
                    >
                        <p className="text-dark-400 text-xs mb-1 flex items-center justify-center gap-1">
                            <Activity className="w-3 h-3" />
                            TPS
                        </p>
                        {tpsLoading ? (
                            <Loader2 className="w-5 h-5 animate-spin text-purple-400 mx-auto my-0.5" />
                        ) : (
                            <p className={clsx(
                                'font-semibold text-lg',
                                tps !== null && tps >= 10 ? 'text-green-400' :
                                tps !== null && tps >= 5 ? 'text-yellow-400' :
                                tps !== null ? 'text-orange-400' : 'text-dark-500'
                            )}>
                                {tps !== null ? tps.toFixed(1) : '-'}
                            </p>
                        )}
                        <p className="text-dark-600 text-[10px] font-mono">token/sn</p>
                        <div className="absolute inset-0 rounded-xl bg-white/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                </div>
            )}

            {/* Mesaj */}
            {message && (
                <div className={clsx(
                    'flex items-center gap-2 text-sm px-4 py-3 rounded-xl border mb-4',
                    message.type === 'success' && 'bg-green-500/10 border-green-500/20 text-green-400',
                    message.type === 'error' && 'bg-red-500/10 border-red-500/20 text-red-400',
                )}>
                    {message.type === 'success' ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                    {message.text}
                </div>
            )}

            {/* Aksiyon Butonları */}
            <div className="flex items-center gap-3 pt-2 border-t border-dark-700">
                <button
                    onClick={handleSave}
                    disabled={saving || !hasChanges}
                    className={clsx(
                        'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all',
                        hasChanges
                            ? 'bg-primary-600 hover:bg-primary-500 text-white shadow-lg shadow-primary-600/20'
                            : 'bg-dark-700 text-dark-500 cursor-not-allowed'
                    )}
                >
                    {saving ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                        <Save className="w-4 h-4" />
                    )}
                    Uygula & Kaydet
                </button>

                <button
                    onClick={handleReset}
                    disabled={saving || activeMode === 'auto'}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm text-dark-300 hover:text-white hover:bg-dark-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                    <RotateCcw className="w-4 h-4" />
                    Otomatiğe Sıfırla
                </button>
            </div>
        </div>
    )
}
