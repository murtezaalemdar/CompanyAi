import { useQuery } from '@tanstack/react-query'
import { adminApi } from '../services/api'
import { AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import clsx from 'clsx'

export default function Queries() {
    const { data: queries, isLoading } = useQuery({
        queryKey: ['recent-queries'],
        queryFn: () => adminApi.getRecentQueries(50),
    })

    if (isLoading) {
        return (
            <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary-500"></div>
            </div>
        )
    }

    return (
        <div className="card overflow-hidden">
            <div className="overflow-x-auto">
                <table className="w-full text-left">
                    <thead className="bg-dark-800/50 text-dark-400 text-xs uppercase font-medium">
                        <tr>
                            <th className="px-3 py-3 sm:px-6 sm:py-4 rounded-tl-lg">Soru</th>
                            <th className="px-3 py-3 sm:px-6 sm:py-4 hidden sm:table-cell">Departman</th>
                            <th className="px-3 py-3 sm:px-6 sm:py-4">Risk</th>
                            <th className="px-3 py-3 sm:px-6 sm:py-4 hidden md:table-cell">Güven</th>
                            <th className="px-3 py-3 sm:px-6 sm:py-4 rounded-tr-lg">Tarih</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-800">
                        {queries?.map((query: any) => (
                            <tr key={query.id} className="hover:bg-dark-800/30 transition-colors">
                                <td className="px-3 py-3 sm:px-6 sm:py-4 max-w-[200px] sm:max-w-md">
                                    <p className="text-white text-sm font-medium truncate" title={query.question}>
                                        {query.question}
                                    </p>
                                </td>
                                <td className="px-3 py-3 sm:px-6 sm:py-4 hidden sm:table-cell">
                                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-500/10 text-primary-400 border border-primary-500/20">
                                        {query.department || 'Genel'}
                                    </span>
                                </td>
                                <td className="px-3 py-3 sm:px-6 sm:py-4">
                                    <div className="flex items-center gap-2">
                                        {query.risk_level === 'Yüksek' ? (
                                            <AlertTriangle className="w-4 h-4 text-red-500" />
                                        ) : query.risk_level === 'Orta' ? (
                                            <Clock className="w-4 h-4 text-yellow-500" />
                                        ) : (
                                            <CheckCircle className="w-4 h-4 text-green-500" />
                                        )}
                                        <span
                                            className={clsx(
                                                'text-sm',
                                                query.risk_level === 'Yüksek'
                                                    ? 'text-red-400'
                                                    : query.risk_level === 'Orta'
                                                        ? 'text-yellow-400'
                                                        : 'text-green-400'
                                            )}
                                        >
                                            {query.risk_level}
                                        </span>
                                    </div>
                                </td>
                                <td className="px-3 py-3 sm:px-6 sm:py-4 hidden md:table-cell">
                                    <div className="w-24 bg-dark-700 rounded-full h-1.5">
                                        <div
                                            className="bg-blue-500 h-1.5 rounded-full"
                                            style={{ width: `${query.confidence * 100}%` }}
                                        />
                                    </div>
                                    <span className="text-xs text-dark-400 mt-1 block">
                                        %{Math.round(query.confidence * 100)}
                                    </span>
                                </td>
                                <td className="px-3 py-3 sm:px-6 sm:py-4 text-sm text-dark-400 whitespace-nowrap">
                                    {new Date(query.created_at).toLocaleDateString('tr-TR', {
                                        hour: '2-digit',
                                        minute: '2-digit',
                                    })}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
