// BiasGuard — Trade Log page
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../lib/api'
import { Panel, Toast, Spinner } from '../components/UI'

const REASONS = [
  'Long-term conviction', 'Short-term opportunity', 'News-based',
  'Tip from someone', 'Felt like it', 'Cutting losses', 'Booking profits',
]

// Curated demo set: all three biases fire, and the AXISBANK round trip
// (sold 285 -> rebought 477) reads cleanly on 50 shares.
const SAMPLE_TRADES = [
  { ticker: 'AXISBANK',  action: 'Buy',  quantity: 50, price: 690,  trade_date: '2020-03-09', reason: 'Long-term conviction' },
  { ticker: 'AXISBANK',  action: 'Sell', quantity: 50, price: 285,  trade_date: '2020-03-23', reason: 'Cutting losses' },
  { ticker: 'ICICIBANK', action: 'Buy',  quantity: 50, price: 540,  trade_date: '2020-03-09', reason: 'Long-term conviction' },
  { ticker: 'ICICIBANK', action: 'Sell', quantity: 50, price: 290,  trade_date: '2020-03-23', reason: 'Cutting losses' },
  { ticker: 'AXISBANK',  action: 'Buy',  quantity: 50, price: 477,  trade_date: '2020-04-17', reason: 'News-based' },
  { ticker: 'TCS',       action: 'Buy',  quantity: 1,  price: 3800, trade_date: '2024-01-15', reason: 'Short-term opportunity' },
  { ticker: 'RELIANCE',  action: 'Buy',  quantity: 1,  price: 2750, trade_date: '2024-01-15', reason: 'Short-term opportunity' },
  { ticker: 'INFY',      action: 'Buy',  quantity: 2,  price: 1680, trade_date: '2024-01-16', reason: 'Tip from someone' },
  { ticker: 'WIPRO',     action: 'Buy',  quantity: 5,  price: 480,  trade_date: '2024-01-16', reason: 'Felt like it' },
  { ticker: 'HDFCBANK',  action: 'Buy',  quantity: 2,  price: 1420, trade_date: '2024-01-17', reason: 'Short-term opportunity' },
  { ticker: 'SBIN',      action: 'Buy',  quantity: 3,  price: 750,  trade_date: '2024-01-17', reason: 'Felt like it' },
  { ticker: 'TCS',       action: 'Sell', quantity: 1,  price: 3850, trade_date: '2024-01-18', reason: 'Booking profits' },
  { ticker: 'INFY',      action: 'Sell', quantity: 2,  price: 1700, trade_date: '2024-01-19', reason: 'Booking profits' },
]

export default function Trades() {
  const navigate = useNavigate()
  const [trades, setTrades] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [loadingSample, setLoadingSample] = useState(false)

  // form state
  const [form, setForm] = useState({
    ticker: '', action: 'Buy', quantity: '', price: '',
    trade_date: '', reason: REASONS[0],
  })

  async function loadTrades() {
    try {
      setTrades(await api.listTrades())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadTrades() }, [])

  async function addTrade(e) {
    e.preventDefault()
    setError('')
    try {
      await api.addTrade({
        ticker: form.ticker.trim().toUpperCase(),
        action: form.action,
        quantity: parseFloat(form.quantity),
        price: parseFloat(form.price),
        trade_date: form.trade_date,
        reason: form.reason,
      })
      setForm({ ...form, ticker: '', quantity: '', price: '' })
      loadTrades()
    } catch (err) {
      setError(err.message)
    }
  }

  async function removeTrade(id) {
    try {
      await api.deleteTrade(id)
      setTrades(trades.filter((t) => t.id !== id))
    } catch (err) {
      setError(err.message)
    }
  }

  async function runAnalysis() {
    setAnalyzing(true)
    setError('')
    try {
      await api.analyze()
      navigate('/app/report')
    } catch (err) {
      setError(err.message)
      setAnalyzing(false)
    }
  }

  async function loadSample() {
    setLoadingSample(true)
    setError('')
    try {
      for (const t of SAMPLE_TRADES) {
        await api.addTrade(t)
      }
      await api.analyze()
      navigate('/app/report')
    } catch (err) {
      setError(err.message)
      setLoadingSample(false)
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const canAnalyze = trades.length >= 10

  return (
    <div className="space-y-8">
      {/* header */}
      <div className="flex items-end justify-between">
        <div>
          <p className="eyebrow mb-2">Step one</p>
          <h1 className="font-display text-4xl font-semibold">Trade Log</h1>
          <p className="text-fog-300 text-sm mt-2">
            Record your trades. We need at least 10 to detect patterns.
          </p>
        </div>
        <div className="text-right">
          <div className="nums text-3xl font-semibold text-mint">
            {trades.length}
          </div>
          <div className="text-xs text-fog-500 uppercase tracking-wider">
            trades logged
          </div>
        </div>
      </div>

      {/* progress toward 10 */}
      {trades.length < 10 && (
        <Panel className="p-4">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-fog-300">
              {10 - trades.length} more trade{10 - trades.length === 1 ? '' : 's'}
              {' '}until analysis unlocks
            </span>
            <span className="nums text-fog-500">{trades.length} / 10</span>
          </div>
          <div className="h-1.5 rounded-full bg-ink-600 overflow-hidden">
            <motion.div
              className="h-full bg-mint rounded-full"
              animate={{ width: `${Math.min(100, trades.length * 10)}%` }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            />
          </div>
        </Panel>
      )}

      <div className="grid lg:grid-cols-[380px_1fr] gap-6">
        {/* ---- add-trade form ---- */}
        <Panel className="p-6 h-fit" delay={0.05}>
          <h2 className="font-display text-xl font-semibold mb-5">
            Add a trade
          </h2>
          <form onSubmit={addTrade} className="space-y-4">
            <div>
              <label className="eyebrow block mb-2">Stock ticker</label>
              <input
                required value={form.ticker} onChange={set('ticker')}
                placeholder="TCS, RELIANCE, INFY…"
                className="field uppercase"
              />
              <p className="text-xs text-fog-500 mt-1.5">
                NSE stocks. Type the symbol — we add .NS automatically.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="eyebrow block mb-2">Action</label>
                <div className="grid grid-cols-2 gap-1.5 p-1 bg-ink-900
                                rounded-lg border border-ink-600">
                  {['Buy', 'Sell'].map((a) => (
                    <button
                      key={a} type="button"
                      onClick={() => setForm({ ...form, action: a })}
                      className={`py-2 rounded-md text-sm font-medium
                        transition-all ${
                          form.action === a
                            ? a === 'Buy'
                              ? 'bg-mint text-ink-900'
                              : 'bg-coral text-ink-900'
                            : 'text-fog-500 hover:text-fog-300'
                        }`}
                    >
                      {a}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="eyebrow block mb-2">Date</label>
                <input
                  type="date" required value={form.trade_date}
                  onChange={set('trade_date')}
                  className="field nums text-sm"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="eyebrow block mb-2">Quantity</label>
                <input
                  type="number" required min="0" step="any"
                  value={form.quantity} onChange={set('quantity')}
                  placeholder="10" className="field nums"
                />
              </div>
              <div>
                <label className="eyebrow block mb-2">Price / share</label>
                <input
                  type="number" required min="0" step="any"
                  value={form.price} onChange={set('price')}
                  placeholder="3500" className="field nums"
                />
              </div>
            </div>

            <div>
              <label className="eyebrow block mb-2">Why this trade?</label>
              <select value={form.reason} onChange={set('reason')}
                      className="field text-sm">
                {REASONS.map((r) => <option key={r}>{r}</option>)}
              </select>
            </div>

            <button type="submit" className="btn-primary w-full !mt-6">
              Log trade
            </button>
          </form>
        </Panel>

        {/* ---- trades list ---- */}
        <Panel className="p-6" delay={0.1}>
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-display text-xl font-semibold">
              Your trades
            </h2>
            <button
              onClick={runAnalysis} disabled={!canAnalyze || analyzing}
              className="btn-primary !py-2 !px-4 text-sm flex items-center gap-2"
            >
              {analyzing
                ? <Spinner />
                : <>Run analysis <ArrowIcon /></>}
            </button>
          </div>

          {loading ? (
            <div className="py-16 flex justify-center">
              <Spinner label="Loading your trades…" />
            </div>
          ) : trades.length === 0 ? (
            <div className="py-16 text-center">
              <p className="text-fog-300">No trades yet.</p>
              <p className="text-fog-500 text-sm mt-1 mb-5">
                Add your first one using the form — or see it in action instantly.
              </p>
              <button
                onClick={loadSample} disabled={loadingSample}
                className="btn-primary inline-flex items-center gap-2"
              >
                {loadingSample ? <Spinner /> : 'Load sample data & analyze'}
              </button>
            </div>
          ) : (
            <div className="space-y-1.5 max-h-[460px] overflow-y-auto pr-1">
              <AnimatePresence>
                {trades.map((t, i) => (
                  <motion.div
                    key={t.id}
                    layout
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 12 }}
                    transition={{ duration: 0.3, delay: i < 12 ? i * 0.02 : 0 }}
                    className="group flex items-center gap-3 px-3 py-2.5
                               rounded-lg hover:bg-ink-700 transition-colors"
                  >
                    {/* action dot */}
                    <span
                      className="w-1.5 h-8 rounded-full shrink-0"
                      style={{ background:
                        t.action === 'Buy' ? '#5eead4' : '#e8654f' }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-sm">
                          {t.ticker}
                        </span>
                        <span className={`text-xs font-medium ${
                          t.action === 'Buy' ? 'text-mint' : 'text-coral'
                        }`}>
                          {t.action}
                        </span>
                      </div>
                      <div className="text-xs text-fog-500 nums">
                        {t.trade_date}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="nums text-sm">
                        {t.quantity} × ₹{t.price}
                      </div>
                      <div className="nums text-xs text-fog-500">
                        ₹{t.value.toLocaleString('en-IN')}
                      </div>
                    </div>
                    <button
                      onClick={() => removeTrade(t.id)}
                      className="opacity-0 group-hover:opacity-100
                                 text-fog-500 hover:text-coral transition-all"
                    >
                      <TrashIcon />
                    </button>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </Panel>
      </div>

      <AnimatePresence>
        {error && <Toast message={error} onDone={() => setError('')} />}
      </AnimatePresence>
    </div>
  )
}

function ArrowIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2.2">
      <path d="M5 12h14M13 6l6 6-6 6"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function TrashIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.8">
      <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13h10l1-13"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
