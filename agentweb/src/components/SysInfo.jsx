import React from 'react'
import { Monitor, Cpu, HardDrive, Globe, Clock, User, Hash } from 'lucide-react'

export default function SysInfo({ agent }) {
  const info = [
    { label: 'Hostname', value: agent.hostname, icon: <Monitor size={18} /> },
    { label: 'Utilisateur', value: agent.username, icon: <User size={18} /> },
    { label: 'IP Locale', value: agent.local_ip, icon: <Globe size={18} /> },
    { label: 'OS', value: agent.os_version, icon: <HardDrive size={18} /> },
    { label: 'Architecture', value: agent.architecture, icon: <Cpu size={18} /> },
    { label: 'Device ID', value: agent.device_id, icon: <Hash size={18} /> },
    { label: 'Version Agent', value: agent.agent_version, icon: <Monitor size={18} /> },
    { label: 'CPU', value: `${agent.cpu_percent || 0}%`, icon: <Cpu size={18} /> },
    { label: 'RAM', value: `${agent.ram_used_percent || 0}%`, icon: <HardDrive size={18} /> },
    { label: 'Statut', value: agent.status, icon: <Globe size={18} /> },
    { label: 'Dernière activité', value: agent.last_seen ? new Date(agent.last_seen).toLocaleString('fr-FR') : 'N/A', icon: <Clock size={18} /> },
  ]

  return (
    <div className="info-grid">
      {info.map((item, i) => (
        <div key={i} className="info-card">
          <label>{item.label}</label>
          <div className="value" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: 'var(--accent-cyan)' }}>{item.icon}</span>
            {item.value || 'N/A'}
          </div>
        </div>
      ))}
    </div>
  )
}
