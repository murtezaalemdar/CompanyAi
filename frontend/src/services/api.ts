import axios from 'axios'

const API_BASE_URL = '/api'

// Axios instance
const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 300000, // 5 minutes
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
}

// AI API
export const aiApi = {
    ask: async (question: string, department?: string) => {
        const response = await api.post('/ask', { question, department })
        return response.data
    },

    askWithFiles: async (question: string, files: File[], department?: string) => {
        const formData = new FormData()
        formData.append('question', question)
        if (department) {
            formData.append('department', department)
        }

        // Append all files
        files.forEach((file, index) => {
            formData.append('files', file)
        })

        const response = await api.post('/ask/multimodal', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        })
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

    uploadDocument: async (file: File, department: string = 'Genel') => {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('department', department)
        const response = await api.post('/rag/documents/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
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

export default api
