import React, { useState, useEffect, useRef } from 'react'
import { supabase } from '../lib/supabase'
import { Camera, RefreshCw, Play, Pause, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react'

export default function Screenshot({ agent }) {
  const [screenshot, setScreenshot] = useState(null)
  const [loading, setLoading] = useState(false)
  const [size, setSize] = useState(0)
  const [error, setError] = useState(null)
  const [liveMode, setLiveMode] = useState(false)
  const [captureTime, setCaptureTime] = useState(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const liveRef = useRef(null)
  const imgRef = useRef(null)

  const capture = async () => {
    if (loading) return
    setLoading(true)
    setScreenshot(null)
    setError(null)
    try {
      const { data, error: insertError } = await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: 'screenshot',
        command_content: 'capture',
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
          setLoading(false)
          if (updated?.result) {
            try {
              const rawResult = updated.result
              let result
              try {
                result = JSON.parse(rawResult)
              } catch (parseErr) {
                const cleaned = rawResult.trim()
                if (cleaned.startsWith('{') && cleaned.endsWith('}')) {
                  try {
                    result = JSON.parse(cleaned)
                  } catch {
                    setError('Réponse corrompue du serveur. Redéployez l\'agent.')
                    return
                  }
                } else {
                  setError('Format de réponse invalide. Vérifiez l\'agent.')
                  return
                }
              }

              if (result.error) {
                setError(result.error)
              } else if (result.screenshot_b64) {
                const b64 = result.screenshot_b64.trim().replace(/[\r\n\s]/g, '')
                try {
                  atob(b64)
                } catch {
                  setError('Données screenshot invalides (base64 corrompu)')
                  return
                }
                setScreenshot(b64)
                setSize(result.size_kb || Math.round(b64.length * 3 / 4 / 1024))
                setCaptureTime(new Date().toLocaleTimeString('fr-FR'))
                setError(null)
                setZoom(1)
                setPan({ x: 0, y: 0 })
              } else {
                setError('Pas de screenshot dans la réponse')
              }
            } catch {
              setError('Erreur parsing résultat')
            }
          } else {
            setError('Pas de réponse de l\'agent')
          }
        }
      }, 500)
      setTimeout(() => clearInterval(poll), 60000)
    } catch (e) {
      setLoading(false)
      setError(e.message)
    }
  }

  useEffect(() => {
    if (liveMode) {
      capture()
      liveRef.current = setInterval(capture, 12000)
    } else {
      clearInterval(liveRef.current)
    }
    return () => clearInterval(liveRef.current)
  }, [liveMode])

  const handleWheel = (e) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? -0.1 : 0.1
    setZoom(z => Math.max(0.25, Math.min(4, z + delta)))
  }

  const handleMouseDown = (e) => {
    if (zoom > 1) {
      setIsDragging(true)
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
    }
  }

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y })
    }
  }

  const handleMouseUp = () => setIsDragging(false)

  const resetZoom = () => { setZoom(1); setPan({ x: 0, y: 0 }) }

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.8rem', marginBottom: '1rem', alignItems: 'center' }}>
        <button className="btn primary" onClick={capture} disabled={loading}>
          <Camera size={16} /> {loading ? 'Capture...' : 'Capturer'}
        </button>
        <button className={`btn ${liveMode ? 'active' : ''}`} onClick={() => setLiveMode(!liveMode)}>
          {liveMode ? <Pause size={14} /> : <Play size={14} />}
          {liveMode ? 'Arrêter Live' : 'Live Auto'}
        </button>
        {screenshot && !liveMode && (
          <button className="btn" onClick={capture} disabled={loading}>
            <RefreshCw size={14} /> Actualiser
          </button>
        )}
        {screenshot && (
          <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center', marginLeft: 'auto' }}>
            <button className="btn" onClick={() => setZoom(z => Math.max(0.25, z - 0.25))} title="Zoom -">
              <ZoomOut size={14} />
            </button>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', minWidth: '40px', textAlign: 'center' }}>
              {Math.round(zoom * 100)}%
            </span>
            <button className="btn" onClick={() => setZoom(z => Math.min(4, z + 0.25))} title="Zoom +">
              <ZoomIn size={14} />
            </button>
            <button className="btn" onClick={resetZoom} title="Reset zoom">
              <RotateCcw size={14} />
            </button>
          </div>
        )}
        {captureTime && (
          <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: 'auto' }}>
            {captureTime} • {size} KB
          </span>
        )}
      </div>

      {error && (
        <div style={{
          padding: '1rem', background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.4)',
          borderRadius: '10px', color: '#fca5a5', marginBottom: '1rem', fontSize: '0.85rem'
        }}>
          {error}
        </div>
      )}

      <div className="screenshot-container">
        {loading && !screenshot && <p style={{ color: 'var(--text-muted)' }}>Capture en cours...</p>}
        {!loading && !screenshot && !error && <p style={{ color: 'var(--text-muted)' }}>Cliquez sur "Capturer" ou activez "Live Auto"</p>}
        {screenshot && (
          <div
            style={{
              textAlign: 'center',
              overflow: 'hidden',
              cursor: zoom > 1 ? (isDragging ? 'grabbing' : 'grab') : 'zoom-in',
              borderRadius: '12px',
              border: liveMode ? '2px solid var(--accent-green)' : '1px solid var(--border-color)',
              background: '#000',
            }}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onClick={() => { if (zoom === 1) setZoom(2) }}
          >
            <img
              ref={imgRef}
              src={`data:image/jpeg;base64,${screenshot}`}
              alt="Screenshot"
              draggable={false}
              style={{
                maxWidth: zoom > 1 ? 'none' : '100%',
                maxHeight: zoom > 1 ? 'none' : '70vh',
                transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
                transformOrigin: 'center center',
                borderRadius: '12px',
                transition: isDragging ? 'none' : 'transform 0.1s ease',
                boxShadow: liveMode ? '0 0 20px rgba(34,197,94,0.3)' : 'none'
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
