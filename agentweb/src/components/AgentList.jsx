import React from 'react'
import { Monitor, Wifi, Settings as SettingsIcon } from 'lucide-react'

export default function AgentList({ agents, stats, selectedAgent, onSelect, view, onViewChange }) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <div className="logo-icon"><Wifi size={20} /></div>
          <div>
            <div className="logo-text">ANTI Agent</div>
            <div className="logo-sub">Remote Control</div>
          </div>
        </div>
      </div>

      <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)' }}>
        <div className="stats-row" style={{ gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.6rem' }}>
          <div className="stat-card online" style={{ padding: '0.8rem' }}>
            <div className="number" style={{ fontSize: '1.4rem' }}>{stats.online}</div>
            <div className="label">Online</div>
          </div>
          <div className="stat-card offline" style={{ padding: '0.8rem' }}>
            <div className="number" style={{ fontSize: '1.4rem' }}>{stats.offline}</div>
            <div className="label">Offline</div>
          </div>
        </div>
      </div>

      <div className="agent-list">
        {agents.length === 0 ? (
          <div className="empty-state" style={{ height: 'auto', padding: '2rem' }}>
            <Monitor size={32} />
            <p>Aucun agent connecté</p>
          </div>
        ) : (
          agents.map(agent => (
            <div
              key={agent.device_id}
              className={`agent-item ${selectedAgent?.device_id === agent.device_id && view !== 'settings' ? 'active' : ''}`}
              onClick={() => onSelect(agent)}
            >
              <div className={`status-dot ${agent.status || 'OFFLINE'}`} />
              <div className="agent-info">
                <div className="agent-name">{agent.hostname || 'Inconnu'}</div>
                <div className="agent-host">{agent.username || 'N/A'} • {agent.local_ip || 'N/A'}</div>
              </div>
            </div>
          ))
        )}
      </div>

      <div style={{ padding: '1rem', borderTop: '1px solid var(--border-color)' }}>
        <button
          className={`btn ${view === 'settings' ? 'active' : ''}`}
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={() => onViewChange('settings')}
        >
          <SettingsIcon size={16} /> Paramètres
        </button>
      </div>
    </div>
  )
}
