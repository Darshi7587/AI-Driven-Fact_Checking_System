import { useNavigate, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  Shield, LayoutDashboard, Search, History, 
  LogOut, ChevronRight, Zap, X, Menu
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useState } from 'react'
import toast from 'react-hot-toast'

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/dashboard' },
  { icon: Search, label: 'Verify Content', path: '/verify' },
  { icon: History, label: 'History', path: '/history' },
]

function Sidebar({ mobile = false, onClose }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()

  const handleLogout = () => {
    logout()
    toast.success('Logged out')
    navigate('/')
  }

  return (
    <div className={`flex flex-col h-full ${mobile ? 'p-4' : 'p-4'}`}>
      {/* Logo */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-violet-600 flex items-center justify-center">
            <Shield size={18} className="text-white" />
          </div>
          <span className="font-display font-bold text-lg text-white">VeritAI</span>
        </div>
        {mobile && (
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X size={20} />
          </button>
        )}
      </div>

      {/* New Verify Button */}
      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={() => { navigate('/verify'); onClose?.() }}
        className="btn-primary w-full mb-6 py-3"
      >
        <Zap size={16} /> New Verification
      </motion.button>

      {/* Nav Items */}
      <nav className="flex-1 space-y-1">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.path}
            onClick={() => { navigate(item.path); onClose?.() }}
            className={`sidebar-item w-full text-left ${location.pathname === item.path ? 'active' : ''}`}
          >
            <item.icon size={18} />
            <span className="flex-1">{item.label}</span>
            {location.pathname === item.path && <ChevronRight size={14} className="text-primary-400" />}
          </button>
        ))}
      </nav>

      {/* User Profile */}
      <div className="border-t border-white/5 pt-4 mt-4">
        <div className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition-colors">
          <img
            src={user?.avatar || `https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.name}`}
            alt="avatar"
            className="w-9 h-9 rounded-xl bg-slate-700"
          />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-white truncate">{user?.name}</div>
            <div className="text-xs text-slate-400 truncate">{user?.email}</div>
          </div>
          <button
            onClick={handleLogout}
            className="text-slate-500 hover:text-red-400 transition-colors"
            title="Logout"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

export default function DashboardLayout({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen bg-mesh flex">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex flex-col w-64 h-screen sticky top-0 glass-card rounded-none border-r border-white/5">
        <Sidebar />
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <motion.aside
            initial={{ x: -300 }}
            animate={{ x: 0 }}
            exit={{ x: -300 }}
            className="absolute left-0 top-0 bottom-0 w-72 glass-card rounded-none"
          >
            <Sidebar mobile onClose={() => setMobileOpen(false)} />
          </motion.aside>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-h-screen">
        {/* Mobile Top Bar */}
        <div className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-white/5">
          <button onClick={() => setMobileOpen(true)} className="text-slate-400 hover:text-white">
            <Menu size={22} />
          </button>
          <div className="flex items-center gap-2">
            <Shield size={18} className="text-primary-400" />
            <span className="font-display font-bold text-white">VeritAI</span>
          </div>
          <div className="w-8" />
        </div>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-4 lg:p-8">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  )
}
