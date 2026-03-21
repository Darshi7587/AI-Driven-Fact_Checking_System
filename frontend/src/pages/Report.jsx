import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  CheckCircle, XCircle, AlertTriangle, HelpCircle, 
  ExternalLink, Shield, Download, ArrowLeft, Clock,
  Brain, Zap, AlertOctagon, TrendingUp, Search,
  ChevronDown, ChevronUp, Globe, Star
} from 'lucide-react'
import { verifyAPI } from '../services/api'
import { 
  RadialBarChart, RadialBar, ResponsiveContainer,
  PieChart, Pie, Cell, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis
} from 'recharts'
import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'
import toast from 'react-hot-toast'

const STATUS_CONFIG = {
  TRUE: { label: 'True', color: '#10b981', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', badge: 'badge-true', icon: CheckCircle },
  FALSE: { label: 'False', color: '#ef4444', bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', badge: 'badge-false', icon: XCircle },
  PARTIALLY_TRUE: { label: 'Partially True', color: '#f59e0b', bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', badge: 'badge-partial', icon: AlertTriangle },
  UNVERIFIABLE: { label: 'Unverifiable', color: '#64748b', bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', badge: 'badge-unverifiable', icon: HelpCircle },
  CONFLICTING: { label: 'Conflicting', color: '#a855f7', bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', badge: 'badge-conflicting', icon: AlertOctagon }
}

function ClaimCard({ claim, index }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = STATUS_CONFIG[claim.status] || STATUS_CONFIG.UNVERIFIABLE
  const Icon = cfg.icon

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08 }}
      className={`glass-card border ${cfg.border} overflow-hidden`}
    >
      {/* Claim Header */}
      <div 
        className="p-5 cursor-pointer hover:bg-white/3 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 flex-1">
            <div className={`w-8 h-8 rounded-xl ${cfg.bg} flex items-center justify-center shrink-0 mt-0.5`}>
              <Icon size={16} className={cfg.text} />
            </div>
            <div className="flex-1">
              <p className="text-slate-200 text-sm leading-relaxed font-medium">{claim.text}</p>
              
              <div className="flex flex-wrap items-center gap-2 mt-3">
                <span className={cfg.badge}><Icon size={10} /> {cfg.label}</span>
                
                <div className="flex items-center gap-1 text-xs text-slate-500">
                  <TrendingUp size={10} />
                  Confidence: <span className={`font-bold ${cfg.text}`}>{Math.round(claim.confidence * 100)}%</span>
                </div>
                
                {claim.is_hallucination && (
                  <span className="px-2 py-0.5 bg-purple-500/15 text-purple-400 border border-purple-500/30 rounded-full text-xs font-bold flex items-center gap-1">
                    <Brain size={10} /> Hallucination
                  </span>
                )}
                {claim.is_temporal && (
                  <span className="px-2 py-0.5 bg-blue-500/15 text-blue-400 border border-blue-500/30 rounded-full text-xs flex items-center gap-1">
                    <Clock size={10} /> Temporal
                  </span>
                )}
                {claim.conflicting_evidence && (
                  <span className="px-2 py-0.5 bg-orange-500/15 text-orange-400 border border-orange-500/30 rounded-full text-xs flex items-center gap-1">
                    <AlertTriangle size={10} /> Conflicting
                  </span>
                )}
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2 shrink-0">
            {/* Confidence Ring */}
            <div className="relative w-12 h-12">
              <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
                <circle
                  cx="18" cy="18" r="15.9" fill="none"
                  stroke={cfg.color} strokeWidth="3" strokeLinecap="round"
                  strokeDasharray={`${claim.confidence * 100} 100`}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center text-xs font-bold text-white">
                {Math.round(claim.confidence * 100)}
              </div>
            </div>
            {expanded ? <ChevronUp size={16} className="text-slate-500" /> : <ChevronDown size={16} className="text-slate-500" />}
          </div>
        </div>
      </div>

      {/* Expanded Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 space-y-4 border-t border-white/5">
              {/* AI Reasoning */}
              <div>
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 mt-4 flex items-center gap-1">
                  <Brain size={12} className="text-primary-400" /> AI Reasoning (Chain of Thought)
                </h4>
                <div className={`p-4 ${cfg.bg} border ${cfg.border} rounded-xl`}>
                  <p className="text-slate-300 text-sm leading-relaxed">{claim.reasoning}</p>
                </div>
              </div>

              {/* Key Finding */}
              {claim.key_finding && (
                <div>
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <Zap size={12} className="text-amber-400" /> Key Finding
                  </h4>
                  <p className="text-amber-300/80 text-sm italic">{claim.key_finding}</p>
                </div>
              )}

              {/* Temporal Note */}
              {claim.temporal_note && (
                <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl flex items-start gap-2">
                  <Clock size={14} className="text-blue-400 shrink-0 mt-0.5" />
                  <p className="text-blue-300/80 text-xs">{claim.temporal_note}</p>
                </div>
              )}

              {/* Search Queries */}
              {claim.search_queries?.length > 0 && (
                <div>
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <Search size={12} /> Search Queries Used
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {claim.search_queries.map((q, i) => (
                      <span key={i} className="px-2 py-1 bg-white/5 text-slate-400 text-xs rounded-lg border border-white/5">
                        {q}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Sources */}
              {claim.sources?.length > 0 && (
                <div>
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1">
                    <Globe size={12} /> Evidence Sources ({claim.sources.length})
                  </h4>
                  <div className="space-y-2">
                    {claim.sources.map((src, i) => (
                      <div key={i} className="p-3 bg-white/3 rounded-xl border border-white/5 hover:border-white/10 transition-colors">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                                src.trust_score >= 0.85 ? 'bg-emerald-500/20 text-emerald-400' :
                                src.trust_score >= 0.65 ? 'bg-amber-500/20 text-amber-400' :
                                'bg-red-500/20 text-red-400'
                              }`}>
                                <Star size={8} className="inline mr-0.5" />
                                {Math.round(src.trust_score * 100)}% trust
                              </span>
                              <span className="text-slate-500 text-xs">{src.domain}</span>
                            </div>
                            <p className="text-slate-300 text-xs font-medium mb-1 truncate">{src.title}</p>
                            <p className="text-slate-500 text-xs line-clamp-2">{src.snippet}</p>
                          </div>
                          <a 
                            href={src.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-primary-400 hover:text-primary-300 shrink-0"
                          >
                            <ExternalLink size={14} />
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default function Report() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await verifyAPI.getReport(id)
        setReport(res.data)
      } catch {
        toast.error('Report not found')
        navigate('/history')
      } finally {
        setLoading(false)
      }
    }
    fetchReport()
  }, [id])

  const exportPDF = async () => {
    setExporting(true)
    try {
      const element = document.getElementById('report-content')
      const canvas = await html2canvas(element, { backgroundColor: '#080d1a', scale: 1.5 })
      const imgData = canvas.toDataURL('image/png')
      const pdf = new jsPDF('p', 'mm', 'a4')
      const pdfWidth = pdf.internal.pageSize.getWidth()
      const pdfHeight = (canvas.height * pdfWidth) / canvas.width
      
      pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight)
      pdf.save(`VeritAI-Report-${id.slice(0, 8)}.pdf`)
      toast.success('PDF exported!')
    } catch {
      toast.error('Export failed')
    }
    setExporting(false)
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-slate-400">Loading report...</span>
      </div>
    </div>
  )

  if (!report) return null

  const pieData = [
    { name: 'True', value: report.true_count, color: '#10b981' },
    { name: 'False', value: report.false_count, color: '#ef4444' },
    { name: 'Partial', value: report.partial_count, color: '#f59e0b' },
    { name: 'Unverifiable', value: report.unverifiable_count, color: '#64748b' },
    { name: 'Conflicting', value: report.conflicting_count, color: '#a855f7' },
  ].filter(d => d.value > 0)

  const accuracyPct = Math.round(report.overall_accuracy * 100)
  const accuracyGrade = accuracyPct >= 80 ? { label: 'Highly Accurate', color: 'text-emerald-400' } :
                        accuracyPct >= 60 ? { label: 'Mostly Accurate', color: 'text-amber-400' } :
                        accuracyPct >= 40 ? { label: 'Partially Accurate', color: 'text-orange-400' } :
                        { label: 'Low Accuracy', color: 'text-red-400' }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Top Bar */}
      <div className="flex items-center justify-between mb-6">
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm">
          <ArrowLeft size={16} /> Back
        </button>
        <div className="flex items-center gap-3">
          <span className="text-slate-500 text-xs">Report ID: {id.slice(0, 8)}...</span>
          <motion.button
            whileHover={{ scale: 1.03 }}
            onClick={exportPDF}
            disabled={exporting}
            className="btn-secondary px-4 py-2 text-sm"
          >
            <Download size={14} /> {exporting ? 'Exporting...' : 'Export PDF'}
          </motion.button>
        </div>
      </div>

      <div id="report-content">
        {/* Accuracy Overview */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-8 mb-6"
        >
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-center">
            {/* Radial Score */}
            <div className="flex flex-col items-center">
              <div className="relative w-36 h-36">
                <svg className="w-36 h-36 -rotate-90" viewBox="0 0 120 120">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="10" />
                  <circle
                    cx="60" cy="60" r="50" fill="none"
                    stroke={accuracyPct >= 70 ? '#10b981' : accuracyPct >= 40 ? '#f59e0b' : '#ef4444'}
                    strokeWidth="10" strokeLinecap="round"
                    strokeDasharray={`${accuracyPct * 3.14} 314`}
                    className="transition-all duration-1000"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="font-display font-black text-4xl text-white">{accuracyPct}%</span>
                  <span className="text-slate-400 text-xs">Accuracy</span>
                </div>
              </div>
              <div className={`mt-3 font-bold text-lg ${accuracyGrade.color}`}>{accuracyGrade.label}</div>
            </div>

            {/* Stats */}
            <div className="md:col-span-2 grid grid-cols-3 gap-4">
              {[
                { label: 'Total Claims', value: report.total_claims, icon: Shield, color: 'text-primary-400' },
                { label: 'True', value: report.true_count, icon: CheckCircle, color: 'text-emerald-400' },
                { label: 'False', value: report.false_count, icon: XCircle, color: 'text-red-400' },
                { label: 'Partial', value: report.partial_count, icon: AlertTriangle, color: 'text-amber-400' },
                { label: 'Hallucinations', value: report.hallucination_count, icon: Brain, color: 'text-purple-400' },
                { label: 'Proc. Time', value: `${report.processing_time}s`, icon: Clock, color: 'text-blue-400' },
              ].map((s, i) => (
                <div key={i} className="text-center p-3 bg-white/3 rounded-xl">
                  <s.icon size={18} className={`${s.color} mx-auto mb-1`} />
                  <div className="font-display font-black text-2xl text-white">{s.value}</div>
                  <div className="text-slate-500 text-xs">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Pie Chart */}
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-6"
          >
            <h3 className="font-display font-bold text-white mb-4 text-sm uppercase tracking-wide">Claims Breakdown</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({ name, percent }) => `${name} ${Math.round(percent * 100)}%`} labelLine={false}>
                  {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '12px' }}
                />
                <Legend iconType="circle" iconSize={8} formatter={(val) => <span className="text-slate-400 text-xs">{val}</span>} />
              </PieChart>
            </ResponsiveContainer>
          </motion.div>

          {/* Bar Chart */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-card p-6"
          >
            <h3 className="font-display font-bold text-white mb-4 text-sm uppercase tracking-wide">Confidence per Claim</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={report.claims.map((c, i) => ({ name: `C${i+1}`, confidence: Math.round(c.confidence * 100), status: c.status }))}>
                <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '12px' }}
                  formatter={(val) => [`${val}%`, 'Confidence']}
                />
                <Bar dataKey="confidence" radius={[4, 4, 0, 0]}>
                  {report.claims.map((c, i) => {
                    const colors = { TRUE: '#10b981', FALSE: '#ef4444', PARTIALLY_TRUE: '#f59e0b', UNVERIFIABLE: '#64748b', CONFLICTING: '#a855f7' }
                    return <Cell key={i} fill={colors[c.status] || '#6366f1'} />
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </motion.div>
        </div>

        {/* Input Text Preview */}
        {report.source_url && (
          <div className="glass-card p-4 mb-6 flex items-center gap-3">
            <Globe size={16} className="text-primary-400 shrink-0" />
            <span className="text-slate-400 text-sm">Source URL:</span>
            <a href={report.source_url} target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:underline text-sm truncate flex items-center gap-1">
              {report.source_url} <ExternalLink size={12} />
            </a>
          </div>
        )}

        {/* Claims List */}
        <div className="mb-6">
          <h2 className="font-display font-bold text-xl text-white mb-4 flex items-center gap-2">
            <Brain size={20} className="text-primary-400" />
            Verified Claims ({report.claims?.length || 0})
          </h2>
          <div className="space-y-3">
            {report.claims?.map((claim, i) => (
              <ClaimCard key={claim.id} claim={claim} index={i} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
