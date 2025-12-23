import React, { useState } from 'react'
import { api } from '../api'

export default function AppDetail({ app, onUpdate, onDelete }) {
  const [loading, setLoading] = useState('')
  const [logs, setLogs] = useState('')
  const [showLogs, setShowLogs] = useState(false)
  const [showEnv, setShowEnv] = useState(false)
  const [envText, setEnvText] = useState(JSON.stringify(app.env_vars || {}, null, 2))
  const [containerPort, setContainerPort] = useState(app.container_port || 8000)

  const handlePrepare = async () => {
    setLoading('prepare')
    try {
      const updated = await api.post(`/apps/${app.id}/prepare/`)
      onUpdate({ ...app, ...updated, status: 'prepared' })
    } catch (err) {
      onUpdate({ ...app, status: 'failed', error_message: err.message })
    } finally {
      setLoading('')
    }
  }

  const handleDeploy = async () => {
    setLoading('deploy')
    try {
      // Update env vars and port first
      let envVars = {}
      try {
        envVars = JSON.parse(envText)
      } catch {}
      
      await api.patch(`/apps/${app.id}/`, {
        env_vars: envVars,
        container_port: containerPort
      })
      
      const updated = await api.post(`/apps/${app.id}/deploy/`)
      onUpdate({ ...app, ...updated, status: 'running' })
    } catch (err) {
      onUpdate({ ...app, status: 'failed', error_message: err.message })
    } finally {
      setLoading('')
    }
  }

  const handleStop = async () => {
    setLoading('stop')
    try {
      await api.post(`/apps/${app.id}/stop/`)
      onUpdate({ ...app, status: 'stopped' })
    } catch (err) {
      onUpdate({ ...app, error_message: err.message })
    } finally {
      setLoading('')
    }
  }

  const handleViewLogs = async () => {
    setLoading('logs')
    try {
      const data = await api.get(`/apps/${app.id}/logs/`)
      setLogs(data.logs || 'No logs available')
      setShowLogs(true)
    } catch (err) {
      setLogs(`Error: ${err.message}`)
      setShowLogs(true)
    } finally {
      setLoading('')
    }
  }

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to delete "${app.name}"? This cannot be undone.`)) {
      return
    }
    setLoading('delete')
    try {
      await api.delete(`/apps/${app.id}/`)
      onDelete(app.id)
    } catch (err) {
      alert(`Delete failed: ${err.message}`)
    } finally {
      setLoading('')
    }
  }

  const getStepNumber = () => {
    switch (app.status) {
      case 'imported': return 1
      case 'preparing': return 1
      case 'prepared': return 2
      case 'deploying': return 3
      case 'running': return 3
      case 'stopped': return 3
      case 'failed': return app.traefik_rule ? 2 : 1
      default: return 1
    }
  }

  const step = getStepNumber()

  return (
    <div className="card">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{app.name}</h2>
            <p className="text-gray-500 mt-1">{app.git_url}</p>
          </div>
          <button
            onClick={handleDelete}
            disabled={loading === 'delete'}
            className="text-red-500 hover:text-red-700 p-2"
            title="Delete app"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>

        {app.error_message && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
            <strong>Error:</strong> {app.error_message}
          </div>
        )}
      </div>

      {/* Workflow Steps */}
      <div className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Deployment Workflow</h3>
        
        <div className="space-y-6">
          {/* Step 1: Import (Done) */}
          <div className={`flex items-start ${step >= 1 ? 'opacity-100' : 'opacity-50'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step > 1 ? 'bg-emerald-500 text-white' : step === 1 ? 'bg-primary-500 text-white' : 'bg-gray-200 text-gray-500'}`}>
              {step > 1 ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : '1'}
            </div>
            <div className="ml-4 flex-1">
              <h4 className="font-medium text-gray-900">Import Repository</h4>
              <p className="text-sm text-gray-500">Repository imported from GitHub</p>
              <p className="text-sm text-gray-600 mt-1">
                Branch: <code className="bg-gray-100 px-1.5 py-0.5 rounded">{app.branch}</code>
              </p>
            </div>
          </div>

          {/* Step 2: Prepare */}
          <div className={`flex items-start ${step >= 2 ? 'opacity-100' : 'opacity-50'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step > 2 ? 'bg-emerald-500 text-white' : step === 2 ? 'bg-primary-500 text-white' : 'bg-gray-200 text-gray-500'}`}>
              {step > 2 ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : '2'}
            </div>
            <div className="ml-4 flex-1">
              <h4 className="font-medium text-gray-900">Prepare for Traefik</h4>
              <p className="text-sm text-gray-500">Clone repo, detect structure, configure routing</p>
              
              {step === 1 && (
                <button
                  onClick={handlePrepare}
                  disabled={loading === 'prepare'}
                  className="btn btn-primary mt-3"
                >
                  {loading === 'prepare' ? (
                    <span className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Preparing...
                    </span>
                  ) : 'Prepare Repository'}
                </button>
              )}
              
              {app.traefik_rule && (
                <p className="text-sm text-emerald-600 mt-2">
                  ✓ Routing configured: <code className="bg-emerald-50 px-1.5 py-0.5 rounded">{app.traefik_rule}</code>
                </p>
              )}
            </div>
          </div>

          {/* Step 3: Deploy */}
          <div className={`flex items-start ${step >= 3 || step === 2 ? 'opacity-100' : 'opacity-50'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${app.status === 'running' ? 'bg-emerald-500 text-white' : step >= 2 ? 'bg-primary-500 text-white' : 'bg-gray-200 text-gray-500'}`}>
              {app.status === 'running' ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : '3'}
            </div>
            <div className="ml-4 flex-1">
              <h4 className="font-medium text-gray-900">Deploy Application</h4>
              <p className="text-sm text-gray-500">Build Docker image and run with Traefik</p>
              
              {step >= 2 && (
                <div className="mt-4 space-y-4">
                  {/* Configuration */}
                  <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                    <div>
                      <label className="label">Container Port</label>
                      <input
                        type="number"
                        className="input w-32"
                        value={containerPort}
                        onChange={(e) => setContainerPort(parseInt(e.target.value) || 8000)}
                        min="1"
                        max="65535"
                      />
                      <p className="text-xs text-gray-500 mt-1">Port your app listens on (Django default: 8000)</p>
                    </div>
                    
                    <div>
                      <button
                        onClick={() => setShowEnv(!showEnv)}
                        className="text-sm text-primary-600 hover:text-primary-700"
                      >
                        {showEnv ? '▼ Hide' : '▶ Show'} Environment Variables
                      </button>
                      
                      {showEnv && (
                        <div className="mt-2">
                          <textarea
                            className="input font-mono text-sm"
                            rows={4}
                            value={envText}
                            onChange={(e) => setEnvText(e.target.value)}
                            placeholder='{"DEBUG": "0", "SECRET_KEY": "..."}'
                          />
                          <p className="text-xs text-gray-500 mt-1">JSON format: {`{"key": "value"}`}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-wrap gap-3">
                    {app.status !== 'running' && (
                      <button
                        onClick={handleDeploy}
                        disabled={loading === 'deploy'}
                        className="btn btn-success"
                      >
                        {loading === 'deploy' ? (
                          <span className="flex items-center">
                            <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                            Deploying...
                          </span>
                        ) : (
                          <>
                            <svg className="w-4 h-4 mr-1.5 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            Deploy Now
                          </>
                        )}
                      </button>
                    )}
                    
                    {app.status === 'running' && (
                      <>
                        <button
                          onClick={handleDeploy}
                          disabled={loading === 'deploy'}
                          className="btn btn-primary"
                        >
                          {loading === 'deploy' ? 'Redeploying...' : 'Redeploy'}
                        </button>
                        <button
                          onClick={handleStop}
                          disabled={loading === 'stop'}
                          className="btn btn-danger"
                        >
                          {loading === 'stop' ? 'Stopping...' : 'Stop'}
                        </button>
                      </>
                    )}
                    
                    <button
                      onClick={handleViewLogs}
                      disabled={loading === 'logs'}
                      className="btn btn-secondary"
                    >
                      {loading === 'logs' ? 'Loading...' : 'View Logs'}
                    </button>
                  </div>

                  {app.status === 'running' && (
                    <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                      <p className="text-emerald-800 font-medium flex items-center">
                        <span className="w-2 h-2 bg-emerald-500 rounded-full mr-2 animate-pulse"></span>
                        Application is running!
                      </p>
                      <p className="text-emerald-700 text-sm mt-1">
                        Access at: <code className="bg-emerald-100 px-2 py-0.5 rounded font-medium">http://YOUR_VPS_IP/{app.slug}</code>
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Logs Modal */}
      {showLogs && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="card w-full max-w-4xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b border-gray-200 flex justify-between items-center">
              <h3 className="font-semibold text-gray-900">Container Logs - {app.name}</h3>
              <button onClick={() => setShowLogs(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4 bg-gray-900">
              <pre className="text-sm text-gray-100 font-mono whitespace-pre-wrap">{logs}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
