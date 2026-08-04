import React, { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { RefreshCw, Trash2, Search } from 'lucide-react'

export default function ProcessList({ agent }) {
  const [processes, setProcesses] = useState([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('')

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

  const filtered = processes.filter(p =>
    p.name.toLowerCase().includes(filter.toLowerCase()) ||
    String(p.pid).includes(filter)
  )

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.8rem', marginBottom: '1rem', alignItems: 'center' }}>
        <button className="btn primary" onClick={fetchProcesses} disabled={loading}>
          <RefreshCw size={14} /> {loading ? 'Chargement...' : 'Actualiser'}
        </button>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.4rem 0.8rem' }}>
          <Search size={14} color="var(--text-muted)" />
          <input
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="Filtrer..."
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
                  <button className="btn danger" style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }} onClick={() => killProcess(p.name)}>
                    <Trash2 size={12} /> Kill
                  </button>
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
