import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Lock, UserRound } from 'lucide-react'

// Vite forwards /api to FastAPI during local development. Deployments can set
// VITE_API_URL to their HTTPS API origin without changing client code.
const API = import.meta.env.VITE_API_URL || '/api'
type AuthMode = 'login' | 'register'

function readableError(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(item => {
    if (typeof item === 'string') return item
    if (item && typeof item === 'object') {
      const issue = item as { msg?: string; loc?: unknown[] }
      const field = Array.isArray(issue.loc) ? issue.loc.filter(part => part !== 'body').join(' ') : ''
      return `${field ? `${field}: ` : ''}${issue.msg || 'Invalid value'}`
    }
    return 'Invalid request'
  }).join('. ')
  if (detail && typeof detail === 'object') {
    const value = detail as { message?: string; detail?: unknown }
    return value.message || readableError(value.detail) || 'Request failed'
  }
  return 'Request failed'
}

export default function Login({ mode }: { mode: AuthMode }) {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [organization, setOrganization] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) return
    fetch(`${API}/accounts/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(response => response.ok ? navigate('/app', { replace: true }) : localStorage.removeItem('token'))
      .catch(() => setError('Could not restore your session. Check your connection and sign in again.'))
  }, [navigate])

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(''); setLoading(true)
    try {
      const endpoint = mode === 'login' ? '/accounts/login' : '/accounts/register'
      const body = mode === 'login' ? { email, password } : { email, password, organization }
      const response = await fetch(`${API}${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(readableError(data.detail ?? data))
      if (!data.token) throw new Error('The server did not return a session token. Please try again.')
      localStorage.setItem('token', data.token); navigate('/app', { replace: true })
    } catch (cause) {
      setError(cause instanceof TypeError ? 'Network error. Is CircularLens AI running?' : (cause as Error).message)
    } finally { setLoading(false) }
  }

  const registering = mode === 'register'
  return <main className="public-page auth-page">
    <Link className="logo public-logo" to="/"><span className="brand-mark"><UserRound size={17}/></span><span>CircularLens</span><i>AI</i></Link>
    <section className="auth-card card">
      <p className="eyebrow">{registering ? 'CREATE YOUR WORKSPACE' : 'WELCOME BACK'}</p>
      <h1>{registering ? 'Start your workspace' : 'Sign in to CircularLens'}</h1>
      <p>{registering ? 'Create a private university workspace. Existing workspaces require an administrator invitation.' : 'Access your private circular intelligence workspace.'}</p>
      {error && <div className="notice" role="alert">{error}</div>}
      <form className="form" onSubmit={submit}>
        {registering && <label>Workspace name<input value={organization} onChange={event => setOrganization(event.target.value)} minLength={2} maxLength={120} required disabled={loading}/></label>}
        <label>Email address<input type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="email" required disabled={loading}/></label>
        <label>Password<input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete={registering ? 'new-password' : 'current-password'} minLength={10} required disabled={loading}/><small>Use at least 10 characters.</small></label>
        <button className="primary" disabled={loading}>{registering ? <UserRound size={16}/> : <Lock size={16}/>}{loading ? 'Please wait…' : registering ? 'Create account' : 'Sign in'}<ArrowRight size={16}/></button>
      </form>
      <p className="auth-switch">{registering ? 'Already have an account? ' : 'New to CircularLens? '}<Link to={registering ? '/login' : '/register'}>{registering ? 'Sign in' : 'Create an account'}</Link></p>
      <Link className="textlink" to="/guest">Continue in temporary Guest Mode</Link>
    </section>
  </main>
}
