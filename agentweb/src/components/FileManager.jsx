import React, { useState, useEffect, useRef } from 'react'
import { supabase } from '../lib/supabase'
import { Folder, File, ArrowUp, RefreshCw, HardDrive, FileText, ChevronRight, Eye, Download, Trash2 } from 'lucide-react'

export default function FileManager({ agent }) {
  const [path, setPath] = useState('C:\\')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [drives, setDrives] = useState([])
  const [viewingFile, setViewingFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [fileLoading, setFileLoading] = useState(false)
  const [actionStatus, setActionStatus] = useState(null)

  const sendCommand = (type, content) => {
    return new Promise(async (resolve) => {
      try {
        const { data, error: insertError } = await supabase.from('agent_commands').insert([{
          device_id: agent.device_id,
          command_type: type,
          command_content: content,
          status: 'PENDING'
        }]).select().single()

        if (insertError) throw insertError

        let attempts = 0
        const poll = setInterval(async () => {
          attempts++
          const { data: updated } = await supabase
            .from('agent_commands')
            .select('status, result')
            .eq('id', data.id)
            .single()

          if (updated?.status === 'COMPLETED' || attempts >= 120) {
            clearInterval(poll)
            if (updated?.result) {
              try { resolve(JSON.parse(updated.result)) }
              catch { resolve({ error: 'Invalid JSON response' }) }
            } else {
              resolve({ error: 'No response (timeout)' })
            }
          }
        }, 500)
        setTimeout(() => { clearInterval(poll); resolve({ error: 'Timeout' }) }, 60000)
      } catch (e) {
        resolve({ error: e.message })
      }
    })
  }

  const listFiles = async (dir) => {
    setLoading(true)
    setError(null)
    setViewingFile(null)
    const result = await sendCommand('file_list', dir)
    setLoading(false)
    if (result.error) {
      setError(result.error)
    } else if (result.items) {
      setItems(result.items)
      setPath(result.path || dir)
    }
  }

  const readFile = async (filePath) => {
    setFileLoading(true)
    setViewingFile(filePath)
    const result = await sendCommand('file_read', filePath)
    setFileLoading(false)
    if (result.error) {
      setFileContent(`[Erreur] ${result.error}`)
    } else {
      setFileContent(result.content || '')
    }
  }

  const downloadFile = async (filePath) => {
    setActionStatus({ type: 'download', name: filePath.split('\\').pop() })
    const result = await sendCommand('file_download', filePath)
    setActionStatus(null)
    if (result.error) {
      setError(`Erreur download: ${result.error}`)
      return
    }
    if (result.content_b64) {
      const byteString = atob(result.content_b64)
      const ab = new ArrayBuffer(byteString.length)
      const ia = new Uint8Array(ab)
      for (let i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i)
      }
      const blob = new Blob([ab])
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = result.filename || filePath.split('\\').pop()
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    }
  }

  const deleteFile = async (filePath, fileName) => {
    if (!confirm(`Supprimer "${fileName}" ?`)) return
    setActionStatus({ type: 'delete', name: fileName })
    const result = await sendCommand('file_delete', filePath)
    setActionStatus(null)
    if (result.error) {
      setError(`Erreur: ${result.error}`)
    } else {
      listFiles(path)
    }
  }

  const fetchDrives = async () => {
    const result = await sendCommand('powershell', "Get-PSDrive -PSProvider FileSystem | ForEach-Object { $_.Root }")
    if (result.stdout) {
      const driveList = result.stdout.split('\n').map(d => d.trim()).filter(d => d.match(/^[A-Z]:\\/))
      setDrives(driveList)
    }
  }

  useEffect(() => {
    listFiles('C:\\')
    fetchDrives()
  }, [agent.device_id])

  const openItem = (item) => {
    if (item.type === 'dir') {
      const sep = path.endsWith('\\') ? '' : '\\'
      listFiles(path + sep + item.name)
    } else {
      readFile(path + (path.endsWith('\\') ? '' : '\\') + item.name)
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

  const navigateToDrive = (drive) => {
    listFiles(drive)
  }

  const formatSize = (bytes) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  }

  const getBreadcrumb = () => {
    const parts = path.replace(/\\+$/, '').split('\\')
    const crumbs = []
    for (let i = 0; i < parts.length; i++) {
      const crumbPath = i === 0 ? parts[0] + '\\' : parts.slice(0, i + 1).join('\\')
      crumbs.push({ label: parts[i] || parts[0], path: crumbPath })
    }
    return crumbs
  }

  const getFileIcon = (item) => {
    if (item.type === 'dir') return <Folder size={20} color="#58a6ff" />
    const ext = item.name.split('.').pop().toLowerCase()
    const iconColors = {
      'txt': '#8b949e', 'log': '#8b949e', 'md': '#8b949e',
      'js': '#f59e0b', 'jsx': '#58a6ff', 'ts': '#3b82f6', 'tsx': '#58a6ff',
      'py': '#22c55e', 'rb': '#ef4444', 'go': '#06b6d4',
      'json': '#f59e0b', 'xml': '#f59e0b', 'yaml': '#f59e0b', 'yml': '#f59e0b',
      'html': '#ef4444', 'css': '#3b82f6', 'scss': '#f472b6',
      'jpg': '#a855f7', 'jpeg': '#a855f7', 'png': '#a855f7', 'gif': '#a855f7', 'svg': '#f59e0b', 'webp': '#a855f7',
      'mp3': '#22c55e', 'wav': '#22c55e', 'mp4': '#ef4444', 'avi': '#ef4444', 'mkv': '#ef4444',
      'zip': '#f59e0b', 'rar': '#f59e0b', '7z': '#f59e0b', 'tar': '#f59e0b', 'gz': '#f59e0b',
      'exe': '#ef4444', 'msi': '#ef4444', 'dll': '#8b949e',
      'pdf': '#ef4444', 'doc': '#3b82f6', 'docx': '#3b82f6', 'xls': '#22c55e', 'xlsx': '#22c55e',
    }
    return <File size={20} color={iconColors[ext] || '#8b949e'} />
  }

  if (viewingFile) {
    return (
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '1rem' }}>
          <button className="btn" onClick={() => { setViewingFile(null); setFileContent(''); listFiles(path) }}>
            <ArrowUp size={14} /> Retour
          </button>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            <FileText size={14} />
            <span style={{ color: 'var(--text-main)', fontWeight: '600' }}>{viewingFile.split('\\').pop()}</span>
            <span style={{ fontSize: '0.75rem' }}>({viewingFile})</span>
          </div>
          <button className="btn" onClick={() => downloadFile(viewingFile)}><Download size={14} /></button>
          <button className="btn" onClick={() => readFile(viewingFile)}><RefreshCw size={14} /></button>
        </div>
        <div style={{
          background: '#0d1117', border: '1px solid var(--border-color)', borderRadius: '12px',
          padding: '1rem', maxHeight: '60vh', overflow: 'auto'
        }}>
          {fileLoading ? (
            <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center' }}>Chargement du fichier...</div>
          ) : (
            <pre style={{
              margin: 0, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.82rem',
              color: '#c9d1d9', whiteSpace: 'pre-wrap', wordBreak: 'break-all', lineHeight: '1.6'
            }}>
              {fileContent || '[Fichier vide]'}
            </pre>
          )}
        </div>
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.8rem' }}>
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

      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.8rem', flexWrap: 'wrap' }}>
        <button className="btn" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }} onClick={() => listFiles('C:\\')}>
          <HardDrive size={12} /> C:\
        </button>
        {drives.filter(d => d !== 'C:\\').map(d => (
          <button key={d} className="btn" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }} onClick={() => navigateToDrive(d)}>
            <HardDrive size={12} /> {d}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        {getBreadcrumb().map((crumb, i, arr) => (
          <React.Fragment key={i}>
            <button
              style={{
                background: 'none', border: 'none', color: i === arr.length - 1 ? 'var(--accent-cyan)' : 'var(--text-muted)',
                cursor: 'pointer', fontSize: '0.82rem', fontWeight: i === arr.length - 1 ? '700' : '400',
                fontFamily: "'JetBrains Mono', monospace", padding: '0.2rem 0.4rem', borderRadius: '4px'
              }}
              onClick={() => listFiles(crumb.path)}
            >
              {crumb.label}
            </button>
            {i < arr.length - 1 && <ChevronRight size={12} color="var(--text-muted)" />}
          </React.Fragment>
        ))}
      </div>

      {actionStatus && (
        <div style={{
          padding: '0.5rem 1rem', background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.4)',
          borderRadius: '8px', color: '#93c5fd', marginBottom: '1rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.5rem'
        }}>
          <RefreshCw size={14} className="spin" />
          {actionStatus.type === 'delete' ? `Suppression de ${actionStatus.name}...` : `Telechargement de ${actionStatus.name}...`}
        </div>
      )}

      {error && (
        <div style={{
          padding: '1rem', background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.4)',
          borderRadius: '10px', color: '#fca5a5', marginBottom: '1rem', fontSize: '0.85rem'
        }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="empty-state"><p>Chargement...</p></div>
      ) : (
        <div className="file-grid">
          {items.map((item, i) => {
            const fullPath = path + (path.endsWith('\\') ? '' : '\\') + item.name
            return (
              <div key={i} className="file-item" style={{ position: 'relative' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flex: 1, minWidth: 0, cursor: 'pointer' }} onClick={() => openItem(item)}>
                  <div className="icon">{getFileIcon(item)}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="name">{item.name}</div>
                    <div className="meta">
                      {item.type === 'dir' ? 'Dossier' : formatSize(item.size)}
                      {item.modified && ` • ${new Date(item.modified).toLocaleDateString('fr-FR')}`}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.2rem', opacity: 0.6, transition: 'opacity 0.2s' }}
                     onMouseEnter={e => e.currentTarget.style.opacity = '1'}
                     onMouseLeave={e => e.currentTarget.style.opacity = '0.6'}>
                  {item.type === 'file' && (
                    <>
                      <button
                        className="btn"
                        style={{ padding: '0.3rem 0.5rem', fontSize: '0.7rem' }}
                        onClick={(e) => { e.stopPropagation(); readFile(fullPath) }}
                        title="Voir le contenu"
                      >
                        <Eye size={12} />
                      </button>
                      <button
                        className="btn"
                        style={{ padding: '0.3rem 0.5rem', fontSize: '0.7rem', background: 'rgba(59,130,246,0.15)', borderColor: 'rgba(59,130,246,0.4)', color: '#60a5fa' }}
                        onClick={(e) => { e.stopPropagation(); downloadFile(fullPath) }}
                        title="Telecharger"
                      >
                        <Download size={12} />
                      </button>
                    </>
                  )}
                  <button
                    className="btn danger"
                    style={{ padding: '0.3rem 0.5rem', fontSize: '0.7rem' }}
                    onClick={(e) => { e.stopPropagation(); deleteFile(fullPath, item.name) }}
                    title="Supprimer"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            )
          })}
          {items.length === 0 && !loading && (
            <div className="empty-state" style={{ gridColumn: '1 / -1' }}>
              <Folder size={32} />
              <p>Dossier vide</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
