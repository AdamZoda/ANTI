import React, { useState, useEffect, useCallback } from 'react'
import { supabase } from './lib/supabase'
import AgentList from './components/AgentList'
import AgentDetail from './components/AgentDetail'
import Settings from './components/Settings'
import { Settings as SettingsIcon, Monitor } from 'lucide-react'

export default function App() {
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState('dashboard')

  const fetchAgents = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from('agents')
        .select('*')
        .order('last_seen', { ascending: false })

      if (!error && data) {
        setAgents(data)
        if (selectedAgent) {
          const updated = data.find(a => a.device_id === selectedAgent.device_id)
          if (updated) setSelectedAgent(updated)
        }
      }
    } catch (e) {
      console.error('Fetch agents error:', e)
    } finally {
      setLoading(false)
    }
  }, [selectedAgent])

  useEffect(() => {
    fetchAgents()
    const interval = setInterval(fetchAgents, 5000)
    return () => clearInterval(interval)
  }, [fetchAgents])

  const stats = {
    total: agents.length,
    online: agents.filter(a => a.status === 'ONLINE').length,
    offline: agents.filter(a => a.status === 'OFFLINE').length,
    busy: agents.filter(a => a.status === 'BUSY').length,
  }

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: '#0a0e1a', color: '#00f2fe', fontSize: '1.1rem', fontWeight: '600'
      }}>
        Chargement des agents...
      </div>
    )
  }

  return (
    <div className="app">
      <AgentList
        agents={agents}
        stats={stats}
        selectedAgent={selectedAgent}
        onSelect={(a) => { setSelectedAgent(a); setView('dashboard'); }}
        view={view}
        onViewChange={setView}
      />
      <div className="main-content">
        {view === 'settings' ? (
          <Settings agents={agents} onRefresh={fetchAgents} />
        ) : (
          <AgentDetail
            agent={selectedAgent}
            onRefresh={fetchAgents}
          />
        )}
      </div>
    </div>
  )
}
