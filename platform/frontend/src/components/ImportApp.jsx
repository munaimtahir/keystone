import React, { useState } from 'react'
import { api } from '../api'

export default function ImportApp({ onClose, onImport }) {
  const [name, setName] = useState('')
  const [gitUrl, setGitUrl] = useState('')
  const [branch, setBranch] = useState('main')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const app = await api.post('/apps/', {
        name: name.trim(),
        git_url: gitUrl.trim(),
        branch: branch.trim() || 'main',
      })
      onImport(app)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="card w-full max-w-lg">
        <div className="p-6 border-b border-gray-200">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-900">Import Repository</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="label">App Name</label>
            <input
              type="text"
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-django-app"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              Will be used in URL: <code className="bg-gray-100 px-1 rounded">/{name || 'app-name'}</code>
            </p>
          </div>

          <div>
            <label className="label">GitHub Repository URL</label>
            <input
              type="url"
              className="input"
              value={gitUrl}
              onChange={(e) => setGitUrl(e.target.value)}
              placeholder="https://github.com/username/repo"
              required
            />
          </div>

          <div>
            <label className="label">Branch</label>
            <input
              type="text"
              className="input"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              placeholder="main"
            />
          </div>

          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !name || !gitUrl}
            >
              {loading ? 'Importing...' : 'Import Repository'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
