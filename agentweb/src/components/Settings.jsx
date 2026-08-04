import React, { useState } from 'react'
import { supabase } from '../lib/supabase'
import { Settings as SettingsIcon, Trash2, RefreshCw, ExternalLink } from 'lucide-react'

export default function Settings({ agents, onRefresh }) {
  const [agentToDelete, setAgentToDelete] = useState(null)

  const deleteAgent = async (deviceId) => {
    try {
      await supabase.from('agents').delete().eq('device_id', deviceId)
      await supabase.from('agent_commands').delete().eq('device_id', deviceId)
      onRefresh()
    } catch (e) {
      console.error('Delete error:', e)
    }
  }

  const updateAgent = async (deviceId, field, value) => {
    try {
      await supabase.from('agents').update({ [field]: value }).eq('device_id', deviceId)
      onRefresh()
    } catch (e) {
      console.error('Update error:', e)
    }
  }

  return (
    <div>
      <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <SettingsIcon size={20} /> Paramètres
      </h3>

      {/* Agent List Management */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border-color)',
        borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h4 style={{ color: 'var(--accent-cyan)' }}>Agents enregistrés ({agents.length})</h4>
          <button className="btn" onClick={onRefresh}><RefreshCw size={14} /> Actualiser</button>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
              <th style={thStyle}>Statut</th>
              <th style={thStyle}>Hostname</th>
              <th style={thStyle}>Utilisateur</th>
              <th style={thStyle}>IP</th>
              <th style={thStyle}>Version</th>
              <th style={thStyle}>Dernière activité</th>
              <th style={thStyle}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {agents.map(agent => (
              <tr key={agent.device_id} style={{ borderBottom: '1px solid rgba(35,51,77,0.5)' }}>
                <td style={tdStyle}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                    padding: '0.2rem 0.6rem', borderRadius: '12px', fontSize: '0.75rem', fontWeight: '700',
                    background: agent.status === 'ONLINE' ? 'rgba(34,197,94,0.15)' : agent.status === 'BUSY' ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.15)',
                    color: agent.status === 'ONLINE' ? '#4ade80' : agent.status === 'BUSY' ? '#fbbf24' : '#f87171'
                  }}>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'currentColor' }} />
                    {agent.status || 'OFFLINE'}
                  </span>
                </td>
                <td style={tdStyle}>{agent.hostname}</td>
                <td style={tdStyle}>{agent.username}</td>
                <td style={tdStyle}>{agent.local_ip}</td>
                <td style={tdStyle}>{agent.agent_version}</td>
                <td style={tdStyle}>{agent.last_seen ? new Date(agent.last_seen).toLocaleString('fr-FR') : 'N/A'}</td>
                <td style={tdStyle}>
                  <button
                    className="btn danger"
                    style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                    onClick={() => deleteAgent(agent.device_id)}
                  >
                    <Trash2 size={12} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Info */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border-color)',
        borderRadius: '12px', padding: '1.5rem'
      }}>
        <h4 style={{ color: 'var(--accent-cyan)', marginBottom: '1rem' }}>Comment ça marche</h4>
        <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: '1.8' }}>
          <p><strong>1.</strong> L'agent (AntiAgent.exe) s'installe silencieusement sur le PC distant</p>
          <p><strong>2.</strong> Il communique avec Supabase toutes les 10 secondes</p>
          <p><strong>3.</strong> Vous envoyez des commandes depuis cette dashboard</p>
          <p><strong>4.</strong> L'agent exécute et renvoie les résultats</p>
          <br />
          <p style={{ color: 'var(--accent-green)' }}>Aucune configuration IP nécessaire - tout passe par le cloud Supabase.</p>
        </div>
      </div>
    </div>
  )
}

const thStyle = {
  padding: '0.8rem', textAlign: 'left', fontSize: '0.75rem', color: 'var(--text-muted)',
  textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: '600'
}

const tdStyle = {
  padding: '0.8rem', fontSize: '0.85rem'
}
