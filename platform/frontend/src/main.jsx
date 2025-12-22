import React from 'react'
import { createRoot } from 'react-dom/client'

function Modal({ title, onClose, children, width = 900 }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,.35)",
        display: "grid",
        placeItems: "center",
        padding: 16,
        zIndex: 50,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(100%, " + width + "px)",
          background: "#fff",
          borderRadius: 14,
          border: "1px solid #eee",
          boxShadow: "0 10px 30px rgba(0,0,0,.15)",
          overflow: "hidden",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderBottom: "1px solid #f0f0f0" }}>
          <div style={{ fontWeight: 700 }}>{title}</div>
          <button onClick={onClose} style={{ padding: "6px 10px" }}>Close</button>
        </div>
        <div style={{ padding: 14 }}>{children}</div>
      </div>
    </div>
  )
}

function safeParseJson(text) {
  if (!text || !text.trim()) return { ok: true, value: {} }
  try {
    const v = JSON.parse(text)
    if (!v || typeof v !== "object" || Array.isArray(v)) return { ok: false, error: "Env vars must be a JSON object like {\"KEY\":\"VALUE\"}." }
    return { ok: true, value: v }
  } catch {
    return { ok: false, error: "Env vars must be valid JSON." }
  }
}

function isValidGitUrl(url) {
  const u = (url || "").trim()
  if (!u) return false
  // Allow HTTPS URLs or common SSH form (git@github.com:org/repo.git)
  if (u.startsWith("git@") && u.includes(":") && u.includes(".git")) return true
  try {
    const parsed = new URL(u)
    return parsed.protocol === "http:" || parsed.protocol === "https:"
  } catch {
    return false
  }
}

function App() {
  const api = (import.meta.env.VITE_API_BASE && import.meta.env.VITE_API_BASE.trim()) || ""
  const [token, setToken] = React.useState(localStorage.getItem("keystone_token") || "")
  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")

  const [repos, setRepos] = React.useState([])
  const [apps, setApps] = React.useState([])
  const [newRepo, setNewRepo] = React.useState({name:"", git_url:"", default_branch:"main", github_token:""})
  const [newApp, setNewApp] = React.useState({name:"", repo:"", container_port: 8000, health_check_path:"", env_vars_text:"{}"})

  const [error, setError] = React.useState("")
  const [info, setInfo] = React.useState("")
  const [loading, setLoading] = React.useState(false)
  const [polling, setPolling] = React.useState(false)

  const [historyApp, setHistoryApp] = React.useState(null)
  const [history, setHistory] = React.useState([])
  const [logsModal, setLogsModal] = React.useState(null) // {deployment, logs}
  const [inspectionModal, setInspectionModal] = React.useState(null) // {repo, details, loading}

  async function apiFetch(path, opts = {}) {
    const headers = new Headers(opts.headers || {})
    headers.set("Accept", "application/json")
    if (!headers.has("Content-Type") && opts.body && typeof opts.body === "string") {
      headers.set("Content-Type", "application/json")
    }
    if (token) headers.set("Authorization", `Token ${token}`)
    const fetchUrl = `${api}${path}`
    
    // #region agent log
    try {
      fetch('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          sessionId: 'debug-session',
          runId: 'api-fetch',
          hypothesisId: 'F',
          location: 'main.jsx:apiFetch',
          message: 'API fetch request',
          data: {
            path: path,
            url: fetchUrl,
            hasToken: !!token,
            tokenPrefix: token ? token.substring(0, 10) + '...' : 'none',
            method: opts.method || 'GET',
          },
          timestamp: Date.now()
        })
      }).catch(() => {})
    } catch {}
    // #endregion
    
    let res;
    try {
      res = await fetch(fetchUrl, { ...opts, headers })
      
      // #region agent log
      try {
        fetch('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            sessionId: 'debug-session',
            runId: 'api-fetch',
            hypothesisId: 'F',
            location: 'main.jsx:apiFetch:response',
            message: 'API fetch response',
            data: {
              path: path,
              status: res.status,
              statusText: res.statusText,
              ok: res.ok,
            },
            timestamp: Date.now()
          })
        }).catch(() => {})
      } catch {}
      // #endregion
    } catch (fetchError) {
      throw fetchError
    }
    const text = await res.text()
    let data = null
    try { data = text ? JSON.parse(text) : null } catch { data = text }
    if (!res.ok) {
      const msg = (data && data.error) ? data.error : `Request failed (${res.status})`
      throw new Error(msg)
    }
    return data
  }

  async function load() {
    const [r, a] = await Promise.all([
      apiFetch("/api/repos/"),
      apiFetch("/api/apps/"),
    ])
    setRepos(r)
    setApps(a)
  }

  React.useEffect(() => {
    if (!token) return
    setLoading(true)
    load().catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [token])

  React.useEffect(() => {
    if (!polling) return
    const interval = setInterval(() => {
      load().catch(() => {})
    }, 2000)
    return () => clearInterval(interval)
  }, [polling, token])

  React.useEffect(() => {
    if (!polling) return
    const deploying = apps.some(a => a.status === "deploying" || a.status === "queued")
    if (!deploying) setPolling(false)
  }, [apps, polling])

  async function login(e) {
    e.preventDefault()
    setError("")
    setInfo("")
    setLoading(true)
    try {
      const data = await apiFetch("/api/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      })
      localStorage.setItem("keystone_token", data.token)
      setToken(data.token)
      setUsername("")
      setPassword("")
      setInfo(`Logged in as ${data.username}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function logout() {
    setError("")
    setInfo("")
    setLoading(true)
    try {
      await apiFetch("/api/auth/logout", { method: "POST" })
    } catch {
      // ignore
    } finally {
      localStorage.removeItem("keystone_token")
      setToken("")
      setRepos([])
      setApps([])
      setHistory([])
      setHistoryApp(null)
      setLogsModal(null)
      setLoading(false)
    }
  }

  async function addRepo(e){
    e.preventDefault()
    setError("")
    setInfo("")
    if (!newRepo.name.trim()) return setError("Repo name is required.")
    if (!isValidGitUrl(newRepo.git_url)) return setError("Git URL must be a valid https:// URL or SSH git@... form.")

    setLoading(true)
    try {
      await apiFetch("/api/repos/", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({
          name: newRepo.name.trim(),
          git_url: newRepo.git_url.trim(),
          default_branch: (newRepo.default_branch || "main").trim() || "main",
          github_token: (newRepo.github_token || "").trim(),
        })
      })
      setNewRepo({name:"", git_url:"", default_branch:"main", github_token:""})
      await load()
      setInfo("Repository added.")
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function addApp(e){
    e.preventDefault()
    setError("")
    setInfo("")
    if (!newApp.name.trim()) return setError("App name is required.")
    if (!newApp.repo) return setError("Repo selection is required.")

    const port = Number(newApp.container_port)
    if (!Number.isFinite(port) || port < 1 || port > 65535) return setError("Container port must be 1–65535.")
    const envParsed = safeParseJson(newApp.env_vars_text)
    if (!envParsed.ok) return setError(envParsed.error)

    setLoading(true)
    try {
      await apiFetch("/api/apps/", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({
          name: newApp.name.trim(),
          repo: Number(newApp.repo),
          container_port: port,
          health_check_path: (newApp.health_check_path || "").trim(),
          env_vars: envParsed.value,
        })
      })
      setNewApp({name:"", repo:"", container_port: 8000, health_check_path:"", env_vars_text:"{}"})
      await load()
      setInfo("App added.")
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function triggerDeploy(id, kind) {
    setError("")
    setInfo("")
    setLoading(true)
    try {
      const action = kind === "update" ? "update" : kind === "rollback" ? "rollback" : "deploy"
      await apiFetch(`/api/apps/${id}/${action}/`, { method:"POST" })
      await load()
      setPolling(true)
      setInfo(`${kind === "update" ? "Update" : kind === "rollback" ? "Rollback" : "Deploy"} queued.`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function openHistory(app) {
    setError("")
    setInfo("")
    setHistoryApp(app)
    setHistory([])
    try {
      const data = await apiFetch(`/api/deployments/?app=${app.id}`)
      setHistory(data)
    } catch (e) {
      setError(e.message)
    }
  }

  async function openLogs(dep) {
    setError("")
    setInfo("")
    try {
      const data = await apiFetch(`/api/deployments/${dep.id}/logs/`)
      setLogsModal({ deployment: dep, logs: data.logs || "" })
    } catch (e) {
      setError(e.message)
    }
  }

  async function checkContainerStatus(app) {
    setError("")
    setInfo("")
    setLoading(true)
    try {
      const data = await apiFetch(`/api/apps/${app.id}/container_status/`)
      setInfo(`Container status for ${app.name}: ${data.status}${data.details ? " — " + data.details : ""}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function inspectRepo(repo) {
    setError("")
    setInfo("")
    setInspectionModal({ repo, details: repo.inspection_details ? { status: repo.inspection_status, details: repo.inspection_details } : null, loading: true })
    try {
      const data = await apiFetch(`/api/repos/${repo.id}/inspect/`, { method: "POST" })
      setInspectionModal({ repo: {...repo, inspection_status: data.status, inspection_details: data.details}, details: data, loading: false })
      await load()
      setInfo("Repository inspected successfully.")
    } catch (e) {
      setInspectionModal({ repo, details: null, loading: false, error: e.message })
      setError(e.message)
    }
  }

  async function prepareRepo(repo) {
    setError("")
    setInfo("")
    setLoading(true)
    try {
      const data = await apiFetch(`/api/repos/${repo.id}/prepare/`, { method: "POST" })
      await load()
      // Update modal with prepared status
      const updatedRepo = {...repo, prepared_for_deployment: true, deployment_config: data.config}
      setInspectionModal({ 
        repo: updatedRepo, 
        details: { status: "prepared", config: data.config, message: data.message },
        loading: false 
      })
      setInfo("Repository prepared for deployment successfully.")
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div style={{fontFamily:"system-ui", padding:20, maxWidth:520, margin:"40px auto"}}>
        <h1 style={{margin:"0 0 6px"}}>Keystone</h1>
        <div style={{opacity:.75, marginBottom:18}}>Login required</div>
        {error && <div style={{background:"#fff1f2", border:"1px solid #fecdd3", color:"#9f1239", padding:10, borderRadius:10, marginBottom:10}}>{error}</div>}
        <form onSubmit={login} style={{display:"grid", gap:10, border:"1px solid #eee", borderRadius:12, padding:14}}>
          <input placeholder="Username" value={username} onChange={e=>setUsername(e.target.value)} />
          <input placeholder="Password" type="password" value={password} onChange={e=>setPassword(e.target.value)} />
          <button disabled={loading || !username || !password}>{loading ? "Signing in..." : "Sign in"}</button>
          <div style={{fontSize:12, opacity:.7}}>
            Default (DEBUG): <code>admin / admin</code>
          </div>
        </form>
      </div>
    )
  }

  const isDeploying = (a) => a.status === "deploying" || a.status === "queued"

  return (
    <div style={{fontFamily:"system-ui", padding:20, maxWidth:1000, margin:"0 auto"}}>
      <div style={{display:"flex", alignItems:"baseline", justifyContent:"space-between", gap:12}}>
        <div>
          <h1 style={{margin:"0 0 6px"}}>Keystone</h1>
          <div style={{opacity:.7, marginBottom:14}}>IP mode • Panel :8080 • Apps :9000–9999</div>
        </div>
        <div style={{display:"flex", gap:8, alignItems:"center"}}>
          {polling && <span style={{fontSize:12, opacity:.7}}>Polling…</span>}
          <button onClick={()=>load().catch(e=>setError(e.message))} disabled={loading}>Refresh</button>
          <button onClick={logout} disabled={loading}>Logout</button>
        </div>
      </div>

      {(error || info) && (
        <div style={{
          background: error ? "#fff1f2" : "#eff6ff",
          border: "1px solid " + (error ? "#fecdd3" : "#bfdbfe"),
          color: error ? "#9f1239" : "#1e40af",
          padding: 10,
          borderRadius: 10,
          marginBottom: 14,
          display:"flex",
          justifyContent:"space-between",
          gap: 10,
        }}>
          <div>{error || info}</div>
          <button onClick={()=>{setError(""); setInfo("")}} style={{padding:"4px 8px"}}>Dismiss</button>
        </div>
      )}

      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:16}}>
        <div style={{border:"1px solid #eee", borderRadius:12, padding:16}}>
          <h2>Repositories</h2>
          <form onSubmit={addRepo} style={{display:"grid", gap:8}}>
            <input placeholder="Name" value={newRepo.name} onChange={e=>setNewRepo({...newRepo, name:e.target.value})} />
            <input placeholder="Git URL" value={newRepo.git_url} onChange={e=>setNewRepo({...newRepo, git_url:e.target.value})} />
            <input placeholder="Branch" value={newRepo.default_branch} onChange={e=>setNewRepo({...newRepo, default_branch:e.target.value})} />
            <input placeholder="GitHub PAT (optional, stored encrypted)" type="password" value={newRepo.github_token} onChange={e=>setNewRepo({...newRepo, github_token:e.target.value})} />
            <button disabled={loading}>Add Repo</button>
          </form>
          <ul style={{listStyle:"none", padding:0, marginTop:12}}>
            {repos.map(r => (
              <li key={r.id} style={{padding:"8px 0", borderBottom:"1px solid #f0f0f0", display:"flex", justifyContent:"space-between", alignItems:"center"}}>
                <div>
                  <b>{r.name}</b> — {r.git_url}
                  <div style={{fontSize:12, opacity:.7, marginTop:4}}>
                    Status: {r.inspection_status || "pending"} 
                    {r.prepared_for_deployment && <span style={{color:"#059669", fontWeight:"bold"}}> • Prepared</span>}
                  </div>
                </div>
                <div style={{display:"flex", gap:4}}>
                  {r.inspection_status === "ready" && r.inspection_details && (
                    <button 
                      onClick={() => setInspectionModal({ 
                        repo: r, 
                        details: { status: r.inspection_status, details: r.inspection_details },
                        loading: false 
                      })} 
                      disabled={loading}
                      style={{padding:"4px 8px", fontSize:12}}
                    >
                      View Details
                    </button>
                  )}
                  <button 
                    onClick={() => inspectRepo(r)} 
                    disabled={loading || r.inspection_status === "inspecting"}
                    style={{padding:"4px 8px", fontSize:12}}
                  >
                    {r.inspection_status === "inspecting" ? "Inspecting..." : r.inspection_status === "ready" ? "Re-inspect" : "Inspect & Prepare"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div style={{border:"1px solid #eee", borderRadius:12, padding:16}}>
          <h2>Apps</h2>
          <form onSubmit={addApp} style={{display:"grid", gap:8}}>
            <input placeholder="App name" value={newApp.name} onChange={e=>setNewApp({...newApp, name:e.target.value})} />
            <select value={newApp.repo} onChange={e=>setNewApp({...newApp, repo:e.target.value})}>
              <option value="">Select repo</option>
              {repos.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
            <input
              placeholder="Container port (default 8000)"
              value={newApp.container_port}
              onChange={e=>setNewApp({...newApp, container_port:e.target.value})}
            />
            <input
              placeholder="Health check path (optional, e.g. /health)"
              value={newApp.health_check_path}
              onChange={e=>setNewApp({...newApp, health_check_path:e.target.value})}
            />
            <textarea
              rows={4}
              placeholder='Env vars JSON (optional). Example: {"FOO":"bar"}'
              value={newApp.env_vars_text}
              onChange={e=>setNewApp({...newApp, env_vars_text:e.target.value})}
              style={{fontFamily:"ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"}}
            />
            <button disabled={loading}>Add App</button>
          </form>

          <table width="100%" cellPadding="8" style={{borderCollapse:"collapse"}}>
            <thead>
              <tr>
                <th align="left">Name</th>
                <th align="left">Repo</th>
                <th align="left">Status</th>
                <th align="left">Port</th>
                <th align="left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {apps.map(a => (
                <tr key={a.id} style={{borderTop:"1px solid #f0f0f0"}}>
                  <td><b>{a.name}</b></td>
                  <td>{a.repo_name}</td>
                  <td>{a.status}</td>
                  <td>{a.current_port || "-"}</td>
                  <td style={{display:"flex", gap:8, flexWrap:"wrap"}}>
                    <button 
                      onClick={()=>triggerDeploy(a.id, "deploy")} 
                      disabled={loading || isDeploying(a) || !a.repo_prepared_for_deployment}
                      title={!a.repo_prepared_for_deployment ? "Repository must be prepared before deployment" : ""}
                    >
                      {isDeploying(a) ? "Deploying…" : "Deploy"}
                    </button>
                    <button 
                      onClick={()=>triggerDeploy(a.id, "update")} 
                      disabled={loading || isDeploying(a) || !a.repo_prepared_for_deployment}
                      title={!a.repo_prepared_for_deployment ? "Repository must be prepared before deployment" : ""}
                    >
                      Update
                    </button>
                    <button onClick={()=>triggerDeploy(a.id, "rollback")} disabled={loading || isDeploying(a)}>Rollback</button>
                    <button onClick={()=>openHistory(a)} disabled={loading}>History</button>
                    <button onClick={()=>checkContainerStatus(a)} disabled={loading}>Check Status</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <p style={{opacity:.7, marginTop:12}}>
            Open deployed app at: <code>http://&lt;VM_IP&gt;:&lt;port&gt;</code>
          </p>
        </div>
      </div>

      {historyApp && (
        <Modal title={`Deployment history — ${historyApp.name}`} onClose={()=>setHistoryApp(null)} width={980}>
          {history.length === 0 ? (
            <div style={{opacity:.75}}>No deployments found.</div>
          ) : (
            <table width="100%" cellPadding="8" style={{borderCollapse:"collapse"}}>
              <thead>
                <tr>
                  <th align="left">Created</th>
                  <th align="left">Type</th>
                  <th align="left">Status</th>
                  <th align="left">Port</th>
                  <th align="left">Error</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {history.map(d => (
                  <tr key={d.id} style={{borderTop:"1px solid #f0f0f0"}}>
                    <td style={{whiteSpace:"nowrap"}}>{new Date(d.created_at).toLocaleString()}</td>
                    <td>{d.deployment_type}</td>
                    <td>{d.status}</td>
                    <td>{d.assigned_port || "-"}</td>
                    <td style={{maxWidth:360, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}} title={d.error_summary || ""}>
                      {d.error_summary || "-"}
                    </td>
                    <td>
                      <button onClick={()=>openLogs(d)} disabled={loading}>View Logs</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Modal>
      )}

      {logsModal && (
        <Modal title={`Logs — deployment #${logsModal.deployment.id}`} onClose={()=>setLogsModal(null)} width={980}>
          <div style={{fontSize:12, opacity:.75, marginBottom:10}}>
            App: <b>{logsModal.deployment.app_name || "-"}</b> • Type: <b>{logsModal.deployment.deployment_type}</b> • Status: <b>{logsModal.deployment.status}</b>
          </div>
          <pre style={{
            margin: 0,
            padding: 12,
            borderRadius: 12,
            border: "1px solid #eee",
            background: "#0b1020",
            color: "#e5e7eb",
            overflow: "auto",
            maxHeight: 520,
            fontSize: 12,
            lineHeight: 1.4,
          }}>
            {logsModal.logs || "(empty)"}
          </pre>
        </Modal>
      )}

      {inspectionModal && (
        <Modal title={`Inspect & Prepare — ${inspectionModal.repo.name}`} onClose={()=>setInspectionModal(null)} width={980}>
          {inspectionModal.loading ? (
            <div style={{textAlign:"center", padding:40}}>Inspecting repository...</div>
          ) : inspectionModal.error ? (
            <div style={{background:"#fff1f2", border:"1px solid #fecdd3", color:"#9f1239", padding:12, borderRadius:8}}>
              <strong>Error:</strong> {inspectionModal.error}
            </div>
          ) : inspectionModal.details ? (
            <div style={{display:"grid", gap:16}}>
              <div style={{background:"#eff6ff", border:"1px solid #bfdbfe", color:"#1e40af", padding:12, borderRadius:8}}>
                <strong>Status:</strong> {inspectionModal.details.status}<br/>
                {inspectionModal.details.message && <div style={{marginTop:8}}>{inspectionModal.details.message}</div>}
              </div>

              {inspectionModal.details.details && (
                <>
                  {inspectionModal.details.details.compose_files_found && inspectionModal.details.details.compose_files_found.length > 0 && (
                    <div>
                      <strong>Docker Compose Files Found:</strong>
                      <ul>
                        {inspectionModal.details.details.compose_files_found.map((f, i) => <li key={i}>{f}</li>)}
                      </ul>
                    </div>
                  )}

                  {inspectionModal.details.details.main_service && (
                    <div>
                      <strong>Main Service:</strong> {inspectionModal.details.details.main_service}
                    </div>
                  )}

                  {inspectionModal.details.details.services && Object.keys(inspectionModal.details.details.services).length > 0 && (
                    <div>
                      <strong>Services Detected:</strong>
                      <ul>
                        {Object.keys(inspectionModal.details.details.services).map(svc => (
                          <li key={svc}>
                            <strong>{svc}</strong>
                            {inspectionModal.details.details.services[svc].build && " (has build)"}
                            {inspectionModal.details.details.services[svc].image && ` (image: ${inspectionModal.details.details.services[svc].image})`}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {inspectionModal.details.details.issues && inspectionModal.details.details.issues.length > 0 && (
                    <div>
                      <strong style={{color:"#dc2626"}}>Issues Found:</strong>
                      <ul style={{color:"#dc2626"}}>
                        {inspectionModal.details.details.issues.map((issue, i) => <li key={i}>{issue}</li>)}
                      </ul>
                    </div>
                  )}

                  {inspectionModal.details.details.recommendations && inspectionModal.details.details.recommendations.length > 0 && (
                    <div>
                      <strong style={{color:"#059669"}}>Recommendations:</strong>
                      <ul style={{color:"#059669"}}>
                        {inspectionModal.details.details.recommendations.map((rec, i) => <li key={i}>{rec}</li>)}
                      </ul>
                    </div>
                  )}

                  {(inspectionModal.repo.prepared_for_deployment || inspectionModal.details.status === "prepared") ? (
                    <div style={{background:"#d1fae5", border:"1px solid #6ee7b7", color:"#065f46", padding:12, borderRadius:8}}>
                      <strong>✓ Repository is prepared for deployment</strong>
                      {inspectionModal.details.config && (
                        <div style={{marginTop:8, fontSize:12}}>
                          <strong>Configuration:</strong>
                          <pre style={{background:"#f0fdf4", padding:8, borderRadius:4, marginTop:4, fontSize:11, overflow:"auto"}}>
                            {JSON.stringify(inspectionModal.details.config, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{marginTop:16}}>
                      <button 
                        onClick={() => prepareRepo(inspectionModal.repo)} 
                        disabled={loading || (inspectionModal.details.status !== "ready" && inspectionModal.details.status !== "prepared")}
                        style={{padding:"8px 16px", background:"#059669", color:"white", border:"none", borderRadius:6, cursor:"pointer"}}
                      >
                        {loading ? "Preparing..." : "Prepare for Deployment"}
                      </button>
                      <div style={{fontSize:12, opacity:.7, marginTop:8}}>
                        This will standardize docker-compose.yml, add Traefik labels, and configure networks.
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          ) : (
            <div>No inspection data available.</div>
          )}
        </Modal>
      )}
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
