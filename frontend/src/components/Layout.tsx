import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import {
    LayoutDashboard,
    MessageSquare,
    History,
    Settings,
    LogOut,
    Menu,
    X,
    BrainCircuit,
    FileText,
    Users,
} from 'lucide-react'
import clsx from 'clsx'

export default function Layout() {
    const { user, logout } = useAuth()
    const navigate = useNavigate()
    const location = useLocation()
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

    const navigation = [
        { name: 'Panel', href: '/', icon: LayoutDashboard, roles: ['admin', 'manager'] },
        { name: 'AI Asistan', href: '/ask', icon: MessageSquare, roles: ['admin', 'manager', 'user'] },
        { name: 'Dokümanlar', href: '/documents', icon: FileText, roles: ['admin', 'manager', 'user'] },
        { name: 'Kullanıcılar', href: '/users', icon: Users, roles: ['admin', 'manager'] },
        { name: 'Sorgu Geçmişi', href: '/queries', icon: History, roles: ['admin', 'manager', 'user'] },
        { name: 'Ayarlar', href: '/settings', icon: Settings, roles: ['admin', 'manager'] },
    ].filter(item => item.roles.includes(user?.role || 'user'))

    const handleLogout = () => {
        logout()
        navigate('/login')
    }

    return (
        <div className="min-h-screen bg-dark-950 flex">
            {/* Sidebar - Desktop */}
            <aside className="hidden md:flex flex-col w-64 bg-dark-900 border-r border-dark-800">
                <div className="p-6 flex items-center gap-3">
                    <div className="bg-primary-500/10 p-2 rounded-lg">
                        <BrainCircuit className="w-8 h-8 text-primary-500" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-white tracking-tight">Company.AI</h1>
                        <p className="text-xs text-dark-400">Kurumsal Asistan</p>
                    </div>
                </div>

                <nav className="flex-1 px-4 py-6 space-y-1">
                    {navigation.map((item) => {
                        const Icon = item.icon
                        const isActive = location.pathname === item.href
                        return (
                            <button
                                key={item.name}
                                onClick={() => navigate(item.href)}
                                className={clsx(
                                    'w-full flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200',
                                    isActive
                                        ? 'bg-primary-500/10 text-primary-400'
                                        : 'text-dark-400 hover:bg-dark-800 hover:text-white'
                                )}
                            >
                                <Icon className="w-5 h-5" />
                                {item.name}
                            </button>
                        )
                    })}
                </nav>

                <div className="p-4 border-t border-dark-800">
                    <div className="flex items-center gap-3 mb-4 px-4">
                        <div className="w-8 h-8 rounded-full bg-primary-500/20 flex items-center justify-center text-primary-400 font-bold border border-primary-500/10">
                            {user?.full_name?.charAt(0) || user?.email.charAt(0).toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white truncate">
                                {user?.full_name || 'Kullanıcı'}
                            </p>
                            <p className="text-xs text-dark-500 truncate">{user?.email}</p>
                        </div>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-3 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                    >
                        <LogOut className="w-5 h-5" />
                        Çıkış Yap
                    </button>
                </div>
            </aside>

            {/* Mobile Header */}
            <div className="md:hidden fixed top-0 left-0 right-0 z-50 bg-dark-900 border-b border-dark-800 px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BrainCircuit className="w-6 h-6 text-primary-500" />
                    <span className="font-bold text-white">Company.AI</span>
                </div>
                <button
                    onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                    className="text-dark-400 hover:text-white"
                >
                    {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
                </button>
            </div>

            {/* Mobile Menu Overlay */}
            {isMobileMenuOpen && (
                <div className="md:hidden fixed inset-0 z-40 bg-dark-950/90 backdrop-blur-sm pt-16">
                    <nav className="p-4 space-y-2">
                        {navigation.map((item) => {
                            const Icon = item.icon
                            const isActive = location.pathname === item.href
                            return (
                                <button
                                    key={item.name}
                                    onClick={() => {
                                        navigate(item.href)
                                        setIsMobileMenuOpen(false)
                                    }}
                                    className={clsx(
                                        'w-full flex items-center gap-3 px-4 py-4 text-base font-medium rounded-lg transition-colors',
                                        isActive
                                            ? 'bg-primary-500/10 text-primary-400'
                                            : 'text-dark-400 hover:bg-dark-800 hover:text-white'
                                    )}
                                >
                                    <Icon className="w-6 h-6" />
                                    {item.name}
                                </button>
                            )
                        })}
                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center gap-3 px-4 py-4 text-base font-medium text-red-400 hover:bg-red-500/10 rounded-lg mt-4"
                        >
                            <LogOut className="w-6 h-6" />
                            Çıkış Yap
                        </button>
                    </nav>
                </div>
            )}

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto h-screen pt-16 md:pt-0">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
                    {/* Header Bar (Desktop Only) */}
                    <header className="hidden md:flex items-center justify-between mb-8">
                        <div>
                            <h2 className="text-2xl font-bold text-white">
                                {navigation.find((i) => i.href === location.pathname)?.name || 'Dashboard'}
                            </h2>
                            <p className="text-dark-400 text-sm mt-1">
                                Hoş geldiniz, bugün size nasıl yardımcı olabilirim?
                            </p>
                        </div>
                        <div className="text-right">
                            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                                Sistem Online
                            </span>
                        </div>
                    </header>

                    <Outlet />
                </div>
            </main>
        </div>
    )
}

import { Outlet } from 'react-router-dom'
