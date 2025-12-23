import React, { useState, useEffect } from 'react'
import Login from './components/Login'
import Dashboard from './components/Dashboard'
import { api } from './api'

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('keystone_token') || '')
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (token) {
      // Verify token is still valid
      api.setToken(token)
      api.get('/apps/')
        .then(() => {
          setLoading(false)
        })
        .catch(() => {
          // Token invalid, clear it
          localStorage.removeItem('keystone_token')
          setToken('')
          setLoading(false)
        })
    } else {
      setLoading(false)
    }
  }, [token])

  const handleLogin = (newToken, username) => {
    localStorage.setItem('keystone_token', newToken)
    api.setToken(newToken)
    setToken(newToken)
    setUser({ username })
  }

  const handleLogout = () => {
    api.post('/auth/logout/').catch(() => {})
    localStorage.removeItem('keystone_token')
    setToken('')
    setUser(null)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!token) {
    return <Login onLogin={handleLogin} />
  }

  return <Dashboard onLogout={handleLogout} user={user} />
}
