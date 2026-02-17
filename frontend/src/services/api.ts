import axios from 'axios'

const API_BASE_URL = '/api'

// Axios instance
const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 900000, // 15 minutes (CPU inference for large models)
    headers: {
        'Content-Type': 'application/json',
    },
})

// Request interceptor - add auth token
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Response interceptor - handle 401
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('token')
            window.location.href = '/login'
        }
        return Promise.reject(error)
    }
)

// Auth API
export const authApi = {
    login: async (email: string, password: string) => {
        const formData = new FormData()
        formData.append('username', email)
        formData.append('password', password)
        const response = await api.post('/auth/login', formData, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
        return response.data
    },

    register: async (email: string, password: string, fullName?: string) => {
        const response = await api.post('/auth/register', { email, password, full_name: fullName })
        return response.data
    },

    getMe: async () => {
        const response = await api.get('/auth/me')
        return response.data
    },

    changePassword: async (currentPassword: string, newPassword: string) => {
        const response = await api.post('/auth/change-password', {
            current_password: currentPassword,
            new_password: newPassword,
        })
        return response.data
    },

    getTheme: async () => {
        const response = await api.get('/auth/preferences/theme')
        return response.data
    },

    setTheme: async (theme: string) => {
        const response = await api.put('/auth/preferences/theme', { theme })
        return response.data
    },
}

// AI API
export const aiApi = {
    ask: async (question: string, department?: string) => {
        const response = await api.post('/ask', { question, department }, {
            timeout: 900000, // 15 minutes - CPU inference can be slow
        })
        return response.data
    },

    askWithFiles: async (question: string, files: File[], department?: string, signal?: AbortSignal) => {
        const formData = new FormData()
        formData.append('question', question)
        if (department) {
            formData.append('department', department)
        }

        // Append all files (image, document, audio, video)
        files.forEach((file, index) => {
            formData.append('files', file)
        })

        const response = await api.post('/ask/multimodal', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            signal,
            timeout: 900000, // 15 minutes - CPU inference can be slow
        })
        return response.data
    },

    // v4.5.0: Omni-modal yetenekleri
    getOmniCapabilities: async () => {
        const response = await api.get('/ask/omni/capabilities')
        return response.data
    },

    // v4.5.0: Ses analizi
    analyzeAudio: async (file: File, question?: string) => {
        const formData = new FormData()
        formData.append('file', file)
        if (question) formData.append('question', question)
        const response = await api.post('/ask/upload/audio', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 600000,
        })
        return response.data
    },

    // v4.5.0: Video analizi
    analyzeVideo: async (file: File, question?: string) => {
        const formData = new FormData()
        formData.append('file', file)
        if (question) formData.append('question', question)
        const response = await api.post('/ask/upload/video', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 900000,
        })
        return response.data
    },

    // Kalıcı Hafıza API'leri
    getMemoryStatus: async () => {
        const response = await api.get('/memory/persistent/status')
        return response.data
    },

    forgetMemory: async () => {
        const response = await api.delete('/memory/persistent/forget')
        return response.data
    },

    // Sohbet Oturumu API'leri
    getActiveSession: async () => {
        const response = await api.get('/memory/sessions/active')
        return response.data
    },

    listSessions: async (limit = 30) => {
        const response = await api.get(`/memory/sessions?limit=${limit}`)
        return response.data
    },

    getSessionMessages: async (sessionId: number) => {
        const response = await api.get(`/memory/sessions/${sessionId}/messages`)
        return response.data
    },

    switchSession: async (sessionId: number) => {
        const response = await api.post(`/memory/sessions/${sessionId}/switch`)
        return response.data
    },

    createNewSession: async () => {
        const response = await api.post('/memory/sessions/new')
        return response.data
    },

    deleteSession: async (sessionId: number) => {
        const response = await api.delete(`/memory/sessions/${sessionId}`)
        return response.data
    },

    uploadDocument: async (file: File, category?: string) => {
        const formData = new FormData()
        formData.append('file', file)
        // Note: Backend expects 'department' form field, mapping category to it
        if (category) {
            formData.append('department', category)
        }

        const response = await api.post('/rag/documents/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        })
        return response.data
    },

    getHealth: async () => {
        const response = await api.get('/health')
        return response.data
    },

    getLlmStatus: async () => {
        const response = await api.get('/llm/status')
        return response.data
    },
}

// Logo API (public — auth gerektirmez)
export const logoApi = {
    getLogo: async () => {
        const response = await axios.get('/api/admin/public/logo')
        return response.data
    },

    uploadLogo: async (file: File) => {
        const formData = new FormData()
        formData.append('file', file)
        const response = await api.post('/admin/upload-logo', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
        return response.data
    },

    deleteLogo: async () => {
        const response = await api.delete('/admin/logo')
        return response.data
    },
}

// Admin API
export const adminApi = {
    getUsers: async () => {
        const response = await api.get('/admin/users')
        return response.data
    },

    getDashboardStats: async () => {
        const response = await api.get('/admin/stats/dashboard')
        return response.data
    },

    getQueryTraffic: async () => {
        const response = await api.get('/admin/stats/query-traffic')
        return response.data
    },

    getSystemResources: async () => {
        const response = await api.get('/admin/stats/system-resources')
        return response.data
    },

    getRecentQueries: async (limit = 20) => {
        const response = await api.get(`/admin/queries/recent?limit=${limit}`)
        return response.data
    },

    updateUserRole: async (userId: number, role: string) => {
        const response = await api.patch(`/admin/users/${userId}/role?role=${role}`)
        return response.data
    },

    createUser: async (userData: any) => {
        const response = await api.post('/admin/users', userData)
        return response.data
    },

    updateUser: async (userId: number, userData: any) => {
        const response = await api.put(`/admin/users/${userId}`, userData)
        return response.data
    },

    deleteUser: async (userId: number) => {
        const response = await api.delete(`/admin/users/${userId}`)
        return response.data
    },

    // v3.3.0 — AI Modül & Governance Dashboard
    getAiModules: async () => {
        const response = await api.get('/admin/stats/ai-modules')
        return response.data
    },

    getGovernanceMetrics: async () => {
        const response = await api.get('/admin/stats/governance')
        return response.data
    },

    getDeptQueryStats: async () => {
        const response = await api.get('/admin/stats/dept-queries')
        return response.data
    },

    getAuditLogs: async (limit = 50) => {
        const response = await api.get(`/admin/audit-logs?limit=${limit}`)
        return response.data
    },

    // v3.4.0 — Yeni Modül API'leri

    // Model Registry
    getModelRegistry: async () => {
        const response = await api.get('/admin/model-registry')
        return response.data
    },
    getRegisteredModels: async () => {
        const response = await api.get('/admin/model-registry/models')
        return response.data
    },
    syncModels: async () => {
        const response = await api.post('/admin/model-registry/sync')
        return response.data
    },
    promoteModel: async (modelName: string) => {
        const response = await api.post(`/admin/model-registry/promote/${modelName}`)
        return response.data
    },

    // Data Versioning
    getDataVersions: async () => {
        const response = await api.get('/admin/data-versions')
        return response.data
    },
    getDatasets: async () => {
        const response = await api.get('/admin/data-versions/datasets')
        return response.data
    },
    createSnapshot: async () => {
        const response = await api.post('/admin/data-versions/snapshot')
        return response.data
    },

    // HITL
    getHitlDashboard: async () => {
        const response = await api.get('/admin/hitl')
        return response.data
    },
    reviewHitlTask: async (taskId: string, action: string, feedback: string = '') => {
        const response = await api.put(`/admin/hitl/review/${taskId}?action=${action}&feedback=${encodeURIComponent(feedback)}`)
        return response.data
    },

    // Monitoring
    getTelemetry: async () => {
        const response = await api.get('/admin/monitoring/telemetry')
        return response.data
    },
    getHealthScore: async () => {
        const response = await api.get('/admin/monitoring/health')
        return response.data
    },
    getAlerts: async () => {
        const response = await api.get('/admin/monitoring/alerts')
        return response.data
    },
    acknowledgeAlert: async (alertId: string) => {
        const response = await api.post(`/admin/monitoring/alerts/${alertId}/acknowledge`)
        return response.data
    },

    // Textile Vision
    getTextileVisionCaps: async () => {
        const response = await api.get('/admin/textile-vision/capabilities')
        return response.data
    },

    // Explainability (XAI)
    getXaiDashboard: async () => {
        const response = await api.get('/admin/explainability')
        return response.data
    },
    getXaiHistory: async (limit: number = 20) => {
        const response = await api.get(`/admin/explainability/history?limit=${limit}`)
        return response.data
    },
    getXaiCalibration: async () => {
        const response = await api.get('/admin/explainability/calibration')
        return response.data
    },
    submitXaiFeedback: async (data: { query_hash: string; user_rating: number; factor_overrides?: Record<string, number>; comment?: string }) => {
        const response = await api.post('/admin/explainability/feedback', data)
        return response.data
    },

    // Insight Engine (v3.9.0)
    getInsightDemo: async () => {
        const response = await api.get('/admin/insights/demo')
        return response.data
    },
    analyzeInsights: async (data: any[], maxInsights: number = 20) => {
        const response = await api.post('/admin/insights/analyze', { data, max_insights: maxInsights })
        return response.data
    },

    // CEO Dashboard (v3.9.0)
    getCeoDashboard: async () => {
        const response = await api.get('/admin/ceo/dashboard')
        return response.data
    },

    // Performance Profile (v5.6.0)
    getPerformanceProfile: async () => {
        const response = await api.get('/admin/performance-profile')
        return response.data
    },
    updatePerformanceProfile: async (data: { mode: string; gpu_percent: number; cpu_percent: number; ram_percent: number }) => {
        const response = await api.put('/admin/performance-profile', data)
        return response.data
    },

    // Ollama Model Yönetimi (v5.8.0)
    getOllamaModels: async () => {
        const response = await api.get('/admin/ollama/models')
        return response.data
    },

    pullOllamaModel: (
        modelName: string,
        onProgress: (data: { status: string; completed?: number; total?: number; error?: string }) => void,
        onDone: () => void,
        onError: (err: string) => void,
    ): (() => void) => {
        const controller = new AbortController()
        const token = localStorage.getItem('token')

        fetch(`/api/admin/ollama/pull`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({ name: modelName }),
            signal: controller.signal,
        })
            .then(async (response) => {
                if (!response.ok) {
                    const txt = await response.text()
                    onError(txt || 'Model indirme başlatılamadı')
                    return
                }
                const reader = response.body?.getReader()
                if (!reader) {
                    onError('Stream okunamıyor')
                    return
                }
                const decoder = new TextDecoder()
                let buffer = ''

                while (true) {
                    const { done, value } = await reader.read()
                    if (done) break
                    buffer += decoder.decode(value, { stream: true })

                    const lines = buffer.split('\n')
                    buffer = lines.pop() || ''

                    for (const line of lines) {
                        const trimmed = line.trim()
                        if (!trimmed || !trimmed.startsWith('data: ')) continue
                        try {
                            const jsonStr = trimmed.slice(6)
                            const data = JSON.parse(jsonStr)
                            if (data.status === 'error') {
                                onError(data.error || 'Bilinmeyen hata')
                                return
                            }
                            if (data.status === 'completed') {
                                onDone()
                                return
                            }
                            onProgress(data)
                        } catch {
                            // parse hatasını yoksay
                        }
                    }
                }
                onDone()
            })
            .catch((err) => {
                if (err.name !== 'AbortError') {
                    onError(err.message || 'Bağlantı hatası')
                }
            })

        // İptal fonksiyonu döndür
        return () => controller.abort()
    },

    switchOllamaModel: async (modelName: string) => {
        const response = await api.post('/admin/ollama/switch', { name: modelName })
        return response.data
    },

    deleteOllamaModel: async (modelName: string) => {
        const response = await api.delete('/admin/ollama/models', { data: { name: modelName } })
        return response.data
    },

    // TPS Benchmark (v5.8.0)
    getOllamaTps: async () => {
        const response = await api.get('/admin/ollama/tps', { timeout: 120000 })
        return response.data
    },
}

// RAG API
export const ragApi = {
    getStatus: async () => {
        const response = await api.get('/rag/status')
        return response.data
    },

    listDocuments: async (department?: string) => {
        const response = await api.get('/rag/documents/list', {
            params: department ? { department } : undefined
        })
        return response.data
    },

    getFormats: async () => {
        const response = await api.get('/rag/formats')
        return response.data
    },

    getCapabilities: async () => {
        const response = await api.get('/rag/capabilities')
        return response.data
    },

    uploadDocument: async (file: File, department: string = 'Genel', onProgress?: (percent: number) => void) => {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('department', department)
        const response = await api.post('/rag/documents/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
                    onProgress(percent)
                }
            },
            timeout: 600000,
        })
        return response.data
    },

    uploadMultiple: async (files: File[], department: string = 'Genel') => {
        const formData = new FormData()
        files.forEach(file => formData.append('files', file))
        formData.append('department', department)
        const response = await api.post('/rag/documents/upload-multiple', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
        return response.data
    },

    searchDocuments: async (query: string, nResults: number = 5, department?: string) => {
        const response = await api.post('/rag/documents/search', {
            query,
            n_results: nResults,
            department
        })
        return response.data
    },

    teach: async (content: string, department: string, title?: string) => {
        const response = await api.post('/rag/teach', {
            content,
            department,
            title
        })
        return response.data
    },

    learnFromUrl: async (url: string, department: string, title?: string) => {
        const response = await api.post('/rag/learn-url', {
            url,
            department,
            title: title || undefined
        })
        return response.data
    },

    learnFromVideo: async (url: string, department: string, title?: string, language: string = 'tr') => {
        const response = await api.post('/rag/learn-video', {
            url,
            department,
            title: title || undefined,
            language
        })
        return response.data
    },

    learnFromImage: async (file: File, department: string, title?: string, useVision: boolean = false) => {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('department', department)
        if (title) formData.append('title', title)
        formData.append('use_vision', String(useVision))
        const response = await api.post('/rag/learn-image', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 120000,
        })
        return response.data
    },

    deleteDocument: async (source: string) => {
        const response = await api.delete(`/rag/documents/${encodeURIComponent(source)}`)
        return response.data
    },

    clearAll: async (password: string) => {
        const response = await api.post('/rag/documents/clear-all', { password })
        return response.data
    }
}

// Memory API
export const memoryApi = {
    getStats: async () => {
        const response = await api.get('/memory/stats')
        return response.data
    },

    search: async (query: string, limit: number = 5) => {
        const response = await api.get(`/memory/search?q=${encodeURIComponent(query)}&limit=${limit}`)
        return response.data
    },

    clear: async () => {
        const response = await api.delete('/memory/clear')
        return response.data
    },
}

// Analiz API (Gelişmiş Doküman Analizi)
export const analyzeApi = {
    /** Dosya yükle + otomatik analiz */
    uploadAndAnalyze: async (file: File, analysisType: string = 'full', question?: string, department: string = 'Genel') => {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('analysis_type', analysisType)
        if (question) formData.append('question', question)
        formData.append('department', department)
        const response = await api.post('/analyze/upload-analyze', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 900000, // 15 dk - analiz zaman alabilir
        })
        return response.data
    },

    /** Dosya yapısını keşfet (sütunlar, türler vs.) */
    discover: async (file: File) => {
        const formData = new FormData()
        formData.append('file', file)
        const response = await api.post('/analyze/discover', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
        return response.data
    },

    /** Cache'teki veriden pivot tablo oluştur */
    pivot: async (rows?: string[], columns?: string[], values?: string[], aggfunc: string = 'sum', filename?: string) => {
        const response = await api.post('/analyze/pivot', {
            rows, columns, values, aggfunc, filename,
        })
        return response.data
    },

    /** Doğal dil ile veri sorgula */
    query: async (question: string, filename?: string) => {
        const response = await api.post('/analyze/query', { question, filename })
        return response.data
    },

    /** İstatistik analiz */
    statistics: async (filename?: string) => {
        const response = await api.post('/analyze/statistics', null, {
            params: filename ? { filename } : undefined,
        })
        return response.data
    },

    /** Trend analizi */
    trend: async (filename?: string, dateCol?: string, valueCol?: string) => {
        const response = await api.post('/analyze/trend', null, {
            params: { ...(filename && { filename }), ...(dateCol && { date_col: dateCol }), ...(valueCol && { value_col: valueCol }) },
        })
        return response.data
    },

    /** Grup karşılaştırması */
    compare: async (filename?: string, groupCol?: string) => {
        const response = await api.post('/analyze/compare', null, {
            params: { ...(filename && { filename }), ...(groupCol && { group_col: groupCol }) },
        })
        return response.data
    },

    /** Cache'teki dosyalar */
    cached: async () => {
        const response = await api.get('/analyze/cached')
        return response.data
    },

    /** Streaming analiz */
    uploadAndAnalyzeStream: (file: File, analysisType: string = 'full', question?: string, department: string = 'Genel') => {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('analysis_type', analysisType)
        if (question) formData.append('question', question)
        formData.append('department', department)

        const token = localStorage.getItem('token')
        return fetch(`${API_BASE_URL}/analyze/upload-analyze/stream`, {
            method: 'POST',
            headers: {
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: formData,
        })
    },

    /** Analiz sonucunu dışa aktar (Excel, PDF, CSV, Word, PPTX) */
    exportAnalysis: async (content: string, format: string, title?: string, analysisType?: string, filename?: string) => {
        const response = await api.post('/analyze/export', {
            content,
            format,
            title,
            analysis_type: analysisType,
            filename,
        })
        return response.data
    },

    /** Export dosyasını indir */
    downloadExport: async (fileId: string, filename: string) => {
        const token = localStorage.getItem('token')
        const response = await fetch(`${API_BASE_URL}/analyze/export/download/${fileId}`, {
            headers: {
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
        })
        if (!response.ok) throw new Error('İndirme başarısız')
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        window.URL.revokeObjectURL(url)
    },
}

// Backup API
export const backupApi = {
    list: async () => {
        const response = await api.get('/backup/list')
        return response.data
    },

    create: async (note?: string) => {
        const response = await api.post('/backup/create', null, {
            params: note ? { note } : undefined,
            timeout: 120000,
        })
        return response.data
    },

    download: (filename: string) => {
        const token = localStorage.getItem('token')
        return `${API_BASE_URL}/backup/download/${encodeURIComponent(filename)}?token=${token}`
    },

    restore: async (filename: string, confirm: boolean = false) => {
        const response = await api.post('/backup/restore', { filename, confirm }, { timeout: 300000 })
        return response.data
    },

    deleteBackup: async (filename: string) => {
        const response = await api.delete(`/backup/delete/${encodeURIComponent(filename)}`)
        return response.data
    },

    upload: async (file: File) => {
        const formData = new FormData()
        formData.append('file', file)
        const response = await api.post('/backup/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 120000,
        })
        return response.data
    },

    getSchedule: async () => {
        const response = await api.get('/backup/schedule')
        return response.data
    },

    updateSchedule: async (schedule: {
        enabled: boolean
        frequency: string
        time: string
        day_of_week?: number
        day_of_month?: number
        max_keep?: number
        note?: string
    }) => {
        const response = await api.put('/backup/schedule', schedule)
        return response.data
    },

    getInfo: async () => {
        const response = await api.get('/backup/info')
        return response.data
    },
}

export default api
