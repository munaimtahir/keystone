import React from 'react'
import { createRoot } from 'react-dom/client'

function App() {
  const api = import.meta.env.VITE_API_BASE || "http://localhost:8000"
  const [repos, setRepos] = React.useState([])
  const [apps, setApps] = React.useState([])
  const [newRepo, setNewRepo] = React.useState({name:"", git_url:"", default_branch:"main"})
  const [newApp, setNewApp] = React.useState({name:"", repo:""})

  async function load() {
    setRepos(await fetch(`${api}/api/repos/`).then(r=>r.json()))
    setApps(await fetch(`${api}/api/apps/`).then(r=>r.json()))
  }
  React.useEffect(()=>{ load() }, [])

  async function addRepo(e){
    e.preventDefault()
    await fetch(`${api}/api/repos/`, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(newRepo)
    })
    setNewRepo({name:"", git_url:"", default_branch:"main"})
    load()
  }

  async function addApp(e){
    e.preventDefault()
    await fetch(`${api}/api/apps/`, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({name:newApp.name, repo:Number(newApp.repo)})
    })
    setNewApp({name:"", repo:""})
    load()
  }

  async function deploy(id){
    await fetch(`${api}/api/apps/${id}/deploy/`, {method:"POST"})
    load()
  }

  return (
    <div style={{fontFamily:"system-ui", padding:20, maxWidth:1000, margin:"0 auto"}}>
      <h1 style={{margin:"0 0 6px"}}>Keystone</h1>
      <div style={{opacity:.7, marginBottom:20}}>IP mode • Panel :8080 • Apps :9000–9999</div>

      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:16}}>
        <div style={{border:"1px solid #eee", borderRadius:12, padding:16}}>
          <h2>Repositories</h2>
          <form onSubmit={addRepo} style={{display:"grid", gap:8}}>
            <input placeholder="Name" value={newRepo.name} onChange={e=>setNewRepo({...newRepo, name:e.target.value})} />
            <input placeholder="Git URL" value={newRepo.git_url} onChange={e=>setNewRepo({...newRepo, git_url:e.target.value})} />
            <input placeholder="Branch" value={newRepo.default_branch} onChange={e=>setNewRepo({...newRepo, default_branch:e.target.value})} />
            <button>Add Repo</button>
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
            <button>Add App</button>
          </form>

          <table width="100%" cellPadding="8" style={{borderCollapse:"collapse"}}>
            <thead><tr><th align="left">Name</th><th align="left">Repo</th><th align="left">Status</th><th align="left">Port</th><th></th></tr></thead>
            <tbody>
              {apps.map(a => (
                <tr key={a.id} style={{borderTop:"1px solid #f0f0f0"}}>
                  <td><b>{a.name}</b></td>
                  <td>{a.repo_name}</td>
                  <td>{a.status}</td>
                  <td>{a.current_port || "-"}</td>
                  <td><button onClick={()=>deploy(a.id)}>Deploy</button></td>
                </tr>
              ))}
            </tbody>
          </table>

          <p style={{opacity:.7, marginTop:12}}>
            Open deployed app at: <code>http://&lt;VM_IP&gt;:&lt;port&gt;</code>
          </p>
        </div>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
