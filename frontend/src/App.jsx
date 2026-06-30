import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import AppShell from './components/AppShell.jsx'
import Login from './pages/Login.jsx'
import Workspace from './pages/Workspace.jsx'

function Protected({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="center-screen">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

// Simple placeholders for pages we build in later sub-steps.
function ComingSoon({ title }) {
  return (
    <div className="page">
      <header className="page-head"><h1 className="page-title">{title}</h1></header>
      <div className="empty-card"><p>This screen arrives in the next build step.</p></div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <Protected>
            <AppShell>
              <Routes>
                <Route path="/" element={<Workspace />} />
                <Route path="/datasets" element={<ComingSoon title="Datasets" />} />
                <Route path="/history" element={<ComingSoon title="History" />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </AppShell>
          </Protected>
        }
      />
    </Routes>
  )
}
