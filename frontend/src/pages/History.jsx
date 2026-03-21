import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  History as HistoryIcon, Search, Trash2, ArrowRight, 
  CheckCircle, XCircle, Brain, Clock, Calendar,
  FileText, Link, ChevronLeft, ChevronRight
} from 'lucide-react'
import { historyAPI } from '../services/api'
import toast from 'react-hot-toast'

export default function History() {
  const navigate = useNavigate()
  const [reports, setReports] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')
  const LIMIT = 10

  const fetchHistory = async (p = 0) => {
    setLoading(true)
    try {
      const res = await historyAPI.getHistory({ limit: LIMIT, skip: p * LIMIT })
      setReports(res.data.reports)
      setTotal(res.data.total)
    } catch {
      toast.error('Failed to load history')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchHistory(page) }, [page])

  const handleDelete = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this report?')) return
    try {
      await historyAPI.deleteReport(id)
      toast.success('Report deleted')
      fetchHistory(page)
    } catch {
      toast.error('Delete failed')
    }
  }

  const getAccuracyColor = (acc) => {
    if (acc >= 0.7) return 'text-emerald-400'
    if (acc >= 0.4) return 'text-amber-400'
    return 'text-red-400'
  }

  const getAccuracyBg = (acc) => {
    if (acc >= 0.7) return 'bg-emerald-500/10 border-emerald-500/20'
    if (acc >= 0.4) return 'bg-amber-500/10 border-amber-500/20'
    return 'bg-red-500/10 border-red-500/20'
  }

  const filtered = reports.filter(r => 
    r.preview?.toLowerCase().includes(search.toLowerCase()) ||
    r.source_url?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="font-display font-black text-3xl text-white mb-2 flex items-center gap-3">
          <HistoryIcon size={28} className="text-primary-400" />
          Verification <span className="gradient-text">History</span>
        </h1>
        <p className="text-slate-400">All your past fact-checking reports</p>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search reports..."
          className="input-primary pl-10"
        />
      </div>

      {/* Reports List */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-24 glass-card shimmer" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-card p-16 text-center">
          <HistoryIcon className="w-16 h-16 text-slate-600 mx-auto mb-4" />
          <h2 className="font-display font-bold text-xl text-white mb-2">No reports found</h2>
          <p className="text-slate-400 mb-6">Start your first verification to see results here</p>
          <button onClick={() => navigate('/verify')} className="btn-primary px-6 py-3">
            Start Verifying
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((report, i) => (
            <motion.div
              key={report.id}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => navigate(`/report/${report.id}`)}
              className="glass-card-hover p-5 cursor-pointer group"
            >
              <div className="flex items-center gap-4">
                {/* Type Icon */}
                <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center shrink-0">
                  {report.input_type === 'url' ? 
                    <Link size={18} className="text-primary-400" /> : 
                    <FileText size={18} className="text-primary-400" />
                  }
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <p className="text-slate-200 text-sm font-medium truncate mb-1">
                    {report.source_url || report.preview}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <Calendar size={10} /> {new Date(report.created_at).toLocaleDateString()}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock size={10} /> {new Date(report.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    <span>{report.total_claims} claims</span>
                    {report.hallucination_count > 0 && (
                      <span className="flex items-center gap-1 text-purple-400">
                        <Brain size={10} /> {report.hallucination_count} hallucination{report.hallucination_count > 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                </div>

                {/* Accuracy Badge */}
                <div className={`px-3 py-1.5 rounded-xl border text-center shrink-0 ${getAccuracyBg(report.overall_accuracy)}`}>
                  <div className={`font-display font-black text-lg leading-none ${getAccuracyColor(report.overall_accuracy)}`}>
                    {Math.round(report.overall_accuracy * 100)}%
                  </div>
                  <div className="text-slate-500 text-xs">accurate</div>
                </div>

                {/* Right Side */}
                <div className="flex items-center gap-2 shrink-0">
                  <div className="flex items-center gap-1.5">
                    {report.true_count > 0 && (
                      <div className="flex items-center gap-0.5 text-emerald-400 text-xs font-bold">
                        <CheckCircle size={12} /> {report.true_count}
                      </div>
                    )}
                    {report.false_count > 0 && (
                      <div className="flex items-center gap-0.5 text-red-400 text-xs font-bold">
                        <XCircle size={12} /> {report.false_count}
                      </div>
                    )}
                  </div>

                  <button
                    onClick={(e) => handleDelete(report.id, e)}
                    className="p-2 text-slate-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <Trash2 size={14} />
                  </button>

                  <ArrowRight size={14} className="text-slate-600 group-hover:text-primary-400 transition-colors" />
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex items-center justify-between mt-6 pt-6 border-t border-white/5">
          <p className="text-slate-400 text-sm">
            Showing {page * LIMIT + 1}–{Math.min((page + 1) * LIMIT, total)} of {total} reports
          </p>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage(p => p - 1)}
              className="btn-secondary px-3 py-2 disabled:opacity-30"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              disabled={(page + 1) * LIMIT >= total}
              onClick={() => setPage(p => p + 1)}
              className="btn-secondary px-3 py-2 disabled:opacity-30"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
