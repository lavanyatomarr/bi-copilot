import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import { DatasetProvider } from './datasets.jsx'
import AppShell from './components/AppShell.jsx'
import Login from './pages/Login.jsx'
import Workspace from './pages/Workspace.jsx'
import Datasets from './pages/Datasets.jsx'
import History from './pages/History.jsx'

function Protected({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="center-screen">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <Protected>
            <DatasetProvider>
              <AppShell>
                <Routes>
                  <Route path="/" element={<Workspace />} />
                  <Route path="/datasets" element={<Datasets />} />
                  <Route path="/history" element={<History />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </AppShell>
            </DatasetProvider>
          </Protected>
        }
      />
    </Routes>
  )
}
