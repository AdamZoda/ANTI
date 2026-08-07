import React, { useState } from 'react'
import Terminal from './Terminal'
import FileManager from './FileManager'
import Screenshot from './Screenshot'
import SysInfo from './SysInfo'
import ProcessList from './ProcessList'
import KeyboardInput from './KeyboardInput'
import { supabase } from '../lib/supabase'
import { Monitor, Terminal as TermIcon, Folder, Camera, Cpu, RefreshCw, List, Keyboard, Gamepad2, Power, Trash2 } from 'lucide-react'

export default function AgentDetail({ agent, onRefresh }) {
  const [tab, setTab] = useState('terminal')
  const [sending, setSending] = useState(null)

  if (!agent) {
    return (
      <div className="empty-state">
        <Monitor size={48} />
        <p>Sélectionnez un agent pour le contrôler</p>
      </div>
    )
  }

  const sendCommand = async (type, content = '', label) => {
    if (!confirm(`Confirmer: ${label} ?`)) return
    setSending(label)
    try {
      await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: type,
        command_content: content,
        status: 'PENDING'
      }])
      if (type === 'stop' || type === 'uninstall') {
        setTimeout(onRefresh, 2000)
      }
    } catch (e) {
      console.error('Command error:', e)
    }
    setSending(null)
  }

  const tabs = [
    { id: 'terminal', label: 'Terminal', icon: <TermIcon size={16} /> },
    { id: 'files', label: 'Fichiers', icon: <Folder size={16} /> },
    { id: 'screenshot', label: 'Screenshot', icon: <Camera size={16} /> },
    { id: 'processes', label: 'Processus', icon: <List size={16} /> },
    { id: 'keyboard', label: 'Clavier', icon: <Keyboard size={16} /> },
    { id: 'sysinfo', label: 'System Info', icon: <Cpu size={16} /> },
    { id: 'control', label: 'Controle', icon: <Gamepad2 size={16} /> },
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
        {tab === 'control' && (
          <div style={{ padding: '1.5rem', maxWidth: '700px' }}>
            <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-cyan)' }}>
              <Gamepad2 size={20} /> Controle de l'agent
            </h3>

            <div style={{
              background: 'var(--bg-card)', border: '1px solid var(--border-color)',
              borderRadius: '12px', padding: '1.5rem', marginBottom: '1.2rem'
            }}>
              <h4 style={{ marginBottom: '1rem', color: 'var(--text-primary)' }}>Mode de polling</h4>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                Réglez la fréquence de requêtes vers la base de données.
              </p>
              <div style={{ display: 'flex', gap: '0.8rem' }}>
                <button
                  className="btn"
                  style={{
                    flex: 1, padding: '0.8rem',
                    background: 'rgba(34,197,94,0.12)', borderColor: 'rgba(34,197,94,0.4)',
                    color: '#4ade80', fontWeight: '700', fontSize: '0.9rem'
                  }}
                  onClick={() => sendCommand('set_mode', 'realtime', 'Passer en mode REALTIME (2s)')}
                  disabled={sending !== null}
                >
                  ⚡ Realtime (2s)
                </button>
                <button
                  className="btn"
                  style={{
                    flex: 1, padding: '0.8rem',
                    background: 'rgba(59,130,246,0.12)', borderColor: 'rgba(59,130,246,0.4)',
                    color: '#60a5fa', fontWeight: '700', fontSize: '0.9rem'
                  }}
                  onClick={() => sendCommand('set_mode', 'low', 'Passer en mode LOW (1 jour)')}
                  disabled={sending !== null}
                >
                  🐌 Low (1 jour)
                </button>
              </div>
            </div>

            <div style={{
              background: 'var(--bg-card)', border: '1px solid var(--border-color)',
              borderRadius: '12px', padding: '1.5rem', marginBottom: '1.2rem'
            }}>
              <h4 style={{ marginBottom: '1rem', color: 'var(--text-primary)' }}>Actions</h4>
              <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap' }}>
                <button
                  className="btn"
                  style={{
                    background: 'rgba(245,158,11,0.12)', borderColor: 'rgba(245,158,11,0.4)',
                    color: '#fbbf24', padding: '0.7rem 1.2rem'
                  }}
                  onClick={() => sendCommand('stop', '', 'Arreter l\'agent')}
                  disabled={sending !== null}
                >
                  <Power size={16} /> {sending === "Arreter l'agent" ? 'Arret...' : 'Arreter l\'agent'}
                </button>
                <button
                  className="btn danger"
                  style={{
                    padding: '0.7rem 1.2rem'
                  }}
                  onClick={() => sendCommand('uninstall', '', 'Desinstaller l\'agent')}
                  disabled={sending !== null}
                >
                  <Trash2 size={16} /> {sending === "Desinstaller l'agent" ? 'Desinstallation...' : 'Desinstaller l\'agent'}
                </button>
              </div>
            </div>

            <div style={{
              background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.25)',
              borderRadius: '12px', padding: '1.2rem'
            }}>
              <h4 style={{ color: '#f87171', marginBottom: '0.5rem' }}>Zone dangereuse</h4>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', lineHeight: '1.6' }}>
                <strong>Arreter</strong> = coupe l'agent mais garde l'installation (reboot = auto-relance)<br />
                <strong>Desinstaller</strong> = supprime completement l'agent, la tache planifiee et tous les fichiers
              </p>
            </div>
          </div>
        )}
      </div>
    </>
  )
}