import React, { useState } from 'react'
import { supabase } from '../lib/supabase'
import { Camera, RefreshCw } from 'lucide-react'

export default function Screenshot({ agent }) {
  const [screenshot, setScreenshot] = useState(null)
  const [loading, setLoading] = useState(false)
  const [size, setSize] = useState(0)

  const capture = async () => {
    setLoading(true)
    setScreenshot(null)
    try {
      const { data, error } = await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: 'screenshot',
        command_content: '',
        status: 'PENDING'
      }]).select().single()

      if (error) throw error

      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        const { data: updated } = await supabase
          .from('agent_commands')
          .select('status, result')
          .eq('id', data.id)
          .single()

        if (updated?.status === 'COMPLETED' || attempts >= 15) {
          clearInterval(poll)
          setLoading(false)
          if (updated?.result) {
            try {
              const result = JSON.parse(updated.result)
              if (result.screenshot_b64) {
                setScreenshot(result.screenshot_b64)
                setSize(result.size_kb || 0)
              }
            } catch {}
          }
        }
      }, 500)
    } catch (e) {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.8rem', marginBottom: '1rem' }}>
        <button className="btn primary" onClick={capture} disabled={loading}>
          <Camera size={16} /> {loading ? 'Capture en cours...' : 'Capturer'}
        </button>
        {screenshot && (
          <button className="btn" onClick={capture} disabled={loading}>
            <RefreshCw size={14} /> Actualiser
          </button>
        )}
      </div>

      <div className="screenshot-container">
        {loading && <p style={{ color: 'var(--text-muted)' }}>Capture en cours...</p>}
        {!loading && !screenshot && <p style={{ color: 'var(--text-muted)' }}>Cliquez sur "Capturer" pour prendre une capture d'écran</p>}
        {screenshot && (
          <div>
            <img src={`data:image/jpeg;base64,${screenshot}`} alt="Screenshot" />
            <div style={{ textAlign: 'center', marginTop: '0.8rem', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
              {size} KB
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
