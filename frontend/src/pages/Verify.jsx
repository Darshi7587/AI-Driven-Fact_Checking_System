import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  FileText, Link, Zap, ArrowRight, AlertCircle, 
  CheckCircle2, Loader2, Search, Brain, Shield,
  ChevronDown, ChevronUp
} from 'lucide-react'
import { verifyAPI } from '../services/api'
import toast from 'react-hot-toast'

const PIPELINE_STAGES = [
  { id: 'preprocess', label: 'Preprocessing', icon: FileText, desc: 'Cleaning and parsing input' },
  { id: 'extract', label: 'Claim Extraction', icon: Brain, desc: 'AI extracting atomic facts' },
  { id: 'search', label: 'Web Search', icon: Search, desc: 'Fetching authoritative sources' },
  { id: 'verify', label: 'Verification', icon: Shield, desc: 'Chain-of-Thought analysis' },
  { id: 'report', label: 'Report Ready', icon: CheckCircle2, desc: 'Generating accuracy report' },
]

const EXAMPLE_TEXTS = [
  {
    label: '🔬 Science Claim',
    text: 'The Great Wall of China is visible from space with the naked eye. Albert Einstein failed math in school. Lightning never strikes the same place twice. Water drains in opposite directions in different hemispheres.',
  },
  {
    label: '📰 News Article',
    text: 'According to recent reports, electric vehicles now account for more than 50% of all new car sales globally. Tesla holds the largest market share with over 30% of EV sales worldwide. The US has more electric charging stations than gas stations.',
  },
  {
    label: '🏛️ Historical Facts',
    text: 'Cleopatra lived closer in time to the Moon landing than to the construction of the Great Pyramid. Napoleon Bonaparte was unusually short for his era. The Library of Alexandria was burned down by Julius Caesar.',
  },
]

function PipelineProgress({ stage }) {
  const currentIdx = PIPELINE_STAGES.findIndex(s => s.id === stage)

  return (
    <div className="glass-card p-6 mb-6">
      <h3 className="font-display font-bold text-white mb-4 flex items-center gap-2">
        <Loader2 size={16} className="animate-spin text-primary-400" />
        Verification Pipeline Running...
      </h3>
      <div className="space-y-3">
        {PIPELINE_STAGES.map((s, i) => {
          const isCompleted = i < currentIdx
          const isActive = i === currentIdx
          const isPending = i > currentIdx
          return (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.1 }}
              className={`pipeline-step ${isCompleted ? 'completed' : isActive ? 'running' : 'pending'}`}
            >
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                isCompleted ? 'bg-emerald-500/20 text-emerald-400' :
                isActive ? 'bg-primary-500/20 text-primary-400' :
                'bg-white/5 text-slate-600'
              }`}>
                {isCompleted ? <CheckCircle2 size={16} /> : 
                 isActive ? <Loader2 size={16} className="animate-spin" /> : 
                 <s.icon size={14} />}
              </div>
              <div className="flex-1">
                <div className={`text-sm font-medium ${
                  isCompleted ? 'text-emerald-300' : 
                  isActive ? 'text-primary-300' : 
                  'text-slate-600'
                }`}>{s.label}</div>
                <div className="text-xs text-slate-500">{s.desc}</div>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

export default function Verify() {
  const [inputType, setInputType] = useState('text')
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [pipelineStage, setPipelineStage] = useState(null)
  const [showExamples, setShowExamples] = useState(false)
  const navigate = useNavigate()

  const simulatePipeline = async () => {
    const stages = ['preprocess', 'extract', 'search', 'verify', 'report']
    for (const stage of stages) {
      setPipelineStage(stage)
      await new Promise(r => setTimeout(r, 800))
    }
  }

  const handleVerify = async (e) => {
    e.preventDefault()
    if (!content.trim() || content.trim().length < 20) {
      toast.error('Please enter at least 20 characters')
      return
    }
    
    setLoading(true)
    simulatePipeline() // Visual progress (real processing happens in backend)
    
    try {
      const res = await verifyAPI.verify({ input_type: inputType, content: content.trim() })
      toast.success('Verification complete!')
      navigate(`/report/${res.data.id}`)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Verification failed. Check your API key.'
      toast.error(msg)
    } finally {
      setLoading(false)
      setPipelineStage(null)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="font-display font-black text-3xl text-white mb-2">
          <span className="gradient-text">Fact Verification</span>
        </h1>
        <p className="text-slate-400">Paste text or a URL to run multi-agent AI verification</p>
      </div>

      {/* Input Type Toggle */}
      <div className="flex gap-3 mb-6">
        <button
          onClick={() => setInputType('text')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition-all ${
            inputType === 'text' 
              ? 'bg-primary-500/20 text-primary-300 border border-primary-500/30' 
              : 'text-slate-400 hover:text-slate-200 border border-white/5 hover:border-white/10'
          }`}
        >
          <FileText size={15} /> Text Input
        </button>
        <button
          onClick={() => setInputType('url')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition-all ${
            inputType === 'url' 
              ? 'bg-primary-500/20 text-primary-300 border border-primary-500/30' 
              : 'text-slate-400 hover:text-slate-200 border border-white/5 hover:border-white/10'
          }`}
        >
          <Link size={15} /> URL / Article
        </button>
      </div>

      {/* Main Input Form */}
      <AnimatePresence mode="wait">
        {!loading ? (
          <motion.form 
            key="form"
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }}
            onSubmit={handleVerify}
          >
            <div className="glass-card p-6 mb-4">
              {inputType === 'text' ? (
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="input-primary resize-none h-52 text-sm leading-relaxed"
                  placeholder="Paste text to fact-check here. For best results, include specific factual claims, statistics, or assertions that can be verified..."
                />
              ) : (
                <div>
                  <input
                    type="url"
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    className="input-primary mb-3"
                    placeholder="https://example.com/article..."
                  />
                  <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-start gap-2">
                    <AlertCircle size={16} className="text-amber-400 shrink-0 mt-0.5" />
                    <p className="text-amber-300/80 text-xs">
                      The URL must be publicly accessible. The AI will scrape and verify facts from the article content.
                    </p>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between mt-4">
                <div className="flex items-center gap-2 text-slate-500 text-xs">
                  <Shield size={12} className="text-primary-400" />
                  Multi-agent AI verification • DuckDuckGo search • Gemini 2.0 Flash
                </div>
                <motion.button
                  type="submit"
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  className="btn-primary px-8 py-3"
                >
                  <Zap size={16} /> Verify Now <ArrowRight size={14} />
                </motion.button>
              </div>
            </div>

            {/* Example Texts */}
            <div className="glass-card overflow-hidden">
              <button
                type="button"
                onClick={() => setShowExamples(!showExamples)}
                className="w-full flex items-center justify-between p-4 text-slate-400 hover:text-slate-200 transition-colors"
              >
                <span className="text-sm font-medium">Try an example</span>
                {showExamples ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>

              <AnimatePresence>
                {showExamples && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="px-4 pb-4 space-y-2 border-t border-white/5">
                      {EXAMPLE_TEXTS.map((ex, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => { setContent(ex.text); setInputType('text'); setShowExamples(false) }}
                          className="w-full text-left p-3 bg-white/3 hover:bg-white/6 rounded-xl transition-all"
                        >
                          <div className="font-medium text-white text-sm mb-1">{ex.label}</div>
                          <div className="text-slate-500 text-xs line-clamp-2">{ex.text}</div>
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.form>
        ) : (
          <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <PipelineProgress stage={pipelineStage} />
            <div className="glass-card p-6 text-center">
              <div className="relative inline-flex items-center justify-center mb-6">
                <div className="w-20 h-20 rounded-full border-4 border-primary-500/20 border-t-primary-500 animate-spin" />
                <Brain className="absolute w-8 h-8 text-primary-400" />
              </div>
              <h3 className="font-display font-bold text-xl text-white mb-2">AI is verifying your content</h3>
              <p className="text-slate-400 text-sm">
                Running claim extraction → web search → evidence analysis...<br />
                This may take 30–90 seconds depending on the number of claims.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
