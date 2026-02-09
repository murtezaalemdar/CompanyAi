import { useQuery } from '@tanstack/react-query'
import { adminApi, aiApi, memoryApi } from '../services/api'
import {
    Users,
    MessageSquare,
    Activity,
    ArrowUpRight,
    ArrowDownRight,
    Clock,
    Zap,
    Database,
    Brain,
} from 'lucide-react'
import {
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    AreaChart,
    Area,
} from 'recharts'
import clsx from 'clsx'

export default function Dashboard() {
    const { data: stats } = useQuery({
        queryKey: ['dashboard-stats'],
        queryFn: adminApi.getDashboardStats,
    })

    const { data: llmStatus } = useQuery({
        queryKey: ['llm-status'],
        queryFn: aiApi.getLlmStatus,
    })

    const { data: memoryStats } = useQuery({
        queryKey: ['memory-stats'],
        queryFn: memoryApi.getStats,
        refetchInterval: 30000, // 30 saniyede bir güncelle
    })

    const { data: queryTraffic } = useQuery({
        queryKey: ['query-traffic'],
        queryFn: adminApi.getQueryTraffic,
        refetchInterval: 60000, // 1 dakikada bir güncelle
    })

    const { data: sysResources } = useQuery({
        queryKey: ['system-resources'],
        queryFn: adminApi.getSystemResources,
        refetchInterval: 15000, // 15 saniyede bir güncelle
    })

    const fmtChange = (val?: number) => {
        if (val == null) return { text: '-', type: 'neutral' as const }
        const sign = val >= 0 ? '+' : ''
        return { text: `${sign}${val}%`, type: val >= 0 ? 'increase' as const : 'decrease' as const }
    }

    const usersChange = fmtChange(stats?.users_change_pct)
    const queriesChange = fmtChange(stats?.queries_change_pct)
    const rtChange = fmtChange(stats?.response_time_change_pct)

    const cards = [
        {
            name: 'Toplam Kullanıcı',
            value: stats?.total_users || 0,
            icon: Users,
            change: usersChange.text,
            changeType: usersChange.type,
            color: 'text-blue-500',
            bg: 'bg-blue-500/10',
        },
        {
            name: 'Günlük Sorgu',
            value: stats?.queries_today || 0,
            icon: MessageSquare,
            change: queriesChange.text,
            changeType: queriesChange.type,
            color: 'text-primary-500',
            bg: 'bg-primary-500/10',
        },
        {
            name: 'Ortalama Yanıt',
            value: `${Math.round(stats?.avg_response_time_ms || 0)}ms`,
            icon: Zap,
            change: rtChange.text,
            changeType: rtChange.type,
            color: 'text-yellow-500',
            bg: 'bg-yellow-500/10',
        },
        {
            name: 'Sistem Durumu',
            value: llmStatus?.available ? 'Online' : 'Offline',
            icon: Activity,
            change: llmStatus?.current_model || '-',
            changeType: 'neutral',
            color: llmStatus?.available ? 'text-green-500' : 'text-red-500',
            bg: llmStatus?.available ? 'bg-green-500/10' : 'bg-red-500/10',
        },
    ]

    // Gerçek sorgu trafiği verisi (API'den) veya boş array
    const data = queryTraffic || []

    const cpuPct = sysResources?.cpu_percent != null ? Math.round(sysResources.cpu_percent) : null
    const memPct = sysResources?.memory_percent != null ? Math.round(sysResources.memory_percent) : null

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
                {cards.map((card) => (
                    <div key={card.name} className="card relative overflow-hidden">
                        <div className="flex items-start justify-between">
                            <div>
                                <p className="text-sm font-medium text-dark-400 truncate">{card.name}</p>
                                <p className="mt-1 text-3xl font-semibold text-white">{card.value}</p>
                            </div>
                            <div className={clsx('p-2 rounded-lg', card.bg)}>
                                <card.icon className={clsx('w-6 h-6', card.color)} />
                            </div>
                        </div>
                        <div className="mt-4 flex items-center text-sm">
                            {card.changeType === 'increase' && (
                                <ArrowUpRight className="self-center flex-shrink-0 h-4 w-4 text-green-500" />
                            )}
                            {card.changeType === 'decrease' && (
                                <ArrowDownRight className="self-center flex-shrink-0 h-4 w-4 text-green-500" />
                            )}
                            <span
                                className={clsx(
                                    'ml-1 font-medium',
                                    card.changeType === 'increase'
                                        ? 'text-green-500'
                                        : card.changeType === 'decrease'
                                            ? 'text-green-500'
                                            : 'text-dark-400'
                                )}
                            >
                                {card.change}
                            </span>
                            <span className="ml-2 text-dark-500 text-xs">geçen haftaya göre</span>
                        </div>
                    </div>
                ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 card">
                    <h3 className="text-lg font-medium text-white mb-6">Sorgu Trafiği</h3>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={data}>
                                <defs>
                                    <linearGradient id="colorQueries" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                <XAxis
                                    dataKey="name"
                                    stroke="#64748b"
                                    fontSize={12}
                                    tickLine={false}
                                    axisLine={false}
                                />
                                <YAxis
                                    stroke="#64748b"
                                    fontSize={12}
                                    tickLine={false}
                                    axisLine={false}
                                    tickFormatter={(value) => `${value}`}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: '#0f172a',
                                        border: '1px solid #1e293b',
                                        borderRadius: '8px',
                                    }}
                                    itemStyle={{ color: '#e2e8f0' }}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="queries"
                                    stroke="#3b82f6"
                                    strokeWidth={2}
                                    fillOpacity={1}
                                    fill="url(#colorQueries)"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="card">
                    <h3 className="text-lg font-medium text-white mb-6">Sistem Durumu</h3>
                    <div className="space-y-6">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-primary-500/10 flex items-center justify-center">
                                    <Zap className="w-5 h-5 text-primary-500" />
                                </div>
                                <div>
                                    <p className="text-sm font-medium text-white">LLM Model</p>
                                    <p className="text-xs text-dark-400">{llmStatus?.current_model || 'Yükleniyor...'}</p>
                                </div>
                            </div>
                            <span className="px-2 py-1 text-xs font-medium bg-green-500/10 text-green-500 rounded-full">
                                Ready
                            </span>
                        </div>

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                                    <Database className="w-5 h-5 text-purple-500" />
                                </div>
                                <div>
                                    <p className="text-sm font-medium text-white">Hafıza (ChromaDB)</p>
                                    <p className="text-xs text-dark-400">
                                        {memoryStats?.total_entries || 0} kayıt
                                    </p>
                                </div>
                            </div>
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${memoryStats?.storage_type === 'chromadb'
                                    ? 'bg-purple-500/10 text-purple-500'
                                    : 'bg-yellow-500/10 text-yellow-500'
                                }`}>
                                {memoryStats?.storage_type === 'chromadb' ? 'Aktif' : 'Fallback'}
                            </span>
                        </div>

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-cyan-500/10 flex items-center justify-center">
                                    <Brain className="w-5 h-5 text-cyan-500" />
                                </div>
                                <div>
                                    <p className="text-sm font-medium text-white">Embedding</p>
                                    <p className="text-xs text-dark-400 truncate max-w-[120px]" title={memoryStats?.embedding_model}>
                                        {memoryStats?.embedding_model?.split('/').pop() || 'Yükleniyor...'}
                                    </p>
                                </div>
                            </div>
                        </div>

                        <div className="border-t border-dark-700 pt-4">
                            <h4 className="text-xs font-semibold text-dark-400 uppercase mb-4">
                                Kaynak Kullanımı
                            </h4>
                            <div className="space-y-4">
                                <div>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-dark-300">CPU</span>
                                        <span className="text-white">{cpuPct != null ? `${cpuPct}%` : '-'}</span>
                                    </div>
                                    <div className="w-full bg-dark-800 rounded-full h-1.5">
                                        <div className="bg-primary-500 h-1.5 rounded-full transition-all" style={{ width: `${cpuPct}%` }} />
                                    </div>
                                </div>
                                <div>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-dark-300">Memory</span>
                                        <span className="text-white">{memPct != null ? `${memPct}%` : '-'}</span>
                                    </div>
                                    <div className="w-full bg-dark-800 rounded-full h-1.5">
                                        <div className="bg-yellow-500 h-1.5 rounded-full transition-all" style={{ width: `${memPct}%` }} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
