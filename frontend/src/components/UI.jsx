// BiasGuard — shared UI components
import { useEffect, useRef, useState } from 'react'
import { motion, useInView, animate } from 'framer-motion'

// -----------------------------------------------------------------
// Logo — a small geometric mark + wordmark
// -----------------------------------------------------------------
export function Logo({ size = 28 }) {
  return (
    <div className="flex items-center gap-2.5 select-none">
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
        {/* a shield-ish hexagon with an inner pulse line */}
        <path
          d="M16 2 L28 9 V23 L16 30 L4 23 V9 Z"
          stroke="#5eead4" strokeWidth="1.5" fill="#5eead40d"
        />
        <path
          d="M9 17 L13 17 L15 11 L18 21 L20 17 L23 17"
          stroke="#5eead4" strokeWidth="1.8"
          strokeLinecap="round" strokeLinejoin="round"
        />
      </svg>
      <span className="font-display font-semibold text-[19px] tracking-tight">
        BiasGuard
      </span>
    </div>
  )
}

// -----------------------------------------------------------------
// AnimatedNumber — counts up to a value when scrolled into view
// -----------------------------------------------------------------
export function AnimatedNumber({ value, decimals = 0, suffix = '', duration = 1.1 }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true })
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    if (!inView) return
    const controls = animate(0, value, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setDisplay(v),
    })
    return () => controls.stop()
  }, [inView, value, duration])

  return (
    <span ref={ref} className="nums">
      {display.toFixed(decimals)}{suffix}
    </span>
  )
}

// -----------------------------------------------------------------
// BiasBar — a horizontal bar that fills on enter, color-coded
// -----------------------------------------------------------------
export function BiasBar({ label, value, max = 100, tone = 'mint', caption }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true })
  const pct = Math.min(100, (value / max) * 100)

  const toneColor = {
    mint: '#5eead4',
    amber: '#e0a740',
    coral: '#e8654f',
  }[tone]

  return (
    <div ref={ref} className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-fog-100">{label}</span>
        <span className="nums text-sm font-semibold" style={{ color: toneColor }}>
          {value.toFixed(1)}%
        </span>
      </div>
      <div className="h-2 rounded-full bg-ink-600 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: toneColor }}
          initial={{ width: 0 }}
          animate={inView ? { width: `${pct}%` } : {}}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
        />
      </div>
      {caption && (
        <p className="text-xs text-fog-500 leading-relaxed">{caption}</p>
      )}
    </div>
  )
}

// -----------------------------------------------------------------
// Panel — the standard surface container, with optional reveal
// -----------------------------------------------------------------
export function Panel({ children, className = '', delay = 0 }) {
  return (
    <motion.div
      className={`panel ${className}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1], delay }}
    >
      {children}
    </motion.div>
  )
}

// -----------------------------------------------------------------
// Toast — transient message (errors, confirmations)
// -----------------------------------------------------------------
export function Toast({ message, tone = 'coral', onDone }) {
  useEffect(() => {
    if (!message) return
    const t = setTimeout(onDone, 4000)
    return () => clearTimeout(t)
  }, [message, onDone])

  if (!message) return null
  const border = tone === 'coral' ? 'border-coral' : 'border-mint'
  const text = tone === 'coral' ? 'text-coral' : 'text-mint'

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20 }}
      className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50
                  bg-ink-700 border ${border} ${text}
                  rounded-lg px-5 py-3 text-sm font-medium shadow-panel`}
    >
      {message}
    </motion.div>
  )
}

// -----------------------------------------------------------------
// Spinner — minimal loading indicator
// -----------------------------------------------------------------
export function Spinner({ label }) {
  return (
    <div className="flex items-center gap-3 text-fog-300">
      <motion.div
        className="w-4 h-4 rounded-full border-2 border-ink-500 border-t-mint"
        animate={{ rotate: 360 }}
        transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
      />
      {label && <span className="text-sm">{label}</span>}
    </div>
  )
}
