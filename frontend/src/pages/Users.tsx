
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '../services/api'
import { DEPARTMENTS } from '../constants'
import {
    Users,
    Shield,
    UserCog,
    Search,
    MoreVertical,
    CheckCircle,
    XCircle,
    Loader2,
    Crown,
    User as UserIcon,
    Plus,
    X,
    Building2,
    Lock,
    Trash2
} from 'lucide-react'
import clsx from 'clsx'

const roles = [
    { id: 'user', label: 'Kullanıcı' },
    { id: 'manager', label: 'Yönetici' },
    { id: 'admin', label: 'Admin' },
]

interface User {
    id: number
    email: string
    full_name: string | null
    department: string | null
    role: string
    is_active: boolean
    created_at: string
}

export default function UserManagement() {
    const queryClient = useQueryClient()
    const [searchTerm, setSearchTerm] = useState('')
    const [isModalOpen, setIsModalOpen] = useState(false)
    const [modalMode, setModalMode] = useState<'create' | 'edit'>('create')
    const [selectedUser, setSelectedUser] = useState<User | null>(null)

    // Form State
    const [formData, setFormData] = useState({
        email: '',
        full_name: '',
        departments: [] as string[],
        role: 'user',
        password: '',
        is_active: true
    })

    // Kullanıcı listesi
    const { data: users, isLoading } = useQuery({
        queryKey: ['admin-users'],
        queryFn: adminApi.getUsers,
    })

    // Mutations
    const createMutation = useMutation({
        mutationFn: (data: any) => adminApi.createUser({
            ...data,
            department: JSON.stringify(data.departments)
        }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['admin-users'] })
            closeModal()
        }
    })

    const updateMutation = useMutation({
        mutationFn: ({ id, data }: { id: number; data: any }) => adminApi.updateUser(id, {
            ...data,
            department: JSON.stringify(data.departments)
        }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['admin-users'] })
            closeModal()
        }
    })

    const deleteMutation = useMutation({
        mutationFn: adminApi.deleteUser,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['admin-users'] })
            closeModal()
        }
    })

    // Helpers
    const parseDepartments = (deptString: string | null): string[] => {
        if (!deptString) return []
        try {
            const parsed = JSON.parse(deptString)
            return Array.isArray(parsed) ? parsed : [deptString]
        } catch {
            return [deptString]
        }
    }

    const openCreateModal = () => {
        setModalMode('create')
        setFormData({
            email: '',
            full_name: '',
            departments: [],
            role: 'user',
            password: '',
            is_active: true
        })
        setIsModalOpen(true)
    }

    const openEditModal = (user: User) => {
        setModalMode('edit')
        setSelectedUser(user)
        setFormData({
            email: user.email,
            full_name: user.full_name || '',
            departments: parseDepartments(user.department),
            role: user.role,
            password: '', // Password is empty on edit unless changing
            is_active: user.is_active
        })
        setIsModalOpen(true)
    }

    const closeModal = () => {
        setIsModalOpen(false)
        setSelectedUser(null)
    }

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()

        if (modalMode === 'create') {
            createMutation.mutate(formData)
        } else {
            // Only include password if it's set
            const updateData: any = { ...formData }
            if (!updateData.password) delete updateData.password
            delete updateData.email // Email cannot be changed usually

            if (selectedUser) {
                updateMutation.mutate({ id: selectedUser.id, data: updateData })
            }
        }
    }

    const handleDelete = () => {
        if (selectedUser && confirm('Bu kullanıcıyı silmek istediğinize emin misiniz?')) {
            deleteMutation.mutate(selectedUser.id)
        }
    }

    // Toggle department selection
    const toggleDepartment = (dept: string) => {
        setFormData(prev => {
            if (prev.departments.includes(dept)) {
                return { ...prev, departments: prev.departments.filter(d => d !== dept) }
            } else {
                return { ...prev, departments: [...prev.departments, dept] }
            }
        })
    }

    // Filtreleme
    const filteredUsers = users?.filter((user: User) =>
        user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
        user.full_name?.toLowerCase().includes(searchTerm.toLowerCase())
    ) || []

    const roleInfo = (role: string) => {
        switch (role) {
            case 'admin': return { label: 'Admin', color: 'text-red-400 bg-red-500/10', icon: Crown }
            case 'manager': return { label: 'Yönetici', color: 'text-yellow-400 bg-yellow-500/10', icon: Shield }
            default: return { label: 'Kullanıcı', color: 'text-blue-400 bg-blue-500/10', icon: UserIcon }
        }
    }

    if (isLoading) return <div className="flex justify-center p-12"><Loader2 className="animate-spin" /></div>

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-white">Kullanıcı Yönetimi</h1>
                    <p className="text-dark-400 mt-1">Sistem kullanıcılarını ve yetkilerini yönetin</p>
                </div>

                <div className="flex items-center gap-3">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                        <input
                            type="text"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            placeholder="Kullanıcı ara..."
                            className="input pl-10 w-full sm:w-64"
                        />
                    </div>
                    <button onClick={openCreateModal} className="btn-primary flex items-center gap-2">
                        <Plus className="w-4 h-4" />
                        Yeni Kullanıcı
                    </button>
                </div>
            </div>

            {/* Kullanıcı Listesi */}
            <div className="card overflow-hidden">
                <div className="overflow-x-auto">
                <table className="w-full">
                    <thead>
                        <tr className="border-b border-dark-700">
                            <th className="text-left py-3 px-3 sm:py-4 sm:px-4 text-xs font-medium text-dark-400 uppercase">Kullanıcı</th>
                            <th className="text-left py-3 px-3 sm:py-4 sm:px-4 text-xs font-medium text-dark-400 uppercase hidden md:table-cell">Departmanlar</th>
                            <th className="text-left py-3 px-3 sm:py-4 sm:px-4 text-xs font-medium text-dark-400 uppercase">Rol</th>
                            <th className="text-left py-3 px-3 sm:py-4 sm:px-4 text-xs font-medium text-dark-400 uppercase hidden sm:table-cell">Durum</th>
                            <th className="text-right py-3 px-3 sm:py-4 sm:px-4 text-xs font-medium text-dark-400 uppercase">İşlem</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-800">
                        {filteredUsers.map((user: User) => {
                            const role = roleInfo(user.role)
                            const RoleIcon = role.icon
                            const userDepts = parseDepartments(user.department)
                            return (
                                <tr key={user.id} className="hover:bg-dark-800/50 transition-colors">
                                    <td className="py-3 px-3 sm:py-4 sm:px-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-primary-500/20 flex items-center justify-center text-primary-400 font-bold text-sm">
                                                {user.full_name?.charAt(0) || user.email.charAt(0).toUpperCase()}
                                            </div>
                                            <div className="min-w-0">
                                                <p className="text-sm font-medium text-white truncate">{user.full_name || 'İsimsiz'}</p>
                                                <p className="text-xs text-dark-400 truncate">{user.email}</p>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="py-3 px-3 sm:py-4 sm:px-4 hidden md:table-cell">
                                        <div className="flex flex-wrap gap-1 text-dark-300">
                                            {userDepts.length > 0 ? (
                                                userDepts.map((d, i) => (
                                                    <span key={i} className="px-2 py-0.5 rounded text-xs bg-dark-700 border border-dark-600">
                                                        {d}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-dark-500">-</span>
                                            )}
                                        </div>
                                    </td>
                                    <td className="py-3 px-3 sm:py-4 sm:px-4">
                                        <span className={clsx('inline-flex items-center gap-1.5 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full text-xs font-medium', role.color)}>
                                            <RoleIcon className="w-3 h-3" />
                                            {role.label}
                                        </span>
                                    </td>
                                    <td className="py-3 px-3 sm:py-4 sm:px-4 hidden sm:table-cell">
                                        {user.is_active ? (
                                            <span className="text-green-400 text-sm flex items-center gap-1"><CheckCircle className="w-4 h-4" /> Aktif</span>
                                        ) : (
                                            <span className="text-red-400 text-sm flex items-center gap-1"><XCircle className="w-4 h-4" /> Pasif</span>
                                        )}
                                    </td>
                                    <td className="py-3 px-3 sm:py-4 sm:px-4 text-right">
                                        <button
                                            onClick={() => openEditModal(user)}
                                            className="p-2 hover:bg-dark-700 rounded-lg text-dark-400 hover:text-white"
                                        >
                                            <UserCog className="w-4 h-4" />
                                        </button>
                                    </td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
                </div>
            </div>

            {/* Modal */}
            {isModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm overflow-y-auto">
                    <div className="card w-full max-w-lg relative animate-in fade-in zoom-in duration-200 mt-10 mb-10">
                        <button onClick={closeModal} className="absolute top-4 right-4 text-dark-400 hover:text-white">
                            <X className="w-5 h-5" />
                        </button>

                        <h2 className="text-xl font-bold text-white mb-6">
                            {modalMode === 'create' ? 'Yeni Kullanıcı Ekle' : 'Kullanıcı Düzenle'}
                        </h2>

                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="block text-xs font-medium text-dark-400 mb-1.5">Email Adresi</label>
                                <input
                                    type="email"
                                    required
                                    disabled={modalMode === 'edit'}
                                    value={formData.email}
                                    onChange={e => setFormData({ ...formData, email: e.target.value })}
                                    className="input w-full disabled:opacity-50"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-dark-400 mb-1.5">Ad Soyad</label>
                                <input
                                    type="text"
                                    value={formData.full_name}
                                    onChange={e => setFormData({ ...formData, full_name: e.target.value })}
                                    className="input w-full"
                                />
                            </div>

                            {/* Departman Seçimi (Checkbox List) */}
                            <div>
                                <label className="block text-xs font-medium text-dark-400 mb-2">Departmanlar</label>
                                <div className="h-48 overflow-y-auto border border-dark-700 rounded-lg p-3 bg-dark-900/50 space-y-2">
                                    {DEPARTMENTS.map(dept => (
                                        <label key={dept} className="flex items-center gap-2 cursor-pointer group">
                                            <input
                                                type="checkbox"
                                                checked={formData.departments.includes(dept)}
                                                onChange={() => toggleDepartment(dept)}
                                                className="w-4 h-4 rounded border-dark-600 bg-dark-800 text-primary-500 focus:ring-primary-500"
                                            />
                                            <span className={clsx(
                                                "text-sm transition-colors",
                                                formData.departments.includes(dept) ? "text-white" : "text-dark-400 group-hover:text-dark-300"
                                            )}>
                                                {dept}
                                            </span>
                                        </label>
                                    ))}
                                </div>
                                <p className="text-xs text-dark-500 mt-1">Birden fazla departman seçebilirsiniz.</p>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-medium text-dark-400 mb-1.5">Rol</label>
                                    <select
                                        value={formData.role}
                                        onChange={e => setFormData({ ...formData, role: e.target.value })}
                                        className="input w-full"
                                    >
                                        {roles.map(r => (
                                            <option key={r.id} value={r.id}>{r.label}</option>
                                        ))}
                                    </select>
                                </div>
                                <div className="flex items-end mb-2">
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={formData.is_active}
                                            onChange={e => setFormData({ ...formData, is_active: e.target.checked })}
                                            className="w-4 h-4 rounded border-dark-600 bg-dark-800 text-primary-500 focus:ring-primary-500"
                                        />
                                        <span className="text-sm text-white">Hesap Aktif</span>
                                    </label>
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-dark-400 mb-1.5">
                                    {modalMode === 'create' ? 'Şifre' : 'Yeni Şifre (Opsiyonel)'}
                                </label>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                                    <input
                                        type="password"
                                        required={modalMode === 'create'}
                                        minLength={6}
                                        value={formData.password}
                                        onChange={e => setFormData({ ...formData, password: e.target.value })}
                                        className="input pl-10 w-full"
                                        placeholder={modalMode === 'edit' ? 'Değiştirmek için giriniz' : ''}
                                    />
                                </div>
                            </div>

                            <div className="flex justify-between pt-4">
                                {modalMode === 'edit' && (
                                    <button
                                        type="button"
                                        onClick={handleDelete}
                                        className="btn bg-red-500/10 text-red-400 hover:bg-red-500/20"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                )}
                                <div className="flex gap-3 ml-auto">
                                    <button type="button" onClick={closeModal} className="btn-ghost">İptal</button>
                                    <button
                                        type="submit"
                                        disabled={createMutation.isPending || updateMutation.isPending}
                                        className="btn-primary"
                                    >
                                        {(createMutation.isPending || updateMutation.isPending) && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                                        {modalMode === 'create' ? 'Kullanıcı Oluştur' : 'Değişiklikleri Kaydet'}
                                    </button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    )
}
