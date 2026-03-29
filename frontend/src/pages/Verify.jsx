import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  FileText, Link, Zap, ArrowRight, AlertCircle, 
  CheckCircle2, Loader2, Search, Brain, Shield,
  ChevronDown, ChevronUp, Upload
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
  const [aiText, setAiText] = useState('')
  const [aiFile, setAiFile] = useState(null)
  const [aiPreviewUrl, setAiPreviewUrl] = useState(null)
  const [aiDetectLoading, setAiDetectLoading] = useState(false)
  const [aiDetectResult, setAiDetectResult] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    return () => {
      if (aiPreviewUrl) {
        URL.revokeObjectURL(aiPreviewUrl)
      }
    }
  }, [aiPreviewUrl])

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
      const res = await verifyAPI.verify({
        input_type: inputType,
        content: content.trim(),
      })
      toast.success('Verification complete!')
      navigate(`/report/${res.data.id}`)
    } catch (err) {
      const detail = err.response?.data?.detail
      let msg = 'Verification failed. Please try again.'
      if (typeof detail === 'string') {
        msg = detail
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail.map((d) => d?.msg).filter(Boolean).join('; ') || msg
      } else if (err.response?.status === 422) {
        msg = 'Input could not be processed. Please provide clearer factual statements or a publicly accessible URL.'
      } else if (err.response?.status === 401) {
        msg = 'Session expired. Please login again.'
      }
      toast.error(msg)
    } finally {
      setLoading(false)
      setPipelineStage(null)
    }
  }

  const handleAiDetect = async () => {
    if (!aiText.trim() && !aiFile) {
      toast.error('Provide text or upload an image/media file')
      return
    }

    try {
      setAiDetectLoading(true)
      const formData = new FormData()
      if (aiText.trim()) formData.append('text', aiText.trim())
      if (aiFile) formData.append('media_file', aiFile)

      const res = await verifyAPI.aiDetect(formData)
      setAiDetectResult(res.data)
      toast.success('AI detection completed')
    } catch (err) {
      const detail = err.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'AI detection failed')
    } finally {
      setAiDetectLoading(false)
    }
  }

  const handleAiFileChange = (e) => {
    const file = e.target.files?.[0] || null
    setAiFile(file)
    setAiDetectResult(null)

    if (aiPreviewUrl) {
      URL.revokeObjectURL(aiPreviewUrl)
      setAiPreviewUrl(null)
    }

    if (file && file.type?.startsWith('image/')) {
      setAiPreviewUrl(URL.createObjectURL(file))
    }
  }

  const getMediaVerdict = (mediaDetection) => {
    const prediction = mediaDetection?.prediction
    if (prediction === 'AI-generated') return 'Deepfake'
    if (prediction === 'Real') return 'Real'
    if (prediction === 'Possibly AI') return 'Possibly AI'
    if (prediction === 'Manipulated') return 'Manipulated'

    const verdict = (mediaDetection?.verdict || '').toLowerCase()
    if (verdict === 'deepfake') return 'Deepfake'
    if (verdict === 'real') return 'Real'

    const p = Number(mediaDetection?.overall_probability || 0)
    if (p >= 0.6) return 'Deepfake'
    if (p <= 0.4) return 'Real'
    return 'Possibly AI'
  }

  const toPercent = (value, fallback = 0) => {
    const n = Number(value)
    if (!Number.isFinite(n)) return fallback
    return n <= 1 ? Math.round(n * 100) : Math.round(n)
  }

  const hasTextDetection = Boolean(aiDetectResult?.text_detection)
  const hasMediaDetection = Boolean(aiDetectResult?.media_detection)

  const toneClass = (percent) => {
    if (percent >= 70) return 'text-rose-300'
    if (percent <= 30) return 'text-emerald-300'
    return 'text-amber-300'
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
        <button
          onClick={() => setInputType('ai')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition-all ${
            inputType === 'ai'
              ? 'bg-primary-500/20 text-primary-300 border border-primary-500/30'
              : 'text-slate-400 hover:text-slate-200 border border-white/5 hover:border-white/10'
          }`}
        >
          <Upload size={15} /> AI Detector
        </button>
      </div>

      {/* Main Input Form */}
      <AnimatePresence mode="wait">
        {inputType === 'ai' ? (
          <motion.div
            key="ai-detector"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="glass-card p-6"
          >
            <h3 className="font-display font-bold text-white mb-1 flex items-center gap-2">
              <Upload size={16} className="text-primary-400" /> AI Detector (Text / Image)
            </h3>
            <p className="text-slate-400 text-xs mb-4">Gemini analysis for text and uploaded media.</p>

            <div className="space-y-3">
              <textarea
                value={aiText}
                onChange={(e) => setAiText(e.target.value)}
                className="input-primary resize-none h-28 text-sm"
                placeholder="Paste text for AI-generated detection (optional if uploading file)..."
              />
              <div className="flex items-center gap-3">
                <input
                  type="file"
                  accept="image/*,audio/*,video/*"
                  onChange={handleAiFileChange}
                  className="text-xs text-slate-300"
                />
                {aiFile && <span className="text-xs text-slate-400 truncate">{aiFile.name}</span>}
              </div>

              {aiPreviewUrl && (
                <div className="rounded-xl overflow-hidden border border-white/10 bg-black/20">
                  <img
                    src={aiPreviewUrl}
                    alt="Uploaded preview"
                    className="w-full max-h-72 object-contain"
                  />
                </div>
              )}

              <button
                type="button"
                onClick={handleAiDetect}
                disabled={aiDetectLoading}
                className="btn-secondary px-4 py-2 text-sm"
              >
                {aiDetectLoading ? 'Checking...' : 'Analyze'}
              </button>
            </div>

            {aiDetectResult && (
              <div className={`mt-4 grid grid-cols-1 ${hasTextDetection && hasMediaDetection ? 'md:grid-cols-2' : 'md:grid-cols-1'} gap-3`}>
                {aiDetectResult.text_detection && (
                  <div className="w-full min-w-0 overflow-hidden p-4 rounded-xl bg-white/5 border border-white/10">
                    <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">Text Detection Report</p>
                    <p className="text-base text-white font-semibold mb-3">{aiDetectResult.text_detection.label}</p>

                    <div className="grid grid-cols-2 gap-2 mb-3">
                      <div className="rounded-lg border border-white/10 bg-black/20 p-2">
                        <p className="text-[11px] text-slate-400">AI Probability</p>
                        <p className={`text-sm font-semibold ${toneClass(toPercent(aiDetectResult.text_detection.ai_probability ?? aiDetectResult.text_detection.probability, 0))}`}>
                          {toPercent(aiDetectResult.text_detection.ai_probability ?? aiDetectResult.text_detection.probability, 0)}%
                        </p>
                      </div>
                      <div className="rounded-lg border border-white/10 bg-black/20 p-2">
                        <p className="text-[11px] text-slate-400">Confidence</p>
                        <p className="text-sm font-semibold text-white">
                          {toPercent(aiDetectResult.text_detection.confidence, 0)}%
                        </p>
                      </div>
                    </div>

                    {Array.isArray(aiDetectResult.text_detection.reasoning) && aiDetectResult.text_detection.reasoning.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">Key Findings</p>
                        <ul className="list-disc list-inside text-xs text-slate-300 space-y-1 leading-relaxed break-words">
                          {aiDetectResult.text_detection.reasoning.slice(0, 3).map((point, idx) => (
                            <li key={idx}>{point}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {aiDetectResult.text_detection.method && (
                      <p className="text-[11px] text-slate-500 mt-3 break-all">Method: {aiDetectResult.text_detection.method}</p>
                    )}
                  </div>
                )}
                {aiDetectResult.media_detection && (
                  <div className="w-full min-w-0 overflow-hidden p-4 rounded-xl bg-white/5 border border-white/10">
                    <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">Media Detection Report</p>
                    <p className="text-base text-white font-semibold mb-3">{getMediaVerdict(aiDetectResult.media_detection)}</p>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3">
                      <div className="rounded-lg border border-white/10 bg-black/20 p-2">
                        <p className="text-[11px] text-slate-400">AI Probability</p>
                        <p className={`text-sm font-semibold ${toneClass(toPercent(aiDetectResult.media_detection.ai_probability ?? aiDetectResult.media_detection.deepfake_probability ?? aiDetectResult.media_detection.overall_probability, 0))}`}>
                          {toPercent(aiDetectResult.media_detection.ai_probability ?? aiDetectResult.media_detection.deepfake_probability ?? aiDetectResult.media_detection.overall_probability, 0)}%
                        </p>
                      </div>
                      <div className="rounded-lg border border-white/10 bg-black/20 p-2">
                        <p className="text-[11px] text-slate-400">Confidence</p>
                        <p className="text-sm font-semibold text-white">
                          {toPercent(aiDetectResult.media_detection.confidence, toPercent((Math.abs((aiDetectResult.media_detection.overall_probability ?? 0) - 0.5) * 200), 0))}%
                        </p>
                      </div>
                      {aiDetectResult.media_detection.huggingface_score != null && (
                        <div className="rounded-lg border border-white/10 bg-black/20 p-2">
                          <p className="text-[11px] text-slate-400">Hugging Face Score</p>
                          <p className={`text-sm font-semibold ${toneClass(toPercent(aiDetectResult.media_detection.huggingface_score, 0))}`}>
                            {toPercent(aiDetectResult.media_detection.huggingface_score, 0)}%
                          </p>
                        </div>
                      )}
                    </div>

                    {aiDetectResult.media_detection.prediction && (
                      <p className="text-xs text-slate-300 mt-1">Model prediction: {aiDetectResult.media_detection.prediction}</p>
                    )}
                    {aiDetectResult.media_detection.borderline && (
                      <p className="text-xs text-amber-300 mt-1">Borderline confidence, verify with additional evidence.</p>
                    )}
                    {Array.isArray(aiDetectResult.media_detection.analysis) && aiDetectResult.media_detection.analysis.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">Key Findings</p>
                        <ul className="list-disc list-inside text-xs text-slate-300 space-y-1 leading-relaxed break-words">
                          {aiDetectResult.media_detection.analysis.slice(0, 3).map((point, idx) => (
                            <li key={idx}>{point}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {aiDetectResult.media_detection.explanation && (
                      <p className="text-xs text-slate-300 mt-2 leading-relaxed break-words">{aiDetectResult.media_detection.explanation}</p>
                    )}
                    {aiDetectResult.media_detection.method && (
                      <p className="text-[11px] text-slate-500 mt-3 break-all">Method: {aiDetectResult.media_detection.method}</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </motion.div>
        ) : !loading ? (
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
                    Multi-agent verification pipeline • Tavily + DuckDuckGo evidence retrieval • Model: GEMINI only
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
