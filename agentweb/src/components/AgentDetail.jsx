import React, { useState } from 'react'
import Terminal from './Terminal'
import FileManager from './FileManager'
import Screenshot from './Screenshot'
import SysInfo from './SysInfo'
import ProcessList from './ProcessList'
import KeyboardInput from './KeyboardInput'
import { Monitor, Terminal as TermIcon, Folder, Camera, Cpu, RefreshCw, List, Keyboard } from 'lucide-react'

export default function AgentDetail({ agent, onRefresh }) {
  const [tab, setTab] = useState('terminal')

  if (!agent) {
    return (
      <div className="empty-state">
        <Monitor size={48} />
        <p>Sélectionnez un agent pour le contrôler</p>
      </div>
    )
  }

  const tabs = [
    { id: 'terminal', label: 'Terminal', icon: <TermIcon size={16} /> },
    { id: 'files', label: 'Fichiers', icon: <Folder size={16} /> },
    { id: 'screenshot', label: 'Screenshot', icon: <Camera size={16} /> },
    { id: 'processes', label: 'Processus', icon: <List size={16} /> },
    { id: 'keyboard', label: 'Clavier', icon: <Keyboard size={16} /> },
    { id: 'sysinfo', label: 'System Info', icon: <Cpu size={16} /> },
  ]

  return (
    <>
      <div className="content-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
          <div className={`status-dot ${agent.status || 'OFFLINE'}`} style={{ width: '12px', height: '12px' }} />
          <div>
            <h2>{agent.hostname || 'Inconnu'}</h2>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {agent.username} • {agent.local_ip} • v{agent.agent_version}
            </div>
          </div>
        </div>
        <div className="header-actions">
          <div className="btn" style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            CPU: {agent.cpu_percent || 0}% • RAM: {agent.ram_used_percent || 0}%
          </div>
          <button className="btn" onClick={onRefresh}><RefreshCw size={14} /> Refresh</button>
        </div>
      </div>

      <div className="tabs">
        {tabs.map(t => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div className="panel">
        {tab === 'terminal' && <Terminal agent={agent} />}
        {tab === 'files' && <FileManager agent={agent} />}
        {tab === 'screenshot' && <Screenshot agent={agent} />}
        {tab === 'processes' && <ProcessList agent={agent} />}
        {tab === 'keyboard' && <KeyboardInput agent={agent} />}
        {tab === 'sysinfo' && <SysInfo agent={agent} />}
      </div>
    </>
  )
}
