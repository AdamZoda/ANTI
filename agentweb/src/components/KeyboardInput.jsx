import React, { useState } from 'react'
import { supabase } from '../lib/supabase'
import { Keyboard, Send } from 'lucide-react'

export default function KeyboardInput({ agent }) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [lastSent, setLastSent] = useState('')

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

          if (updated?.status === 'COMPLETED' || attempts >= 30) {
            clearInterval(poll)
            resolve(updated?.result ? JSON.parse(updated.result) : null)
          }
        }, 500)
        setTimeout(() => { clearInterval(poll); resolve(null) }, 15000)
      } catch (e) {
        resolve(null)
      }
    })
  }

  const sendText = async () => {
    if (!text.trim() || sending) return
    setSending(true)
    try {
      await sendCommand('keyboard_text', text)
      setLastSent(text)
      setText('')
    } catch {}
    setSending(false)
  }

  const sendKey = async (keyName) => {
    setSending(true)
    const vkMap = {
      'Enter': '{ENTER}', 'Tab': '{TAB}', 'Escape': '{ESC}', 'Backspace': '{BS}',
      'Delete': '{DEL}', 'Space': ' ',
      'Up': '{UP}', 'Down': '{DOWN}', 'Left': '{LEFT}', 'Right': '{RIGHT}',
      'Home': '{HOME}', 'End': '{END}', 'PageUp': '{PGUP}', 'PageDown': '{PGDN}',
      'F1': '{F1}', 'F2': '{F2}', 'F3': '{F3}', 'F4': '{F4}',
      'F5': '{F5}', 'F6': '{F6}', 'F7': '{F7}', 'F8': '{F8}',
      'F9': '{F9}', 'F10': '{F10}', 'F11': '{F11}', 'F12': '{F12}',
      'Ctrl+A': '^a', 'Ctrl+C': '^c', 'Ctrl+V': '^v',
      'Ctrl+X': '^x', 'Ctrl+Z': '^z', 'Ctrl+S': '%s',
      'Alt+F4': '%{F4}',
    }

    const sendKeys = vkMap[keyName] || keyName
    await sendCommand('keyboard_text', sendKeys)
    setSending(false)
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
          {['Enter', 'Tab', 'Escape', 'Backspace', 'Delete', 'Space', 'Up', 'Down', 'Left', 'Right',
            'Home', 'End', 'PageUp', 'PageDown',
            'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12'
          ].map(key => (
            <button key={key} className="btn" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
              onClick={() => sendKey(key)} disabled={sending}>
              {key}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          {['Ctrl+A', 'Ctrl+C', 'Ctrl+V', 'Ctrl+X', 'Ctrl+Z', 'Ctrl+S', 'Alt+F4'].map(key => (
            <button key={key} className="btn" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem', background: 'rgba(0,242,254,0.08)' }}
              onClick={() => sendKey(key)} disabled={sending}>
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
