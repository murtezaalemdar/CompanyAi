import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { authApi } from '../services/api'
import {
    User,
    Lock,
    Eye,
    EyeOff,
    Sun,
    Moon,
    Monitor,
    Check,
    AlertCircle,
    Shield,
    Mail,
    Briefcase,
    Crown,
} from 'lucide-react'
import clsx from 'clsx'

export default function Profile() {
    const { user } = useAuth()
    const { theme, setTheme } = useTheme()

    // Şifre değiştirme state
    const [currentPassword, setCurrentPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [showCurrentPassword, setShowCurrentPassword] = useState(false)
    const [showNewPassword, setShowNewPassword] = useState(false)
    const [passwordLoading, setPasswordLoading] = useState(false)
    const [passwordMessage, setPasswordMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

    // Tema state
    const [themeLoading, setThemeLoading] = useState(false)
    const [themeMessage, setThemeMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

    const roleLabel = user?.role === 'admin' ? 'Admin' : user?.role === 'manager' ? 'Yönetici' : 'Kullanıcı'
    const roleBadgeClass = user?.role === 'admin'
        ? 'bg-red-500/10 text-red-400 border-red-500/20'
        : user?.role === 'manager'
            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
            : 'bg-slate-500/10 text-slate-400 border-slate-500/20'

    const handlePasswordChange = async (e: React.FormEvent) => {
        e.preventDefault()
        setPasswordMessage(null)

        if (newPassword !== confirmPassword) {
            setPasswordMessage({ type: 'error', text: 'Yeni şifreler eşleşmiyor' })
            return
        }

        if (newPassword.length < 8) {
            setPasswordMessage({ type: 'error', text: 'Şifre en az 8 karakter olmalıdır' })
            return
        }

        setPasswordLoading(true)
        try {
            await authApi.changePassword(currentPassword, newPassword)
            setPasswordMessage({ type: 'success', text: 'Şifre başarıyla değiştirildi!' })
            setCurrentPassword('')
            setNewPassword('')
            setConfirmPassword('')
        } catch (error: any) {
            const msg = error.response?.data?.detail || 'Şifre değiştirilemedi'
            setPasswordMessage({ type: 'error', text: msg })
        } finally {
            setPasswordLoading(false)
        }
    }

    const handleThemeChange = async (newTheme: 'dark' | 'light' | 'system') => {
        setThemeLoading(true)
        setThemeMessage(null)
        try {
            setTheme(newTheme)
            await authApi.setTheme(newTheme)
            setThemeMessage({ type: 'success', text: 'Tema güncellendi!' })
            setTimeout(() => setThemeMessage(null), 2000)
        } catch {
            // localStorage'da zaten kaydedildi, API hatası olsa da çalışır
        } finally {
            setThemeLoading(false)
        }
    }

    const themeOptions = [
        { value: 'dark' as const, label: 'Koyu', icon: Moon, desc: 'Koyu arka plan' },
        { value: 'light' as const, label: 'Açık', icon: Sun, desc: 'Açık arka plan' },
        { value: 'system' as const, label: 'Sistem', icon: Monitor, desc: 'Sistem ayarını takip et' },
    ]

    return (
        <div className="max-w-2xl mx-auto space-y-6">
            {/* Profil Bilgileri */}
            <div className="bg-dark-800/50 dark:bg-dark-800/50 bg-white/80 backdrop-blur-sm rounded-xl border border-dark-700/50 dark:border-dark-700/50 border-slate-200 p-6">
                <h2 className="text-lg font-semibold text-white dark:text-white text-slate-900 mb-6 flex items-center gap-2">
                    <User className="w-5 h-5 text-primary-500" />
                    Profil Bilgileri
                </h2>
                <div className="space-y-4">
                    <div className="flex items-center gap-4">
                        <div className={clsx(
                            "w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold border-2",
                            user?.role === 'admin'
                                ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
                                : "bg-primary-500/20 text-primary-400 border-primary-500/30"
                        )}>
                            {user?.role === 'admin'
                                ? <Crown className="w-8 h-8" />
                                : (user?.full_name?.charAt(0) || user?.email?.charAt(0)?.toUpperCase() || '?')
                            }
                        </div>
                        <div>
                            <h3 className="text-xl font-bold text-white dark:text-white text-slate-900">
                                {user?.full_name || 'İsimsiz Kullanıcı'}
                            </h3>
                            <span className={clsx(
                                "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border mt-1",
                                roleBadgeClass
                            )}>
                                <Shield className="w-3 h-3" />
                                {roleLabel}
                            </span>
                        </div>
                    </div>

                    <div className="grid gap-3 mt-4">
                        <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-dark-900/50 dark:bg-dark-900/50 bg-slate-50">
                            <Mail className="w-4 h-4 text-dark-400 dark:text-dark-400 text-slate-500" />
                            <div>
                                <p className="text-xs text-dark-400 dark:text-dark-400 text-slate-500">E-posta</p>
                                <p className="text-sm font-medium text-white dark:text-white text-slate-900">{user?.email}</p>
                            </div>
                        </div>
                        {user?.department && (
                            <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-dark-900/50 dark:bg-dark-900/50 bg-slate-50">
                                <Briefcase className="w-4 h-4 text-dark-400 dark:text-dark-400 text-slate-500" />
                                <div>
                                    <p className="text-xs text-dark-400 dark:text-dark-400 text-slate-500">Departman</p>
                                    <p className="text-sm font-medium text-white dark:text-white text-slate-900">{user.department}</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Tema Seçimi */}
            <div className="bg-dark-800/50 dark:bg-dark-800/50 bg-white/80 backdrop-blur-sm rounded-xl border border-dark-700/50 dark:border-dark-700/50 border-slate-200 p-6">
                <h2 className="text-lg font-semibold text-white dark:text-white text-slate-900 mb-4 flex items-center gap-2">
                    <Sun className="w-5 h-5 text-primary-500" />
                    Tema
                </h2>
                <div className="grid grid-cols-3 gap-3">
                    {themeOptions.map((opt) => {
                        const Icon = opt.icon
                        const isActive = theme === opt.value
                        return (
                            <button
                                key={opt.value}
                                onClick={() => handleThemeChange(opt.value)}
                                disabled={themeLoading}
                                className={clsx(
                                    'relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200 cursor-pointer',
                                    isActive
                                        ? 'border-primary-500 bg-primary-500/10 shadow-lg shadow-primary-500/10'
                                        : 'border-dark-600 dark:border-dark-600 border-slate-200 hover:border-dark-500 dark:hover:border-dark-500 hover:border-slate-300 bg-dark-900/30 dark:bg-dark-900/30 bg-slate-50'
                                )}
                            >
                                {isActive && (
                                    <div className="absolute top-2 right-2">
                                        <Check className="w-4 h-4 text-primary-500" />
                                    </div>
                                )}
                                <Icon className={clsx(
                                    'w-6 h-6',
                                    isActive ? 'text-primary-400' : 'text-dark-400 dark:text-dark-400 text-slate-500'
                                )} />
                                <span className={clsx(
                                    'text-sm font-medium',
                                    isActive ? 'text-primary-400' : 'text-dark-300 dark:text-dark-300 text-slate-700'
                                )}>
                                    {opt.label}
                                </span>
                                <span className="text-xs text-dark-500 dark:text-dark-500 text-slate-400">
                                    {opt.desc}
                                </span>
                            </button>
                        )
                    })}
                </div>
                {themeMessage && (
                    <div className={clsx(
                        'mt-3 flex items-center gap-2 text-sm px-3 py-2 rounded-lg',
                        themeMessage.type === 'success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                    )}>
                        <Check className="w-4 h-4" />
                        {themeMessage.text}
                    </div>
                )}
            </div>

            {/* Şifre Değiştirme */}
            <div className="bg-dark-800/50 dark:bg-dark-800/50 bg-white/80 backdrop-blur-sm rounded-xl border border-dark-700/50 dark:border-dark-700/50 border-slate-200 p-6">
                <h2 className="text-lg font-semibold text-white dark:text-white text-slate-900 mb-4 flex items-center gap-2">
                    <Lock className="w-5 h-5 text-primary-500" />
                    Şifre Değiştir
                </h2>
                <form onSubmit={handlePasswordChange} className="space-y-4">
                    {/* Mevcut Şifre */}
                    <div>
                        <label className="block text-sm font-medium text-dark-300 dark:text-dark-300 text-slate-600 mb-1.5">
                            Mevcut Şifre
                        </label>
                        <div className="relative">
                            <input
                                type={showCurrentPassword ? 'text' : 'password'}
                                value={currentPassword}
                                onChange={(e) => setCurrentPassword(e.target.value)}
                                required
                                className="w-full bg-dark-900 dark:bg-dark-900 bg-slate-50 border border-dark-600 dark:border-dark-600 border-slate-300 rounded-lg px-4 py-3 text-white dark:text-white text-slate-900 placeholder-dark-400 dark:placeholder-dark-400 placeholder-slate-400 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all pr-12"
                                placeholder="Mevcut şifrenizi girin"
                            />
                            <button
                                type="button"
                                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-white dark:hover:text-white hover:text-slate-700 transition-colors"
                            >
                                {showCurrentPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                            </button>
                        </div>
                    </div>

                    {/* Yeni Şifre */}
                    <div>
                        <label className="block text-sm font-medium text-dark-300 dark:text-dark-300 text-slate-600 mb-1.5">
                            Yeni Şifre
                        </label>
                        <div className="relative">
                            <input
                                type={showNewPassword ? 'text' : 'password'}
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                required
                                minLength={8}
                                className="w-full bg-dark-900 dark:bg-dark-900 bg-slate-50 border border-dark-600 dark:border-dark-600 border-slate-300 rounded-lg px-4 py-3 text-white dark:text-white text-slate-900 placeholder-dark-400 dark:placeholder-dark-400 placeholder-slate-400 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all pr-12"
                                placeholder="En az 8 karakter, harf ve rakam"
                            />
                            <button
                                type="button"
                                onClick={() => setShowNewPassword(!showNewPassword)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-white dark:hover:text-white hover:text-slate-700 transition-colors"
                            >
                                {showNewPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                            </button>
                        </div>
                    </div>

                    {/* Şifre Tekrar */}
                    <div>
                        <label className="block text-sm font-medium text-dark-300 dark:text-dark-300 text-slate-600 mb-1.5">
                            Yeni Şifre (Tekrar)
                        </label>
                        <input
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            required
                            className="w-full bg-dark-900 dark:bg-dark-900 bg-slate-50 border border-dark-600 dark:border-dark-600 border-slate-300 rounded-lg px-4 py-3 text-white dark:text-white text-slate-900 placeholder-dark-400 dark:placeholder-dark-400 placeholder-slate-400 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all"
                            placeholder="Yeni şifrenizi tekrar girin"
                        />
                    </div>

                    {/* Mesaj */}
                    {passwordMessage && (
                        <div className={clsx(
                            'flex items-center gap-2 text-sm px-4 py-3 rounded-lg',
                            passwordMessage.type === 'success'
                                ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                                : 'bg-red-500/10 text-red-400 border border-red-500/20'
                        )}>
                            {passwordMessage.type === 'success'
                                ? <Check className="w-4 h-4 flex-shrink-0" />
                                : <AlertCircle className="w-4 h-4 flex-shrink-0" />
                            }
                            {passwordMessage.text}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={passwordLoading || !currentPassword || !newPassword || !confirmPassword}
                        className={clsx(
                            'w-full flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium transition-all duration-200',
                            passwordLoading || !currentPassword || !newPassword || !confirmPassword
                                ? 'bg-dark-700 text-dark-400 cursor-not-allowed'
                                : 'bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-500 hover:to-primary-400 text-white shadow-lg shadow-primary-500/25 hover:shadow-primary-500/40'
                        )}
                    >
                        {passwordLoading ? (
                            <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-white" />
                        ) : (
                            <>
                                <Lock className="w-4 h-4" />
                                Şifreyi Değiştir
                            </>
                        )}
                    </button>
                </form>
            </div>
        </div>
    )
}
