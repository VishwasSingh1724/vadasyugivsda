import { useState, type FormEvent } from 'react'
import { useLogin } from '../api/auth'
import { ApiError } from '../api/client'

export function LoginPage() {
  const login = useLogin()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    login.mutate({ username, password })
  }
  const error = login.error
  const message =
    error instanceof ApiError && error.status === 401
      ? 'Incorrect username or password.'
      : error?.message

  return (
    <div className="login-wrap">
      <form className="card login" onSubmit={submit}>
        <h1>WindWatch</h1>
        <p className="muted">Sign in to view day-ahead wind forecasts.</p>
        <label>
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {message && (
          <div className="banner error" role="alert">
            {message}
          </div>
        )}
        <button className="primary" type="submit" disabled={login.isPending}>
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
