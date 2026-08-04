import React, { useState, useRef, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { Send } from 'lucide-react'

export default function Terminal({ agent }) {
  const [input, setInput] = useState('')
  const [executing, setExecuting] = useState(false)
  const [history, setHistory] = useState([])
  const [cmdHistory, setCmdHistory] = useState([])
  const [historyIdx, setHistoryIdx] = useState(-1)
  const outputRef = useRef(null)

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [history])

  useEffect(() => {
    const loadHistory = async () => {
      setHistory([])
      try {
        const { data } = await supabase
          .from('agent_commands')
          .select('id, command_type, command_content, status, result, created_at')
          .eq('device_id', agent.device_id)
          .in('command_type', ['cmd', 'powershell'])
          .order('created_at', { ascending: true })
          .limit(100)

        if (data) {
          const entries = []
          for (const cmd of data) {
            entries.push({ type: 'cmd', text: cmd.command_content, device: agent.device_id, id: cmd.id })
            if (cmd.result) {
              try {
                const result = JSON.parse(cmd.result)
                entries.push({
                  type: 'result',
                  text: result.stdout || result.stderr || JSON.stringify(result, null, 2),
                  isError: result.returncode !== 0,
                  device: agent.device_id,
                  id: cmd.id
                })
              } catch {
                entries.push({ type: 'result', text: cmd.result, device: agent.device_id, id: cmd.id })
              }
            }
          }
          setHistory(entries)
          setCmdHistory(data.map(c => c.command_content))
        }
      } catch {}
    }
    loadHistory()
  }, [agent.device_id])

  const executeCommand = async (cmd) => {
    if (!cmd.trim() || executing) return

    setExecuting(true)
    setInput('')

    try {
      const { data, error } = await supabase.from('agent_commands').insert([{
        device_id: agent.device_id,
        command_type: 'powershell',
        command_content: cmd,
        status: 'PENDING'
      }]).select().single()

      if (error) throw error

      setHistory(prev => [...prev, { type: 'cmd', text: cmd, device: agent.device_id, id: data.id }])
      setCmdHistory(prev => [...prev.filter(c => c !== cmd), cmd])
      setHistoryIdx(-1)

      const cmdId = data.id
      let attempts = 0
      const maxAttempts = 120

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
                isError: result.returncode !== 0,
                device: agent.device_id
              }])
            } catch {
              setHistory(prev => [...prev, { type: 'result', text: updated.result, device: agent.device_id }])
            }
          } else {
            setHistory(prev => [...prev, { type: 'result', text: 'Pas de réponse (timeout)', isError: true, device: agent.device_id }])
          }
        }
      }, 500)

      setTimeout(() => clearInterval(poll), 60000)
    } catch (e) {
      setHistory(prev => [...prev, { type: 'result', text: `Erreur: ${e.message}`, isError: true, device: agent.device_id }])
      setExecuting(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      executeCommand(input)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (cmdHistory.length === 0) return
      const newIdx = historyIdx === -1 ? cmdHistory.length - 1 : Math.max(0, historyIdx - 1)
      setHistoryIdx(newIdx)
      setInput(cmdHistory[newIdx])
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (historyIdx === -1) return
      const newIdx = historyIdx + 1
      if (newIdx >= cmdHistory.length) {
        setHistoryIdx(-1)
        setInput('')
      } else {
        setHistoryIdx(newIdx)
        setInput(cmdHistory[newIdx])
      }
    }
  }

  return (
    <div className="terminal" style={{ height: '100%' }}>
      <div className="terminal-output" ref={outputRef}>
        {history.length === 0 && (
          <div style={{ color: '#475569', padding: '1rem' }}>
            Tapez une commande pour l'exécuter sur {agent.hostname}...<br/>
            <span style={{ fontSize: '0.75rem' }}>Fleche haut/bas pour naviguer l'historique</span>
          </div>
        )}
        {history.map((entry, i) => (
          <div key={entry.id || i} style={{ marginBottom: '0.5rem' }}>
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
          onChange={e => { setInput(e.target.value); setHistoryIdx(-1) }}
          onKeyDown={handleKeyDown}
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
