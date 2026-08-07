import React, { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { RefreshCw, Trash2, Search, Maximize2, Play } from 'lucide-react'

export default function ProcessList({ agent }) {
  const [processes, setProcesses] = useState([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('')
  const [appName, setAppName] = useState('')
  const [launchResult, setLaunchResult] = useState(null)
  const [launching, setLaunching] = useState(false)

  const fetchProcesses = async () => {
    setLoading(true)
    try {
      const { data, error } = await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: 'process_list',
        command_content: '',
        status: 'PENDING'
      }]).select().single()

      if (error) throw error

      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        const { data: updated } = await supabase
          .from('agent_commands')
          .select('status, result')
          .eq('id', data.id)
          .single()

        if (updated?.status === 'COMPLETED' || attempts >= 60) {
          clearInterval(poll)
          setLoading(false)
          if (updated?.result) {
            try {
              const result = JSON.parse(updated.result)
              if (result.processes) {
                setProcesses(result.processes)
              }
            } catch {}
          }
        }
      }, 500)
      setTimeout(() => clearInterval(poll), 30000)
    } catch (e) {
      setLoading(false)
    }
  }

  useEffect(() => { fetchProcesses() }, [])

  const killProcess = async (name) => {
    try {
      await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: 'process_kill',
        command_content: name,
        status: 'PENDING'
      }])
      setTimeout(fetchProcesses, 3000)
    } catch {}
  }

  const focusProcess = async (pid, name) => {
    try {
      await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: 'process_focus',
        command_content: name,
        status: 'PENDING'
      }])
    } catch {}
  }

  const launchApp = async () => {
    if (!appName.trim() || launching) return
    setLaunching(true)
    setLaunchResult(null)
    try {
      const { data, error } = await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: 'app_launch',
        command_content: appName.trim(),
        status: 'PENDING'
      }]).select().single()

      if (error) throw error

      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        const { data: updated } = await supabase
          .from('agent_commands')
          .select('status, result')
          .eq('id', data.id)
          .single()

        if (updated?.status === 'COMPLETED' || attempts >= 30) {
          clearInterval(poll)
          setLaunching(false)
          if (updated?.result) {
            try {
              const result = JSON.parse(updated.result)
              setLaunchResult(result)
              if (result.success) {
                setTimeout(fetchProcesses, 2000)
              }
            } catch {
              setLaunchResult({ error: 'Réponse invalide' })
            }
          } else {
            setLaunchResult({ error: 'Pas de réponse' })
          }
        }
      }, 500)
      setTimeout(() => clearInterval(poll), 15000)
    } catch (e) {
      setLaunching(false)
      setLaunchResult({ error: e.message })
    }
  }

  const filtered = processes.filter(p =>
    p.name.toLowerCase().includes(filter.toLowerCase()) ||
    String(p.pid).includes(filter)
  )

  return (
    <div>
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1rem', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
          <Play size={16} color="var(--accent)" />
          <strong style={{ fontSize: '0.85rem' }}>Lancer une application</strong>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.6rem', alignItems: 'center' }}>
          <input
            value={appName}
            onChange={e => { setAppName(e.target.value); setLaunchResult(null) }}
            onKeyDown={e => e.key === 'Enter' && launchApp()}
            placeholder="Nom de l'app (ex: Discord, Chrome, Notepad...)"
            style={{ flex: 1, background: 'var(--bg-dark)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.5rem 0.8rem', color: 'var(--text-main)', fontSize: '0.85rem', outline: 'none' }}
          />
          <button className="btn primary" onClick={launchApp} disabled={launching || !appName.trim()}>
            <Play size={14} /> {launching ? 'Lancement...' : 'Lancer'}
          </button>
        </div>
        {launchResult && (
          <div style={{
            marginTop: '0.6rem', padding: '0.5rem 0.8rem', borderRadius: '8px', fontSize: '0.8rem',
            background: launchResult.success ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
            border: `1px solid ${launchResult.success ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)'}`,
            color: launchResult.success ? '#4ade80' : '#fca5a5'
          }}>
            {launchResult.success ? (
              <span>Lancé: {launchResult.path} ({launchResult.matches} résultat{launchResult.matches > 1 ? 's' : ''})</span>
            ) : (
              <span>{launchResult.error}</span>
            )}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '0.8rem', marginBottom: '1rem', alignItems: 'center' }}>
        <button className="btn primary" onClick={fetchProcesses} disabled={loading}>
          <RefreshCw size={14} /> {loading ? 'Chargement...' : 'Actualiser'}
        </button>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.4rem 0.8rem' }}>
          <Search size={14} color="var(--text-muted)" />
          <input
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="Filtrer processus..."
            style={{ flex: 1, background: 'transparent', border: 'none', color: 'var(--text-main)', outline: 'none', fontSize: '0.85rem' }}
          />
        </div>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{filtered.length} processus</span>
      </div>

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '12px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
              <th style={thStyle}>PID</th>
              <th style={thStyle}>Nom</th>
              <th style={thStyle}>CPU (s)</th>
              <th style={thStyle}>RAM (MB)</th>
              <th style={thStyle}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p, i) => (
              <tr key={i} style={{ borderBottom: '1px solid rgba(35,51,77,0.5)' }}>
                <td style={tdStyle}>{p.pid}</td>
                <td style={tdStyle}><strong>{p.name}</strong></td>
                <td style={tdStyle}>{p.cpu}</td>
                <td style={tdStyle}>{p.ram_mb}</td>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <button
                      className="btn"
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', background: 'rgba(34,197,94,0.15)', borderColor: 'rgba(34,197,94,0.4)', color: '#4ade80' }}
                      onClick={() => focusProcess(p.pid, p.name)}
                      title="Ouvrir/Focus"
                    >
                      <Maximize2 size={12} /> Focus
                    </button>
                    <button className="btn danger" style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }} onClick={() => killProcess(p.name)}>
                      <Trash2 size={12} /> Kill
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const thStyle = { padding: '0.8rem', textAlign: 'left', fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: '600' }
const tdStyle = { padding: '0.7rem 0.8rem', fontSize: '0.85rem' }
