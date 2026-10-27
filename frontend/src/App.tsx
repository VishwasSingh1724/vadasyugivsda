import { Suspense, lazy } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useLogout, useMe } from './api/auth'
import { ErrorBanner } from './components/ui'
import { LoginPage } from './pages/LoginPage'

// Route-level code splitting keeps the charting library out of the initial bundle.
const DecisionPage = lazy(() =>
  import('./pages/DecisionPage').then((m) => ({ default: m.DecisionPage })),
)
const AccuracyPage = lazy(() =>
  import('./pages/AccuracyPage').then((m) => ({ default: m.AccuracyPage })),
)

export default function App() {
  const me = useMe()
  const logout = useLogout()
  if (me.isPending) return <div className="skeleton" aria-busy="true" aria-label="Loading" />
  if (me.isError) return <ErrorBanner error={me.error} onRetry={() => me.refetch()} />
  if (!me.data) return <LoginPage />

  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <div className="brand">
          WindWatch <span className="muted">GB day-ahead wind</span>
        </div>
        <nav aria-label="Primary">
          <NavLink to="/decision">Decision</NavLink>
          <NavLink to="/accuracy">Accuracy</NavLink>
        </nav>
        <div className="user">
          <button onClick={() => window.print()}>Print / PDF</button>
          <span className="muted">{me.data.username}</span>
          <button onClick={() => logout.mutate()} disabled={logout.isPending}>
            Sign out
          </button>
        </div>
      </header>
      <main id="main">
        <Suspense fallback={<div className="skeleton" aria-busy="true" />}>
          <Routes>
            <Route path="/decision" element={<DecisionPage />} />
            <Route path="/accuracy" element={<AccuracyPage />} />
            <Route path="*" element={<Navigate to="/decision" replace />} />
          </Routes>
        </Suspense>
      </main>
      <footer className="muted small">
        Data: Elexon BMRS (FUELHH actuals, WINDFOR forecasts), national GB wind. Hourly comparison;
        times Europe/London.
      </footer>
    </>
  )
}
