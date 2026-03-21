import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  CheckCircle, XCircle, AlertTriangle, HelpCircle,
  TrendingUp, Zap, History, ArrowRight, Brain,
  BarChart3, Shield, Clock
} from 'lucide-react'
import { historyAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'
import { RadialBarChart, RadialBar, ResponsiveContainer, Tooltip } from 'recharts'

function StatCard({ icon: Icon, label, value, color, subtext }) {
  return (
    <motion.div whileHover={{ y: -2 }} className="glass-card p-6">
      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center mb-4`}>
        <Icon size={20} className="text-white" />
      </div>
      <div className="font-display font-black text-3xl text-white mb-1">{value}</div>
      <div className="text-slate-400 text-sm">{label}</div>
      {subtext && <div className="text-slate-500 text-xs mt-1">{subtext}</div>}
    </motion.div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [recentReports, setRecentReports] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, histRes] = await Promise.all([
          historyAPI.getStats(),
          historyAPI.getHistory({ limit: 5 })
        ])
        setStats(statsRes.data)
        setRecentReports(histRes.data.reports)
      } catch (e) {
        // Silently fail
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const accuracyData = stats ? [
    { name: 'Accuracy', value: Math.round((stats.avg_accuracy || 0) * 100), fill: '#6366f1' }
  ] : []

  const statusColor = (acc) => {
    if (acc >= 0.7) return 'text-emerald-400'
    if (acc >= 0.4) return 'text-amber-400'
    return 'text-red-400'
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <h1 className="font-display font-black text-3xl text-white mb-1">
            Welcome back, <span className="gradient-text">{user?.name?.split(' ')[0]}</span> 👋
          </h1>
          <p className="text-slate-400">Ready to verify some facts?</p>
        </motion.div>
      </div>

      {/* Quick Action */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="gradient-border p-6 mb-8"
      >
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-display font-bold text-xl text-white mb-1">Start a New Verification</h2>
            <p className="text-slate-400 text-sm">Paste text or a URL to fact-check with AI</p>
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => navigate('/verify')}
            className="btn-primary px-6 py-3"
          >
            <Zap size={16} /> Verify Now <ArrowRight size={16} />
          </motion.button>
        </div>
      </motion.div>

      {/* Stats Grid */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="glass-card p-6 h-36 shimmer" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard icon={Shield} label="Total Reports" value={stats?.total_reports || 0} color="from-primary-500 to-violet-600" />
          <StatCard icon={CheckCircle} label="Claims Verified" value={stats?.total_claims || 0} color="from-emerald-500 to-teal-600" />
          <StatCard icon={Brain} label="Hallucinations Found" value={stats?.total_hallucinations || 0} color="from-purple-500 to-indigo-600" />
          <StatCard icon={TrendingUp} label="Avg Accuracy" value={`${Math.round((stats?.avg_accuracy || 0) * 100)}%`} color="from-amber-500 to-orange-600" />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Reports */}
        <div className="lg:col-span-2 glass-card p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-display font-bold text-lg text-white flex items-center gap-2">
              <History size={18} className="text-primary-400" /> Recent Reports
            </h2>
            <button onClick={() => navigate('/history')} className="text-primary-400 text-sm hover:text-primary-300 flex items-center gap-1">
              View all <ArrowRight size={14} />
            </button>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => <div key={i} className="h-16 rounded-xl shimmer" />)}
            </div>
          ) : recentReports.length === 0 ? (
            <div className="text-center py-12">
              <BarChart3 className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">No reports yet</p>
              <button onClick={() => navigate('/verify')} className="text-primary-400 text-sm mt-2 hover:underline">
                Create your first verification →
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {recentReports.map((report, i) => (
                <motion.div
                  key={report.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                  onClick={() => navigate(`/report/${report.id}`)}
                  className="flex items-center justify-between p-4 bg-white/3 rounded-xl hover:bg-white/6 cursor-pointer transition-all border border-white/5 hover:border-white/10"
                >
                  <div className="flex-1 min-w-0 mr-4">
                    <p className="text-slate-300 text-sm truncate">{report.preview}</p>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-slate-500 text-xs flex items-center gap-1">
                        <Clock size={10} /> {new Date(report.created_at).toLocaleDateString()}
                      </span>
                      <span className="text-slate-500 text-xs">{report.total_claims} claims</span>
                      <span className={`text-xs font-bold ${statusColor(report.overall_accuracy)}`}>
                        {Math.round(report.overall_accuracy * 100)}% accurate
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <div className="flex gap-1">
                      {report.true_count > 0 && (
                        <span className="badge-true">{report.true_count}</span>
                      )}
                      {report.false_count > 0 && (
                        <span className="badge-false">{report.false_count}</span>
                      )}
                    </div>
                    <ArrowRight size={14} className="text-slate-600" />
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Accuracy Chart */}
        <div className="glass-card p-6">
          <h2 className="font-display font-bold text-lg text-white mb-4 flex items-center gap-2">
            <TrendingUp size={18} className="text-primary-400" /> Overall Health
          </h2>
          
          {!loading && stats?.avg_accuracy !== undefined ? (
            <>
              <div className="h-48 relative">
                <ResponsiveContainer width="100%" height="100%">
                  <RadialBarChart cx="50%" cy="50%" innerRadius="60%" outerRadius="90%" data={accuracyData}>
                    <RadialBar dataKey="value" cornerRadius={10} background={{ fill: 'rgba(255,255,255,0.05)' }} />
                    <Tooltip
                      contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                      formatter={(val) => [`${val}%`, 'Avg Accuracy']}
                    />
                  </RadialBarChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <div className="font-display font-black text-3xl text-white">
                      {Math.round((stats?.avg_accuracy || 0) * 100)}%
                    </div>
                    <div className="text-slate-400 text-xs">avg accuracy</div>
                  </div>
                </div>
              </div>

              <div className="space-y-3 mt-4">
                {[
                  { label: 'True Claims', value: stats.total_true, color: 'bg-emerald-500', icon: CheckCircle },
                  { label: 'False Claims', value: stats.total_false, color: 'bg-red-500', icon: XCircle },
                  { label: 'Hallucinations', value: stats.total_hallucinations, color: 'bg-purple-500', icon: Brain },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${item.color}`} />
                    <span className="text-slate-400 text-sm flex-1">{item.label}</span>
                    <span className="text-white font-medium text-sm">{item.value || 0}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="text-center py-8">
              <TrendingUp className="w-12 h-12 text-slate-600 mx-auto mb-2" />
              <p className="text-slate-500 text-sm">Run your first verification to see analytics</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
