import React from 'react'

const STATUS_STYLES = {
  imported: 'bg-gray-100 text-gray-700',
  preparing: 'bg-yellow-100 text-yellow-700',
  prepared: 'bg-blue-100 text-blue-700',
  deploying: 'bg-purple-100 text-purple-700',
  running: 'bg-emerald-100 text-emerald-700',
  stopped: 'bg-gray-100 text-gray-700',
  failed: 'bg-red-100 text-red-700',
}

export default function AppCard({ app, selected, onClick }) {
  return (
    <div
      onClick={onClick}
      className={`card p-4 cursor-pointer transition-all hover:shadow-md ${
        selected ? 'ring-2 ring-primary-500 border-primary-500' : ''
      }`}
    >
      <div className="flex justify-between items-start">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">{app.name}</h3>
          <p className="text-sm text-gray-500 truncate mt-0.5">{app.git_url}</p>
        </div>
        <span className={`px-2 py-1 text-xs font-medium rounded-full ${STATUS_STYLES[app.status] || STATUS_STYLES.imported}`}>
          {app.status}
        </span>
      </div>

      {app.status === 'running' && (
        <div className="mt-3 flex items-center text-sm text-emerald-600">
          <span className="w-2 h-2 bg-emerald-500 rounded-full mr-2 animate-pulse"></span>
          Live at <code className="ml-1 bg-emerald-50 px-1.5 py-0.5 rounded">/{app.slug}</code>
        </div>
      )}

      {app.status === 'failed' && app.error_message && (
        <p className="mt-2 text-xs text-red-600 truncate">{app.error_message}</p>
      )}
    </div>
  )
}
