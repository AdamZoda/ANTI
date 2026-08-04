import React, { useState, useEffect, useRef } from 'react'
import { supabase } from '../lib/supabase'
import { Folder, File, ArrowUp, RefreshCw } from 'lucide-react'

export default function FileManager({ agent }) {
  const [path, setPath] = useState('C:\\')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const agentRef = useRef(agent.device_id)

  const listFiles = async (dir) => {
    setLoading(true)
    try {
      const { data, error } = await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: 'file_list',
        command_content: dir,
        status: 'PENDING'
      }]).select().single()

      if (error) throw error

      let attempts = 0
      const maxAttempts = 120

      const poll = setInterval(async () => {
        attempts++
        const { data: updated } = await supabase
          .from('agent_commands')
          .select('status, result')
          .eq('id', data.id)
          .single()

        if (updated?.status === 'COMPLETED' || attempts >= maxAttempts) {
          clearInterval(poll)
          setLoading(false)
          if (updated?.result) {
            try {
              const result = JSON.parse(updated.result)
              if (result.items) {
                setItems(result.items)
                setPath(result.path || dir)
              }
            } catch {}
          }
        }
      }, 500)

      setTimeout(() => clearInterval(poll), 60000)
    } catch (e) {
      setLoading(false)
    }
  }

  useEffect(() => {
    agentRef.current = agent.device_id
    setItems([])
    setPath('C:\\')
    listFiles('C:\\')
  }, [agent.device_id])

  const openItem = (item) => {
    if (item.type === 'dir') {
      const sep = path.endsWith('\\') ? '' : '\\'
      listFiles(path + sep + item.name)
    }
  }

  const goUp = () => {
    const normalized = path.replace(/\\+$/, '')
    const parts = normalized.split('\\')
    if (parts.length > 1) {
      parts.pop()
      const newPath = parts.length === 1 ? parts[0] + '\\' : parts.join('\\')
      listFiles(newPath)
    }
  }

  const formatSize = (bytes) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '1rem' }}>
        <button className="btn" onClick={goUp} disabled={path === 'C:\\'}><ArrowUp size={14} /></button>
        <input
          value={path}
          onChange={e => setPath(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && listFiles(path)}
          style={{
            flex: 1, padding: '0.6rem 1rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)',
            borderRadius: '8px', color: 'var(--text-main)', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem'
          }}
        />
        <button className="btn" onClick={() => listFiles(path)}><RefreshCw size={14} /></button>
      </div>

      {loading ? (
        <div className="empty-state"><p>Chargement...</p></div>
      ) : (
        <div className="file-grid">
          {items.map((item, i) => (
            <div key={i} className="file-item" onClick={() => openItem(item)}>
              <div className="icon">{item.type === 'dir' ? <Folder size={24} color="#58a6ff" /> : <File size={24} color="#8b949e" />}</div>
              <div>
                <div className="name">{item.name}</div>
                <div className="meta">{item.type === 'dir' ? 'Dossier' : formatSize(item.size)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
