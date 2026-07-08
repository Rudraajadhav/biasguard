// BiasGuard — Auth page (login + signup combined)
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../lib/api'
import { Logo, Toast, Spinner } from '../components/UI'

export default function Auth() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('login')   // 'login' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (mode === 'signup') await api.signup(email, password)
      else await api.login(email, password)
      navigate('/app/trades')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* ---- Left: the pitch panel ---- */}
      <div className="hidden lg:flex w-[46%] relative grid-texture
                      border-r border-ink-600 flex-col justify-between p-12">
        {/* atmospheric glow */}
        <div className="absolute inset-0 pointer-events-none"
             style={{ background:
               'radial-gradient(ellipse 60% 40% at 30% 20%, rgba(94,234,212,0.08), transparent)' }} />

        <div className="relative">
          <Logo size={32} />
        </div>

        <div className="relative space-y-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="eyebrow mb-4">Behavioral analytics for investors</p>
            <h1 className="font-display text-[44px] leading-[1.1] font-semibold">
              Your worst trades<br />
              follow a <span className="text-mint italic">pattern.</span>
            </h1>
            <p className="mt-5 text-fog-300 text-[15px] leading-relaxed max-w-md">
              BiasGuard reads your trade history and surfaces the three
              behavioral patterns that quietly cost retail investors money —
              panic selling, FOMO buying, and overtrading.
            </p>
          </motion.div>

          {/* three stat chips */}
          <motion.div
            className="flex gap-3"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          >
            {[
              ['Panic', 'coral'],
              ['FOMO', 'amber'],
              ['Overtrading', 'mint'],
            ].map(([name, tone]) => (
              <div key={name}
                   className="panel px-4 py-3 flex items-center gap-2.5">
                <span className="w-2 h-2 rounded-full"
                      style={{ background: {
                        coral: '#e8654f', amber: '#e0a740', mint: '#5eead4',
                      }[tone] }} />
                <span className="text-sm text-fog-300">{name}</span>
              </div>
            ))}
          </motion.div>
        </div>

        <div className="relative text-xs text-fog-500">
          Detection methodology validated on 226,000+ real retail transactions.
        </div>
      </div>

      {/* ---- Right: the form ---- */}
      <div className="flex-1 flex items-center justify-center p-8">
        <motion.div
          className="w-full max-w-sm"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* mobile logo */}
          <div className="lg:hidden mb-10">
            <Logo size={30} />
          </div>

          <h2 className="font-display text-3xl font-semibold">
            {mode === 'login' ? 'Welcome back.' : 'Create your account.'}
          </h2>
          <p className="text-fog-300 text-sm mt-2">
            {mode === 'login'
              ? 'Sign in to review your trading patterns.'
              : 'Start tracking the biases in your trades.'}
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <label className="eyebrow block mb-2">Email</label>
              <input
                type="email" required value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="field"
              />
            </div>
            <div>
              <label className="eyebrow block mb-2">Password</label>
              <input
                type="password" required value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'signup'
                  ? 'At least 8 characters' : '••••••••'}
                className="field"
              />
            </div>

            <button type="submit" disabled={busy}
                    className="btn-primary w-full flex items-center
                               justify-center gap-2 !mt-6">
              {busy
                ? <Spinner />
                : (mode === 'login' ? 'Sign in' : 'Create account')}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-fog-300">
            {mode === 'login' ? "Don't have an account? " : 'Already registered? '}
            <button
              onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError('') }}
              className="text-mint font-medium hover:underline"
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </div>
        </motion.div>
      </div>

      <AnimatePresence>
        {error && <Toast message={error} onDone={() => setError('')} />}
      </AnimatePresence>
    </div>
  )
}
