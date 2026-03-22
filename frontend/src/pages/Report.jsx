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
import toast from 'react-hot-toast'

const STATUS_CONFIG = {
  TRUE: { label: 'True', color: '#10b981', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', badge: 'badge-true', icon: CheckCircle },
  FALSE: { label: 'False', color: '#ef4444', bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', badge: 'badge-false', icon: XCircle },
  PARTIALLY_TRUE: { label: 'Partially True', color: '#f59e0b', bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', badge: 'badge-partial', icon: AlertTriangle },
  UNVERIFIABLE: { label: 'Unverifiable', color: '#64748b', bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', badge: 'badge-unverifiable', icon: HelpCircle },
  CONFLICTING: { label: 'Conflicting', color: '#a855f7', bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', badge: 'badge-conflicting', icon: AlertOctagon }
}

const PDF_PRESETS = {
  detailed: {
    label: 'Detailed Evidence Report',
    fileSuffix: 'Detailed',
    includeReasoning: true,
    includeTemporalNote: true,
    includeQueries: true,
    includeSources: true,
    sourceLimit: 999,
    snippetLimit: 0,
  },
  standard: {
    label: 'Analyst Review Report',
    fileSuffix: 'Standard',
    includeReasoning: true,
    includeTemporalNote: true,
    includeQueries: true,
    includeSources: true,
    sourceLimit: 3,
    snippetLimit: 500,
  },
  summary: {
    label: 'Executive Snapshot',
    fileSuffix: 'Summary',
    includeReasoning: false,
    includeTemporalNote: false,
    includeQueries: false,
    includeSources: true,
    sourceLimit: 2,
    snippetLimit: 0,
  },
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
                          {src.image_url && (
                            <a
                              href={src.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="shrink-0"
                            >
                              <img
                                src={src.image_url}
                                alt={src.title || 'Source preview'}
                                className="w-24 h-16 object-cover rounded-lg border border-white/10"
                                loading="lazy"
                                referrerPolicy="no-referrer"
                              />
                            </a>
                          )}
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

function detectionTone(probability = 0) {
  if (probability >= 0.65) {
    return { chip: 'bg-red-500/20 text-red-300 border-red-500/30', text: 'Likely AI/Synthetic' }
  }
  if (probability <= 0.35) {
    return { chip: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30', text: 'Likely Authentic/Human' }
  }
  return { chip: 'bg-amber-500/20 text-amber-300 border-amber-500/30', text: 'Uncertain' }
}

export default function Report() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [showMethodology, setShowMethodology] = useState(false)

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

  const exportPDF = async (presetKey = 'detailed') => {
    setExporting(true)
    setExportMenuOpen(false)
    try {
      const preset = PDF_PRESETS[presetKey] || PDF_PRESETS.detailed
      const pdf = new jsPDF('p', 'mm', 'a4')
      const pageWidth = pdf.internal.pageSize.getWidth()
      const pageHeight = pdf.internal.pageSize.getHeight()
      const margin = 12
      const maxTextWidth = pageWidth - margin * 2
      let y = margin

      const clipText = (text, maxChars = 0) => {
        const safe = String(text || '').trim()
        if (!maxChars || safe.length <= maxChars) return safe
        return `${safe.slice(0, maxChars)}...`
      }

      const ensureSpace = (needed = 6) => {
        if (y + needed > pageHeight - margin) {
          pdf.addPage()
          y = margin
        }
      }

      const addWrappedText = (text, opts = {}) => {
        const {
          fontSize = 10,
          fontStyle = 'normal',
          color = [15, 23, 42],
          indent = 0,
          lineHeight = 5,
          spacingAfter = 1,
        } = opts

        const safeText = String(text ?? '').trim()
        if (!safeText) return

        pdf.setFont('helvetica', fontStyle)
        pdf.setFontSize(fontSize)
        pdf.setTextColor(...color)

        const lines = pdf.splitTextToSize(safeText, maxTextWidth - indent)
        for (const line of lines) {
          ensureSpace(lineHeight)
          pdf.text(line, margin + indent, y)
          y += lineHeight
        }
        y += spacingAfter
      }

      const addDivider = () => {
        ensureSpace(3)
        pdf.setDrawColor(203, 213, 225)
        pdf.line(margin, y, pageWidth - margin, y)
        y += 3
      }

      const statusLabel = (status) => {
        const labels = {
          TRUE: 'True',
          FALSE: 'False',
          PARTIALLY_TRUE: 'Partially True',
          UNVERIFIABLE: 'Unverifiable',
          CONFLICTING: 'Conflicting',
        }
        return labels[status] || 'Unverifiable'
      }

      const generatedAt = new Date().toLocaleString()
      addWrappedText('VeritAI Fact-Check Report', { fontSize: 16, fontStyle: 'bold', color: [2, 6, 23], lineHeight: 7, spacingAfter: 2 })
      addWrappedText(`Export Type: ${preset.label}`, { fontSize: 10, fontStyle: 'bold', color: [30, 64, 175], spacingAfter: 1 })
      addWrappedText(`Report ID: ${id}`, { fontSize: 9, color: [71, 85, 105] })
      addWrappedText(`Generated: ${generatedAt}`, { fontSize: 9, color: [71, 85, 105] })
      if (report.verified_as_of) {
        addWrappedText(`Verified As Of: ${report.verified_as_of}`, { fontSize: 9, color: [71, 85, 105] })
      }
      addDivider()

      addWrappedText('Summary', { fontSize: 13, fontStyle: 'bold', color: [15, 23, 42], spacingAfter: 2 })
      addWrappedText(`Overall Accuracy: ${Math.round((report.overall_accuracy || 0) * 100)}%`, { fontSize: 10 })
      addWrappedText(`Total Claims: ${report.total_claims || 0}`, { fontSize: 10 })
      addWrappedText(`True: ${report.true_count || 0} | False: ${report.false_count || 0} | Partial: ${report.partial_count || 0} | Unverifiable: ${report.unverifiable_count || 0} | Conflicting: ${report.conflicting_count || 0}`, { fontSize: 10 })
      addWrappedText(`Hallucinations: ${report.hallucination_count || 0} | Processing Time: ${report.processing_time || 0}s`, { fontSize: 10 })
      if (report.ai_text_detection) {
        addWrappedText(`AI-Generated Text Probability: ${Math.round((report.ai_text_detection.probability || 0) * 100)}% (${report.ai_text_detection.label || 'unknown'})`, { fontSize: 10 })
      }
      if (report.ai_media_detection) {
        addWrappedText(`AI-Generated Media Probability: ${Math.round((report.ai_media_detection.overall_probability || 0) * 100)}% (${report.ai_media_detection.label || 'unknown'})`, { fontSize: 10 })
      }

      if (report.ai_text_detection?.indicators?.length) {
        addWrappedText('Text Detection Indicators', { fontSize: 10, fontStyle: 'bold', color: [30, 41, 59], spacingAfter: 1 })
        report.ai_text_detection.indicators.forEach((item) => {
          addWrappedText(`- ${item}`, { fontSize: 9, color: [51, 65, 85], indent: 2, spacingAfter: 0.5 })
        })
      }

      if (report.ai_media_detection?.items?.length && presetKey !== 'summary') {
        addWrappedText('Media Detection Items', { fontSize: 10, fontStyle: 'bold', color: [30, 41, 59], spacingAfter: 1 })
        report.ai_media_detection.items.slice(0, presetKey === 'detailed' ? 8 : 3).forEach((item, idx) => {
          addWrappedText(
            `${idx + 1}. ${item.type} | ${Math.round((item.synthetic_probability || 0) * 100)}% synthetic | ${item.domain}`,
            { fontSize: 9, color: [51, 65, 85], indent: 2, spacingAfter: 0.5 }
          )
          if (item.url) {
            addWrappedText(`URL: ${item.url}`, { fontSize: 8, color: [30, 64, 175], indent: 4, spacingAfter: 0.5 })
          }
        })
      }

      if (report.source_url) {
        addWrappedText('Source URL', { fontSize: 11, fontStyle: 'bold', spacingAfter: 1 })
        addWrappedText(report.source_url, { fontSize: 9, color: [30, 64, 175], spacingAfter: 2 })
      }

      addDivider()
      addWrappedText(`Verified Claims (${report.claims?.length || 0})`, { fontSize: 13, fontStyle: 'bold', spacingAfter: 2 })

      ;(report.claims || []).forEach((claim, claimIdx) => {
        ensureSpace(10)
        addWrappedText(`Claim ${claimIdx + 1}`, { fontSize: 12, fontStyle: 'bold', color: [15, 23, 42], spacingAfter: 1 })
        addWrappedText(claim.text, { fontSize: 10, color: [2, 6, 23], spacingAfter: 2 })

        const confidence = Math.round((claim.confidence || 0) * 100)
        addWrappedText(
          `Verdict: ${statusLabel(claim.status)} | Confidence: ${confidence}% | Temporal: ${claim.is_temporal ? 'Yes' : 'No'} | Hallucination: ${claim.is_hallucination ? 'Yes' : 'No'} | Conflicting: ${claim.conflicting_evidence ? 'Yes' : 'No'}`,
          { fontSize: 9, color: [51, 65, 85], spacingAfter: 2 }
        )

        if (preset.includeReasoning && claim.reasoning) {
          addWrappedText('AI Reasoning', { fontSize: 10, fontStyle: 'bold', color: [30, 41, 59], spacingAfter: 1 })
          addWrappedText(clipText(claim.reasoning, presetKey === 'standard' ? 900 : 0), { fontSize: 9, color: [30, 41, 59], spacingAfter: 2 })
        }

        if (claim.key_finding) {
          addWrappedText('Key Finding', { fontSize: 10, fontStyle: 'bold', color: [30, 41, 59], spacingAfter: 1 })
          addWrappedText(claim.key_finding, { fontSize: 9, color: [30, 41, 59], spacingAfter: 2 })
        }

        if (preset.includeTemporalNote && claim.temporal_note) {
          addWrappedText('Temporal Note', { fontSize: 10, fontStyle: 'bold', color: [30, 41, 59], spacingAfter: 1 })
          addWrappedText(claim.temporal_note, { fontSize: 9, color: [30, 41, 59], spacingAfter: 2 })
        }

        if (preset.includeQueries && claim.search_queries?.length) {
          addWrappedText('Search Queries Used', { fontSize: 10, fontStyle: 'bold', color: [30, 41, 59], spacingAfter: 1 })
          claim.search_queries.forEach((query) => {
            addWrappedText(`- ${query}`, { fontSize: 9, color: [51, 65, 85], indent: 2, spacingAfter: 0.5 })
          })
          y += 1
        }

        if (preset.includeSources && claim.sources?.length) {
          const sources = claim.sources.slice(0, preset.sourceLimit)
          addWrappedText(`Evidence Sources (${sources.length}${claim.sources.length > sources.length ? ` of ${claim.sources.length}` : ''})`, { fontSize: 10, fontStyle: 'bold', color: [30, 41, 59], spacingAfter: 1 })

          sources.forEach((src, srcIdx) => {
            ensureSpace(14)
            addWrappedText(`Source ${srcIdx + 1} | ${Math.round((src.trust_score || 0) * 100)}% trust | ${src.domain || 'unknown domain'}`, {
              fontSize: 9,
              fontStyle: 'bold',
              color: [15, 23, 42],
              indent: 2,
              spacingAfter: 0.5,
            })
            if (src.title) addWrappedText(`Title: ${src.title}`, { fontSize: 9, color: [51, 65, 85], indent: 4, spacingAfter: 0.5 })
            if (src.url) addWrappedText(`URL: ${src.url}`, { fontSize: 8, color: [30, 64, 175], indent: 4, spacingAfter: 0.5 })
            if (preset.snippetLimit !== 0 && src.snippet) {
              addWrappedText(`Snippet: ${clipText(src.snippet, preset.snippetLimit)}`, { fontSize: 8, color: [71, 85, 105], indent: 4, spacingAfter: 1 })
            }
          })
        }

        addDivider()
      })

      pdf.save(`VeritAI-Report-${id.slice(0, 8)}-${preset.fileSuffix}.pdf`)
      toast.success(`${preset.label} exported!`)
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
  const textDetection = report.ai_text_detection || { probability: 0, label: 'unknown', confidence: 0, indicators: [] }
  const mediaDetection = report.ai_media_detection || { overall_probability: 0, label: 'not_applicable', analyzed_count: 0, items: [] }
  const textAnalyzerPreviewImage = (mediaDetection.items || []).find((item) => item.type === 'image')?.url || null
  const textTone = detectionTone(textDetection.probability)
  const mediaTone = detectionTone(mediaDetection.overall_probability)
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
          <div className="relative">
            <motion.button
              whileHover={{ scale: 1.03 }}
              onClick={() => setExportMenuOpen((v) => !v)}
              disabled={exporting}
              className="btn-secondary px-4 py-2 text-sm"
            >
              <Download size={14} /> {exporting ? 'Exporting...' : 'Export PDF'} <ChevronDown size={14} />
            </motion.button>

            {exportMenuOpen && !exporting && (
              <div className="absolute right-0 mt-2 w-64 bg-slate-900 border border-white/10 rounded-xl shadow-xl overflow-hidden z-20">
                {Object.entries(PDF_PRESETS).map(([key, preset]) => (
                  <button
                    key={key}
                    onClick={() => exportPDF(key)}
                    className="w-full text-left px-4 py-3 hover:bg-white/5 transition-colors"
                  >
                    <p className="text-slate-100 text-sm font-medium">{preset.label}</p>
                    <p className="text-slate-500 text-xs mt-0.5">
                      {key === 'detailed' ? 'Full claim reasoning, all sources, complete snippets' :
                       key === 'standard' ? 'Condensed reasoning, top sources, trimmed snippets' :
                       'Decision-focused summary, key findings, top sources'}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
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

        {/* Bonus Detection Signals */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="glass-card p-6 mb-6"
        >
          <div className="flex items-center justify-between gap-3 mb-4">
            <h3 className="font-display font-bold text-white text-sm uppercase tracking-wide">AI Authenticity Signals</h3>
            <button
              onClick={() => setShowMethodology((v) => !v)}
              className="text-xs text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1"
            >
              <HelpCircle size={12} /> {showMethodology ? 'Hide Methodology' : 'Show Methodology'}
            </button>
          </div>

          {showMethodology && (
            <div className="mb-4 p-3 rounded-xl border border-white/10 bg-slate-900/40">
              <p className="text-slate-300 text-xs leading-relaxed">
                Text detection uses stylometric heuristics (sentence length, lexical diversity, transition frequency, hedging language) to estimate a probability that text is AI-generated.
                Media detection analyzes embedded image/audio/video URLs from the input page using source trust and synthetic-pattern indicators in URLs.
                These are risk signals for triage, not forensic proof.
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl border border-white/10 bg-white/3">
              <div className="flex items-center justify-between">
                <p className="text-slate-300 text-sm font-medium">AI-Generated Text Detection</p>
                <span className={`text-xs px-2 py-1 rounded-full border ${textTone.chip}`}>{textTone.text}</span>
              </div>

              <div className="mt-3 rounded-lg overflow-hidden border border-white/10 bg-slate-900/40">
                {textAnalyzerPreviewImage ? (
                  <img
                    src={textAnalyzerPreviewImage}
                    alt="Text analyzer media context"
                    className="w-full h-24 object-cover"
                    loading="lazy"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="h-24 flex items-center justify-center text-xs text-slate-500">
                    No related preview image detected
                  </div>
                )}
              </div>

              <p className="mt-2 text-2xl font-display font-black text-white">{Math.round((textDetection.probability || 0) * 100)}%</p>
              <p className="text-slate-500 text-xs">Method: {textDetection.method || 'heuristic-v1'}</p>
              {textDetection.indicators?.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {textDetection.indicators.slice(0, 3).map((ind, idx) => (
                    <li key={idx} className="text-xs text-slate-400">- {ind}</li>
                  ))}
                </ul>
              )}
            </div>

            <div className="p-4 rounded-xl border border-white/10 bg-white/3">
              <div className="flex items-center justify-between">
                <p className="text-slate-300 text-sm font-medium">AI-Generated Media Detection</p>
                <span className={`text-xs px-2 py-1 rounded-full border ${mediaTone.chip}`}>{mediaTone.text}</span>
              </div>
              <p className="mt-2 text-2xl font-display font-black text-white">{Math.round((mediaDetection.overall_probability || 0) * 100)}%</p>
              <p className="text-slate-500 text-xs">Analyzed Media: {mediaDetection.analyzed_count || 0}</p>
              {mediaDetection.note && <p className="text-slate-500 text-xs mt-1">{mediaDetection.note}</p>}
              {mediaDetection.items?.length > 0 && (
                <div className="mt-3 space-y-2 max-h-40 overflow-auto pr-1">
                  {mediaDetection.items.slice(0, 3).map((item, idx) => (
                    <a
                      key={idx}
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block p-2 rounded-lg border border-white/10 bg-white/3 hover:bg-white/5 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        {item.type === 'image' ? (
                          <img
                            src={item.url}
                            alt={`Detected media ${idx + 1}`}
                            className="w-16 h-12 rounded object-cover border border-white/10 shrink-0"
                            loading="lazy"
                            referrerPolicy="no-referrer"
                          />
                        ) : (
                          <div className="w-16 h-12 rounded border border-white/10 shrink-0 flex items-center justify-center text-[10px] uppercase text-slate-400 bg-slate-900/40">
                            {item.type}
                          </div>
                        )}

                        <div className="min-w-0">
                          <p className="text-xs text-slate-300 truncate">{item.domain}</p>
                          <p className="text-xs text-slate-500">
                            {Math.round((item.synthetic_probability || 0) * 100)}% synthetic risk
                          </p>
                        </div>
                      </div>
                    </a>
                  ))}
                </div>
              )}
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
