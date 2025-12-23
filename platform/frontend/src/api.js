/**
 * Keystone API Client
 * Clean, extensible API layer for future AI features
 */

const API_BASE = import.meta.env.VITE_API_BASE || ''

class ApiClient {
  constructor() {
    this.token = null
  }

  setToken(token) {
    this.token = token
  }

  async request(method, path, data = null) {
    const url = `${API_BASE}/api${path}`
    
    const headers = {
      'Accept': 'application/json',
    }
    
    if (this.token) {
      headers['Authorization'] = `Token ${this.token}`
    }
    
    const options = { method, headers }
    
    if (data) {
      headers['Content-Type'] = 'application/json'
      options.body = JSON.stringify(data)
    }
    
    const response = await fetch(url, options)
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.error || errorData.detail || `Request failed: ${response.status}`)
    }
    
    return response.json()
  }

  get(path) {
    return this.request('GET', path)
  }

  post(path, data) {
    return this.request('POST', path, data)
  }

  put(path, data) {
    return this.request('PUT', path, data)
  }

  patch(path, data) {
    return this.request('PATCH', path, data)
  }

  delete(path) {
    return this.request('DELETE', path)
  }
}

export const api = new ApiClient()
