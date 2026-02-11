import { useState, useEffect, useRef } from 'react'
import {
    Save, Upload, Trash2, ImageIcon, CheckCircle, AlertCircle,
    HardDrive, Clock, RotateCcw, Download, Shield, Database,
    Calendar, PlayCircle, Loader2, ChevronDown, ChevronUp,
    FileArchive, AlertTriangle, Info, RefreshCw, X, UploadCloud,
    Timer
} from 'lucide-react'
import { logoApi, backupApi } from '../services/api'
import clsx from 'clsx'

export default function Settings() {
    const [formData, setFormData] = useState({
        notifications: true,
        theme: 'dark',
        language: 'tr',
        apiKey: 'sk-....................',
    })

    // Logo state
    const [logoPreview, setLogoPreview] = useState<string | null>(null)
    const [logoFile, setLogoFile] = useState<File | null>(null)
    const [logoUploading, setLogoUploading] = useState(false)
    const [logoMessage, setLogoMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    // Mevcut logoyu yükle
    useEffect(() => {
        logoApi.getLogo().then(data => {
            if (data.logo) setLogoPreview(data.logo)
        }).catch(() => {})
    }, [])

    const handleLogoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        // Tip kontrolü
        const allowed = ['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp']
        if (!allowed.includes(file.type)) {
            setLogoMessage({ type: 'error', text: 'Yalnızca PNG, JPEG, SVG ve WebP dosyaları desteklenir.' })
            return
        }

        // Boyut kontrolü (2MB)
        if (file.size > 2 * 1024 * 1024) {
            setLogoMessage({ type: 'error', text: 'Logo dosyası 2MB\'dan büyük olamaz.' })
            return
        }

        setLogoFile(file)
        setLogoMessage(null)

        // Preview
        const reader = new FileReader()
        reader.onload = (ev) => setLogoPreview(ev.target?.result as string)
        reader.readAsDataURL(file)
    }

    const handleLogoUpload = async () => {
        if (!logoFile) return
        setLogoUploading(true)
        setLogoMessage(null)
        try {
            const data = await logoApi.uploadLogo(logoFile)
            setLogoPreview(data.logo)
            setLogoFile(null)
            setLogoMessage({ type: 'success', text: 'Logo başarıyla kaydedildi!' })
        } catch (err: any) {
            setLogoMessage({ type: 'error', text: err.response?.data?.detail || 'Logo yüklenirken hata oluştu.' })
        } finally {
            setLogoUploading(false)
        }
    }

    const handleLogoDelete = async () => {
        try {
            await logoApi.deleteLogo()
            setLogoPreview(null)
            setLogoFile(null)
            setLogoMessage({ type: 'success', text: 'Logo silindi.' })
        } catch {
            setLogoMessage({ type: 'error', text: 'Logo silinirken hata oluştu.' })
        }
    }

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        alert('Ayarlar kaydedildi (Demo)')
    }

    // ── Backup State ─────────────────────────────────
    interface BackupItem {
        filename: string
        size_mb: number
        created_at: string
        tables: string[]
        note?: string
        row_counts?: Record<string, number>
        chromadb_included?: boolean
        chromadb_size_mb?: number
    }

    const [backups, setBackups] = useState<BackupItem[]>([])
    const [backupLoading, setBackupLoading] = useState(false)
    const [backupCreating, setBackupCreating] = useState(false)
    const [backupMessage, setBackupMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null)
    const [backupNote, setBackupNote] = useState('')
    const [showBackupSection, setShowBackupSection] = useState(true)
    const [expandedBackup, setExpandedBackup] = useState<string | null>(null)
    const [restoreConfirm, setRestoreConfirm] = useState<string | null>(null)
    const [restoring, setRestoring] = useState(false)
    const [deletingBackup, setDeletingBackup] = useState<string | null>(null)

    // Zamanlama state
    const [schedule, setSchedule] = useState({
        enabled: false,
        frequency: 'daily',
        time: '03:00',
        day_of_week: 0,
        day_of_month: 1,
        max_keep: 10,
        note: '',
        next_run: null as string | null,
        last_run: null as string | null,
    })
    const [scheduleLoading, setScheduleLoading] = useState(false)
    const [scheduleSaving, setScheduleSaving] = useState(false)

    // Info state
    const [backupInfo, setBackupInfo] = useState<any>(null)

    const backupFileInputRef = useRef<HTMLInputElement>(null)

    // Yedekleri ve zamanlama bilgisini yükle
    useEffect(() => {
        loadBackups()
        loadSchedule()
        loadBackupInfo()
    }, [])

    const loadBackups = async () => {
        setBackupLoading(true)
        try {
            const data = await backupApi.list()
            setBackups(data.backups || [])
        } catch {
            // sessiz
        } finally {
            setBackupLoading(false)
        }
    }

    const loadSchedule = async () => {
        setScheduleLoading(true)
        try {
            const data = await backupApi.getSchedule()
            setSchedule(prev => ({ ...prev, ...data }))
        } catch {
            // sessiz
        } finally {
            setScheduleLoading(false)
        }
    }

    const loadBackupInfo = async () => {
        try {
            const data = await backupApi.getInfo()
            setBackupInfo(data)
        } catch {
            // sessiz
        }
    }

    const handleCreateBackup = async () => {
        setBackupCreating(true)
        setBackupMessage(null)
        try {
            const data = await backupApi.create(backupNote || undefined)
            setBackupMessage({ type: 'success', text: `Yedek oluşturuldu: ${data.filename} (${data.total_rows} satır, ${data.size_mb} MB)` })
            setBackupNote('')
            loadBackups()
            loadBackupInfo()
        } catch (err: any) {
            setBackupMessage({ type: 'error', text: err.response?.data?.detail || 'Yedek oluşturulurken hata oluştu.' })
        } finally {
            setBackupCreating(false)
        }
    }

    const handleDeleteBackup = async (filename: string) => {
        setDeletingBackup(filename)
        try {
            await backupApi.deleteBackup(filename)
            setBackups(prev => prev.filter(b => b.filename !== filename))
            setBackupMessage({ type: 'success', text: `${filename} silindi.` })
            loadBackupInfo()
        } catch {
            setBackupMessage({ type: 'error', text: 'Silme hatası.' })
        } finally {
            setDeletingBackup(null)
        }
    }

    const handleRestore = async (filename: string) => {
        setRestoring(true)
        setBackupMessage(null)
        try {
            const data = await backupApi.restore(filename, true)
            const restored = Object.values(data.results as Record<string, any>)
                .reduce((sum: number, r: any) => sum + (r.restored || 0), 0)
            setBackupMessage({ type: 'success', text: `Geri yükleme başarılı! ${restored} satır geri yüklendi. (Kaynak: ${data.restored_from})` })
            setRestoreConfirm(null)
        } catch (err: any) {
            setBackupMessage({ type: 'error', text: err.response?.data?.detail || 'Geri yükleme hatası.' })
        } finally {
            setRestoring(false)
        }
    }

    const handleUploadBackup = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return
        setBackupMessage(null)
        try {
            await backupApi.upload(file)
            setBackupMessage({ type: 'success', text: `Yedek dosyası yüklendi: ${file.name}` })
            loadBackups()
        } catch (err: any) {
            setBackupMessage({ type: 'error', text: err.response?.data?.detail || 'Dosya yükleme hatası.' })
        }
        e.target.value = ''
    }

    const handleSaveSchedule = async () => {
        setScheduleSaving(true)
        try {
            const data = await backupApi.updateSchedule({
                enabled: schedule.enabled,
                frequency: schedule.frequency,
                time: schedule.time,
                day_of_week: schedule.day_of_week,
                day_of_month: schedule.day_of_month,
                max_keep: schedule.max_keep,
                note: schedule.note || undefined,
            })
            setSchedule(prev => ({ ...prev, ...data.schedule }))
            setBackupMessage({ type: 'success', text: 'Zamanlama ayarları kaydedildi.' })
        } catch {
            setBackupMessage({ type: 'error', text: 'Zamanlama kaydedilemedi.' })
        } finally {
            setScheduleSaving(false)
        }
    }

    const handleDownloadBackup = (filename: string) => {
        const url = backupApi.download(filename)
        window.open(url, '_blank')
    }

    const formatDate = (iso: string) => {
        try {
            return new Date(iso).toLocaleString('tr-TR', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
            })
        } catch { return iso }
    }

    const frequencyLabels: Record<string, string> = {
        daily: 'Her Gün',
        weekly: 'Her Hafta',
        monthly: 'Her Ay',
    }

    const dayLabels = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']

    return (
        <div className="flex flex-col lg:flex-row gap-6 max-w-7xl items-start">
            {/* ══ SOL KOLON — Genel Ayarlar ══════════════════════ */}
            <div className="w-full lg:w-1/2 space-y-6">
            {/* ── Şirket Logosu ─────────────────────────────── */}
            <div className="card">
                <h3 className="text-lg font-medium text-white mb-4">Şirket Logosu</h3>
                <p className="text-xs text-dark-400 mb-4">
                    Login sayfasında gösterilecek şirket logosunu yükleyin. PNG, JPEG, SVG veya WebP — maks 2MB.
                </p>

                <div className="flex items-center gap-6">
                    {/* Preview */}
                    <div className="shrink-0 w-32 h-32 rounded-xl border-2 border-dashed border-dark-600 bg-dark-800/50 flex items-center justify-center overflow-hidden">
                        {logoPreview ? (
                            <img src={logoPreview} alt="Logo" className="max-w-full max-h-full object-contain p-2" />
                        ) : (
                            <ImageIcon className="w-10 h-10 text-dark-600" />
                        )}
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col gap-2">
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/png,image/jpeg,image/svg+xml,image/webp"
                            onChange={handleLogoSelect}
                            className="hidden"
                        />
                        <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            className="btn-primary flex items-center gap-2 text-sm"
                        >
                            <Upload className="w-4 h-4" />
                            Logo Seç
                        </button>

                        {logoFile && (
                            <button
                                type="button"
                                onClick={handleLogoUpload}
                                disabled={logoUploading}
                                className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white transition-colors disabled:opacity-50"
                            >
                                {logoUploading ? (
                                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                ) : (
                                    <Save className="w-4 h-4" />
                                )}
                                Kaydet
                            </button>
                        )}

                        {logoPreview && !logoFile && (
                            <button
                                type="button"
                                onClick={handleLogoDelete}
                                className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-400 transition-colors"
                            >
                                <Trash2 className="w-4 h-4" />
                                Logoyu Kaldır
                            </button>
                        )}
                    </div>
                </div>

                {/* Message */}
                {logoMessage && (
                    <div className={`mt-4 flex items-center gap-2 text-sm ${
                        logoMessage.type === 'success' ? 'text-green-400' : 'text-red-400'
                    }`}>
                        {logoMessage.type === 'success' ? (
                            <CheckCircle className="w-4 h-4" />
                        ) : (
                            <AlertCircle className="w-4 h-4" />
                        )}
                        {logoMessage.text}
                    </div>
                )}
            </div>

            {/* ── Genel Ayarlar ─────────────────────────────── */}
            <div className="card">
                <h3 className="text-lg font-medium text-white mb-6">Sistem Ayarları</h3>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-dark-200 mb-2">
                            Bildirim Tercihleri
                        </label>
                        <div className="flex items-center gap-3">
                            <input
                                type="checkbox"
                                id="notifications"
                                checked={formData.notifications}
                                onChange={(e) => setFormData({ ...formData, notifications: e.target.checked })}
                                className="w-4 h-4 rounded border-dark-600 bg-dark-800 text-primary-600 focus:ring-primary-500"
                            />
                            <label htmlFor="notifications" className="text-sm text-dark-400">
                                Email bildirimlerini al
                            </label>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-dark-200 mb-2">
                            Tema
                        </label>
                        <select
                            value={formData.theme}
                            onChange={(e) => setFormData({ ...formData, theme: e.target.value })}
                            className="input"
                        >
                            <option value="dark">Koyu Tema</option>
                            <option value="light">Açık Tema</option>
                            <option value="system">Sistem Teması</option>
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-dark-200 mb-2">
                            LLM API Key (Opsiyonel)
                        </label>
                        <input
                            type="password"
                            value={formData.apiKey}
                            onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                            className="input font-mono"
                        />
                        <p className="mt-1 text-xs text-dark-500">
                            Harici LLM servisi kullanıyorsanız API anahtarını buraya girin.
                        </p>
                    </div>

                    <div className="pt-4 border-t border-dark-700">
                        <button type="submit" className="btn-primary flex items-center gap-2">
                            <Save className="w-4 h-4" />
                            Kaydet
                        </button>
                    </div>
                </form>
            </div>
            </div>{/* SOL KOLON SONU */}

            {/* ══ SAĞ KOLON — Yedekleme ══════════════════════════ */}
            <div className="w-full lg:w-1/2 min-w-0">
            {/* ── Yedekleme & Geri Yükleme ─────────────────────── */}
            <div className="card">
                <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setShowBackupSection(!showBackupSection)}
                >
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center">
                            <HardDrive className="w-5 h-5 text-blue-400" />
                        </div>
                        <div>
                            <h3 className="text-lg font-medium text-white">Yedekleme & Geri Yükleme</h3>
                            <p className="text-xs text-dark-400">
                                Veritabanı yedekle, zamanla ve geri yükle
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {backupInfo && (
                            <span className="text-xs text-dark-500 hidden sm:inline">
                                {backupInfo.backup_count} yedek • {backupInfo.backup_total_size_mb} MB
                            </span>
                        )}
                        {showBackupSection ? (
                            <ChevronUp className="w-5 h-5 text-dark-400" />
                        ) : (
                            <ChevronDown className="w-5 h-5 text-dark-400" />
                        )}
                    </div>
                </div>

                {showBackupSection && (
                    <div className="mt-6 space-y-6">
                        {/* Bilgi Mesajı */}
                        {backupMessage && (
                            <div className={clsx(
                                "flex items-start gap-2 text-sm px-4 py-3 rounded-xl border",
                                backupMessage.type === 'success' && "bg-green-500/10 border-green-500/20 text-green-400",
                                backupMessage.type === 'error' && "bg-red-500/10 border-red-500/20 text-red-400",
                                backupMessage.type === 'info' && "bg-blue-500/10 border-blue-500/20 text-blue-400",
                            )}>
                                {backupMessage.type === 'success' ? <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" /> :
                                 backupMessage.type === 'error' ? <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" /> :
                                 <Info className="w-4 h-4 mt-0.5 shrink-0" />}
                                <span className="flex-1">{backupMessage.text}</span>
                                <button onClick={() => setBackupMessage(null)} className="p-0.5 hover:bg-white/10 rounded">
                                    <X className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        )}

                        {/* Genel Bilgi Kartları */}
                        {backupInfo && (
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                <div className="bg-dark-800/50 rounded-xl p-3 border border-dark-700/50">
                                    <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
                                        <Database className="w-3.5 h-3.5" />
                                        Veritabanı
                                    </div>
                                    <p className="text-white font-semibold text-lg">{backupInfo.database_size_mb} MB</p>
                                    <p className="text-dark-500 text-xs">{backupInfo.total_rows?.toLocaleString('tr-TR')} satır</p>
                                </div>
                                <div className="bg-dark-800/50 rounded-xl p-3 border border-dark-700/50">
                                    <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
                                        <FileArchive className="w-3.5 h-3.5" />
                                        Yedekler
                                    </div>
                                    <p className="text-white font-semibold text-lg">{backupInfo.backup_count}</p>
                                    <p className="text-dark-500 text-xs">{backupInfo.backup_total_size_mb} MB toplam</p>
                                </div>
                                <div className="bg-dark-800/50 rounded-xl p-3 border border-dark-700/50">
                                    <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
                                        <Timer className="w-3.5 h-3.5" />
                                        Zamanlama
                                    </div>
                                    <p className={clsx("font-semibold text-lg", schedule.enabled ? "text-green-400" : "text-dark-500")}>
                                        {schedule.enabled ? 'Aktif' : 'Kapalı'}
                                    </p>
                                    <p className="text-dark-500 text-xs">
                                        {schedule.enabled ? frequencyLabels[schedule.frequency] : '—'}
                                    </p>
                                </div>
                                <div className="bg-dark-800/50 rounded-xl p-3 border border-dark-700/50">
                                    <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
                                        <Shield className="w-3.5 h-3.5" />
                                        AI Hafıza
                                    </div>
                                    <p className={clsx("font-semibold text-lg", backupInfo.chromadb_available ? "text-green-400" : "text-dark-500")}>
                                        {backupInfo.chromadb_available ? `${backupInfo.chromadb_size_mb} MB` : 'Yok'}
                                    </p>
                                    <p className="text-dark-500 text-xs">ChromaDB vektör</p>
                                </div>
                            </div>
                        )}

                        {/* ── Manuel Yedekleme ──────────────────────────── */}
                        <div className="bg-dark-800/30 rounded-xl p-4 border border-dark-700/50">
                            <h4 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
                                <PlayCircle className="w-4 h-4 text-blue-400" />
                                Manuel Yedekleme
                            </h4>
                            <div className="flex flex-col sm:flex-row gap-2">
                                <input
                                    type="text"
                                    value={backupNote}
                                    onChange={(e) => setBackupNote(e.target.value)}
                                    placeholder="Yedek notu (opsiyonel)..."
                                    className="input flex-1 text-sm"
                                />
                                <div className="flex gap-2">
                                    <button
                                        type="button"
                                        onClick={handleCreateBackup}
                                        disabled={backupCreating}
                                        className="btn-primary flex items-center gap-2 text-sm whitespace-nowrap disabled:opacity-50"
                                    >
                                        {backupCreating ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                            <HardDrive className="w-4 h-4" />
                                        )}
                                        Yedek Al
                                    </button>
                                    <input
                                        ref={backupFileInputRef}
                                        type="file"
                                        accept=".zip"
                                        onChange={handleUploadBackup}
                                        className="hidden"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => backupFileInputRef.current?.click()}
                                        className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg bg-dark-700 hover:bg-dark-600 text-dark-300 hover:text-white transition-colors"
                                        title="Harici yedek dosyası yükle"
                                    >
                                        <UploadCloud className="w-4 h-4" />
                                        <span className="hidden sm:inline">Yükle</span>
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* ── Otomatik Zamanlama ──────────────────────── */}
                        <div className="bg-dark-800/30 rounded-xl p-4 border border-dark-700/50">
                            <h4 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
                                <Calendar className="w-4 h-4 text-purple-400" />
                                Otomatik Zamanlama
                            </h4>

                            <div className="space-y-4">
                                {/* Aktif/Pasif Toggle */}
                                <div className="flex items-center justify-between">
                                    <label className="text-sm text-dark-300">Otomatik yedekleme</label>
                                    <button
                                        type="button"
                                        onClick={() => setSchedule(prev => ({ ...prev, enabled: !prev.enabled }))}
                                        className={clsx(
                                            "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
                                            schedule.enabled ? "bg-green-500" : "bg-dark-600"
                                        )}
                                    >
                                        <span
                                            className={clsx(
                                                "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                                                schedule.enabled ? "translate-x-6" : "translate-x-1"
                                            )}
                                        />
                                    </button>
                                </div>

                                {schedule.enabled && (
                                    <>
                                        {/* Sıklık + Saat */}
                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                            <div>
                                                <label className="block text-xs text-dark-400 mb-1">Sıklık</label>
                                                <select
                                                    value={schedule.frequency}
                                                    onChange={(e) => setSchedule(prev => ({ ...prev, frequency: e.target.value }))}
                                                    className="input text-sm w-full"
                                                >
                                                    <option value="daily">Her Gün</option>
                                                    <option value="weekly">Her Hafta</option>
                                                    <option value="monthly">Her Ay</option>
                                                </select>
                                            </div>

                                            <div>
                                                <label className="block text-xs text-dark-400 mb-1">Saat</label>
                                                <input
                                                    type="time"
                                                    value={schedule.time}
                                                    onChange={(e) => setSchedule(prev => ({ ...prev, time: e.target.value }))}
                                                    className="input text-sm w-full"
                                                />
                                            </div>

                                            {schedule.frequency === 'weekly' && (
                                                <div>
                                                    <label className="block text-xs text-dark-400 mb-1">Gün</label>
                                                    <select
                                                        value={schedule.day_of_week}
                                                        onChange={(e) => setSchedule(prev => ({ ...prev, day_of_week: parseInt(e.target.value) }))}
                                                        className="input text-sm w-full"
                                                    >
                                                        {dayLabels.map((day, i) => (
                                                            <option key={i} value={i}>{day}</option>
                                                        ))}
                                                    </select>
                                                </div>
                                            )}

                                            {schedule.frequency === 'monthly' && (
                                                <div>
                                                    <label className="block text-xs text-dark-400 mb-1">Ayın Günü</label>
                                                    <select
                                                        value={schedule.day_of_month}
                                                        onChange={(e) => setSchedule(prev => ({ ...prev, day_of_month: parseInt(e.target.value) }))}
                                                        className="input text-sm w-full"
                                                    >
                                                        {Array.from({ length: 28 }, (_, i) => (
                                                            <option key={i + 1} value={i + 1}>{i + 1}</option>
                                                        ))}
                                                    </select>
                                                </div>
                                            )}
                                        </div>

                                        {/* Maks. Yedek + Not */}
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                            <div>
                                                <label className="block text-xs text-dark-400 mb-1">Maks. Saklanan Yedek</label>
                                                <input
                                                    type="number"
                                                    min={1}
                                                    max={50}
                                                    value={schedule.max_keep}
                                                    onChange={(e) => setSchedule(prev => ({ ...prev, max_keep: parseInt(e.target.value) || 10 }))}
                                                    className="input text-sm w-full"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs text-dark-400 mb-1">Not</label>
                                                <input
                                                    type="text"
                                                    value={schedule.note || ''}
                                                    onChange={(e) => setSchedule(prev => ({ ...prev, note: e.target.value }))}
                                                    placeholder="Otomatik yedek"
                                                    className="input text-sm w-full"
                                                />
                                            </div>
                                        </div>

                                        {/* Sonraki çalışma */}
                                        {schedule.next_run && (
                                            <div className="flex items-center gap-2 text-xs text-dark-400 bg-dark-900/50 px-3 py-2 rounded-lg">
                                                <Clock className="w-3.5 h-3.5 text-blue-400" />
                                                Sonraki çalışma: <span className="text-white">{formatDate(schedule.next_run)}</span>
                                            </div>
                                        )}
                                    </>
                                )}

                                {/* Kaydet Butonu */}
                                <button
                                    type="button"
                                    onClick={handleSaveSchedule}
                                    disabled={scheduleSaving}
                                    className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white transition-colors disabled:opacity-50"
                                >
                                    {scheduleSaving ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Save className="w-4 h-4" />
                                    )}
                                    Zamanlamayı Kaydet
                                </button>
                            </div>
                        </div>

                        {/* ── Yedek Listesi ──────────────────────────────── */}
                        <div>
                            <div className="flex items-center justify-between mb-3">
                                <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                                    <FileArchive className="w-4 h-4 text-cyan-400" />
                                    Mevcut Yedekler
                                </h4>
                                <button
                                    type="button"
                                    onClick={() => { loadBackups(); loadBackupInfo() }}
                                    className="flex items-center gap-1 text-xs text-dark-400 hover:text-white transition-colors"
                                >
                                    <RefreshCw className={clsx("w-3.5 h-3.5", backupLoading && "animate-spin")} />
                                    Yenile
                                </button>
                            </div>

                            {backupLoading && backups.length === 0 ? (
                                <div className="flex items-center justify-center py-8">
                                    <Loader2 className="w-6 h-6 text-dark-400 animate-spin" />
                                </div>
                            ) : backups.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-8 text-dark-500">
                                    <HardDrive className="w-10 h-10 mb-2 opacity-30" />
                                    <p className="text-sm">Henüz yedek bulunmuyor</p>
                                    <p className="text-xs mt-1">Üstteki "Yedek Al" butonuyla ilk yedeğinizi oluşturun.</p>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {backups.map((b) => (
                                        <div
                                            key={b.filename}
                                            className={clsx(
                                                "bg-dark-800/50 rounded-xl border transition-all",
                                                expandedBackup === b.filename
                                                    ? "border-primary-500/30 ring-1 ring-primary-500/10"
                                                    : "border-dark-700/50 hover:border-dark-600"
                                            )}
                                        >
                                            {/* Yedek Satırı */}
                                            <div
                                                className="flex items-center gap-3 p-3 cursor-pointer"
                                                onClick={() => setExpandedBackup(expandedBackup === b.filename ? null : b.filename)}
                                            >
                                                <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center shrink-0">
                                                    <FileArchive className="w-4 h-4 text-blue-400" />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm text-white font-medium truncate">{b.filename}</p>
                                                    <div className="flex items-center gap-3 text-xs text-dark-400 mt-0.5">
                                                        <span>{formatDate(b.created_at)}</span>
                                                        <span>{b.size_mb} MB</span>
                                                        {b.chromadb_included && <span className="text-green-400">🧠 AI</span>}
                                                        {b.note && <span className="truncate max-w-[150px]">{b.note}</span>}
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-1 shrink-0">
                                                    <button
                                                        type="button"
                                                        onClick={(e) => { e.stopPropagation(); handleDownloadBackup(b.filename) }}
                                                        className="p-1.5 rounded-lg hover:bg-dark-700 text-dark-400 hover:text-blue-400 transition-colors"
                                                        title="İndir"
                                                    >
                                                        <Download className="w-4 h-4" />
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={(e) => { e.stopPropagation(); setRestoreConfirm(b.filename) }}
                                                        className="p-1.5 rounded-lg hover:bg-dark-700 text-dark-400 hover:text-green-400 transition-colors"
                                                        title="Geri Yükle"
                                                    >
                                                        <RotateCcw className="w-4 h-4" />
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={(e) => { e.stopPropagation(); handleDeleteBackup(b.filename) }}
                                                        disabled={deletingBackup === b.filename}
                                                        className="p-1.5 rounded-lg hover:bg-dark-700 text-dark-400 hover:text-red-400 transition-colors disabled:opacity-50"
                                                        title="Sil"
                                                    >
                                                        {deletingBackup === b.filename ? (
                                                            <Loader2 className="w-4 h-4 animate-spin" />
                                                        ) : (
                                                            <Trash2 className="w-4 h-4" />
                                                        )}
                                                    </button>
                                                </div>
                                            </div>

                                            {/* Genişletilmiş Detaylar */}
                                            {expandedBackup === b.filename && (
                                                <div className="px-3 pb-3 pt-0 border-t border-dark-700/30 mt-0">
                                                    <div className="pt-3 space-y-2">
                                                        {b.tables && b.tables.length > 0 && (
                                                            <div>
                                                                <p className="text-xs text-dark-400 mb-1.5">İçerdiği Tablolar:</p>
                                                                <div className="flex flex-wrap gap-1.5">
                                                                    {b.tables.map((t) => (
                                                                        <span
                                                                            key={t}
                                                                            className="px-2 py-0.5 text-xs rounded-md bg-dark-700/50 text-dark-300 border border-dark-600/50"
                                                                        >
                                                                            {t}
                                                                            {b.row_counts?.[t] != null && (
                                                                                <span className="ml-1 text-dark-500">({b.row_counts[t]})</span>
                                                                            )}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                        {b.note && (
                                                            <p className="text-xs text-dark-400">
                                                                <span className="text-dark-500">Not:</span> {b.note}
                                                            </p>
                                                        )}
                                                        {b.chromadb_included && (
                                                            <div className="flex items-center gap-1.5 mt-1">
                                                                <span className="px-2 py-0.5 text-xs rounded-md bg-green-900/30 text-green-400 border border-green-700/50">
                                                                    ✓ AI Hafıza (ChromaDB) dahil — {b.chromadb_size_mb || '?'} MB
                                                                </span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Tablo İstatistikleri */}
                        {backupInfo?.table_stats && (
                            <div className="bg-dark-800/30 rounded-xl p-4 border border-dark-700/50">
                                <h4 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
                                    <Database className="w-4 h-4 text-emerald-400" />
                                    Tablo İstatistikleri
                                </h4>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                    {Object.entries(backupInfo.table_stats as Record<string, number>).map(([table, count]) => (
                                        <div key={table} className="bg-dark-900/50 rounded-lg px-3 py-2 border border-dark-700/30">
                                            <p className="text-xs text-dark-400 truncate">{table}</p>
                                            <p className="text-sm text-white font-semibold">
                                                {(count as number) >= 0 ? (count as number).toLocaleString('tr-TR') : '—'}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            </div>{/* SAĞ KOLON SONU */}

            {/* Restore Onay Modalı */}
            {restoreConfirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="bg-dark-900 border border-dark-700 rounded-2xl p-6 max-w-md mx-4 shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-12 h-12 bg-orange-500/20 rounded-xl flex items-center justify-center">
                                <AlertTriangle className="w-6 h-6 text-orange-400" />
                            </div>
                            <div>
                                <h3 className="text-lg font-semibold text-white">Geri Yükleme Onayı</h3>
                                <p className="text-xs text-dark-400">Bu işlem geri alınamaz!</p>
                            </div>
                        </div>
                        <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-3 mb-4">
                            <p className="text-sm text-red-300 leading-relaxed">
                                <strong>⚠️ DİKKAT:</strong> Bu işlem mevcut veritabanındaki <strong>tüm verileri silecek</strong> ve
                                seçilen yedekteki verilerle değiştirecektir.
                            </p>
                        </div>
                        <p className="text-sm text-dark-300 mb-1">
                            Yedek: <span className="text-white font-mono text-xs">{restoreConfirm}</span>
                        </p>
                        <p className="text-xs text-dark-500 mb-6">
                            Devam etmeden önce güncel bir yedek almanızı öneririz.
                        </p>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setRestoreConfirm(null)}
                                disabled={restoring}
                                className="flex-1 px-4 py-2.5 text-sm bg-dark-800 hover:bg-dark-700 text-white rounded-xl transition-colors"
                            >
                                Vazgeç
                            </button>
                            <button
                                onClick={() => handleRestore(restoreConfirm)}
                                disabled={restoring}
                                className="flex-1 px-4 py-2.5 text-sm bg-orange-600 hover:bg-orange-700 text-white rounded-xl transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                            >
                                {restoring ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <RotateCcw className="w-4 h-4" />
                                )}
                                Evet, Geri Yükle
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
