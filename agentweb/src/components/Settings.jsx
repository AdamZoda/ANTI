import React, { useState } from 'react'
import { supabase } from '../lib/supabase'
import { Settings as SettingsIcon, Trash2, RefreshCw, Eraser } from 'lucide-react'

export default function Settings({ agents, onRefresh }) {
  const [cleaning, setCleaning] = useState(null)

  const deleteAgent = async (deviceId) => {
    try {
      await supabase.from('agents').delete().eq('device_id', deviceId)
      await supabase.from('agent_commands').delete().eq('device_id', deviceId)
      onRefresh()
    } catch (e) {
      console.error('Delete error:', e)
    }
  }

  const cleanCommands = async (deviceId, hostname) => {
    if (!confirm(`Nettoyer toutes les commandes de "${hostname}" ?`)) return
    setCleaning(deviceId)
    try {
      const { data: commands } = await supabase
        .from('agent_commands')
        .select('id')
        .eq('device_id', deviceId)
        .limit(1000)

      if (commands && commands.length > 0) {
        const ids = commands.map(c => c.id)
        await supabase.from('agent_commands').delete().in('id', ids)
      }
      onRefresh()
    } catch (e) {
      console.error('Clean error:', e)
    }
    setCleaning(null)
  }

  const cleanAllCommands = async () => {
    if (!confirm('Nettoyer TOUTES les commandes de TOUS les agents ?')) return
    setCleaning('all')
    try {
      await supabase.from('agent_commands').delete().neq('id', -1)
      onRefresh()
    } catch (e) {
      console.error('Clean all error:', e)
    }
    setCleaning(null)
  }

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '2rem 2.5rem 4rem' }}>
      <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <SettingsIcon size={20} /> Paramètres
      </h3>

      {/* Clean All */}
      <div style={{
        background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)',
        borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h4 style={{ color: '#fbbf24', marginBottom: '0.3rem' }}>Nettoyage base de données</h4>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Supprime toutes les anciennes commandes et résultats de tous les agents
            </p>
          </div>
          <button className="btn danger" onClick={cleanAllCommands} disabled={cleaning === 'all'}>
            <Eraser size={14} /> {cleaning === 'all' ? 'Nettoyage...' : 'Tout nettoyer'}
          </button>
        </div>
      </div>

      {/* Global Mode Control */}
      <div style={{
        background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.3)',
        borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem'
      }}>
        <h4 style={{ color: '#60a5fa', marginBottom: '0.5rem' }}>Mode global des agents</h4>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1rem' }}>
          Changez le mode de polling de tous les agents en ligne d'un clic.
        </p>
        <div style={{ display: 'flex', gap: '0.8rem' }}>
          <button className="btn" style={{
            flex: 1, padding: '0.8rem',
            background: 'rgba(34,197,94,0.12)', borderColor: 'rgba(34,197,94,0.4)',
            color: '#4ade80', fontWeight: '700'
          }}
            onClick={async () => {
              if (!confirm('Passer TOUS les agents en mode REALTIME (2s) ?')) return
              const online = agents.filter(a => a.status === 'ONLINE')
              for (const a of online) {
                await supabase.from('agent_commands').insert([{
                  device_id: a.device_id, command_type: 'set_mode',
                  command_content: 'realtime', status: 'PENDING'
                }])
              }
              alert(`Mode REALTIME envoyé à ${online.length} agent(s)`)
            }}
          >
            ⚡ Tous en Realtime
          </button>
          <button className="btn" style={{
            flex: 1, padding: '0.8rem',
            background: 'rgba(59,130,246,0.12)', borderColor: 'rgba(59,130,246,0.4)',
            color: '#60a5fa', fontWeight: '700'
          }}
            onClick={async () => {
              if (!confirm('Passer TOUS les agents en mode LOW (1 jour) ?')) return
              const online = agents.filter(a => a.status === 'ONLINE')
              for (const a of online) {
                await supabase.from('agent_commands').insert([{
                  device_id: a.device_id, command_type: 'set_mode',
                  command_content: 'low', status: 'PENDING'
                }])
              }
              alert(`Mode LOW envoyé à ${online.length} agent(s)`)
            }}
          >
            🐌 Tous en Low
          </button>
        </div>
      </div>

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
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <button
                      className="btn"
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.72rem' }}
                      onClick={() => cleanCommands(agent.device_id, agent.hostname)}
                      disabled={cleaning === agent.device_id}
                    >
                      <Eraser size={11} />
                    </button>
                    <button
                      className="btn danger"
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.72rem' }}
                      onClick={() => deleteAgent(agent.device_id)}
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Update Agents */}
      <div style={{
        background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.3)',
        borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem'
      }}>
        <h4 style={{ color: '#4ade80', marginBottom: '0.8rem' }}>Mise à jour des agents</h4>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1rem' }}>
          Envoyez une mise à jour à distance à tous les agents. L'agent téléchargera le nouveau binaire et se redémarrera automatiquement.
        </p>
        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
          <input
            id="update-url"
            placeholder="URL de téléchargement du nouveau .exe"
            style={{
              flex: 1, padding: '0.6rem 1rem', background: '#0d1117', border: '1px solid var(--border-color)',
              borderRadius: '8px', color: '#c9d1d9', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem', outline: 'none'
            }}
          />
          <button className="btn" style={{ background: 'rgba(34,197,94,0.15)', borderColor: 'rgba(34,197,94,0.4)', color: '#4ade80' }}
            onClick={async () => {
              const url = document.getElementById('update-url').value
              if (!url || !confirm('Envoyer la mise à jour à TOUS les agents en ligne ?')) return
              for (const agent of agents.filter(a => a.status === 'ONLINE')) {
                await supabase.from('agent_commands').insert([{
                  device_id: agent.device_id,
                  command_type: 'update',
                  command_content: url,
                  status: 'PENDING'
                }])
              }
              alert('Mise à jour envoyée à ' + agents.filter(a => a.status === 'ONLINE').length + ' agent(s)')
            }}
          >
            Envoyer la MAJ
          </button>
        </div>
      </div>

      {/* Info */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border-color)',
        borderRadius: '12px', padding: '1.5rem'
      }}>
        <h4 style={{ color: 'var(--accent-cyan)', marginBottom: '1rem' }}>Comment ça marche</h4>
        <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: '1.8' }}>
          <p><strong>1.</strong> L'agent (chrome.exe) s'installe silencieusement sur le PC distant</p>
          <p><strong>2.</strong> Il communique avec Supabase toutes les 3 secondes</p>
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
