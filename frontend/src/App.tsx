import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Queries from './pages/Queries'
import Ask from './pages/Ask'
import Settings from './pages/Settings'
import Documents from './pages/Documents'
import Users from './pages/Users'

// Protected Route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, isLoading } = useAuth()

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary-500"></div>
            </div>
        )
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />
    }

    return <>{children}</>
}

function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <Routes>
                    <Route path="/login" element={<Login />} />
                    <Route
                        path="/"
                        element={
                            <ProtectedRoute>
                                <Layout />
                            </ProtectedRoute>
                        }
                    >
                        <Route index element={<Dashboard />} />
                        <Route path="queries" element={<Queries />} />
                        <Route path="ask" element={<Ask />} />
                        <Route path="documents" element={<Documents />} />
                        <Route path="users" element={<Users />} />
                        <Route path="settings" element={<Settings />} />
                    </Route>
                </Routes>
            </AuthProvider>
        </BrowserRouter>
    )
}

export default App
