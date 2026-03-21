import { motion, AnimatePresence } from 'framer-motion'
import { Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { 
  Shield, Search, Zap, ChevronRight, Star, CheckCircle, 
  XCircle, AlertTriangle, BarChart3, Globe, Lock, ArrowRight,
  Sparkles, Brain, Target, TrendingUp
} from 'lucide-react'

const FEATURES = [
  { icon: Brain, title: 'Multi-Agent AI Pipeline', desc: 'Orchestrated AI agents for extraction, search, verification, and analysis', color: 'from-violet-500 to-purple-600' },
  { icon: Search, title: 'Real-Time Web Search', desc: 'Autonomous search queries across multiple sources with trust scoring', color: 'from-blue-500 to-cyan-600' },
  { icon: Shield, title: 'Hallucination Detection', desc: 'Identify AI-generated misinformation and LLM hallucinations', color: 'from-emerald-500 to-teal-600' },
  { icon: BarChart3, title: 'Accuracy Analytics', desc: 'Detailed reports with confidence scores, charts and citations', color: 'from-amber-500 to-orange-600' },
  { icon: Target, title: 'Source Trust Score', desc: 'Rate source credibility from government to social media', color: 'from-pink-500 to-rose-600' },
  { icon: Zap, title: 'Temporal Fact Checking', desc: 'Detect outdated facts and time-sensitive claims automatically', color: 'from-indigo-500 to-blue-600' },
]

const STATS = [
  { value: '99.2%', label: 'Accuracy Rate', icon: Target },
  { value: '< 30s', label: 'Avg. Analysis Time', icon: Zap },
  { value: '500+', label: 'Source Domains', icon: Globe },
  { value: '10K+', label: 'Claims Verified', icon: CheckCircle },
]

const DEMO_CLAIMS = [
  { text: 'The Eiffel Tower was built in 1889.', status: 'TRUE', confidence: 0.98 },
  { text: 'The Great Wall of China is visible from space.', status: 'FALSE', confidence: 0.95 },
  { text: 'Coffee is the most traded commodity globally.', status: 'PARTIALLY_TRUE', confidence: 0.72 },
]

function FloatingOrb({ className, delay = 0 }) {
  return (
    <motion.div
      className={`absolute rounded-full blur-3xl opacity-20 ${className}`}
      animate={{ y: [-20, 20, -20], x: [-10, 10, -10], scale: [1, 1.1, 1] }}
      transition={{ duration: 8 + delay, repeat: Infinity, ease: "easeInOut", delay }}
    />
  )
}

function StatusBadge({ status }) {
  const map = {
    'TRUE': { cls: 'badge-true', icon: CheckCircle },
    'FALSE': { cls: 'badge-false', icon: XCircle },
    'PARTIALLY_TRUE': { cls: 'badge-partial', icon: AlertTriangle },
  }
  const { cls, icon: Icon } = map[status] || map['TRUE']
  return (
    <span className={`${cls} flex items-center gap-1`}>
      <Icon size={10} /> {status.replace('_', ' ')}
    </span>
  )
}

export default function Landing() {
  const [activeDemo, setActiveDemo] = useState(0)
  const [typed, setTyped] = useState('')
  const fullText = 'The Great Wall of China is over 13,000 miles long and is visible from space...'

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveDemo(prev => (prev + 1) % DEMO_CLAIMS.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    let i = 0
    const timer = setInterval(() => {
      setTyped(fullText.slice(0, i))
      i++
      if (i > fullText.length) clearInterval(timer)
    }, 40)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="min-h-screen bg-mesh overflow-hidden">
      {/* Navbar */}
      <motion.nav 
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="fixed top-0 left-0 right-0 z-50 px-6 py-4"
      >
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-violet-600 flex items-center justify-center">
              <Shield size={18} className="text-white" />
            </div>
            <span className="font-display font-bold text-xl text-white">VeritAI</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="btn-secondary px-4 py-2 text-sm">Sign In</Link>
            <Link to="/signup" className="btn-primary px-4 py-2 text-sm">Get Started <ArrowRight size={14} /></Link>
          </div>
        </div>
      </motion.nav>

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center px-6 pt-20">
        <FloatingOrb className="w-96 h-96 bg-primary-500 -top-20 -left-20" delay={0} />
        <FloatingOrb className="w-80 h-80 bg-violet-600 top-1/3 -right-20" delay={2} />
        <FloatingOrb className="w-64 h-64 bg-emerald-500 bottom-0 left-1/3" delay={4} />

        <div className="relative max-w-5xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <motion.div 
              className="inline-flex items-center gap-2 px-4 py-2 glass-card text-sm text-primary-300 mb-8"
              whileHover={{ scale: 1.05 }}
            >
              <Sparkles size={14} className="text-primary-400" />
              Powered by Google Gemini 2.0 Flash
              <span className="px-2 py-0.5 bg-primary-500/20 rounded-full text-xs font-bold text-primary-300">NEW</span>
            </motion.div>

            <h1 className="font-display font-black text-5xl md:text-7xl leading-tight mb-6">
              <span className="text-white">The World's Most</span>
              <br />
              <span className="gradient-text">Advanced Fact-Checker</span>
            </h1>

            <p className="text-slate-400 text-xl max-w-3xl mx-auto mb-12 leading-relaxed">
              AI-powered claim verification using a multi-agent pipeline. Paste text or a URL and get 
              a comprehensive accuracy report with evidence citations in seconds.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link to="/signup">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="btn-primary px-8 py-4 text-base font-bold"
                >
                  <Zap size={18} /> Start Verifying Free
                </motion.button>
              </Link>
              <Link to="/login">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="btn-secondary px-8 py-4 text-base"
                >
                  Sign In <ChevronRight size={18} />
                </motion.button>
              </Link>
            </div>
          </motion.div>

          {/* Hero Demo Card */}
          <motion.div
            initial={{ opacity: 0, y: 60 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="mt-20 glass-card p-6 text-left"
          >
            <div className="flex items-center gap-2 mb-4">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <div className="w-3 h-3 rounded-full bg-yellow-500" />
              <div className="w-3 h-3 rounded-full bg-emerald-500" />
              <span className="ml-4 text-slate-500 text-xs font-mono">veritai.app — verification pipeline</span>
            </div>
            
            <div className="font-mono text-sm text-slate-300 mb-4 min-h-[2rem]">
              <span className="text-primary-400">›</span> {typed}
              <span className="animate-pulse">|</span>
            </div>

            <div className="space-y-3">
              {DEMO_CLAIMS.map((claim, i) => (
                <motion.div
                  key={i}
                  animate={{ opacity: activeDemo === i ? 1 : 0.4 }}
                  className="flex items-center justify-between p-3 bg-white/5 rounded-xl"
                >
                  <span className="text-slate-300 text-sm flex-1 mr-4">{claim.text}</span>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right">
                      <div className="text-xs text-slate-500">Confidence</div>
                      <div className="text-sm font-bold text-white">{Math.round(claim.confidence * 100)}%</div>
                    </div>
                    <StatusBadge status={claim.status} />
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6">
          {STATS.map((stat, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="glass-card p-6 text-center"
            >
              <stat.icon className="w-6 h-6 text-primary-400 mx-auto mb-2" />
              <div className="font-display font-black text-3xl gradient-text">{stat.value}</div>
              <div className="text-slate-400 text-sm mt-1">{stat.label}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <motion.div 
            className="text-center mb-16"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
          >
            <h2 className="font-display font-black text-4xl md:text-5xl text-white mb-4">
              Built for the Age of <span className="gradient-text">Misinformation</span>
            </h2>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              Every feature engineered to catch lies, verify facts, and expose hallucinations.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((feature, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                whileHover={{ y: -5 }}
                className="glass-card p-6 group"
              >
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${feature.color} p-3 mb-4 group-hover:scale-110 transition-transform`}>
                  <feature.icon className="w-full h-full text-white" />
                </div>
                <h3 className="font-display font-bold text-lg text-white mb-2">{feature.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{feature.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <motion.div 
            className="text-center mb-16"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
          >
            <h2 className="font-display font-black text-4xl text-white mb-4">
              5-Step Verification Pipeline
            </h2>
          </motion.div>
          
          {[
            { n: '01', title: 'Input Text or URL', desc: 'Paste any text, article, or URL for analysis' },
            { n: '02', title: 'Claim Extraction', desc: 'AI extracts atomic, verifiable factual claims' },
            { n: '03', title: 'Smart Web Search', desc: 'Autonomous queries across authoritative sources' },
            { n: '04', title: 'Evidence Verification', desc: 'Chain-of-Thought reasoning compares claims vs evidence' },
            { n: '05', title: 'Accuracy Report', desc: 'Detailed report with scores, citations, and highlighting' },
          ].map((step, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.1 }}
              className="flex items-start gap-6 mb-8"
            >
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-600 to-violet-600 flex items-center justify-center text-white font-display font-black text-lg shrink-0">
                {step.n}
              </div>
              <div className="glass-card p-5 flex-1">
                <h3 className="font-display font-bold text-white text-lg mb-1">{step.title}</h3>
                <p className="text-slate-400">{step.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6">
        <motion.div 
          className="max-w-3xl mx-auto text-center glass-card p-16"
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
        >
          <Shield className="w-16 h-16 text-primary-400 mx-auto mb-8" />
          <h2 className="font-display font-black text-4xl text-white mb-4">
            Stop Believing Lies.<br />
            <span className="gradient-text">Start Verifying Facts.</span>
          </h2>
          <p className="text-slate-400 mb-8">Join thousands using VeritAI to fight misinformation.</p>
          <Link to="/signup">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="btn-primary px-10 py-4 text-lg font-bold"
            >
              <Sparkles size={20} /> Get Started Free
            </motion.button>
          </Link>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-white/5">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2 text-slate-400">
            <Shield size={16} className="text-primary-400" />
            <span className="font-display font-semibold">VeritAI</span>
          </div>
          <p className="text-slate-600 text-sm">© 2025 VeritAI. AI-Powered Truth.</p>
        </div>
      </footer>
    </div>
  )
}
