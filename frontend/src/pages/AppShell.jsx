// BiasGuard — authenticated app shell with responsive nav
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { api } from '../lib/api'
import { Logo } from '../components/UI'

const NAV = [
  { to: '/app/trades', label: 'Trade Log', icon: LedgerIcon },
  { to: '/app/report', label: 'Bias Report', icon: PulseIcon },
]

export default function AppShell() {
  const navigate = useNavigate()

  function logout() {
    api.logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen md:flex">
      {/* Nav: horizontal top bar on mobile, fixed sidebar on desktop */}
      <aside className="z-20 bg-ink-800 border-ink-600
                        flex items-center justify-between gap-2 px-4 py-3 border-b
                        md:flex-col md:items-stretch md:justify-start md:gap-0
                        md:w-60 md:h-full md:p-5 md:fixed md:border-b-0 md:border-r">
        <div className="md:px-2 md:py-3">
          <Logo size={26} />
        </div>

        <nav className="flex items-center gap-1
                        md:flex-col md:items-stretch md:mt-8 md:space-y-1 md:flex-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to} to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm
                 font-medium transition-all ${
                   isActive
                     ? 'bg-ink-700 text-mint'
                     : 'text-fog-300 hover:text-fog-100 hover:bg-ink-700/50'
                 }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon active={isActive} />
                  <span className="hidden sm:inline">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <button onClick={logout}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg
                           text-sm font-medium text-fog-500
                           hover:text-coral transition-colors">
          <LogoutIcon />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 md:ml-60 grid-texture min-h-screen">
        <motion.div
          key={window.location.pathname}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
          className="max-w-5xl mx-auto px-5 py-8 md:px-10 md:py-12"
        >
          <Outlet />
        </motion.div>
      </main>
    </div>
  )
}

// --- inline icons (kept tiny, stroke-based) ----------------------
function LedgerIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke={active ? '#5eead4' : 'currentColor'} strokeWidth="1.8">
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M9 8h6M9 12h6M9 16h3" strokeLinecap="round" />
    </svg>
  )
}
function PulseIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke={active ? '#5eead4' : 'currentColor'} strokeWidth="1.8">
      <path d="M3 12h4l3-8 4 16 3-8h4"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function LogoutIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.8">
      <path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4M9 12h11M16 8l4 4-4 4"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
