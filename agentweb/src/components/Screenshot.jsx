import React, { useState, useEffect, useRef } from 'react'
import { supabase } from '../lib/supabase'
import { Camera, RefreshCw, Play, Pause } from 'lucide-react'

export default function Screenshot({ agent }) {
  const [screenshot, setScreenshot] = useState(null)
  const [loading, setLoading] = useState(false)
  const [size, setSize] = useState(0)
  const [error, setError] = useState(null)
  const [liveMode, setLiveMode] = useState(false)
  const [captureTime, setCaptureTime] = useState(null)
  const liveRef = useRef(null)

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
              const result = JSON.parse(updated.result)
              if (result.screenshot_b64) {
                setScreenshot(result.screenshot_b64)
                setSize(result.size_kb || 0)
                setCaptureTime(new Date().toLocaleTimeString('fr-FR'))
                setError(null)
              } else if (result.error) {
                setError(result.error)
              } else {
                setError('Pas de screenshot')
              }
            } catch {
              setError('Erreur parsing')
            }
          } else {
            setError('Pas de réponse')
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
          <div style={{ textAlign: 'center' }}>
            <img
              src={`data:image/jpeg;base64,${screenshot}`}
              alt="Screenshot"
              style={{
                maxWidth: '100%',
                maxHeight: '70vh',
                borderRadius: '12px',
                border: liveMode ? '2px solid var(--accent-green)' : '1px solid var(--border-color)',
                boxShadow: liveMode ? '0 0 20px rgba(34,197,94,0.3)' : 'none'
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
