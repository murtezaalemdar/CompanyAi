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
    Shield,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    BarChart3,
    TrendingUp,
    Cpu,
} from 'lucide-react'
import {
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    AreaChart,
    Area,
    BarChart,
    Bar,
    Cell,
    PieChart,
    Pie,
} from 'recharts'
import clsx from 'clsx'

// ── Modül etiketleri (Türkçe) ──
const MODULE_LABELS: Record<string, string> = {
    tools: 'Tool Calling',
    reasoning: 'Çok Adımlı Muhakeme',
    structured_output: 'Yapısal Çıktı',
    kpi_engine: 'KPI Motoru',
    textile_knowledge: 'Tekstil Bilgi Tabanı',
    risk_analyzer: 'Risk Analizi',
    reflection: 'Kendini Değerlendirme',
    agent_pipeline: 'Çoklu Ajan Pipeline',
    scenario_engine: 'Senaryo Simülasyon',
    monte_carlo: 'Monte Carlo Risk',
    decision_ranking: 'Karar Önceliklendirme',
    governance: 'AI Governance',
    experiment_layer: 'A/B Strateji Deneyi',
    graph_impact: 'Etki Grafı Analizi',
    arima_forecasting: 'ARIMA Tahminleme',
    sql_generator: 'SQL Üretici',
    export: 'Dışa Aktarma',
    web_search: 'Web Arama',
}

const DEPT_COLORS = ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444', '#06b6d4', '#ec4899', '#f97316']

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
        refetchInterval: 30000,
    })

    const { data: queryTraffic } = useQuery({
        queryKey: ['query-traffic'],
        queryFn: adminApi.getQueryTraffic,
        refetchInterval: 60000,
    })

    const { data: sysResources } = useQuery({
        queryKey: ['system-resources'],
        queryFn: adminApi.getSystemResources,
        refetchInterval: 15000,
    })

    // v3.3.0 — Yeni veri kaynakları
    const { data: aiModules } = useQuery({
        queryKey: ['ai-modules'],
        queryFn: adminApi.getAiModules,
        refetchInterval: 60000,
    })

    const { data: governance } = useQuery({
        queryKey: ['governance-metrics'],
        queryFn: adminApi.getGovernanceMetrics,
        refetchInterval: 30000,
    })

    const { data: deptStats } = useQuery({
        queryKey: ['dept-query-stats'],
        queryFn: adminApi.getDeptQueryStats,
        refetchInterval: 60000,
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

    // Sorgu trafiği
    const data = queryTraffic || []

    const cpuPct = sysResources?.cpu_percent != null ? Math.round(sysResources.cpu_percent) : null
    const memPct = sysResources?.memory_percent != null ? Math.round(sysResources.memory_percent) : null
    const diskPct = sysResources?.disk_percent != null ? Math.round(sysResources.disk_percent) : null

    // AI Modüller
    const modules = aiModules?.modules || {}
    const activeModuleCount = Object.values(modules).filter(Boolean).length
    const totalModuleCount = Object.keys(modules).length

    // Governance
    const govAvailable = governance?.available === true
    const biasAlerts = governance?.bias_alerts || 0
    const avgConf = governance?.avg_confidence || 0
    const driftDetected = governance?.drift_detected || false

    // Departman istatistikleri — pie data
    const deptPieData = (deptStats || []).map((d: any, i: number) => ({
        name: d.department,
        value: d.count,
        fill: DEPT_COLORS[i % DEPT_COLORS.length],
    }))

    return (
        <div className="space-y-6">
            {/* ── KPI Kartları ── */}
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

            {/* ── Sorgu Trafiği + Sistem Durumu ── */}
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
                                        <div className="bg-primary-500 h-1.5 rounded-full transition-all" style={{ width: `${cpuPct ?? 0}%` }} />
                                    </div>
                                </div>
                                <div>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-dark-300">Memory</span>
                                        <span className="text-white">{memPct != null ? `${memPct}%` : '-'}</span>
                                    </div>
                                    <div className="w-full bg-dark-800 rounded-full h-1.5">
                                        <div className="bg-yellow-500 h-1.5 rounded-full transition-all" style={{ width: `${memPct ?? 0}%` }} />
                                    </div>
                                </div>
                                <div>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-dark-300">Disk</span>
                                        <span className="text-white">{diskPct != null ? `${diskPct}%` : '-'}</span>
                                    </div>
                                    <div className="w-full bg-dark-800 rounded-full h-1.5">
                                        <div className="bg-orange-500 h-1.5 rounded-full transition-all" style={{ width: `${diskPct ?? 0}%` }} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* ── AI Modül Durumu Grid (v3.3.0) ── */}
            <div className="card">
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <Cpu className="w-5 h-5 text-primary-500" />
                        <h3 className="text-lg font-medium text-white">AI Modülleri</h3>
                    </div>
                    <span className="px-3 py-1 text-sm font-medium bg-primary-500/10 text-primary-400 rounded-full">
                        {activeModuleCount}/{totalModuleCount} Aktif
                    </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                    {Object.entries(modules).map(([key, active]) => (
                        <div
                            key={key}
                            className={clsx(
                                'flex items-center gap-2 px-3 py-2.5 rounded-lg border transition-all',
                                active
                                    ? 'border-green-500/30 bg-green-500/5'
                                    : 'border-dark-700 bg-dark-800/50 opacity-60'
                            )}
                        >
                            {active ? (
                                <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                            ) : (
                                <XCircle className="w-4 h-4 text-dark-500 flex-shrink-0" />
                            )}
                            <span className="text-xs font-medium text-dark-200 truncate" title={MODULE_LABELS[key] || key}>
                                {MODULE_LABELS[key] || key}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {/* ── Governance + Departman Dağılımı (v3.3.0) ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Governance Paneli */}
                <div className="card">
                    <div className="flex items-center gap-3 mb-6">
                        <Shield className="w-5 h-5 text-purple-500" />
                        <h3 className="text-lg font-medium text-white">AI Governance</h3>
                    </div>
                    {govAvailable ? (
                        <div className="space-y-5">
                            <div className="grid grid-cols-3 gap-4">
                                <div className="text-center p-3 bg-dark-800/50 rounded-lg">
                                    <p className="text-2xl font-bold text-white">{governance?.total_queries_monitored || 0}</p>
                                    <p className="text-xs text-dark-400 mt-1">İzlenen Sorgu</p>
                                </div>
                                <div className="text-center p-3 bg-dark-800/50 rounded-lg">
                                    <p className={clsx('text-2xl font-bold', avgConf >= 0.7 ? 'text-green-400' : avgConf >= 0.4 ? 'text-yellow-400' : 'text-red-400')}>
                                        {(avgConf * 100).toFixed(0)}%
                                    </p>
                                    <p className="text-xs text-dark-400 mt-1">Ort. Güven</p>
                                </div>
                                <div className="text-center p-3 bg-dark-800/50 rounded-lg">
                                    <p className={clsx('text-2xl font-bold', biasAlerts === 0 ? 'text-green-400' : 'text-red-400')}>
                                        {biasAlerts}
                                    </p>
                                    <p className="text-xs text-dark-400 mt-1">Bias Uyarısı</p>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-dark-700">
                                {driftDetected ? (
                                    <>
                                        <AlertTriangle className="w-4 h-4 text-yellow-500" />
                                        <span className="text-sm text-yellow-400">Drift Tespit Edildi — Model performansı değişkenlik gösteriyor</span>
                                    </>
                                ) : (
                                    <>
                                        <CheckCircle2 className="w-4 h-4 text-green-500" />
                                        <span className="text-sm text-green-400">Model stabil — drift tespit edilmedi</span>
                                    </>
                                )}
                            </div>

                            {governance?.recent_alerts?.length > 0 && (
                                <div>
                                    <h4 className="text-xs font-semibold text-dark-400 uppercase mb-2">Son Uyarılar</h4>
                                    <div className="space-y-1 max-h-32 overflow-y-auto">
                                        {governance.recent_alerts.slice(0, 5).map((alert: any, i: number) => (
                                            <div key={i} className="flex items-center gap-2 text-xs text-dark-300 px-2 py-1.5 bg-dark-800/30 rounded">
                                                <AlertTriangle className="w-3 h-3 text-yellow-500 flex-shrink-0" />
                                                <span className="truncate">{alert.message || alert.type || JSON.stringify(alert)}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-8 text-dark-400">
                            <Shield className="w-10 h-10 mb-3 opacity-30" />
                            <p className="text-sm">Governance verisi yükleniyor...</p>
                        </div>
                    )}
                </div>

                {/* Departman Sorgu Dağılımı */}
                <div className="card">
                    <div className="flex items-center gap-3 mb-6">
                        <BarChart3 className="w-5 h-5 text-cyan-500" />
                        <h3 className="text-lg font-medium text-white">Departman Dağılımı</h3>
                    </div>
                    {deptPieData.length > 0 ? (
                        <div className="flex items-center gap-4">
                            <div className="w-1/2 h-56">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={deptPieData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={40}
                                            outerRadius={75}
                                            dataKey="value"
                                            stroke="none"
                                        >
                                            {deptPieData.map((entry: any, index: number) => (
                                                <Cell key={index} fill={entry.fill} />
                                            ))}
                                        </Pie>
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: '#0f172a',
                                                border: '1px solid #1e293b',
                                                borderRadius: '8px',
                                            }}
                                            itemStyle={{ color: '#e2e8f0' }}
                                            formatter={(value: number, name: string) => [`${value} sorgu`, name]}
                                        />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                            <div className="w-1/2 space-y-2 max-h-56 overflow-y-auto">
                                {(deptStats || []).map((d: any, i: number) => (
                                    <div key={i} className="flex items-center justify-between text-sm">
                                        <div className="flex items-center gap-2">
                                            <div
                                                className="w-3 h-3 rounded-full flex-shrink-0"
                                                style={{ backgroundColor: DEPT_COLORS[i % DEPT_COLORS.length] }}
                                            />
                                            <span className="text-dark-200 truncate max-w-[100px]">{d.department}</span>
                                        </div>
                                        <div className="text-right">
                                            <span className="text-white font-medium">{d.count}</span>
                                            <span className="text-dark-500 text-xs ml-1">({Math.round(d.avg_time_ms)}ms)</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-8 text-dark-400">
                            <BarChart3 className="w-10 h-10 mb-3 opacity-30" />
                            <p className="text-sm">Henüz sorgu verisi yok</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
