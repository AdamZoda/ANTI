import React, { useState } from 'react'
import { supabase } from '../lib/supabase'
import { Keyboard, Send } from 'lucide-react'

export default function KeyboardInput({ agent }) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [lastSent, setLastSent] = useState('')

  const sendText = async () => {
    if (!text.trim() || sending) return
    setSending(true)
    try {
      const { data, error } = await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: 'keyboard',
        command_content: text,
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

        if (updated?.status === 'COMPLETED' || attempts >= 30) {
          clearInterval(poll)
          setSending(false)
          setLastSent(text)
          setText('')
        }
      }, 500)
      setTimeout(() => clearInterval(poll), 15000)
    } catch (e) {
      setSending(false)
    }
  }

  const sendKey = async (key) => {
    const keyMap = {
      'Enter': 13, 'Tab': 9, 'Escape': 27, 'Backspace': 8,
      'Delete': 46, 'Space': 32, 'Up': 38, 'Down': 40, 'Left': 37, 'Right': 39,
      'Alt+F4': 115, 'Ctrl+S': 19, 'Ctrl+C': 67, 'Ctrl+V': 86,
    }
    try {
      await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: 'cmd',
        command_content: `[System.Windows.Forms.SendKeys]::SendWait('${key}')`,
        status: 'PENDING'
      }])
    } catch {}
  }

  return (
    <div>
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem' }}>
        <h4 style={{ color: 'var(--accent-cyan)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Keyboard size={18} /> Saisie clavier distante
        </h4>

        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1rem' }}>
          Tapez du texte et envoyez-le sur le PC distant. Le texte sera saisi à l'endroit où le curseur se trouve.
        </p>

        <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '1rem' }}>
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Tapez ici le texte à envoyer..."
            rows={3}
            style={{
              flex: 1, padding: '0.8rem', background: '#0d1117', border: '1px solid var(--border-color)',
              borderRadius: '8px', color: '#c9d1d9', fontFamily: "'JetBrains Mono', monospace",
              fontSize: '0.85rem', resize: 'vertical', outline: 'none'
            }}
            onKeyDown={e => {
              if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); sendText() }
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          {['Enter', 'Tab', 'Escape', 'Backspace', 'Delete', 'Space', 'Up', 'Down', 'Left', 'Right'].map(key => (
            <button key={key} className="btn" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
              onClick={() => sendKey(key)}>
              {key}
            </button>
          ))}
        </div>

        <button className="btn primary" onClick={sendText} disabled={sending || !text.trim()}>
          <Send size={14} /> {sending ? 'Envoi...' : 'Envoyer (Ctrl+Enter)'}
        </button>

        {lastSent && (
          <div style={{ marginTop: '0.8rem', color: 'var(--accent-green)', fontSize: '0.82rem' }}>
            Dernier envoi : "{lastSent}"
          </div>
        )}
      </div>
    </div>
  )
}
