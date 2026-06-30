import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

export default function Login() {
  const { login, register, user } = useAuth()
  const nav = useNavigate()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) { nav('/'); return null }

  async function submit(e) {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      if (mode === 'login') await login(email, password)
      else await register(email, password)
      nav('/')
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not sign you in. Check your email and password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-brand"><span className="brand-mark">BI</span> Copilot</div>
        <h1 className="auth-title">{mode === 'login' ? 'Sign in' : 'Create account'}</h1>
        <p className="auth-sub">Ask your data questions in plain English.</p>

        <form onSubmit={submit} className="auth-form">
          <label className="field">
            <span>Email</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </label>
          <label className="field">
            <span>Password</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
          </label>
          {error && <div className="auth-error">{error}</div>}
          <button className="btn-primary" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <div className="auth-switch">
          {mode === 'login' ? (
            <>New here? <button onClick={() => { setMode('register'); setError('') }}>Create an account</button></>
          ) : (
            <>Have an account? <button onClick={() => { setMode('login'); setError('') }}>Sign in</button></>
          )}
        </div>
      </div>
    </div>
  )
}
