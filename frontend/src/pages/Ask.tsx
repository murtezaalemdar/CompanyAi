import { useState, useRef, useEffect, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { aiApi } from '../services/api'
import {
    Send,
    Loader2,
    Bot,
    User as UserIcon,
    AlertTriangle,
    Paperclip,
    Image as ImageIcon,
    Camera,
    FileText,
    X,
    Eye,
    Download,
    Mic,
    MicOff,
    Building2,
    Trash2,
    Sparkles,
    Brain,
    ShieldX,
    MessageSquarePlus,
    History,
    ChevronLeft
} from 'lucide-react'
import clsx from 'clsx'
import FileUploadModal from '../components/FileUploadModal'
import WeatherCard from '../components/WeatherCard'
import ImageResultsCard from '../components/ImageResultsCard'
import ExportCard from '../components/ExportCard'
import QuickExportButtons from '../components/QuickExportButtons'
import { useAuth } from '../contexts/AuthContext'
import { DEPARTMENTS }  from '../constants'

interface AttachedFile {
    id: string
    file: File
    preview?: string
    type: 'image' | 'document' | 'other'
}

interface Message {
    id: string
    role: 'user' | 'assistant'
    content: string
    attachments?: AttachedFile[]
    rich_data?: any
    metadata?: {
        department?: string
        risk_level?: string
        processing_time_ms?: number
    }
}

interface ChatSessionInfo {
    id: number
    title: string
    is_active?: boolean
    created_at: string
    updated_at?: string
    message_count?: number
}

export default function Ask() {
    const [input, setInput] = useState('')
    const [messages, setMessages] = useState<Message[]>([])
    const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([])
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
    const [previewImage, setPreviewImage] = useState<string | null>(null)
    const [isDragging, setIsDragging] = useState(false)

    // Session state
    const [currentSessionId, setCurrentSessionId] = useState<number | null>(null)
    const [sessions, setSessions] = useState<ChatSessionInfo[]>([])
    const [showSessions, setShowSessions] = useState(false)
    const [sessionsLoaded, setSessionsLoaded] = useState(false)

    // Departman Mantığı
    const { user } = useAuth()

    const userDepartments = user?.department ? (() => {
        try {
            const parsed = JSON.parse(user.department)
            return Array.isArray(parsed) ? parsed : [user.department]
        } catch {
            return [user.department]
        }
    })() : []

    const isRestricted = user?.role === 'user'

    const availableDepartments = isRestricted && userDepartments.length > 0
        ? userDepartments
        : ['Genel', ...DEPARTMENTS]

    const [selectedDepartment, setSelectedDepartment] = useState<string>(availableDepartments[0] || 'Genel')
    const [memoryCount, setMemoryCount] = useState<number>(0)
    const [showForgetConfirm, setShowForgetConfirm] = useState(false)

    // Seçili departmanı güncelle (User değişiminde)
    useEffect(() => {
        if (isRestricted && userDepartments.length > 0) {
            if (!userDepartments.includes(selectedDepartment)) {
                setSelectedDepartment(availableDepartments[0])
            }
        }
    }, [user, isRestricted])

    // Aktif oturumu ve mesajları yükle (sayfa açılışında + yenilemede)
    const loadActiveSession = useCallback(async () => {
        try {
            // Aktif oturumu al
            const session = await aiApi.getActiveSession()
            if (session?.id) {
                setCurrentSessionId(session.id)
                // Oturumun mesajlarını yükle
                const data = await aiApi.getSessionMessages(session.id)
                if (data?.messages?.length > 0) {
                    const restored: Message[] = []
                    for (const msg of data.messages) {
                        restored.push({
                            id: `q-${msg.id}`,
                            role: 'user',
                            content: msg.question,
                        })
                        restored.push({
                            id: `a-${msg.id}`,
                            role: 'assistant',
                            content: msg.answer,
                            metadata: { department: msg.department },
                        })
                    }
                    setMessages(restored)
                }
            }
        } catch {
            // Hata varsa sessiz geç
        }
    }, [])

    useEffect(() => {
        loadActiveSession()
    }, [loadActiveSession])

    // Hafıza sayısını yükle
    useEffect(() => {
        aiApi.getMemoryStatus()
            .then((data) => setMemoryCount(data.conversation_count || 0))
            .catch(() => {})
    }, [])

    // Yeni mesaj geldiğinde hafıza sayısını güncelle
    useEffect(() => {
        if (messages.length > 0) {
            setMemoryCount((prev) => prev + 1)
        }
    }, [messages.length])

    // Oturum listesini yükle
    const loadSessions = async () => {
        try {
            const data = await aiApi.listSessions()
            setSessions(data?.sessions || [])
            setSessionsLoaded(true)
        } catch {
            // sessiz geç
        }
    }

    // Oturumları tarih gruplarına ayır
    const groupSessionsByDate = (sessionList: ChatSessionInfo[]) => {
        const now = new Date()
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        const yesterday = new Date(today.getTime() - 86400000)
        const weekAgo = new Date(today.getTime() - 7 * 86400000)
        const monthAgo = new Date(today.getTime() - 30 * 86400000)

        const groups: { label: string; sessions: ChatSessionInfo[] }[] = [
            { label: 'Bugün', sessions: [] },
            { label: 'Dün', sessions: [] },
            { label: 'Bu Hafta', sessions: [] },
            { label: 'Bu Ay', sessions: [] },
            { label: 'Daha Eski', sessions: [] },
        ]

        for (const s of sessionList) {
            const d = new Date(s.updated_at || s.created_at)
            if (d >= today) groups[0].sessions.push(s)
            else if (d >= yesterday) groups[1].sessions.push(s)
            else if (d >= weekAgo) groups[2].sessions.push(s)
            else if (d >= monthAgo) groups[3].sessions.push(s)
            else groups[4].sessions.push(s)
        }

        return groups.filter(g => g.sessions.length > 0)
    }

    // Oturum değiştir
    const handleSwitchSession = async (sessionId: number) => {
        try {
            const data = await aiApi.switchSession(sessionId)
            setCurrentSessionId(sessionId)
            if (data?.messages?.length > 0) {
                const restored: Message[] = []
                for (const msg of data.messages) {
                    restored.push({
                        id: `q-${msg.id}`,
                        role: 'user',
                        content: msg.question,
                    })
                    restored.push({
                        id: `a-${msg.id}`,
                        role: 'assistant',
                        content: msg.answer,
                        metadata: { department: msg.department },
                    })
                }
                setMessages(restored)
            } else {
                setMessages([])
            }
            setShowSessions(false)
        } catch {
            // sessiz geç
        }
    }

    // Tekil oturumu sil
    const handleDeleteSession = async (e: React.MouseEvent, sessionId: number) => {
        e.stopPropagation()
        try {
            await aiApi.deleteSession(sessionId)
            // Eğer silinen oturum aktif ise yeni sohbet başlat
            if (sessionId === currentSessionId) {
                const data = await aiApi.createNewSession()
                setCurrentSessionId(data.session_id)
                setMessages([])
            }
            // Listeyi güncelle
            setSessions(prev => prev.filter(s => s.id !== sessionId))
        } catch {
            // sessiz geç
        }
    }

    // Yeni sohbet oluştur
    const handleNewChat = async () => {
        try {
            const data = await aiApi.createNewSession()
            setCurrentSessionId(data.session_id)
            setMessages([])
            setShowSessions(false)
            // Oturum listesini güncelle
            loadSessions()
        } catch {
            // sessiz geç
        }
    }

    const messagesEndRef = useRef<HTMLDivElement>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const askMutation = useMutation({
        mutationFn: async ({ question, files, department }: { question: string; files: File[]; department?: string }) => {
            // Konuşma geçmişi artık PostgreSQL'de kalıcı saklanıyor
            return await aiApi.askWithFiles(question, files, department)
        },
        onSuccess: (data) => {
            const botMessage: Message = {
                id: Date.now().toString(),
                role: 'assistant',
                content: data.answer,
                rich_data: data.rich_data || null,
                metadata: {
                    department: data.department,
                    risk_level: data.risk_level,
                    processing_time_ms: data.processing_time_ms,
                },
            }
            setMessages((prev) => [...prev, botMessage])
            // Mesaj gönderildikten sonra oturum listesini yenile (başlık güncellenmesi için)
            loadSessions()
        },
        onError: (error) => {
            const errorMessage: Message = {
                id: Date.now().toString(),
                role: 'assistant',
                content: 'Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.',
            }
            setMessages((prev) => [...prev, errorMessage])
        },
    })

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages])

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto'
            textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px'
        }
    }, [input])

    const getFileType = (file: File): 'image' | 'document' | 'other' => {
        if (file.type.startsWith('image/')) return 'image'
        if (
            file.type.includes('pdf') ||
            file.type.includes('word') ||
            file.type.includes('excel') ||
            file.type.includes('text')
        ) return 'document'
        return 'other'
    }

    const processFiles = (files: FileList | File[]) => {
        const fileArray = Array.from(files)
        const newFiles: AttachedFile[] = []

        fileArray.forEach((file) => {
            const type = getFileType(file)
            const attachedFile: AttachedFile = {
                id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                file,
                type,
            }

            // Generate preview for images
            if (type === 'image') {
                const reader = new FileReader()
                reader.onload = (e) => {
                    setAttachedFiles((prev) =>
                        prev.map((f) =>
                            f.id === attachedFile.id
                                ? { ...f, preview: e.target?.result as string }
                                : f
                        )
                    )
                }
                reader.readAsDataURL(file)
            }

            newFiles.push(attachedFile)
        })

        setAttachedFiles((prev) => [...prev, ...newFiles])
    }

    const handleFilesFromModal = (files: File[]) => {
        processFiles(files)
    }

    const handleQuickFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            processFiles(e.target.files)
            e.target.value = '' // Reset for re-selection
        }
    }

    const removeAttachedFile = (id: string) => {
        setAttachedFiles((prev) => prev.filter((f) => f.id !== id))
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
        processFiles(e.dataTransfer.files)
    }

    const handlePaste = (e: React.ClipboardEvent) => {
        const items = e.clipboardData?.items
        if (items) {
            const files: File[] = []
            for (let i = 0; i < items.length; i++) {
                if (items[i].kind === 'file') {
                    const file = items[i].getAsFile()
                    if (file) files.push(file)
                }
            }
            if (files.length > 0) {
                processFiles(files)
            }
        }
    }

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if ((!input.trim() && attachedFiles.length === 0) || askMutation.isPending) return

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input || (attachedFiles.length > 0 ? `[${attachedFiles.length} dosya eklendi]` : ''),
            attachments: [...attachedFiles],
        }
        setMessages((prev) => [...prev, userMessage])

        askMutation.mutate({
            question: input,
            files: attachedFiles.map((f) => f.file),
            department: selectedDepartment !== 'Genel' ? selectedDepartment : undefined,
        })
        setInput('')
        setAttachedFiles([])
    }

    const clearChat = () => {
        handleNewChat()
    }

    const handleForgetMemory = async () => {
        try {
            await aiApi.forgetMemory()
            setMessages([])
            setMemoryCount(0)
            setShowForgetConfirm(false)
        } catch {
            // hata durumunda sessizce geç
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit(e)
        }
    }

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes'
        const k = 1024
        const sizes = ['Bytes', 'KB', 'MB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
    }

    const getFileIcon = (type: 'image' | 'document' | 'other') => {
        switch (type) {
            case 'image':
                return <ImageIcon className="w-4 h-4" />
            case 'document':
                return <FileText className="w-4 h-4" />
            default:
                return <Paperclip className="w-4 h-4" />
        }
    }

    return (
        <>
            <div
                className={clsx(
                    "flex flex-col h-[calc(100vh-8rem)] md:h-[calc(100vh-10rem)] bg-dark-900/50 rounded-2xl border overflow-hidden transition-all",
                    isDragging ? "border-primary-400 bg-primary-500/5" : "border-dark-800"
                )}
                onDrop={handleDrop}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={(e) => { e.preventDefault(); setIsDragging(false) }}
            >
                {/* Drag Overlay */}
                {isDragging && (
                    <div className="absolute inset-0 z-10 flex items-center justify-center bg-dark-900/90 rounded-2xl">
                        <div className="flex flex-col items-center gap-4 text-center p-8">
                            <div className="w-20 h-20 rounded-2xl bg-primary-500/20 flex items-center justify-center">
                                <Paperclip className="w-10 h-10 text-primary-400" />
                            </div>
                            <div>
                                <p className="text-xl font-medium text-white">Dosyaları buraya bırakın</p>
                                <p className="text-sm text-dark-400 mt-1">Resim, doküman veya diğer dosyalar</p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-4 space-y-6">
                    {messages.length === 0 && (
                        <div className="h-full flex flex-col items-center justify-center text-center p-4 md:p-8 opacity-50">
                            <Bot className="w-12 h-12 md:w-16 md:h-16 text-dark-400 mb-3 md:mb-4" />
                            <h3 className="text-lg md:text-xl font-medium text-white">AI Asistan</h3>
                            <p className="text-dark-400 mt-2 max-w-md text-sm">
                                Hoş geldiniz, bugün size nasıl yardımcı olabilirim?
                            </p>
                            <div className="flex items-center gap-2 mt-3 text-xs md:text-sm text-primary-400">
                                <Sparkles className="w-4 h-4" />
                                <span>RAG destekli • Şirket verileriyle öğrenmiş</span>
                            </div>
                            <div className="hidden sm:flex flex-wrap justify-center gap-3 mt-6">
                                <div className="flex items-center gap-2 px-4 py-2 bg-dark-800/50 rounded-full text-sm text-dark-400">
                                    <ImageIcon className="w-4 h-4" />
                                    Resim yükleyin
                                </div>
                                <div className="flex items-center gap-2 px-4 py-2 bg-dark-800/50 rounded-full text-sm text-dark-400">
                                    <Camera className="w-4 h-4" />
                                    Fotoğraf çekin
                                </div>
                                <div className="flex items-center gap-2 px-4 py-2 bg-dark-800/50 rounded-full text-sm text-dark-400">
                                    <FileText className="w-4 h-4" />
                                    Doküman ekleyin
                                </div>
                            </div>
                        </div>
                    )}

                    {messages.map((msg) => (
                        <div
                            key={msg.id}
                            className={clsx(
                                'flex gap-2 sm:gap-4 max-w-full sm:max-w-3xl',
                                msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''
                            )}
                        >
                            <div
                                className={clsx(
                                    'w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center shrink-0',
                                    msg.role === 'user' ? 'bg-primary-500' : 'bg-dark-700'
                                )}
                            >
                                {msg.role === 'user' ? (
                                    <UserIcon className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                                ) : (
                                    <Bot className="w-4 h-4 sm:w-5 sm:h-5 text-primary-400" />
                                )}
                            </div>

                            <div
                                className={clsx(
                                    'rounded-2xl px-3 py-2 sm:px-5 sm:py-3 text-sm leading-relaxed max-w-[calc(100%-3rem)] sm:max-w-[85%]',
                                    msg.role === 'user'
                                        ? 'bg-primary-600 text-white rounded-tr-none'
                                        : 'bg-dark-800 text-dark-200 rounded-tl-none border border-dark-700'
                                )}
                            >
                                {/* Attachments */}
                                {msg.attachments && msg.attachments.length > 0 && (
                                    <div className="mb-3 space-y-2">
                                        <div className="flex flex-wrap gap-2">
                                            {msg.attachments.map((att) => (
                                                <div key={att.id}>
                                                    {att.type === 'image' && att.preview ? (
                                                        <div
                                                            className="relative group cursor-pointer"
                                                            onClick={() => setPreviewImage(att.preview!)}
                                                        >
                                                            <img
                                                                src={att.preview}
                                                                alt={att.file.name}
                                                                className="w-24 h-24 object-cover rounded-lg border border-white/20"
                                                            />
                                                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center">
                                                                <Eye className="w-5 h-5 text-white" />
                                                            </div>
                                                        </div>
                                                    ) : (
                                                        <div className="flex items-center gap-2 px-3 py-2 bg-white/10 rounded-lg">
                                                            {getFileIcon(att.type)}
                                                            <span className="text-xs truncate max-w-[100px]">
                                                                {att.file.name}
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                <div className="whitespace-pre-wrap">{msg.content}</div>

                                {/* Rich Data — Hava Durumu, Görsel Arama Kartları vb. */}
                                {msg.rich_data && Array.isArray(msg.rich_data) && msg.rich_data.map((card: any, cardIdx: number) => (
                                    <div key={cardIdx}>
                                        {card.type === 'weather' && <WeatherCard data={card} />}
                                        {card.type === 'images' && <ImageResultsCard data={card} />}
                                        {card.type === 'export' && <ExportCard data={card} />}
                                    </div>
                                ))}

                                {msg.role === 'assistant' && msg.metadata && (
                                    <div className="mt-3 pt-3 border-t border-dark-700/50 flex flex-wrap gap-2 text-xs">
                                        <span className="bg-dark-900/50 px-2 py-1 rounded text-dark-400 border border-dark-700">
                                            {msg.metadata.department}
                                        </span>
                                        {msg.metadata.risk_level === 'Yüksek' && (
                                            <span className="bg-red-500/10 text-red-400 px-2 py-1 rounded border border-red-500/20 flex items-center gap-1">
                                                <AlertTriangle className="w-3 h-3" />
                                                Yüksek Risk
                                            </span>
                                        )}
                                        {msg.metadata.processing_time_ms && (
                                            <span className="text-dark-500 ml-auto">
                                                {msg.metadata.processing_time_ms}ms
                                            </span>
                                        )}
                                    </div>
                                )}

                                {/* Her assistant mesajında export butonları */}
                                {msg.role === 'assistant' && msg.content && msg.content.length > 50 && (
                                    <QuickExportButtons content={msg.content} />
                                )}
                            </div>
                        </div>
                    ))}

                    {askMutation.isPending && (
                        <div className="flex gap-4 max-w-3xl">
                            <div className="w-8 h-8 rounded-full bg-dark-700 flex items-center justify-center shrink-0">
                                <Bot className="w-5 h-5 text-primary-400" />
                            </div>
                            <div className="bg-dark-800 rounded-2xl rounded-tl-none px-5 py-4 border border-dark-700">
                                <div className="flex gap-1">
                                    <div className="w-2 h-2 bg-dark-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                    <div className="w-2 h-2 bg-dark-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                    <div className="w-2 h-2 bg-dark-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Attached Files Preview */}
                {attachedFiles.length > 0 && (
                    <div className="px-4 py-3 border-t border-dark-800 bg-dark-900/30">
                        <div className="flex gap-2 overflow-x-auto pb-1">
                            {attachedFiles.map((file) => (
                                <div
                                    key={file.id}
                                    className="relative flex-shrink-0 group"
                                >
                                    {file.type === 'image' && file.preview ? (
                                        <div className="relative">
                                            <img
                                                src={file.preview}
                                                alt={file.file.name}
                                                className="w-16 h-16 object-cover rounded-lg border border-dark-700"
                                            />
                                            <button
                                                onClick={() => removeAttachedFile(file.id)}
                                                className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                                            >
                                                <X className="w-3 h-3 text-white" />
                                            </button>
                                        </div>
                                    ) : (
                                        <div className="relative flex items-center gap-2 px-3 py-2 bg-dark-800 rounded-lg border border-dark-700">
                                            {getFileIcon(file.type)}
                                            <div className="max-w-[100px]">
                                                <p className="text-xs text-white truncate">{file.file.name}</p>
                                                <p className="text-xs text-dark-500">{formatFileSize(file.file.size)}</p>
                                            </div>
                                            <button
                                                onClick={() => removeAttachedFile(file.id)}
                                                className="p-1 hover:bg-dark-700 rounded"
                                            >
                                                <X className="w-3 h-3 text-dark-400" />
                                            </button>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Input Area */}
                <div className="p-2 sm:p-4 border-t border-dark-800 bg-dark-900/50">
                    {/* Toolbar */}
                    <div className="flex items-center justify-between mb-2 sm:mb-3 px-1">
                        {/* Department Selector */}
                        <div className="flex items-center gap-1.5 sm:gap-2">
                            <Building2 className="w-4 h-4 text-dark-400 hidden sm:block" />
                            <select
                                value={selectedDepartment}
                                onChange={(e) => setSelectedDepartment(e.target.value)}
                                className="bg-dark-800 border border-dark-700 text-xs sm:text-sm text-white rounded-lg px-2 sm:px-3 py-1.5 focus:ring-primary-500 focus:border-primary-500"
                            >
                                {availableDepartments.map((dept) => (
                                    <option key={dept} value={dept}>
                                        {dept}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Right side buttons */}
                        <div className="flex items-center gap-1 sm:gap-2">
                            {/* Session History Button */}
                            <button
                                type="button"
                                onClick={() => { setShowSessions(!showSessions); loadSessions(); }}
                                className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 text-xs text-dark-400 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-colors"
                                title="Sohbet geçmişi"
                            >
                                <History className="w-3.5 h-3.5" />
                                <span className="hidden sm:inline">Geçmiş</span>
                            </button>

                            {/* New Chat Button */}
                            <button
                                type="button"
                                onClick={handleNewChat}
                                className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 text-xs text-dark-400 hover:text-green-400 hover:bg-green-500/10 rounded-lg transition-colors"
                                title="Yeni sohbet başlat"
                            >
                                <MessageSquarePlus className="w-3.5 h-3.5" />
                                <span className="hidden sm:inline">Yeni</span> Sohbet
                            </button>

                            {/* Memory indicator */}
                            {memoryCount > 0 && (
                                <div className="hidden sm:flex items-center gap-1 px-2 py-1.5 text-xs text-dark-500" title={`${memoryCount} konuşma hafızada`}>
                                    <Brain className="w-3.5 h-3.5 text-primary-400" />
                                    <span>{memoryCount}</span>
                                </div>
                            )}

                            {/* Forget Memory Button */}
                            {memoryCount > 0 && (
                                <button
                                    type="button"
                                    onClick={() => setShowForgetConfirm(true)}
                                    className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 text-xs text-dark-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                                    title="Tüm hafızayı sil"
                                >
                                    <ShieldX className="w-3.5 h-3.5" />
                                    <span className="hidden sm:inline">Beni</span> Unut
                                </button>
                            )}
                        </div>
                    </div>

                    <form onSubmit={handleSubmit} className="flex items-end gap-1.5 sm:gap-3">
                        {/* Attachment Buttons */}
                        <div className="flex gap-0.5 sm:gap-1 shrink-0">
                            {/* Full Upload Modal Button */}
                            <button
                                type="button"
                                onClick={() => setIsUploadModalOpen(true)}
                                className="p-2 sm:p-3 hover:bg-dark-800 rounded-xl transition-colors text-dark-400 hover:text-primary-400"
                                title="Dosya Ekle"
                            >
                                <Paperclip className="w-5 h-5" />
                            </button>

                            {/* Quick Image Button - hidden on small screens */}
                            <button
                                type="button"
                                onClick={() => {
                                    fileInputRef.current?.setAttribute('accept', 'image/*')
                                    fileInputRef.current?.click()
                                }}
                                className="hidden sm:block p-2 sm:p-3 hover:bg-dark-800 rounded-xl transition-colors text-dark-400 hover:text-green-400"
                                title="Resim Ekle"
                            >
                                <ImageIcon className="w-5 h-5" />
                            </button>

                            {/* Camera Button - hidden on small screens */}
                            <button
                                type="button"
                                onClick={() => setIsUploadModalOpen(true)}
                                className="hidden sm:block p-2 sm:p-3 hover:bg-dark-800 rounded-xl transition-colors text-dark-400 hover:text-blue-400"
                                title="Kamera"
                            >
                                <Camera className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Hidden File Input */}
                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            className="hidden"
                            onChange={handleQuickFileSelect}
                        />

                        {/* Text Input */}
                        <div className="flex-1 min-w-0 relative">
                            <textarea
                                ref={textareaRef}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                onPaste={handlePaste}
                                disabled={askMutation.isPending}
                                placeholder="Bir soru sorun veya dosya ekleyin..."
                                rows={1}
                                className="input w-full resize-none min-h-[44px] sm:min-h-[48px] max-h-[200px] py-2.5 sm:py-3 pr-10 sm:pr-12 text-sm"
                            />
                            {attachedFiles.length > 0 && (
                                <div className="absolute right-2 sm:right-3 top-1/2 -translate-y-1/2">
                                    <span className="flex items-center justify-center w-5 h-5 sm:w-6 sm:h-6 bg-primary-500 text-white text-xs font-medium rounded-full">
                                        {attachedFiles.length}
                                    </span>
                                </div>
                            )}
                        </div>

                        {/* Send Button */}
                        <button
                            type="submit"
                            disabled={(!input.trim() && attachedFiles.length === 0) || askMutation.isPending}
                            className="btn-primary p-2.5 sm:p-3 shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {askMutation.isPending ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <Send className="w-5 h-5" />
                            )}
                        </button>
                    </form>

                    {/* Quick Tips - hidden on mobile */}
                    <div className="hidden sm:flex items-center justify-center gap-4 mt-2 text-xs text-dark-500">
                        <span>Ctrl+V ile yapıştır</span>
                        <span>•</span>
                        <span>Shift+Enter yeni satır</span>
                        <span>•</span>
                        <span>Sürükle-bırak desteklenir</span>
                    </div>
                </div>
            </div>

            {/* File Upload Modal */}
            <FileUploadModal
                isOpen={isUploadModalOpen}
                onClose={() => setIsUploadModalOpen(false)}
                onFilesSelected={handleFilesFromModal}
                maxFiles={10}
                maxSizePerFile={50}
            />

            {/* Image Preview Modal */}
            {previewImage && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/90"
                    onClick={() => setPreviewImage(null)}
                >
                    <img
                        src={previewImage}
                        alt="Preview"
                        className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg"
                    />
                    <button
                        onClick={() => setPreviewImage(null)}
                        className="absolute top-4 right-4 p-2 bg-dark-800 hover:bg-dark-700 rounded-full transition-colors"
                    >
                        <X className="w-6 h-6 text-white" />
                    </button>
                </div>
            )}

            {/* Session History Sidebar */}
            {showSessions && (
                <div className="fixed inset-0 z-50 flex" onClick={() => setShowSessions(false)}>
                    <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
                    <div
                        className="relative ml-auto w-80 max-w-[85vw] h-full bg-dark-900 border-l border-dark-700 shadow-2xl flex flex-col"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="shrink-0 bg-dark-900/95 backdrop-blur border-b border-dark-700 p-4 flex items-center justify-between">
                            <h3 className="text-white font-semibold flex items-center gap-2">
                                <History className="w-5 h-5 text-primary-400" />
                                Sohbet Geçmişi
                            </h3>
                            <button
                                onClick={() => setShowSessions(false)}
                                className="p-1.5 hover:bg-dark-800 rounded-lg transition-colors"
                            >
                                <X className="w-5 h-5 text-dark-400" />
                            </button>
                        </div>

                        {/* New Chat Button */}
                        <div className="shrink-0 p-3 pb-0">
                            <button
                                onClick={handleNewChat}
                                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-sm font-semibold transition-colors shadow-lg shadow-primary-600/20"
                            >
                                <MessageSquarePlus className="w-4 h-4" />
                                Yeni Sohbet Başlat
                            </button>
                        </div>

                        {/* Session List - Scrollable */}
                        <div className="flex-1 overflow-y-auto p-3 space-y-1">
                            {groupSessionsByDate(sessions).map((group) => (
                                <div key={group.label} className="mb-3">
                                    <p className="text-[11px] font-semibold text-dark-500 uppercase tracking-wider px-2 py-2">
                                        {group.label}
                                    </p>
                                    <div className="space-y-0.5">
                                        {group.sessions.map((s) => (
                                            <div
                                                key={s.id}
                                                onClick={() => handleSwitchSession(s.id)}
                                                className={clsx(
                                                    "group w-full text-left px-3 py-2.5 rounded-xl text-sm transition-all cursor-pointer relative",
                                                    s.id === currentSessionId
                                                        ? "bg-primary-500/15 text-primary-200 ring-1 ring-primary-500/30"
                                                        : "text-dark-300 hover:bg-dark-800/80 hover:text-white"
                                                )}
                                            >
                                                <div className="flex items-start gap-2">
                                                    <div className="flex-1 min-w-0">
                                                        <p className="truncate font-medium leading-snug">
                                                            {s.title || 'Yeni Sohbet'}
                                                        </p>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <span className="text-[11px] text-dark-500">
                                                                {new Date(s.updated_at || s.created_at).toLocaleDateString('tr-TR', {
                                                                    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
                                                                })}
                                                            </span>
                                                            {(s.message_count ?? 0) > 0 && (
                                                                <span className="text-[10px] bg-dark-700/60 text-dark-400 px-1.5 py-0.5 rounded-full">
                                                                    {s.message_count} mesaj
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                    {/* Delete Button */}
                                                    <button
                                                        onClick={(e) => handleDeleteSession(e, s.id)}
                                                        className="shrink-0 p-1 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-500/20 hover:text-red-400 text-dark-600 transition-all"
                                                        title="Sohbeti sil"
                                                    >
                                                        <Trash2 className="w-3.5 h-3.5" />
                                                    </button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                            {sessions.length === 0 && sessionsLoaded && (
                                <div className="flex flex-col items-center justify-center py-12 text-dark-500">
                                    <History className="w-10 h-10 mb-3 opacity-30" />
                                    <p className="text-sm">Henüz sohbet yok</p>
                                    <p className="text-xs mt-1">Yeni bir sohbet başlatın</p>
                                </div>
                            )}
                        </div>

                        {/* Footer - Session Count */}
                        {sessions.length > 0 && (
                            <div className="shrink-0 border-t border-dark-700 px-4 py-2.5 text-center">
                                <span className="text-[11px] text-dark-500">{sessions.length} sohbet kayıtlı</span>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Forget Confirmation Modal */}
            {showForgetConfirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
                    <div className="bg-dark-900 border border-dark-700 rounded-2xl p-6 max-w-sm mx-4 shadow-xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 bg-red-500/20 rounded-full flex items-center justify-center">
                                <ShieldX className="w-5 h-5 text-red-400" />
                            </div>
                            <h3 className="text-lg font-semibold text-white">Beni Unut</h3>
                        </div>
                        <p className="text-dark-300 text-sm mb-1">
                            Tum konusma gecmisini ve hatirlanan bilgileri (isim, tercihler vs.) kalici olarak silmek istediginize emin misiniz?
                        </p>
                        <p className="text-dark-500 text-xs mb-6">
                            Bu islem geri alinamaz. {memoryCount} konusma silinecek.
                        </p>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setShowForgetConfirm(false)}
                                className="flex-1 px-4 py-2 text-sm bg-dark-800 hover:bg-dark-700 text-white rounded-lg transition-colors"
                            >
                                Vazgec
                            </button>
                            <button
                                onClick={handleForgetMemory}
                                className="flex-1 px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
                            >
                                Evet, Unut
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}
