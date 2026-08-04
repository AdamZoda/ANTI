import React, { useState, useRef, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { Send, Trash2 } from 'lucide-react'

export default function Terminal({ agent }) {
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [executing, setExecuting] = useState(false)
  const outputRef = useRef(null)

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [history])

  const executeCommand = async (cmd) => {
    if (!cmd.trim() || executing) return

    setExecuting(true)
    setHistory(prev => [...prev, { type: 'cmd', text: cmd }])
    setInput('')

    try {
      const { data, error } = await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: cmd.startsWith('Get-') || cmd.startsWith('Set-') || cmd.startsWith('Restart-') ? 'powershell' : 'cmd',
        command_content: cmd,
        status: 'PENDING'
      }]).select().single()

      if (error) throw error

      const cmdId = data.id
      let attempts = 0
      const maxAttempts = 30

      const poll = setInterval(async () => {
        attempts++
        const { data: updated } = await supabase
          .from('agent_commands')
          .select('status, result')
          .eq('id', cmdId)
          .single()

        if (updated?.status === 'COMPLETED' || attempts >= maxAttempts) {
          clearInterval(poll)
          setExecuting(false)
          if (updated?.result) {
            try {
              const result = JSON.parse(updated.result)
              setHistory(prev => [...prev, {
                type: 'result',
                text: result.stdout || result.stderr || JSON.stringify(result, null, 2),
                isError: result.returncode !== 0
              }])
            } catch {
              setHistory(prev => [...prev, { type: 'result', text: updated.result }])
            }
          } else {
            setHistory(prev => [...prev, { type: 'result', text: 'Pas de réponse', isError: true }])
          }
        }
      }, 1000)

      setTimeout(() => clearInterval(poll), 30000)
    } catch (e) {
      setHistory(prev => [...prev, { type: 'result', text: `Erreur: ${e.message}`, isError: true }])
      setExecuting(false)
    }
  }

  return (
    <div className="terminal" style={{ height: '100%' }}>
      <div className="terminal-output" ref={outputRef}>
        {history.length === 0 && (
          <div style={{ color: '#475569', padding: '1rem' }}>
            Tapez une commande pour l'exécuter sur {agent.hostname}...
          </div>
        )}
        {history.map((entry, i) => (
          <div key={i} style={{ marginBottom: '0.5rem' }}>
            {entry.type === 'cmd' ? (
              <div className="cmd">$ {entry.text}</div>
            ) : (
              <pre className={entry.isError ? 'error' : 'result'} style={{
                whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0, fontSize: '0.82rem'
              }}>
                {entry.text}
              </pre>
            )}
          </div>
        ))}
        {executing && <div style={{ color: '#58a6ff' }}>Exécution en cours...</div>}
      </div>
      <div className="terminal-input">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && executeCommand(input)}
          placeholder="Entrez une commande..."
          disabled={executing}
        />
        <button onClick={() => executeCommand(input)} disabled={executing}>
          <Send size={16} />
        </button>
      </div>
    </div>
  )
}
