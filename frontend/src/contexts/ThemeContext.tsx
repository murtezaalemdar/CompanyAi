import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'
import { authApi } from '../services/api'

type Theme = 'dark' | 'light' | 'system'

interface ThemeContextType {
    theme: Theme
    resolvedTheme: 'dark' | 'light'
    setTheme: (theme: Theme) => void
    loadThemeFromServer: () => Promise<void>
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

function getSystemTheme(): 'dark' | 'light' {
    if (typeof window !== 'undefined' && window.matchMedia) {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }
    return 'dark'
}

function applyTheme(resolved: 'dark' | 'light') {
    const root = document.documentElement
    if (resolved === 'dark') {
        root.classList.add('dark')
        root.classList.remove('light')
    } else {
        root.classList.remove('dark')
        root.classList.add('light')
    }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
    const [theme, setThemeState] = useState<Theme>(() => {
        return (localStorage.getItem('theme') as Theme) || 'dark'
    })

    const resolvedTheme: 'dark' | 'light' =
        theme === 'system' ? getSystemTheme() : theme

    useEffect(() => {
        applyTheme(resolvedTheme)
    }, [resolvedTheme])

    // System tema değişikliğini dinle
    useEffect(() => {
        if (theme !== 'system') return
        const mq = window.matchMedia('(prefers-color-scheme: dark)')
        const handler = () => applyTheme(getSystemTheme())
        mq.addEventListener('change', handler)
        return () => mq.removeEventListener('change', handler)
    }, [theme])

    // Sunucudan tema yüklendiğinde güncelle
    useEffect(() => {
        const handler = () => {
            const saved = localStorage.getItem('theme') as Theme
            if (saved && saved !== theme) {
                setThemeState(saved)
            }
        }
        window.addEventListener('theme-loaded', handler)
        return () => window.removeEventListener('theme-loaded', handler)
    }, [theme])

    const setTheme = (newTheme: Theme) => {
        setThemeState(newTheme)
        localStorage.setItem('theme', newTheme)
    }

    const loadThemeFromServer = useCallback(async () => {
        try {
            const data = await authApi.getTheme()
            if (data.theme && ['dark', 'light', 'system'].includes(data.theme)) {
                setThemeState(data.theme as Theme)
                localStorage.setItem('theme', data.theme)
            }
        } catch {
            // Sunucu tercih dönmezse localStorage'daki kalır
        }
    }, [])

    return (
        <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme, loadThemeFromServer }}>
            {children}
        </ThemeContext.Provider>
    )
}

export function useTheme() {
    const context = useContext(ThemeContext)
    if (context === undefined) {
        throw new Error('useTheme must be used within a ThemeProvider')
    }
    return context
}
