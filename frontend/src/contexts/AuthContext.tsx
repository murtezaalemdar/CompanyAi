import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { authApi } from '../services/api'

interface User {
    id: number
    email: string
    full_name: string | null
    role: string
    is_active: boolean
    department: string | null
}

interface AuthContextType {
    user: User | null
    isAuthenticated: boolean
    isLoading: boolean
    login: (email: string, password: string) => Promise<void>
    logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        checkAuth()
    }, [])

    const checkAuth = async () => {
        const token = localStorage.getItem('token')
        if (!token) {
            setIsLoading(false)
            return
        }

        try {
            const userData = await authApi.getMe()
            setUser(userData)
        } catch (error) {
            localStorage.removeItem('token')
        } finally {
            setIsLoading(false)
        }
    }

    const login = async (email: string, password: string) => {
        const { access_token } = await authApi.login(email, password)
        localStorage.setItem('token', access_token)
        const userData = await authApi.getMe()
        setUser(userData)
    }

    const logout = () => {
        localStorage.removeItem('token')
        setUser(null)
    }

    return (
        <AuthContext.Provider
            value={{
                user,
                isAuthenticated: !!user,
                isLoading,
                login,
                logout,
            }}
        >
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}
