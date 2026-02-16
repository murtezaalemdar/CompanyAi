
import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    FileText,
    Upload,
    Trash2,
    Search,
    Database,
    AlertCircle,
    CheckCircle,
    Loader2,
    File as FileIcon,
    X,
    FolderOpen,
    Building2,
    Brain,
    Mic,
    MicOff,
    PenTool,
    MessageSquare,
    Globe,
    Play,
    Link2,
    Youtube,
    FolderTree,
    ChevronRight,
    ChevronDown,
    RefreshCw,
    Filter,
    Eye,
    Clock,
    User,
    Hash,
    ExternalLink,
    Video,
    ShieldAlert,
    Lock
} from 'lucide-react'
import clsx from 'clsx'
import { ragApi } from '../services/api'
import { DEPARTMENTS } from '../constants'
import { useAuth } from '../contexts/AuthContext'

// ═══════════════════════════════════════════════════════════════
// TİPLER
// ═══════════════════════════════════════════════════════════════
type TabType = 'upload' | 'teach' | 'url' | 'video'

interface DocumentItem {
    source: string
    type: string
    department: string
    author: string
    created_at: string
    chunk_count: number
}

interface FolderNode {
    name: string
    path: string
    files: File[]
    children: FolderNode[]
    expanded: boolean
}

// ═══════════════════════════════════════════════════════════════
// YARDIMCI FONKSİYONLAR
// ═══════════════════════════════════════════════════════════════
function getDocTypeIcon(type: string): string {
    const icons: Record<string, string> = {
        'pdf': '📄', 'docx': '📝', 'excel': '📊', 'powerpoint': '📑',
        'text': '📃', 'markdown': '📋', 'csv': '📈', 'json': '🔧',
        'python': '🐍', 'javascript': '⚡', 'typescript': '💎',
        'web_page': '🌐', 'video_transcript': '🎬', 'manual': '✍️',
        'image': '🖼️', 'email': '📧', 'epub': '📚',
        'html': '🌐', 'xml': '📐', 'sql': '🗃️', 'yaml': '⚙️',
    }
    return icons[type] || '📄'
}

function getDocTypeBadgeColor(type: string): string {
    const colors: Record<string, string> = {
        'pdf': 'bg-red-500/20 text-red-400',
        'docx': 'bg-blue-500/20 text-blue-400',
        'excel': 'bg-green-500/20 text-green-400',
        'powerpoint': 'bg-orange-500/20 text-orange-400',
        'web_page': 'bg-cyan-500/20 text-cyan-400',
        'video_transcript': 'bg-purple-500/20 text-purple-400',
        'manual': 'bg-yellow-500/20 text-yellow-400',
        'image': 'bg-pink-500/20 text-pink-400',
    }
    return colors[type] || 'bg-dark-600 text-dark-300'
}

function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function formatDate(dateStr: string): string {
    if (!dateStr) return '-'
    try {
        // ISO format veya Python datetime formatını destekle
        const normalized = dateStr.replace(' ', 'T')
        const date = new Date(normalized)
        if (isNaN(date.getTime())) return '-'
        return date.toLocaleDateString('tr-TR', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        })
    } catch {
        return '-'
    }
}

function buildFolderTree(files: File[]): FolderNode {
    const root: FolderNode = { name: 'root', path: '', files: [], children: [], expanded: true }

    for (const file of files) {
        const path = (file as any).webkitRelativePath || file.name
        const parts = path.split('/')

        if (parts.length === 1) {
            root.files.push(file)
        } else {
            let current = root
            for (let i = 0; i < parts.length - 1; i++) {
                let child = current.children.find(c => c.name === parts[i])
                if (!child) {
                    child = { name: parts[i], path: parts.slice(0, i + 1).join('/'), files: [], children: [], expanded: true }
                    current.children.push(child)
                }
                current = child
            }
            current.files.push(file)
        }
    }
    return root
}

// Kabul edilen dosya uzantıları (backend ile senkron)
const ACCEPTED_EXTENSIONS = '.txt,.md,.csv,.json,.xml,.html,.htm,.rtf,.rst,.tex,.ini,.cfg,.env,.toml,.properties,.pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.odt,.ods,.odp,.epub,.py,.js,.ts,.jsx,.tsx,.java,.cs,.cpp,.c,.h,.hpp,.sql,.yaml,.yml,.go,.rb,.php,.swift,.kt,.scala,.rs,.r,.R,.sh,.bat,.ps1,.dockerfile,.vue,.svelte,.graphql,.gql,.proto,.eml,.msg,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.tif,.webp,.log'


// ═══════════════════════════════════════════════════════════════
// KLASÖR AĞACI BİLEŞENİ
// ═══════════════════════════════════════════════════════════════
function FolderTreeView({ node, onRemoveFile, depth = 0 }: {
    node: FolderNode
    onRemoveFile: (file: File) => void
    depth?: number
}) {
    const [expanded, setExpanded] = useState(node.expanded)
    const totalFiles = countFiles(node)

    return (
        <div style={{ marginLeft: depth * 16 }}>
            {node.name !== 'root' && (
                <div
                    className="flex items-center gap-2 py-1 px-2 rounded hover:bg-dark-700 cursor-pointer text-sm"
                    onClick={() => setExpanded(!expanded)}
                >
                    {expanded ? <ChevronDown className="w-3.5 h-3.5 text-dark-400" /> : <ChevronRight className="w-3.5 h-3.5 text-dark-400" />}
                    <FolderOpen className="w-4 h-4 text-yellow-400" />
                    <span className="text-dark-200">{node.name}</span>
                    <span className="text-xs text-dark-500 ml-auto">{totalFiles} dosya</span>
                </div>
            )}
            {expanded && (
                <>
                    {node.children.map((child, i) => (
                        <FolderTreeView key={i} node={child} onRemoveFile={onRemoveFile} depth={depth + 1} />
                    ))}
                    {node.files.map((file, i) => (
                        <div key={`f-${i}`} className="flex items-center gap-2 py-1 px-2 ml-4 rounded hover:bg-dark-700 text-sm group" style={{ marginLeft: (depth + 1) * 16 }}>
                            <FileIcon className="w-3.5 h-3.5 text-primary-400" />
                            <span className="text-dark-300 truncate flex-1">{file.name}</span>
                            <span className="text-xs text-dark-500">{formatFileSize(file.size)}</span>
                            <button onClick={() => onRemoveFile(file)} className="opacity-0 group-hover:opacity-100 p-0.5 text-dark-400 hover:text-red-400">
                                <X className="w-3 h-3" />
                            </button>
                        </div>
                    ))}
                </>
            )}
        </div>
    )
}

function countFiles(node: FolderNode): number {
    return node.files.length + node.children.reduce((sum, c) => sum + countFiles(c), 0)
}


// ═══════════════════════════════════════════════════════════════
// ANA BİLEŞEN
// ═══════════════════════════════════════════════════════════════
export default function Documents() {
    const { user } = useAuth()
    const queryClient = useQueryClient()
    const [activeTab, setActiveTab] = useState<TabType>('upload')
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedFiles, setSelectedFiles] = useState<File[]>([])
    const [uploadProgress, setUploadProgress] = useState<Record<string, 'pending' | 'success' | 'error'>>({})
    const [uploadPercent, setUploadPercent] = useState<Record<string, number>>({})
    const [uploadPhase, setUploadPhase] = useState<Record<string, 'uploading' | 'processing' | 'done'>>({})
    const [uploadMessage, setUploadMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
    const [isDragging, setIsDragging] = useState(false)
    const [docListFilter, setDocListFilter] = useState<string>('all')

    // Teach Mode States
    const [teachContent, setTeachContent] = useState('')
    const [isListening, setIsListening] = useState(false)
    const recognitionRef = useRef<any>(null)

    // URL Learning States
    const [urlInput, setUrlInput] = useState('')
    const [urlTitle, setUrlTitle] = useState('')

    // Video Learning States
    const [videoUrl, setVideoUrl] = useState('')
    const [videoTitle, setVideoTitle] = useState('')
    const [videoLanguage, setVideoLanguage] = useState('tr')

    // Clear All Modal States
    const [showClearModal, setShowClearModal] = useState(false)
    const [clearPassword, setClearPassword] = useState('')
    const [clearError, setClearError] = useState('')

    // Kullanıcı departmanlarını çözümle
    const userDepartments = useMemo(() => {
        if (!user?.department) return []
        try {
            const parsed = JSON.parse(user.department)
            const depts = Array.isArray(parsed) ? parsed : [user.department]
            return depts.filter(Boolean)
        } catch {
            return user.department ? [user.department] : []
        }
    }, [user])

    const isAdmin = user?.role === 'admin' || user?.role === 'manager'
    const isRestricted = user?.role === 'user'

    // Gösterilecek departmanlar
    const availableDepartments = useMemo(() => {
        if (isRestricted) {
            return userDepartments.length > 0 ? userDepartments : ['Genel']
        }
        return ['Genel', ...DEPARTMENTS]
    }, [isRestricted, userDepartments])

    const [selectedDepartment, setSelectedDepartment] = useState(availableDepartments[0] || 'Genel')

    // ── QUERIES ──

    const { data: ragStatus } = useQuery({
        queryKey: ['rag-status'],
        queryFn: ragApi.getStatus,
        refetchInterval: 30000,
    })

    const { data: documentsData, isLoading: isLoadingDocs, refetch: refetchDocs } = useQuery({
        queryKey: ['documents-list'],
        queryFn: () => ragApi.listDocuments(),
        refetchInterval: 15000,
    })

    const { data: capabilities } = useQuery({
        queryKey: ['rag-capabilities'],
        queryFn: ragApi.getCapabilities,
        staleTime: 60000,
    })

    const { data: searchResults, isLoading: isSearching, refetch: doSearch } = useQuery({
        queryKey: ['rag-search', searchQuery],
        queryFn: () => ragApi.searchDocuments(searchQuery, 5, isRestricted ? selectedDepartment : undefined),
        enabled: false,
    })

    // ── MUTATIONS ──

    const uploadMutation = useMutation({
        mutationFn: (data: { file: File, department: string }) =>
            ragApi.uploadDocument(data.file, data.department),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['rag-status'] })
            queryClient.invalidateQueries({ queryKey: ['documents-list'] })
        }
    })

    const teachMutation = useMutation({
        mutationFn: (data: { content: string, department: string, title: string }) =>
            ragApi.teach(data.content, data.department, data.title),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['rag-status'] })
            queryClient.invalidateQueries({ queryKey: ['documents-list'] })
            setTeachContent('')
        },
    })

    const urlLearnMutation = useMutation({
        mutationFn: (data: { url: string, department: string, title?: string }) =>
            ragApi.learnFromUrl(data.url, data.department, data.title),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['rag-status'] })
            queryClient.invalidateQueries({ queryKey: ['documents-list'] })
            setUrlInput('')
            setUrlTitle('')
        },
    })

    const videoLearnMutation = useMutation({
        mutationFn: (data: { url: string, department: string, title?: string, language: string }) =>
            ragApi.learnFromVideo(data.url, data.department, data.title, data.language),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['rag-status'] })
            queryClient.invalidateQueries({ queryKey: ['documents-list'] })
            setVideoUrl('')
            setVideoTitle('')
        },
    })

    const clearAllMutation = useMutation({
        mutationFn: (password: string) => ragApi.clearAll(password),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['rag-status'] })
            queryClient.invalidateQueries({ queryKey: ['documents-list'] })
            setShowClearModal(false)
            setClearPassword('')
            setClearError('')
        },
        onError: (error: any) => {
            setClearError(error?.response?.data?.detail || 'Silme işlemi başarısız')
        }
    })

    const deleteMutation = useMutation({
        mutationFn: ragApi.deleteDocument,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['rag-status'] })
            queryClient.invalidateQueries({ queryKey: ['documents-list'] })
            if (searchQuery) doSearch()
        }
    })

    // ── EVENT HANDLERS ──

    const [micError, setMicError] = useState('')

    const switchToHttps = () => {
        const httpsUrl = window.location.href.replace('http://', 'https://')
        window.location.href = httpsUrl
    }

    const toggleListening = () => {
        setMicError('')
        if (isListening) {
            recognitionRef.current?.stop()
            setIsListening(false)
            return
        }

        // HTTPS kontrolü — SpeechRecognition sadece HTTPS veya localhost'ta çalışır
        const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1'
        if (!isSecureContext) {
            setMicError('HTTPS_REQUIRED')
            return
        }

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
            const recognition = new SpeechRecognition()
            recognition.lang = 'tr-TR'
            recognition.continuous = true
            recognition.interimResults = true
            recognition.onresult = (event: any) => {
                let finalTranscript = ''
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript
                    }
                }
                if (finalTranscript) {
                    setTeachContent(prev => prev + ' ' + finalTranscript)
                }
            }
            recognition.onerror = (event: any) => {
                setIsListening(false)
                if (event.error === 'not-allowed') {
                    setMicError('Mikrofon erişimi reddedildi. Tarayıcı ayarlarından mikrofon iznini kontrol edin.')
                } else if (event.error === 'no-speech') {
                    setMicError('Ses algılanamadı. Lütfen tekrar deneyin.')
                } else {
                    setMicError(`Sesle yazma hatası: ${event.error}`)
                }
            }
            recognition.onend = () => setIsListening(false)
            recognitionRef.current = recognition
            try {
                recognition.start()
                setIsListening(true)
            } catch (e: any) {
                setMicError('Sesle yazma başlatılamadı. Lütfen HTTPS üzerinden erişin.')
            }
        } else {
            setMicError('Tarayıcınız sesle yazmayı desteklemiyor. Chrome veya Edge kullanın.')
        }
    }

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
        const files = Array.from(e.dataTransfer.files)
        setSelectedFiles(prev => [...prev, ...files])
    }, [])

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const files = Array.from(e.target.files)
            setSelectedFiles(prev => [...prev, ...files])
        }
    }

    const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const files = Array.from(e.target.files)
            setSelectedFiles(prev => [...prev, ...files])
        }
    }

    const removeFile = (fileToRemove: File) => {
        setSelectedFiles(prev => prev.filter(f => f !== fileToRemove))
    }

    const removeFileByIndex = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index))
    }

    const uploadFiles = async () => {
        const progress: Record<string, 'pending' | 'success' | 'error'> = {}
        const phases: Record<string, 'uploading' | 'processing' | 'done'> = {}
        const percents: Record<string, number> = {}
        const errors: Record<string, string> = {}
        selectedFiles.forEach(f => {
            progress[f.name] = 'pending'
            phases[f.name] = 'uploading'
            percents[f.name] = 0
        })
        setUploadProgress(progress)
        setUploadPhase(phases)
        setUploadPercent(percents)
        setUploadMessage(null)

        let successCount = 0
        let errorCount = 0

        for (const file of selectedFiles) {
            try {
                setUploadPhase(prev => ({ ...prev, [file.name]: 'uploading' }))
                setUploadPercent(prev => ({ ...prev, [file.name]: 0 }))

                await ragApi.uploadDocument(file, selectedDepartment, (percent) => {
                    setUploadPercent(prev => ({ ...prev, [file.name]: percent }))
                    if (percent >= 100) {
                        setUploadPhase(prev => ({ ...prev, [file.name]: 'processing' }))
                    }
                })

                setUploadProgress(prev => ({ ...prev, [file.name]: 'success' }))
                setUploadPhase(prev => ({ ...prev, [file.name]: 'done' }))
                setUploadPercent(prev => ({ ...prev, [file.name]: 100 }))
                successCount++
                queryClient.invalidateQueries({ queryKey: ['rag-status'] })
                queryClient.invalidateQueries({ queryKey: ['documents-list'] })
            } catch (err: any) {
                errorCount++
                let errorMsg = 'Bilinmeyen hata'
                const status = err?.response?.status
                if (status === 413) {
                    errorMsg = `Dosya çok büyük (${formatFileSize(file.size)}). Maksimum 500 MB.`
                } else if (status === 408 || err?.code === 'ECONNABORTED') {
                    errorMsg = 'Zaman aşımı — dosya çok büyük veya bağlantı yavaş'
                } else if (status === 500) {
                    errorMsg = 'Sunucu hatası — dosya işlenirken bir sorun oluştu'
                } else if (err?.message?.includes('Network Error')) {
                    errorMsg = 'Bağlantı hatası — ağ bağlantınızı kontrol edin'
                } else if (err?.response?.data?.detail) {
                    errorMsg = err.response.data.detail
                }
                errors[file.name] = errorMsg
                setUploadProgress(prev => ({ ...prev, [file.name]: 'error' }))
                setUploadPhase(prev => ({ ...prev, [file.name]: 'done' }))
            }
        }

        // Sonuç bildirimi
        if (errorCount === 0 && successCount > 0) {
            setUploadMessage({ type: 'success', text: `${successCount} dosya başarıyla yüklendi ve öğrenildi!` })
        } else if (errorCount > 0 && successCount > 0) {
            const errNames = Object.keys(errors)
            setUploadMessage({ type: 'error', text: `${successCount} başarılı, ${errorCount} başarısız: ${errNames.map(n => `${n} (${errors[n]})`).join(', ')}` })
        } else if (errorCount > 0) {
            const firstErr = Object.values(errors)[0]
            setUploadMessage({ type: 'error', text: `Yükleme başarısız: ${firstErr}` })
        }

        setTimeout(() => {
            setSelectedFiles([])
            setUploadProgress({})
            setUploadPercent({})
            setUploadPhase({})
        }, errorCount > 0 ? 6000 : 3000)

        // Mesajı daha uzun göster
        setTimeout(() => setUploadMessage(null), 8000)
    }

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault()
        if (searchQuery.trim()) doSearch()
    }

    const handleClearAll = () => {
        setShowClearModal(true)
        setClearPassword('')
        setClearError('')
    }

    const handleClearConfirm = () => {
        if (!clearPassword.trim()) {
            setClearError('Şifrenizi girin')
            return
        }
        clearAllMutation.mutate(clearPassword)
    }

    const handleTeachSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (!teachContent.trim()) return
        const title = teachContent.split('\n')[0].substring(0, 50) + (teachContent.length > 50 ? '...' : '')
        teachMutation.mutate({ content: teachContent, department: selectedDepartment, title })
    }

    const handleUrlSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (!urlInput.trim()) return
        urlLearnMutation.mutate({ url: urlInput.trim(), department: selectedDepartment, title: urlTitle || undefined })
    }

    const handleVideoSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (!videoUrl.trim()) return
        videoLearnMutation.mutate({ url: videoUrl.trim(), department: selectedDepartment, title: videoTitle || undefined, language: videoLanguage })
    }

    // ── COMPUTED ──

    const documents: DocumentItem[] = documentsData?.documents || []

    const filteredDocuments = useMemo(() => {
        if (docListFilter === 'all') return documents
        return documents.filter(d => d.type === docListFilter || d.department === docListFilter)
    }, [documents, docListFilter])

    const documentTypes = useMemo(() => {
        const types = new Set(documents.map(d => d.type))
        return Array.from(types).sort()
    }, [documents])

    const documentDepartments = useMemo(() => {
        const depts = new Set(documents.map(d => d.department))
        return Array.from(depts).sort()
    }, [documents])

    const folderTree = useMemo(() => buildFolderTree(selectedFiles), [selectedFiles])

    // ── TABS CONFIG ──
    const tabs: { id: TabType; label: string; icon: any; desc: string }[] = [
        { id: 'upload', label: 'Dosya Yükle', icon: Upload, desc: 'Dosya veya klasör yükleyin' },
        { id: 'teach', label: 'Bilgi Gir', icon: PenTool, desc: 'Metin ile öğretin' },
        { id: 'url', label: 'URL Öğren', icon: Globe, desc: 'Web sayfasından öğrenin' },
        { id: 'video', label: 'Video Öğren', icon: Play, desc: 'YouTube videosundan öğrenin' },
    ]

    // ═══════════════════════════════════════════════════════════════
    // RENDER
    // ═══════════════════════════════════════════════════════════════
    return (
        <div className="space-y-6">
            {/* ── HEADER ── */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                    <h1 className="text-xl sm:text-2xl font-bold text-white">Doküman Yönetimi & Öğrenme</h1>
                    <p className="text-dark-400 mt-1 text-sm">
                        {isRestricted
                            ? `${userDepartments.join(', ')} departmanı için içerik yönetimi`
                            : 'Departman bazlı doküman yükleyin, URL & video ile eğitin'}
                    </p>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                    {capabilities && (
                        <div className="hidden md:flex items-center gap-2 text-xs text-dark-500">
                            {capabilities.web_scraping && <span className="px-2 py-1 bg-cyan-500/10 text-cyan-400 rounded">🌐 URL</span>}
                            {capabilities.youtube_transcript && <span className="px-2 py-1 bg-purple-500/10 text-purple-400 rounded">🎬 Video</span>}
                            {capabilities.ocr && <span className="px-2 py-1 bg-pink-500/10 text-pink-400 rounded">🖼️ OCR</span>}
                        </div>
                    )}
                    {ragStatus && (
                        <div className={clsx(
                            'flex items-center gap-2 px-4 py-2 rounded-lg',
                            ragStatus.available ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                        )}>
                            <Database className="w-5 h-5" />
                            <span className="font-medium">
                                {ragStatus.available ? `${ragStatus.document_count} Doküman` : 'RAG Devre Dışı'}
                            </span>
                        </div>
                    )}
                </div>
            </div>

            {/* ── ÜST BÖLÜM: Öğrenme Araçları + Arama ── */}
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

                {/* ── SOL: Öğrenme Araçları (3/5) ── */}
                <div className="lg:col-span-3 card">
                    {/* Sekmeler */}
                    <div className="flex border-b border-dark-700 mb-5 overflow-x-auto">
                        {tabs.map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={clsx(
                                    'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap',
                                    activeTab === tab.id
                                        ? 'border-primary-500 text-white'
                                        : 'border-transparent text-dark-400 hover:text-dark-300'
                                )}
                            >
                                <tab.icon className="w-4 h-4" />
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* Departman seçici */}
                    <div className="mb-4">
                        <label className="block text-xs font-medium text-dark-400 mb-1.5">
                            Hangi departman için öğrenilecek?
                        </label>
                        <div className="relative">
                            <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                            <select
                                value={selectedDepartment}
                                onChange={(e) => setSelectedDepartment(e.target.value)}
                                className="input pl-10 w-full"
                                disabled={isRestricted && availableDepartments.length === 1}
                            >
                                {availableDepartments.map(dept => (
                                    <option key={dept} value={dept}>{dept}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* ═══ DOSYA YÜKLE TAB ═══ */}
                    {activeTab === 'upload' && (
                        <>
                            <div
                                onDrop={handleDrop}
                                onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                                onDragLeave={() => setIsDragging(false)}
                                className={clsx(
                                    'border-2 border-dashed rounded-xl p-8 text-center transition-all',
                                    isDragging ? 'border-primary-400 bg-primary-500/10' : 'border-dark-700 hover:border-dark-600'
                                )}
                            >
                                <Upload className="w-12 h-12 text-dark-400 mx-auto mb-4" />
                                <p className="text-white font-medium mb-1">Dosyaları buraya sürükleyin</p>
                                <p className="text-xs text-dark-500 mb-4">PDF, Office, Kod, Resim ve 60+ format desteklenir</p>
                                <div className="flex items-center justify-center gap-3">
                                    <label className="btn-secondary cursor-pointer inline-flex items-center gap-2">
                                        <input type="file" multiple accept={ACCEPTED_EXTENSIONS} onChange={handleFileSelect} className="hidden" />
                                        <FileIcon className="w-4 h-4" />
                                        Dosya Seç
                                    </label>
                                    <label className="btn-secondary cursor-pointer inline-flex items-center gap-2">
                                        <input
                                            type="file"
                                            /* @ts-ignore */
                                            webkitdirectory=""
                                            directory=""
                                            multiple
                                            onChange={handleFolderSelect}
                                            className="hidden"
                                        />
                                        <FolderTree className="w-4 h-4" />
                                        Klasör Seç
                                    </label>
                                </div>
                            </div>

                            {/* Seçilen dosyalar - Klasör ağacı veya düz liste */}
                            {selectedFiles.length > 0 && (
                                <div className="mt-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-sm text-dark-300 font-medium">
                                            {selectedFiles.length} dosya seçildi
                                        </span>
                                        <button
                                            onClick={() => setSelectedFiles([])}
                                            className="text-xs text-dark-400 hover:text-red-400 flex items-center gap-1"
                                        >
                                            <X className="w-3 h-3" /> Temizle
                                        </button>
                                    </div>

                                    <div className="bg-dark-800 rounded-lg p-3 max-h-64 overflow-y-auto">
                                        {folderTree.children.length > 0 ? (
                                            /* Klasör ağacı görünümü */
                                            <FolderTreeView node={folderTree} onRemoveFile={removeFile} />
                                        ) : (
                                            /* Düz dosya listesi */
                                            <div className="space-y-1">
                                                {selectedFiles.map((file, index) => {
                                                    const status = uploadProgress[file.name]
                                                    const phase = uploadPhase[file.name]
                                                    const percent = uploadPercent[file.name] ?? 0

                                                    return (
                                                        <div key={index} className="relative py-1.5 px-2 rounded hover:bg-dark-700 group overflow-hidden">
                                                            {/* Animated progress background */}
                                                            {status === 'pending' && (
                                                                <div className="absolute inset-0 rounded overflow-hidden">
                                                                    {phase === 'uploading' ? (
                                                                        <div
                                                                            className="absolute inset-y-0 left-0 bg-gradient-to-r from-primary-500/20 via-primary-400/30 to-primary-500/10 transition-all duration-300 ease-out"
                                                                            style={{ width: `${percent}%` }}
                                                                        >
                                                                            <div className="absolute inset-0 animate-upload-shimmer bg-gradient-to-r from-transparent via-white/10 to-transparent" />
                                                                        </div>
                                                                    ) : (
                                                                        <div className="absolute inset-0 bg-gradient-to-r from-amber-500/10 via-amber-400/20 to-amber-500/10">
                                                                            <div className="absolute inset-0 animate-upload-shimmer bg-gradient-to-r from-transparent via-white/10 to-transparent" />
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )}
                                                            {status === 'success' && (
                                                                <div className="absolute inset-0 rounded bg-green-500/10 animate-fade-in" />
                                                            )}
                                                            {status === 'error' && (
                                                                <div className="absolute inset-0 rounded bg-red-500/10 animate-fade-in" />
                                                            )}

                                                            {/* Content */}
                                                            <div className="relative flex items-center justify-between z-10">
                                                                <div className="flex items-center gap-2 min-w-0">
                                                                    <FileText className="w-4 h-4 text-primary-400 flex-shrink-0" />
                                                                    <span className="text-sm text-dark-200 truncate">{file.name}</span>
                                                                </div>
                                                                <div className="flex items-center gap-2 flex-shrink-0">
                                                                    {/* Phase-specific status */}
                                                                    {status === 'pending' && phase === 'uploading' && percent < 100 && (
                                                                        <span className="text-xs text-primary-300 font-medium tabular-nums min-w-[3ch] text-right">%{percent}</span>
                                                                    )}
                                                                    {status === 'pending' && phase === 'processing' && (
                                                                        <span className="text-xs text-amber-300 flex items-center gap-1">
                                                                            <Brain className="w-3 h-3 animate-pulse" /> Öğreniyor
                                                                        </span>
                                                                    )}
                                                                    <span className="text-xs text-dark-500">{formatFileSize(file.size)}</span>
                                                                    {status === 'success' && <CheckCircle className="w-4 h-4 text-green-400" />}
                                                                    {status === 'error' && <AlertCircle className="w-4 h-4 text-red-400" />}
                                                                    {status === 'pending' && <Loader2 className="w-4 h-4 text-primary-400 animate-spin" />}
                                                                    {!status && (
                                                                        <button onClick={() => removeFileByIndex(index)} className="opacity-0 group-hover:opacity-100 p-0.5 text-dark-400 hover:text-red-400">
                                                                            <X className="w-3.5 h-3.5" />
                                                                        </button>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    )
                                                })}
                                            </div>
                                        )}
                                    </div>

                                    <button
                                        onClick={uploadFiles}
                                        disabled={Object.keys(uploadProgress).length > 0}
                                        className="relative w-full mt-3 overflow-hidden rounded-lg"
                                    >
                                        {Object.keys(uploadProgress).length > 0 ? (
                                            (() => {
                                                const total = selectedFiles.length
                                                const completed = selectedFiles.filter(f => uploadProgress[f.name] === 'success' || uploadProgress[f.name] === 'error').length
                                                const currentFile = selectedFiles.find(f => uploadProgress[f.name] === 'pending')
                                                const currentPhase = currentFile ? uploadPhase[currentFile.name] : null
                                                const currentPercent = currentFile ? (uploadPercent[currentFile.name] ?? 0) : 0
                                                const overallPercent = total > 0 ? Math.round(((completed + (currentPercent / 100)) / total) * 100) : 0
                                                const allDone = completed === total

                                                return (
                                                    <div className="relative bg-dark-800 border border-dark-600 rounded-lg overflow-hidden">
                                                        {/* Background progress fill */}
                                                        <div
                                                            className="absolute inset-y-0 left-0 bg-gradient-to-r from-primary-600/30 via-primary-500/40 to-primary-400/30 transition-all duration-500 ease-out"
                                                            style={{ width: `${overallPercent}%` }}
                                                        >
                                                            <div className="absolute inset-0 animate-upload-shimmer bg-gradient-to-r from-transparent via-white/15 to-transparent" />
                                                        </div>
                                                        {/* Content */}
                                                        <div className="relative z-10 flex items-center justify-between px-4 py-2.5">
                                                            <div className="flex items-center gap-2">
                                                                {allDone ? (
                                                                    <CheckCircle className="w-4 h-4 text-green-400" />
                                                                ) : currentPhase === 'processing' ? (
                                                                    <Brain className="w-4 h-4 text-amber-300 animate-pulse" />
                                                                ) : (
                                                                    <Loader2 className="w-4 h-4 text-primary-300 animate-spin" />
                                                                )}
                                                                <span className="text-sm font-medium text-white">
                                                                    {allDone
                                                                        ? 'Tamamlandı!'
                                                                        : currentPhase === 'processing'
                                                                            ? `Öğreniyor... (${completed + 1}/${total})`
                                                                            : `Yükleniyor... %${currentPercent} (${completed + 1}/${total})`
                                                                    }
                                                                </span>
                                                            </div>
                                                            <span className="text-xs font-bold text-primary-200 tabular-nums">%{overallPercent}</span>
                                                        </div>
                                                    </div>
                                                )
                                            })()
                                        ) : (
                                            <div className="btn-primary w-full flex justify-center items-center gap-2">
                                                <Brain className="w-4 h-4" /> Yükle ve Öğren ({selectedFiles.length} dosya)
                                            </div>
                                        )}
                                    </button>

                                    {/* Upload sonuç bildirimi */}
                                    {uploadMessage && (
                                        <div className={clsx(
                                            'mt-3 flex items-start gap-2 text-sm p-3 rounded-lg animate-fade-in',
                                            uploadMessage.type === 'success'
                                                ? 'text-green-400 bg-green-500/10 border border-green-500/20'
                                                : 'text-red-400 bg-red-500/10 border border-red-500/20'
                                        )}>
                                            {uploadMessage.type === 'success'
                                                ? <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                                                : <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                                            }
                                            <span>{uploadMessage.text}</span>
                                        </div>
                                    )}
                                </div>
                            )}
                        </>
                    )}

                    {/* ═══ BİLGİ GİR TAB ═══ */}
                    {activeTab === 'teach' && (
                        <form onSubmit={handleTeachSubmit} className="space-y-4">
                            <div className="relative">
                                <textarea
                                    value={teachContent}
                                    onChange={(e) => setTeachContent(e.target.value)}
                                    placeholder="Bilgiyi buraya yazın veya mikrofonu kullanın..."
                                    className="input w-full h-48 resize-none p-4"
                                />
                                <button
                                    type="button"
                                    onClick={toggleListening}
                                    className={clsx(
                                        "absolute bottom-4 right-4 p-2 rounded-full",
                                        isListening ? "bg-red-500 animate-pulse text-white" : "text-dark-400 hover:text-white"
                                    )}
                                >
                                    {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                                </button>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-xs text-dark-500">{teachContent.length} karakter</span>
                                <button
                                    type="submit"
                                    disabled={!teachContent.trim() || teachMutation.isPending}
                                    className="btn-primary flex items-center gap-2"
                                >
                                    {teachMutation.isPending
                                        ? <><Loader2 className="w-4 h-4 animate-spin" /> Öğretiliyor...</>
                                        : <><MessageSquare className="w-4 h-4" /> Bilgiyi Öğret</>
                                    }
                                </button>
                            </div>
                            {teachMutation.isSuccess && (
                                <div className="flex items-center gap-2 text-sm text-green-400 bg-green-500/10 p-3 rounded-lg">
                                    <CheckCircle className="w-4 h-4" /> Bilgi başarıyla öğretildi!
                                </div>
                            )}
                            {teachMutation.isError && (
                                <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 p-3 rounded-lg">
                                    <AlertCircle className="w-4 h-4" /> Bilgi öğretilirken hata oluştu.
                                </div>
                            )}
                            {micError && (
                                <div className="flex items-center justify-between text-sm text-amber-400 bg-amber-500/10 p-3 rounded-lg">
                                    <div className="flex items-center gap-2">
                                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                                        <span>
                                            {micError === 'HTTPS_REQUIRED'
                                                ? 'Sesle yazma güvenli bağlantı (HTTPS) gerektirir.'
                                                : micError}
                                        </span>
                                    </div>
                                    {micError === 'HTTPS_REQUIRED' && (
                                        <button
                                            type="button"
                                            onClick={switchToHttps}
                                            className="ml-3 px-3 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 rounded text-xs font-medium whitespace-nowrap transition-colors"
                                        >
                                            🔒 HTTPS'e Geç
                                        </button>
                                    )}
                                </div>
                            )}
                        </form>
                    )}

                    {/* ═══ URL ÖĞREN TAB ═══ */}
                    {activeTab === 'url' && (
                        <form onSubmit={handleUrlSubmit} className="space-y-4">
                            <div>
                                <label className="block text-xs font-medium text-dark-400 mb-1.5">Web Sayfası URL'si</label>
                                <div className="relative">
                                    <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                                    <input
                                        type="url"
                                        value={urlInput}
                                        onChange={(e) => setUrlInput(e.target.value)}
                                        placeholder="https://ornek.com/makale"
                                        className="input pl-10 w-full"
                                        required
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-dark-400 mb-1.5">Başlık (Opsiyonel)</label>
                                <input
                                    type="text"
                                    value={urlTitle}
                                    onChange={(e) => setUrlTitle(e.target.value)}
                                    placeholder="Otomatik sayfa başlığı kullanılır"
                                    className="input w-full"
                                />
                            </div>
                            <div className="bg-dark-800 rounded-lg p-3 text-xs text-dark-400 space-y-1">
                                <p>💡 <strong className="text-dark-300">İpucu:</strong> Herhangi bir web sayfasının URL'sini girin.</p>
                                <p>Sistem sayfayı otomatik olarak tarar, ana içeriği çıkarır ve öğrenir.</p>
                                <p>Blog yazıları, dokümentasyon, haber siteleri vb. desteklenir.</p>
                            </div>
                            <button
                                type="submit"
                                disabled={!urlInput.trim() || urlLearnMutation.isPending}
                                className="btn-primary w-full flex justify-center items-center gap-2"
                            >
                                {urlLearnMutation.isPending
                                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Sayfa taranıyor...</>
                                    : <><Link2 className="w-4 h-4" /> URL'den Öğren</>
                                }
                            </button>
                            {urlLearnMutation.isSuccess && (
                                <div className="flex items-center gap-2 text-sm text-green-400 bg-green-500/10 p-3 rounded-lg">
                                    <CheckCircle className="w-4 h-4" />
                                    <span>Web sayfası öğrenildi! ({urlLearnMutation.data?.chars?.toLocaleString()} karakter)</span>
                                </div>
                            )}
                            {urlLearnMutation.isError && (
                                <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 p-3 rounded-lg">
                                    <AlertCircle className="w-4 h-4" />
                                    <span>{(urlLearnMutation.error as any)?.response?.data?.detail || 'URL işlenirken hata oluştu.'}</span>
                                </div>
                            )}
                        </form>
                    )}

                    {/* ═══ VİDEO ÖĞREN TAB ═══ */}
                    {activeTab === 'video' && (
                        <form onSubmit={handleVideoSubmit} className="space-y-4">
                            <div>
                                <label className="block text-xs font-medium text-dark-400 mb-1.5">YouTube Video URL'si</label>
                                <div className="relative">
                                    <Youtube className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                                    <input
                                        type="url"
                                        value={videoUrl}
                                        onChange={(e) => setVideoUrl(e.target.value)}
                                        placeholder="https://youtube.com/watch?v=..."
                                        className="input pl-10 w-full"
                                        required
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-medium text-dark-400 mb-1.5">Başlık (Opsiyonel)</label>
                                    <input
                                        type="text"
                                        value={videoTitle}
                                        onChange={(e) => setVideoTitle(e.target.value)}
                                        placeholder="Otomatik video başlığı"
                                        className="input w-full"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-dark-400 mb-1.5">Altyazı Dili</label>
                                    <select
                                        value={videoLanguage}
                                        onChange={(e) => setVideoLanguage(e.target.value)}
                                        className="input w-full"
                                    >
                                        <option value="tr">Türkçe</option>
                                        <option value="en">İngilizce</option>
                                        <option value="de">Almanca</option>
                                        <option value="fr">Fransızca</option>
                                        <option value="es">İspanyolca</option>
                                        <option value="ar">Arapça</option>
                                        <option value="ru">Rusça</option>
                                        <option value="zh">Çince</option>
                                        <option value="ja">Japonca</option>
                                    </select>
                                </div>
                            </div>
                            <div className="bg-dark-800 rounded-lg p-3 text-xs text-dark-400 space-y-1">
                                <p>🎬 <strong className="text-dark-300">İpucu:</strong> YouTube video linkini girin.</p>
                                <p>Sistem videonun altyazısını (subtitle/transcript) çıkarır ve öğrenir.</p>
                                <p>Videonun altyazıya sahip olması gerekir (elle eklenmiş veya otomatik).</p>
                            </div>
                            <button
                                type="submit"
                                disabled={!videoUrl.trim() || videoLearnMutation.isPending}
                                className="btn-primary w-full flex justify-center items-center gap-2"
                            >
                                {videoLearnMutation.isPending
                                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Video işleniyor...</>
                                    : <><Video className="w-4 h-4" /> Videodan Öğren</>
                                }
                            </button>
                            {videoLearnMutation.isSuccess && (
                                <div className="flex items-center gap-2 text-sm text-green-400 bg-green-500/10 p-3 rounded-lg">
                                    <CheckCircle className="w-4 h-4" />
                                    <span>Video içeriği öğrenildi! ({videoLearnMutation.data?.chars?.toLocaleString()} karakter, Dil: {videoLearnMutation.data?.language})</span>
                                </div>
                            )}
                            {videoLearnMutation.isError && (
                                <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 p-3 rounded-lg">
                                    <AlertCircle className="w-4 h-4" />
                                    <span>{(videoLearnMutation.error as any)?.response?.data?.detail || 'Video işlenirken hata oluştu.'}</span>
                                </div>
                            )}
                        </form>
                    )}

                    {/* Admin: Tümünü Sil */}
                    {isAdmin && ragStatus && ragStatus.document_count > 0 && (
                        <div className="mt-6 pt-4 border-t border-dark-700">
                            <button
                                onClick={handleClearAll}
                                className="flex items-center gap-2 text-sm text-red-400 hover:text-red-300"
                            >
                                <Trash2 className="w-4 h-4" />
                                Tüm Hafızayı Temizle (Admin)
                            </button>
                        </div>
                    )}
                </div>

                {/* ═══ CLEAR ALL MODAL ═══ */}
                {showClearModal && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                        <div className="bg-dark-800 border border-red-500/50 rounded-xl shadow-2xl w-full max-w-md mx-4 p-0 overflow-hidden">
                            {/* Modal Header - Kırmızı uyarı bandı */}
                            <div className="bg-red-500/20 border-b border-red-500/30 px-6 py-4 flex items-center gap-3">
                                <div className="p-2 bg-red-500/20 rounded-full">
                                    <ShieldAlert className="w-6 h-6 text-red-400" />
                                </div>
                                <div>
                                    <h3 className="text-lg font-semibold text-red-400">Kritik Uyarı!</h3>
                                    <p className="text-xs text-red-300/70">Bu işlem geri alınamaz</p>
                                </div>
                            </div>

                            <div className="px-6 py-5 space-y-4">
                                {/* Uyarı mesajları */}
                                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 space-y-2">
                                    <p className="text-sm text-red-300 font-medium">
                                        Bu işlem aşağıdaki verileri kalıcı olarak silecektir:
                                    </p>
                                    <ul className="text-xs text-red-300/80 space-y-1 ml-4 list-disc">
                                        <li><strong>TÜM departmanlardaki</strong> tüm dokümanlar silinecek</li>
                                        <li>Yüklenen dosyalar, URL'lerden öğrenilenler, video transkriptleri</li>
                                        <li>Manuel girilen bilgiler dahil tüm RAG hafızası</li>
                                        <li className="font-semibold text-red-400">Toplam {ragStatus?.document_count || 0} doküman</li>
                                    </ul>
                                </div>

                                {/* Şifre girişi */}
                                <div>
                                    <label className="block text-xs font-medium text-dark-300 mb-1.5">
                                        Onaylamak için admin şifrenizi girin:
                                    </label>
                                    <div className="relative">
                                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                                        <input
                                            type="password"
                                            value={clearPassword}
                                            onChange={(e) => { setClearPassword(e.target.value); setClearError('') }}
                                            onKeyDown={(e) => e.key === 'Enter' && handleClearConfirm()}
                                            placeholder="Admin şifresi"
                                            className="input pl-10 w-full"
                                            autoFocus
                                        />
                                    </div>
                                    {clearError && (
                                        <p className="text-xs text-red-400 mt-1.5 flex items-center gap-1">
                                            <AlertCircle className="w-3 h-3" /> {clearError}
                                        </p>
                                    )}
                                </div>

                                {/* Butonlar */}
                                <div className="flex gap-3 pt-2">
                                    <button
                                        onClick={() => { setShowClearModal(false); setClearPassword(''); setClearError('') }}
                                        className="btn-secondary flex-1"
                                        disabled={clearAllMutation.isPending}
                                    >
                                        İptal
                                    </button>
                                    <button
                                        onClick={handleClearConfirm}
                                        disabled={clearAllMutation.isPending || !clearPassword.trim()}
                                        className="flex-1 bg-red-600 hover:bg-red-500 disabled:bg-red-800 disabled:text-red-400 text-white font-medium px-6 py-2.5 rounded-lg transition-all flex items-center justify-center gap-2"
                                    >
                                        {clearAllMutation.isPending
                                            ? <><Loader2 className="w-4 h-4 animate-spin" /> Siliniyor...</>
                                            : <><Trash2 className="w-4 h-4" /> Tümünü Sil</>
                                        }
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* ── SAĞ: Hafızada Ara (2/5) ── */}
                <div className="lg:col-span-2 card">
                    <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                        <Search className="w-5 h-5 text-primary-400" />
                        Hafızada Ara
                    </h2>

                    <form onSubmit={handleSearch} className="flex gap-2 mb-4">
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Ara..."
                            className="input flex-1"
                        />
                        <button type="submit" disabled={isSearching || !searchQuery.trim()} className="btn-primary px-4">
                            {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                        </button>
                    </form>

                    <div className="space-y-3 max-h-[500px] overflow-y-auto">
                        {searchResults && searchResults.length > 0 ? (
                            searchResults.map((result: any, index: number) => (
                                <div key={index} className="p-3 bg-dark-800 rounded-lg group relative border border-dark-700">
                                    <div className="flex items-center justify-between mb-1.5">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <span className="text-sm font-medium text-primary-400 truncate">{result.source}</span>
                                        </div>
                                        <span className="text-xs text-dark-400 flex-shrink-0">{Math.round(result.relevance * 100)}%</span>
                                    </div>
                                    <p className="text-sm text-dark-300 line-clamp-3">{result.content}</p>
                                    {isAdmin && (
                                        <button
                                            onClick={() => { if (confirm(`"${result.source}" silinsin mi?`)) deleteMutation.mutate(result.source) }}
                                            className="absolute top-2 right-2 p-1 text-dark-400 hover:text-red-400 opacity-0 group-hover:opacity-100"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    )}
                                </div>
                            ))
                        ) : searchResults ? (
                            <div className="text-center py-8 text-dark-400">
                                <Search className="w-8 h-8 mx-auto mb-2 opacity-30" />
                                Sonuç bulunamadı
                            </div>
                        ) : (
                            <div className="text-center py-8 text-dark-500">
                                <Brain className="w-8 h-8 mx-auto mb-2 opacity-20" />
                                <p className="text-sm">Hafızada arama yapın</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ═══════════════════════════════════════════════════════════════ */}
            {/* ALT BÖLÜM: DOKÜMAN LİSTESİ                                     */}
            {/* ═══════════════════════════════════════════════════════════════ */}
            <div className="card">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-medium text-white flex items-center gap-2">
                        <FolderOpen className="w-5 h-5 text-primary-400" />
                        Doküman Kütüphanesi
                        <span className="text-sm font-normal text-dark-400">({filteredDocuments.length})</span>
                    </h2>
                    <div className="flex items-center gap-2">
                        {/* Filtre */}
                        <div className="relative">
                            <Filter className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-dark-400" />
                            <select
                                value={docListFilter}
                                onChange={(e) => setDocListFilter(e.target.value)}
                                className="input pl-8 pr-3 py-1.5 text-xs"
                            >
                                <option value="all">Tümü</option>
                                <optgroup label="Tür">
                                    {documentTypes.map(t => (
                                        <option key={t} value={t}>{getDocTypeIcon(t)} {t}</option>
                                    ))}
                                </optgroup>
                                <optgroup label="Departman">
                                    {documentDepartments.map(d => (
                                        <option key={d} value={d}>🏢 {d}</option>
                                    ))}
                                </optgroup>
                            </select>
                        </div>
                        <button
                            onClick={() => refetchDocs()}
                            className="p-2 text-dark-400 hover:text-white rounded-lg hover:bg-dark-700"
                            title="Yenile"
                        >
                            <RefreshCw className={clsx("w-4 h-4", isLoadingDocs && "animate-spin")} />
                        </button>
                    </div>
                </div>

                {isLoadingDocs ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
                        <span className="ml-3 text-dark-400">Dokümanlar yükleniyor...</span>
                    </div>
                ) : filteredDocuments.length === 0 ? (
                    <div className="text-center py-12">
                        <FolderOpen className="w-12 h-12 text-dark-600 mx-auto mb-3" />
                        <p className="text-dark-400 font-medium">Henüz doküman yok</p>
                        <p className="text-dark-500 text-sm mt-1">Yukarıdaki araçları kullanarak doküman ekleyin</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-dark-700">
                                    <th className="text-left text-xs font-medium text-dark-400 pb-3 pl-3">Kaynak</th>
                                    <th className="text-left text-xs font-medium text-dark-400 pb-3 hidden sm:table-cell">Tür</th>
                                    <th className="text-left text-xs font-medium text-dark-400 pb-3 hidden md:table-cell">Departman</th>
                                    <th className="text-left text-xs font-medium text-dark-400 pb-3 hidden lg:table-cell">Ekleyen</th>
                                    <th className="text-left text-xs font-medium text-dark-400 pb-3 hidden sm:table-cell">Tarih</th>
                                    <th className="text-center text-xs font-medium text-dark-400 pb-3 hidden md:table-cell">Parça</th>
                                    <th className="text-right text-xs font-medium text-dark-400 pb-3 pr-3">İşlem</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredDocuments.map((doc, index) => (
                                    <tr key={index} className="border-b border-dark-800 hover:bg-dark-800/50 group transition-colors">
                                        <td className="py-2.5 pl-3">
                                            <div className="flex items-center gap-2 min-w-0">
                                                <span className="text-base flex-shrink-0">{getDocTypeIcon(doc.type)}</span>
                                                <span className="text-sm text-dark-200 truncate max-w-[250px]" title={doc.source}>
                                                    {doc.source}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="py-2.5 hidden sm:table-cell">
                                            <span className={clsx('text-xs px-2 py-0.5 rounded-full', getDocTypeBadgeColor(doc.type))}>
                                                {doc.type}
                                            </span>
                                        </td>
                                        <td className="py-2.5 hidden md:table-cell">
                                            <span className="flex items-center gap-1 text-xs text-dark-300">
                                                <Building2 className="w-3 h-3" />
                                                {doc.department}
                                            </span>
                                        </td>
                                        <td className="py-2.5 hidden lg:table-cell">
                                            <span className="flex items-center gap-1 text-xs text-dark-400">
                                                <User className="w-3 h-3" />
                                                {doc.author || '-'}
                                            </span>
                                        </td>
                                        <td className="py-2.5 hidden sm:table-cell">
                                            <span className="flex items-center gap-1 text-xs text-dark-500">
                                                <Clock className="w-3 h-3" />
                                                {formatDate(doc.created_at)}
                                            </span>
                                        </td>
                                        <td className="py-2.5 text-center hidden md:table-cell">
                                            <span className="flex items-center justify-center gap-1 text-xs text-dark-400">
                                                <Hash className="w-3 h-3" />
                                                {doc.chunk_count}
                                            </span>
                                        </td>
                                        <td className="py-2.5 pr-3 text-right">
                                            <button
                                                onClick={() => {
                                                    if (confirm(`"${doc.source}" dokümanını silmek istediğinize emin misiniz?`))
                                                        deleteMutation.mutate(doc.source)
                                                }}
                                                disabled={deleteMutation.isPending}
                                                className="p-1.5 text-dark-500 hover:text-red-400 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity rounded hover:bg-red-500/10"
                                                title="Sil"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    )
}
