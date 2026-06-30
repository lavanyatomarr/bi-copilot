import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

export default function AppShell({ children }) {
  const { user, logout } = useAuth()
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">BI</span>
          <span className="brand-name">Copilot</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end className="nav-link">Workspace</NavLink>
          <NavLink to="/datasets" className="nav-link">Datasets</NavLink>
          <NavLink to="/history" className="nav-link">History</NavLink>
        </nav>
        <div className="sidebar-foot">
          <div className="user-email" title={user?.email}>{user?.email}</div>
          <button className="btn-ghost" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  )
}
