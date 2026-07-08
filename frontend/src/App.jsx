// BiasGuard — root app + routing
import {
  BrowserRouter, Routes, Route, Navigate,
} from 'react-router-dom'
import { api } from './lib/api'
import Auth from './pages/Auth'
import AppShell from './pages/AppShell'
import Trades from './pages/Trades'
import Report from './pages/Report'

// Gate — redirects to /auth if no token
function Protected({ children }) {
  return api.isLoggedIn() ? children : <Navigate to="/" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* public: auth screen is the landing */}
        <Route
          path="/"
          element={
            api.isLoggedIn()
              ? <Navigate to="/app/trades" replace />
              : <Auth />
          }
        />

        {/* protected app */}
        <Route
          path="/app"
          element={<Protected><AppShell /></Protected>}
        >
          <Route index element={<Navigate to="/app/trades" replace />} />
          <Route path="trades" element={<Trades />} />
          <Route path="report" element={<Report />} />
        </Route>

        {/* fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
