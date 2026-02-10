import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { BrainCircuit, Loader2, AlertCircle } from 'lucide-react'

export default function Login() {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)
    const { login } = useAuth()
    const navigate = useNavigate()

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setIsSubmitting(true)

        try {
            await login(email, password)
            navigate('/')
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Giriş yapılırken bir hata oluştu')
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <div className="min-h-screen bg-dark-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
            {/* Background decoration */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-primary-500/5 rounded-full blur-3xl -z-10" />

            <div className="sm:mx-auto sm:w-full sm:max-w-md">
                <div className="flex justify-center animate-float">
                    <div className="bg-primary-500/10 p-4 rounded-2xl border border-primary-500/20 backdrop-blur-sm">
                        <BrainCircuit className="w-12 h-12 text-primary-500" />
                    </div>
                </div>
                <h2 className="mt-6 text-center text-3xl font-extrabold text-white tracking-tight">
                    Company.AI
                </h2>
                <p className="mt-2 text-center text-sm text-dark-400">
                    Kurumsal Yapay Zeka Asistanınız
                </p>
            </div>

            <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
                <div className="bg-dark-900/50 backdrop-blur-md py-8 px-4 shadow-2xl border border-dark-800 rounded-2xl sm:px-10">
                    <form className="space-y-6" onSubmit={handleSubmit}>
                        {error && (
                            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 flex items-start gap-3">
                                <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                                <p className="text-sm text-red-400">{error}</p>
                            </div>
                        )}

                        <div>
                            <label htmlFor="email" className="block text-sm font-medium text-dark-200">
                                Email Adresi
                            </label>
                            <div className="mt-1">
                                <input
                                    id="email"
                                    name="email"
                                    type="email"
                                    autoComplete="email"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="input"
                                    placeholder="ornek@sirket.com"
                                />
                            </div>
                        </div>

                        <div>
                            <label htmlFor="password" className="block text-sm font-medium text-dark-200">
                                Şifre
                            </label>
                            <div className="mt-1">
                                <input
                                    id="password"
                                    name="password"
                                    type="password"
                                    autoComplete="current-password"
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="input"
                                    placeholder="••••••••"
                                />
                            </div>
                        </div>

                        <div>
                            <button
                                type="submit"
                                disabled={isSubmitting}
                                className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-dark-900 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                            >
                                {isSubmitting ? (
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                ) : (
                                    'Giriş Yap'
                                )}
                            </button>
                        </div>
                    </form>

                    <div className="mt-6">
                        <div className="relative">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-dark-700" />
                            </div>
                            <div className="relative flex justify-center text-sm">
                                <span className="px-2 bg-dark-900/50 text-dark-400">
                                    Demo Hesabı
                                </span>
                            </div>
                        </div>

                        <div className="mt-4 grid grid-cols-1 gap-2 text-xs text-dark-500 text-center">
                            <p>Email: admin@company.ai</p>
                            <p>Şifre: admin123</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Designer Signature */}
            <div className="absolute bottom-6 left-0 right-0 flex justify-center">
                <p className="text-[11px] tracking-[0.35em] uppercase text-dark-600/60 font-light select-none">
                    Designed by{' '}
                    <span className="font-medium text-dark-500/70 tracking-[0.25em]">
                        Murteza ALEMDAR
                    </span>
                </p>
            </div>
        </div>
    )
}
