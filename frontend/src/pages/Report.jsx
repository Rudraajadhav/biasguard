// BiasGuard — Bias Report page
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Cell, Tooltip,
  LineChart, Line, CartesianGrid, ReferenceDot, ReferenceArea,
} from 'recharts'
import { api } from '../lib/api'
import { Panel, AnimatedNumber, BiasBar, Spinner } from '../components/UI'

export default function Report() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.report()
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="py-32 flex justify-center">
        <Spinner label="Loading your report…" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="py-24 text-center">
        <h1 className="font-display text-3xl font-semibold mb-3">
          No report yet
        </h1>
        <p className="text-fog-300 mb-6">{error}</p>
        <Link to="/app/trades" className="btn-primary inline-block">
          Go log trades & run analysis
        </Link>
      </div>
    )
  }

  const detail = report.detail || {}
  const biases = [
    {
      key: 'panic', label: 'Panic Selling', tone: 'coral',
      rate: report.panic_rate, count: report.panic_flagged,
      blurb: 'Selling into fear — dumping a position fast during a market drop, soon after buying.',
    },
    {
      key: 'fomo', label: 'FOMO Buying', tone: 'amber',
      rate: report.fomo_rate, count: report.fomo_flagged,
      blurb: 'Chasing a rally — making an oversized buy into a stock that already ran up sharply.',
    },
    {
      key: 'overtrading', label: 'Overtrading', tone: 'mint',
      rate: report.overtrading_rate, count: report.overtrading_flagged,
      blurb: 'Trading too often — high churn weeks where activity outpaces a considered strategy.',
    },
  ]

  // headline: how many distinct biases showed up at all
  const activeBiases = biases.filter((b) => b.count > 0).length

  const chartData = biases.map((b) => ({
    name: b.label.split(' ')[0],
    rate: b.rate,
    fill: { coral: '#e8654f', amber: '#e0a740', mint: '#5eead4' }[b.tone],
  }))

  return (
    <div className="space-y-8">
      {/* header */}
      <div>
        <p className="eyebrow mb-2">Your behavioral report</p>
        <h1 className="font-display text-4xl font-semibold">Bias Report</h1>
        <p className="text-fog-300 text-sm mt-2">
          Generated {new Date(report.run_at).toLocaleString('en-IN')}
        </p>
      </div>

      {/* headline panel */}
      <Panel className="p-8 relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none"
             style={{ background:
               'radial-gradient(ellipse 50% 80% at 85% 50%, rgba(94,234,212,0.07), transparent)' }} />
        <div className="relative flex items-end justify-between flex-wrap gap-6">
          <div>
            <p className="eyebrow mb-3">Behavioral patterns detected</p>
            <div className="flex items-baseline gap-3">
              <span className="font-display text-7xl font-semibold text-mint">
                <AnimatedNumber value={activeBiases} />
              </span>
              <span className="text-fog-300 text-lg">of 3</span>
            </div>
            <p className="text-fog-300 text-sm mt-3 max-w-md leading-relaxed">
              {activeBiases === 0
                ? 'No behavioral biases flagged in your trades. Disciplined trading.'
                : `We found ${activeBiases} bias pattern${activeBiases > 1 ? 's' : ''} in your trade history. The breakdown is below.`}
            </p>
          </div>

          {/* mini chart */}
          <div className="w-[280px] h-[140px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}
                        margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
                <XAxis dataKey="name" stroke="#6b7280"
                       tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }}
                       axisLine={false} tickLine={false} />
                <YAxis stroke="#6b7280"
                       tick={{ fontSize: 10, fontFamily: 'IBM Plex Mono' }}
                       axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                  contentStyle={{
                    background: '#161a22', border: '1px solid #2b323f',
                    borderRadius: 8, fontSize: 12,
                  }}
                  formatter={(v) => [`${v.toFixed(1)}%`, 'rate']}
                />
                <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
                  {chartData.map((d, i) => (
                    <Cell key={i} fill={d.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </Panel>

      {/* per-bias breakdown */}
      <div className="grid md:grid-cols-3 gap-5">
        {biases.map((b, i) => (
          <Panel key={b.key} className="p-6" delay={0.1 + i * 0.08}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-lg font-semibold">
                {b.label}
              </h3>
              <span className="w-2.5 h-2.5 rounded-full"
                    style={{ background: {
                      coral: '#e8654f', amber: '#e0a740', mint: '#5eead4',
                    }[b.tone] }} />
            </div>

            <div className="flex items-baseline gap-2 mb-1">
              <span className="font-display text-4xl font-semibold"
                    style={{ color: {
                      coral: '#e8654f', amber: '#e0a740', mint: '#5eead4',
                    }[b.tone] }}>
                <AnimatedNumber value={b.rate} decimals={1} suffix="%" />
              </span>
            </div>
            <p className="text-xs text-fog-500 mb-4">
              {b.count} trade{b.count === 1 ? '' : 's'} flagged
            </p>

            <BiasBar label="" value={b.rate} tone={b.tone} />

            <p className="text-xs text-fog-500 leading-relaxed mt-4">
              {b.blurb}
            </p>
          </Panel>
        ))}
      </div>

      {/* cost of bias */}
      <CostOfBias detail={detail} />

      {/* cost of bias, drawn */}
      <BiasTimeline detail={detail} />

      {/* flagged trades detail */}
      <FlaggedTrades detail={detail} />

      <div className="text-center pt-4">
        <Link to="/app/trades"
              className="btn-ghost inline-block">
          Back to trade log
        </Link>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------
// FlaggedTrades — expandable detail of individual flagged trades
// -----------------------------------------------------------------
function FlaggedTrades({ detail }) {
  const panic = detail.panic?.flags || []
  const fomo = detail.fomo?.flags || []

  if (panic.length === 0 && fomo.length === 0) {
    return (
      <Panel className="p-8 text-center" delay={0.3}>
        <p className="text-fog-300">
          No individual trades were flagged. Nothing to review.
        </p>
      </Panel>
    )
  }

  return (
    <Panel className="p-6" delay={0.35}>
      <h2 className="font-display text-xl font-semibold mb-1">
        Flagged trades
      </h2>
      <p className="text-fog-500 text-sm mb-5">
        The specific trades that triggered each pattern.
      </p>

      <div className="space-y-2">
        {panic.map((f, i) => (
          <FlagRow key={`p${i}`} flag={f} tone="coral" type="Panic sell" />
        ))}
        {fomo.map((f, i) => (
          <FlagRow key={`f${i}`} flag={f} tone="amber" type="FOMO buy" />
        ))}
      </div>
    </Panel>
  )
}

function FlagRow({ flag, tone, type }) {
  const color = { coral: '#e8654f', amber: '#e0a740' }[tone]
  const ticker = flag.ticker || '—'
  const date = flag.date
    ? new Date(flag.date).toLocaleDateString('en-IN')
    : '—'
  const confidence = flag.panic_confidence ?? flag.fomo_confidence ?? 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.3 }}
      className="flex items-center gap-4 px-4 py-3 rounded-lg
                 bg-ink-900 border border-ink-600"
    >
      <span className="px-2 py-1 rounded text-[11px] font-semibold"
            style={{ background: `${color}1a`, color }}>
        {type}
      </span>
      <span className="font-mono font-semibold text-sm">{ticker}</span>
      <span className="nums text-xs text-fog-500">{date}</span>
      <div className="flex-1" />
      <div className="text-right">
        <div className="text-[11px] text-fog-500 uppercase tracking-wider">
          Confidence
        </div>
        <div className="nums text-sm font-semibold" style={{ color }}>
          {Number(confidence).toFixed(0)}/100
        </div>
      </div>
    </motion.div>
  )
}


// -----------------------------------------------------------------
// CostOfBias — what each flagged bias actually cost (forward view)
// -----------------------------------------------------------------
function CostOfBias({ detail }) {
  const costs = detail.costs
  if (!costs) return null

  const inr = (n) =>
    '₹' + Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })

  const roundTrips = costs.round_trips || []
  const hasAny =
    (costs.panic_missed_recovery || 0) > 0 ||
    (costs.fomo_chase_loss || 0) > 0 ||
    roundTrips.length > 0
  if (!hasAny) return null

  return (
    <Panel className="p-6" delay={0.3}>
      <h2 className="font-display text-xl font-semibold mb-1">
        What these biases cost
      </h2>
      <p className="text-fog-500 text-sm mb-5">
        Measured against holding {costs.horizon_trading_days || 30} trading days —
        these aren't just patterns, they have a price.
      </p>

      {roundTrips.map((rt, i) => (
        <div key={i} className="mb-5 p-5 rounded-lg border"
             style={{ borderColor: '#e8654f44', background: '#e8654f0d' }}>
          <p className="text-[11px] uppercase tracking-wider text-fog-500 mb-2">
            Panic &rarr; FOMO round trip
          </p>
          <p className="text-sm text-fog-300 leading-relaxed">
            Sold <span className="font-mono font-semibold">{rt.ticker}</span> at{' '}
            {inr(rt.sold_price)} on {rt.sold_date} (panic), then rebought it at{' '}
            {inr(rt.rebought_price)} on {rt.rebought_date} (FOMO) —{' '}
            {Number(rt.shares).toFixed(0)} shares.
          </p>
          <p className="font-display text-3xl font-semibold mt-3" style={{ color: '#e8654f' }}>
            {inr(rt.cost)} lost
          </p>
          <p className="text-xs text-fog-500 mt-1">
            sold low, bought the same stock back high
          </p>
        </div>
      ))}

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="p-4 rounded-lg bg-ink-900 border border-ink-600">
          <p className="text-xs text-fog-500 mb-1">Panic selling — missed recovery</p>
          <p className="font-display text-2xl font-semibold" style={{ color: '#e8654f' }}>
            {inr(costs.panic_missed_recovery)}
          </p>
          <p className="text-[11px] text-fog-500 mt-1">vs. holding through the rebound</p>
        </div>
        <div className="p-4 rounded-lg bg-ink-900 border border-ink-600">
          <p className="text-xs text-fog-500 mb-1">FOMO buying — chase loss</p>
          <p className="font-display text-2xl font-semibold" style={{ color: '#e0a740' }}>
            {inr(costs.fomo_chase_loss)}
          </p>
          <p className="text-[11px] text-fog-500 mt-1">after buying into the run-up</p>
        </div>
      </div>
    </Panel>
  )
}


// -----------------------------------------------------------------
// BiasTimeline — the round trip drawn on the stock's real price line
// -----------------------------------------------------------------
function BiasTimeline({ detail }) {
  const timelines = detail.costs?.timelines || []
  if (timelines.length === 0) return null
  return (
    <Panel className="p-6" delay={0.32}>
      <h2 className="font-display text-xl font-semibold mb-1">
        The round trip, drawn
      </h2>
      <p className="text-fog-500 text-sm mb-5">
        Your sell and buy on the stock's actual price. The shaded gap is the move you sat out.
      </p>
      {timelines.map((tl, i) => <TimelineChart key={i} tl={tl} />)}
    </Panel>
  )
}

function TimelineChart({ tl }) {
  if (!tl || !tl.series || !tl.sell || !tl.buy) return null
  const inr = (n) =>
    '₹' + Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })
  return (
    <div className="mb-4">
      <div className="flex items-baseline justify-between mb-3">
        <span className="font-mono font-semibold text-sm">{tl.ticker}</span>
        <span className="text-xs text-fog-500">
          sold {inr(tl.sell.price)} &rarr; bought {inr(tl.buy.price)} &middot; {inr(tl.cost)} lost
        </span>
      </div>
      <div className="w-full h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={tl.series} margin={{ top: 12, right: 18, bottom: 0, left: -8 }}>
            <CartesianGrid stroke="#2b323f" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" stroke="#6b7280" minTickGap={48}
                   tick={{ fontSize: 10, fontFamily: 'IBM Plex Mono' }}
                   axisLine={false} tickLine={false} />
            <YAxis stroke="#6b7280" domain={['auto', 'auto']} width={50}
                   tick={{ fontSize: 10, fontFamily: 'IBM Plex Mono' }}
                   axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: '#161a22', border: '1px solid #2b323f',
                              borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: '#9aa4b2' }}
              formatter={(v) => [inr(v), 'close']} />
            <ReferenceArea x1={tl.sell.date} x2={tl.buy.date}
                           fill="#e8654f" fillOpacity={0.07} stroke="none" />
            <Line type="monotone" dataKey="close" stroke="#5eead4"
                  strokeWidth={1.8} dot={false} />
            <ReferenceDot x={tl.sell.date} y={tl.sell.price} r={6}
                          fill="#e8654f" stroke="#0b0e14" strokeWidth={2}
                          label={{ value: 'SOLD', position: 'bottom',
                                   fill: '#e8654f', fontSize: 10, fontWeight: 600 }} />
            <ReferenceDot x={tl.buy.date} y={tl.buy.price} r={6}
                          fill="#e0a740" stroke="#0b0e14" strokeWidth={2}
                          label={{ value: 'BOUGHT', position: 'top',
                                   fill: '#e0a740', fontSize: 10, fontWeight: 600 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
