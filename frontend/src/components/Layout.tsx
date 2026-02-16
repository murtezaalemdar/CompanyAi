import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { logoApi } from '../services/api'
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
    BarChart3,
    Shield,
    Crown,
    UserCircle,
    ChevronsLeft,
    ChevronsRight,
} from 'lucide-react'
import clsx from 'clsx'
import { APP_VERSION } from '../constants'

export default function Layout() {
    const { user, logout } = useAuth()
    const navigate = useNavigate()
    const location = useLocation()
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
    const [companyLogo, setCompanyLogo] = useState<string | null>(null)
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
        const saved = localStorage.getItem('sidebar-collapsed')
        return saved === 'true'
    })

    // Sidebar durumunu localStorage'a kaydet
    useEffect(() => {
        localStorage.setItem('sidebar-collapsed', String(isSidebarCollapsed))
    }, [isSidebarCollapsed])

    // Mobile menü açıkken body scroll'u kilitle
    useEffect(() => {
        if (isMobileMenuOpen) {
            document.body.style.overflow = 'hidden'
        } else {
            document.body.style.overflow = ''
        }
        return () => { document.body.style.overflow = '' }
    }, [isMobileMenuOpen])

    const isAdmin = user?.role === 'admin' || user?.role === 'manager'

    // Şirket logosunu yükle
    useEffect(() => {
        logoApi.getLogo().then(data => {
            if (data.logo) setCompanyLogo(data.logo)
        }).catch(() => {})
    }, [])

    // Route değişince mobil menüyü kapat
    useEffect(() => {
        setIsMobileMenuOpen(false)
    }, [location.pathname])

    const userNavigation = [
        { name: 'AI Asistan', href: '/ask', icon: MessageSquare, roles: ['admin', 'manager', 'user'] },
        { name: 'Dokümanlar', href: '/documents', icon: FileText, roles: ['admin', 'manager', 'user'] },
        { name: 'Analiz', href: '/analyze', icon: BarChart3, roles: ['admin', 'manager', 'user'] },
        { name: 'Sorgu Geçmişi', href: '/queries', icon: History, roles: ['admin', 'manager', 'user'] },
        { name: 'Profilim', href: '/profile', icon: UserCircle, roles: ['admin', 'manager', 'user'] },
    ].filter(item => item.roles.includes(user?.role || 'user'))

    const adminNavigation = [
        { name: 'Yönetim Paneli', href: '/', icon: LayoutDashboard },
        { name: 'Kullanıcılar', href: '/users', icon: Users },
        { name: 'Ayarlar', href: '/settings', icon: Settings },
    ]

    const navigation = isAdmin
        ? [...userNavigation, ...adminNavigation.map(item => ({ ...item, roles: ['admin', 'manager'] }))]
        : userNavigation

    const roleLabel = user?.role === 'admin' ? 'Admin' : user?.role === 'manager' ? 'Yönetici' : 'Kullanıcı'
    const roleBadgeClass = user?.role === 'admin'
        ? 'bg-red-500/10 text-red-400 border-red-500/20'
        : user?.role === 'manager'
            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
            : 'bg-dark-700 text-dark-400 border-dark-600'

    const handleLogout = () => {
        logout()
        navigate('/login')
    }

    return (
        <div className="min-h-screen bg-dark-950 flex">
            {/* Sidebar - Desktop */}
            <aside className={clsx(
                "hidden md:flex flex-col bg-dark-900 border-r border-dark-800 shrink-0 transition-all duration-300 ease-in-out relative",
                isSidebarCollapsed ? "w-[68px]" : "w-64"
            )}>
                {/* Collapse Toggle */}
                <button
                    onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                    className="absolute -right-3 top-7 z-10 w-6 h-6 bg-dark-800 border border-dark-700 rounded-full flex items-center justify-center text-dark-400 hover:text-white hover:bg-primary-500/20 hover:border-primary-500/40 transition-colors shadow-lg"
                    title={isSidebarCollapsed ? 'Menüyü Aç' : 'Menüyü Kapat'}
                >
                    {isSidebarCollapsed
                        ? <ChevronsRight className="w-3.5 h-3.5" />
                        : <ChevronsLeft className="w-3.5 h-3.5" />
                    }
                </button>

                <button
                    onClick={() => navigate(isAdmin ? '/' : '/ask')}
                    className={clsx(
                        "flex items-center hover:bg-dark-800/50 transition-colors rounded-lg mx-2 mt-2 cursor-pointer",
                        isSidebarCollapsed ? "p-3 justify-center" : "p-4 lg:p-6 gap-3"
                    )}
                >
                    {companyLogo ? (
                        <img
                            src={companyLogo}
                            alt="Company Logo"
                            className={clsx(
                                "object-contain rounded-lg shrink-0",
                                isSidebarCollapsed ? "w-8 h-8" : "w-10 h-10"
                            )}
                        />
                    ) : (
                        <div className="bg-primary-500/10 p-2 rounded-lg shrink-0">
                            <BrainCircuit className={clsx(
                                "text-primary-500",
                                isSidebarCollapsed ? "w-5 h-5" : "w-8 h-8"
                            )} />
                        </div>
                    )}
                    {!isSidebarCollapsed && (
                        <div className="text-left min-w-0">
                            <h1 className="text-lg lg:text-xl font-bold text-white tracking-tight truncate">Company.AI</h1>
                            <p className="text-xs text-dark-400">Kurumsal Asistan</p>
                        </div>
                    )}
                </button>

                <nav className={clsx(
                    "flex-1 py-6 space-y-1 overflow-y-auto overflow-x-hidden",
                    isSidebarCollapsed ? "px-2" : "px-4"
                )}>
                    {userNavigation.map((item) => {
                        const Icon = item.icon
                        const isActive = location.pathname === item.href
                        return (
                            <button
                                key={item.name}
                                onClick={() => navigate(item.href)}
                                title={isSidebarCollapsed ? item.name : undefined}
                                className={clsx(
                                    'w-full flex items-center text-sm font-medium rounded-lg transition-all duration-200',
                                    isSidebarCollapsed ? 'justify-center px-0 py-3' : 'gap-3 px-4 py-3',
                                    isActive
                                        ? 'bg-primary-500/10 text-primary-400'
                                        : 'text-dark-400 hover:bg-dark-800 hover:text-white'
                                )}
                            >
                                <Icon className="w-5 h-5 shrink-0" />
                                {!isSidebarCollapsed && <span className="truncate">{item.name}</span>}
                            </button>
                        )
                    })}

                    {/* Admin/Manager Section */}
                    {isAdmin && (
                        <>
                            <div className={clsx("pt-4 pb-2", isSidebarCollapsed ? "px-1" : "px-4")}>
                                {isSidebarCollapsed ? (
                                    <div className="h-[1px] bg-gradient-to-r from-transparent via-amber-500/30 to-transparent" />
                                ) : (
                                    <div className="flex items-center gap-2">
                                        <div className="h-[1px] flex-1 bg-gradient-to-r from-amber-500/30 to-transparent" />
                                        <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-500/60 flex items-center gap-1">
                                            <Shield className="w-3 h-3" />
                                            Yönetim
                                        </span>
                                        <div className="h-[1px] flex-1 bg-gradient-to-l from-amber-500/30 to-transparent" />
                                    </div>
                                )}
                            </div>
                            {adminNavigation.map((item) => {
                                const Icon = item.icon
                                const isActive = location.pathname === item.href
                                return (
                                    <button
                                        key={item.name}
                                        onClick={() => navigate(item.href)}
                                        title={isSidebarCollapsed ? item.name : undefined}
                                        className={clsx(
                                            'w-full flex items-center text-sm font-medium rounded-lg transition-all duration-200',
                                            isSidebarCollapsed ? 'justify-center px-0 py-3' : 'gap-3 px-4 py-3',
                                            isActive
                                                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                                : 'text-dark-400 hover:bg-amber-500/5 hover:text-amber-300'
                                        )}
                                    >
                                        <Icon className="w-5 h-5 shrink-0" />
                                        {!isSidebarCollapsed && <span className="truncate">{item.name}</span>}
                                    </button>
                                )
                            })}
                        </>
                    )}
                </nav>

                <div className={clsx("border-t border-dark-800", isSidebarCollapsed ? "p-2" : "p-4")}>
                    {!isSidebarCollapsed && (
                        <div className="flex items-center gap-3 mb-4 px-4">
                            <div className={clsx(
                                "w-8 h-8 rounded-full flex items-center justify-center font-bold border shrink-0",
                                isAdmin
                                    ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
                                    : "bg-primary-500/20 text-primary-400 border-primary-500/10"
                            )}>
                                {isAdmin
                                    ? <Crown className="w-4 h-4" />
                                    : (user?.full_name?.charAt(0) || user?.email.charAt(0).toUpperCase())
                                }
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <p className="text-sm font-medium text-white truncate">
                                        {user?.full_name || 'Kullanıcı'}
                                    </p>
                                    <span className={clsx(
                                        "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border shrink-0",
                                        roleBadgeClass
                                    )}>
                                        {roleLabel}
                                    </span>
                                </div>
                                <p className="text-xs text-dark-500 truncate">{user?.email}</p>
                            </div>
                        </div>
                    )}
                    <button
                        onClick={handleLogout}
                        title={isSidebarCollapsed ? 'Çıkış Yap' : undefined}
                        className={clsx(
                            "w-full flex items-center text-sm font-medium text-red-400 hover:bg-red-500/10 rounded-lg transition-colors",
                            isSidebarCollapsed ? "justify-center px-0 py-2" : "gap-3 px-4 py-2"
                        )}
                    >
                        <LogOut className="w-5 h-5 shrink-0" />
                        {!isSidebarCollapsed && 'Çıkış Yap'}
                    </button>
                    {/* Designer Signature + Version */}
                    {!isSidebarCollapsed && (
                        <div className="mt-4 pt-3 border-t border-dark-800/50 space-y-1">
                            <p className="text-[10px] tracking-[0.3em] uppercase text-dark-600/50 text-center font-light select-none">
                                Designed by{' '}
                                <span className="font-medium text-dark-500/60 tracking-[0.2em]">
                                    Murteza ALEMDAR
                                </span>
                            </p>
                            <p className="text-[10px] font-mono text-dark-400/60 text-center select-none">
                                v{APP_VERSION}
                            </p>
                        </div>
                    )}
                    {isSidebarCollapsed && (
                        <p className="text-[9px] font-mono text-dark-400/60 text-center select-none mt-2">
                            v{APP_VERSION}
                        </p>
                    )}
                </div>
            </aside>

            {/* Mobile Header */}
            <div className="md:hidden fixed top-0 left-0 right-0 z-50 bg-dark-900 border-b border-dark-800 px-4 py-3 flex items-center justify-between">
                <button
                    onClick={() => navigate(isAdmin ? '/' : '/ask')}
                    className="flex items-center gap-2 hover:opacity-80 transition-opacity min-w-0"
                >
                    {companyLogo ? (
                        <img
                            src={companyLogo}
                            alt="Logo"
                            className="w-7 h-7 object-contain rounded"
                        />
                    ) : (
                        <BrainCircuit className="w-6 h-6 text-primary-500 shrink-0" />
                    )}
                    <span className="font-bold text-white truncate">Company.AI</span>
                </button>
                <button
                    onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                    className="text-dark-400 hover:text-white p-1"
                >
                    {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
                </button>
            </div>

            {/* Mobile Menu Overlay */}
            {isMobileMenuOpen && (
                <div className="md:hidden fixed inset-0 z-40 bg-dark-950/90 backdrop-blur-sm pt-16">
                    <nav className="p-4 space-y-2">
                        {userNavigation.map((item) => {
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

                        {/* Mobile Admin Section */}
                        {isAdmin && (
                            <>
                                <div className="pt-3 pb-1 px-4">
                                    <div className="flex items-center gap-2">
                                        <div className="h-[1px] flex-1 bg-gradient-to-r from-amber-500/30 to-transparent" />
                                        <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-500/60 flex items-center gap-1">
                                            <Shield className="w-3 h-3" />
                                            Yönetim
                                        </span>
                                        <div className="h-[1px] flex-1 bg-gradient-to-l from-amber-500/30 to-transparent" />
                                    </div>
                                </div>
                                {adminNavigation.map((item) => {
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
                                                    ? 'bg-amber-500/10 text-amber-400'
                                                    : 'text-dark-400 hover:bg-amber-500/5 hover:text-amber-300'
                                            )}
                                        >
                                            <Icon className="w-6 h-6" />
                                            {item.name}
                                        </button>
                                    )
                                })}
                            </>
                        )}

                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center gap-3 px-4 py-4 text-base font-medium text-red-400 hover:bg-red-500/10 rounded-lg mt-4"
                        >
                            <LogOut className="w-6 h-6" />
                            Çıkış Yap
                        </button>
                    </nav>
                    {/* Mobile Designer Signature + Version */}
                    <div className="absolute bottom-8 left-0 right-0 flex flex-col items-center gap-1.5">
                        <p className="text-[11px] tracking-[0.3em] uppercase text-dark-600/50 font-light select-none">
                            Designed by{' '}
                            <span className="font-medium text-dark-500/60 tracking-[0.2em]">
                                Murteza ALEMDAR
                            </span>
                        </p>
                        <span className="text-[11px] font-mono text-dark-400/60 tracking-wide select-none px-2.5 py-0.5 rounded-full border border-dark-700/30 bg-dark-800/20">
                            v{APP_VERSION}
                        </span>
                    </div>
                </div>
            )}

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto h-screen pt-14 md:pt-0 min-w-0">
                <div className="w-full px-4 sm:px-6 lg:px-8 py-4 sm:py-6 md:py-8 animate-fade-in">
                    {/* Header Bar (Desktop Only) */}
                    <header className="hidden md:flex items-center justify-between mb-6 lg:mb-8 flex-wrap gap-4">
                        <div>
                            <h2 className="text-2xl font-bold text-white">
                                {[...userNavigation, ...adminNavigation].find((i) => i.href === location.pathname)?.name || 'Dashboard'}
                            </h2>
                            <p className="text-dark-400 text-sm mt-1">
                                Hoş geldiniz, bugün size nasıl yardımcı olabilirim?
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            {isAdmin && (
                                <span className={clsx(
                                    "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border",
                                    roleBadgeClass
                                )}>
                                    <Crown className="w-3 h-3" />
                                    {roleLabel}
                                </span>
                            )}
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
