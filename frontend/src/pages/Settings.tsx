import { useState } from 'react'
import { Save } from 'lucide-react'

export default function Settings() {
    const [formData, setFormData] = useState({
        notifications: true,
        theme: 'dark',
        language: 'tr',
        apiKey: 'sk-....................',
    })

    // Mock implementation for demo
    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        // TODO: Implement settings update API
        alert('Ayarlar kaydedildi (Demo)')
    }

    return (
        <div className="max-w-2xl">
            <div className="card">
                <h3 className="text-lg font-medium text-white mb-6">Sistem Ayarları</h3>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-dark-200 mb-2">
                            Bildirim Tercihleri
                        </label>
                        <div className="flex items-center gap-3">
                            <input
                                type="checkbox"
                                id="notifications"
                                checked={formData.notifications}
                                onChange={(e) => setFormData({ ...formData, notifications: e.target.checked })}
                                className="w-4 h-4 rounded border-dark-600 bg-dark-800 text-primary-600 focus:ring-primary-500"
                            />
                            <label htmlFor="notifications" className="text-sm text-dark-400">
                                Email bildirimlerini al
                            </label>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-dark-200 mb-2">
                            Tema
                        </label>
                        <select
                            value={formData.theme}
                            onChange={(e) => setFormData({ ...formData, theme: e.target.value })}
                            className="input"
                        >
                            <option value="dark">Koyu Tema</option>
                            <option value="light">Açık Tema</option>
                            <option value="system">Sistem Teması</option>
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-dark-200 mb-2">
                            LLM API Key (Opsiyonel)
                        </label>
                        <input
                            type="password"
                            value={formData.apiKey}
                            onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                            className="input font-mono"
                        />
                        <p className="mt-1 text-xs text-dark-500">
                            Harici LLM servisi kullanıyorsanız API anahtarını buraya girin.
                        </p>
                    </div>

                    <div className="pt-4 border-t border-dark-700">
                        <button type="submit" className="btn-primary flex items-center gap-2">
                            <Save className="w-4 h-4" />
                            Kaydet
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}
