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
  // #region agent log
  const rawApiBase = import.meta.env.VITE_API_BASE;
  fetch('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.jsx:66',message:'VITE_API_BASE env var value',data:{rawApiBase,type:typeof rawApiBase,isFalsy:!rawApiBase,isEmpty:rawApiBase===''},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  // #endregion
  const api = (import.meta.env.VITE_API_BASE && import.meta.env.VITE_API_BASE.trim()) || ""
  // #region agent log
  fetch('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.jsx:68',message:'Final api base value',data:{api,apiLength:api.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  // #endregion
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

  async function apiFetch(path, opts = {}) {
    const headers = new Headers(opts.headers || {})
    headers.set("Accept", "application/json")
    if (!headers.has("Content-Type") && opts.body && typeof opts.body === "string") {
      headers.set("Content-Type", "application/json")
    }
    if (token) headers.set("Authorization", `Token ${token}`)
    const fetchUrl = `${api}${path}`
    // #region agent log
    fetch('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.jsx:92',message:'About to fetch API',data:{fetchUrl,api,path,method:opts.method||'GET'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    let res;
    try {
      res = await fetch(fetchUrl, { ...opts, headers })
      // #region agent log
      fetch('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.jsx:96',message:'Fetch response received',data:{status:res.status,statusText:res.statusText,ok:res.ok,url:res.url},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
      // #endregion
    } catch (fetchError) {
      // #region agent log
      fetch('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.jsx:100',message:'Fetch error caught',data:{errorMessage:fetchError.message,errorName:fetchError.name,errorStack:fetchError.stack,fetchUrl},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
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
    // #region agent log
    fetch('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.jsx:132',message:'Login attempt started',data:{username,api,hasPassword:!!password},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    try {
      const data = await apiFetch("/api/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      })
      // #region agent log
      fetch('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.jsx:142',message:'Login success',data:{hasToken:!!data.token,username:data.username},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      localStorage.setItem("keystone_token", data.token)
      setToken(data.token)
      setUsername("")
      setPassword("")
      setInfo(`Logged in as ${data.username}`)
    } catch (e) {
      // #region agent log
      fetch('http://localhost:7253/ingest/b43efa04-b0ac-48de-ba53-3dfd4466ed70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.jsx:149',message:'Login error caught',data:{errorMessage:e.message,errorName:e.name,api},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
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
          <ul>
            {repos.map(r => <li key={r.id}><b>{r.name}</b> — {r.git_url}</li>)}
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
                    <button onClick={()=>triggerDeploy(a.id, "deploy")} disabled={loading || isDeploying(a)}>
                      {isDeploying(a) ? "Deploying…" : "Deploy"}
                    </button>
                    <button onClick={()=>triggerDeploy(a.id, "update")} disabled={loading || isDeploying(a)}>Update</button>
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
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
