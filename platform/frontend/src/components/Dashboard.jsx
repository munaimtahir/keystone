import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import ImportApp from './ImportApp'
import AppCard from './AppCard'
import AppDetail from './AppDetail'

export default function Dashboard({ onLogout, user }) {
  const [apps, setApps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [selectedApp, setSelectedApp] = useState(null)

  const loadApps = useCallback(async () => {
    try {
      const data = await api.get('/apps/')
      setApps(data)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadApps()
    // Poll for updates every 5 seconds
    const interval = setInterval(loadApps, 5000)
    return () => clearInterval(interval)
  }, [loadApps])

  const handleAppImported = (newApp) => {
    setApps(prev => [newApp, ...prev])
    setShowImport(false)
    setSelectedApp(newApp)
  }

  const handleAppUpdated = (updatedApp) => {
    setApps(prev => prev.map(a => a.id === updatedApp.id ? updatedApp : a))
    setSelectedApp(updatedApp)
  }

  const handleAppDeleted = (appId) => {
    setApps(prev => prev.filter(a => a.id !== appId))
    setSelectedApp(null)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
                </svg>
              </div>
              <h1 className="text-xl font-bold text-gray-900">Keystone</h1>
            </div>

            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">
                {user?.username || 'admin'}
              </span>
              <button
                onClick={onLogout}
                className="btn btn-secondary text-sm"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg flex justify-between items-center">
            <span>{error}</span>
            <button onClick={() => setError('')} className="text-red-500 hover:text-red-700">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Apps List */}
          <div className="lg:col-span-1">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Your Apps</h2>
              <button
                onClick={() => setShowImport(true)}
                className="btn btn-primary text-sm"
              >
                <svg className="w-4 h-4 mr-1.5 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Import Repo
              </button>
            </div>

            {loading ? (
              <div className="card p-8 text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
                <p className="text-gray-500 mt-2">Loading apps...</p>
              </div>
            ) : apps.length === 0 ? (
              <div className="card p-8 text-center">
                <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                </div>
                <h3 className="text-gray-900 font-medium mb-1">No apps yet</h3>
                <p className="text-gray-500 text-sm mb-4">Import your first GitHub repository</p>
                <button
                  onClick={() => setShowImport(true)}
                  className="btn btn-primary"
                >
                  Import Repository
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {apps.map(app => (
                  <AppCard
                    key={app.id}
                    app={app}
                    selected={selectedApp?.id === app.id}
                    onClick={() => setSelectedApp(app)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* App Detail */}
          <div className="lg:col-span-2">
            {selectedApp ? (
              <AppDetail
                app={selectedApp}
                onUpdate={handleAppUpdated}
                onDelete={handleAppDeleted}
              />
            ) : (
              <div className="card p-12 text-center">
                <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
                  </svg>
                </div>
                <h3 className="text-gray-900 font-medium mb-1">Select an app</h3>
                <p className="text-gray-500 text-sm">Choose an app from the list to view details and manage deployment</p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Import Modal */}
      {showImport && (
        <ImportApp
          onClose={() => setShowImport(false)}
          onImport={handleAppImported}
        />
      )}
    </div>
  )
}
