import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type Stats = {
  events: number
  memories: number
  dream_runs: number
}

type Memory = {
  id: string
  path: string
  content: string
  frontmatter: Record<string, string>
}

type SearchResult = {
  id: string
  source: 'event' | 'memory'
  path?: string
  title: string
  content: string
  score: number
}

type Session = {
  session_id: string
  client: string
  agent_name?: string | null
  model_name?: string | null
  started_at: string
  event_count: number
}

type SessionEvent = {
  id: string
  event_name: string
  tool_name?: string | null
  user_prompt?: string | null
  occurred_at: string
}

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

function App() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [memories, setMemories] = useState<Memory[]>([])
  const [selectedPath, setSelectedPath] = useState<string>('')
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedSession, setSelectedSession] = useState<string>('')
  const [sessionEvents, setSessionEvents] = useState<SessionEvent[]>([])
  const [query, setQuery] = useState('pgvector age')
  const [scope, setScope] = useState('all')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loadingSearch, setLoadingSearch] = useState(false)

  const selectedMemory = useMemo(
    () => memories.find((memory) => memory.path === selectedPath) ?? null,
    [memories, selectedPath],
  )

  useEffect(() => {
    void refreshDashboard()
  }, [])

  useEffect(() => {
    if (sessions.length > 0 && selectedSession === '') {
      void loadSessionEvents(sessions[0].session_id)
    }
  }, [sessions, selectedSession])

  async function refreshDashboard() {
    await Promise.all([loadStats(), loadMemories(), loadSessions()])
  }

  async function loadStats() {
    const response = await fetch(`${API_BASE}/stats`)
    setStats(await response.json())
  }

  async function loadMemories() {
    const response = await fetch(`${API_BASE}/memories`)
    const payload = (await response.json()) as Memory[]
    setMemories(payload)
    if (payload.length > 0) {
      setSelectedPath((current) => current || payload[0].path)
    }
  }

  async function loadSessions() {
    const response = await fetch(`${API_BASE}/sessions`)
    const payload = (await response.json()) as Session[]
    setSessions(payload)
    if (payload.length > 0) {
      setSelectedSession((current) => current || payload[0].session_id)
    }
  }

  async function loadSessionEvents(sessionId: string) {
    setSelectedSession(sessionId)
    const response = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}/events`)
    setSessionEvents(await response.json())
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoadingSearch(true)
    try {
      const response = await fetch(
        `${API_BASE}/search?query=${encodeURIComponent(query)}&scope=${encodeURIComponent(scope)}&limit=5`,
      )
      setResults(await response.json())
    } finally {
      setLoadingSearch(false)
    }
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Unified Agentic Memory</p>
          <h1>Search, browse, and summarize durable agent memory.</h1>
          <p className="lede">
            This dashboard combines event history, semantic memories, session timelines, and dream
            phase activity behind one local interface.
          </p>
        </div>
        <button className="refresh-button" onClick={() => void refreshDashboard()} type="button">
          Refresh
        </button>
      </header>

      <section className="stats-grid">
        <StatCard label="Events" value={stats?.events ?? 0} />
        <StatCard label="Memories" value={stats?.memories ?? 0} />
        <StatCard label="Dream runs" value={stats?.dream_runs ?? 0} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Hybrid search</h2>
            <p>Combine vector and full-text results with shared reranking.</p>
          </div>
        </div>
        <form className="search-form" onSubmit={(event) => void handleSearch(event)}>
          <input value={query} onChange={(event) => setQuery(event.target.value)} />
          <select value={scope} onChange={(event) => setScope(event.target.value)}>
            <option value="all">all</option>
            <option value="events">events</option>
            <option value="memories">memories</option>
          </select>
          <button type="submit">{loadingSearch ? 'Searching...' : 'Search'}</button>
        </form>
        <div className="result-list">
          {results.length === 0 ? (
            <p className="empty">Run a search to see ranked results.</p>
          ) : (
            results.map((result) => (
              <article className="result-card" key={`${result.source}-${result.id}`}>
                <div className="result-meta">
                  <span>{result.source}</span>
                  <span>{result.score.toFixed(3)}</span>
                </div>
                <h3>{result.path ?? result.title}</h3>
                <p>{result.content}</p>
              </article>
            ))
          )}
        </div>
      </section>

      <section className="two-column">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2>Memory browser</h2>
              <p>Browse semantic memory paths and inspect merged content.</p>
            </div>
          </div>
          <div className="memory-layout">
            <nav className="memory-nav">
              {memories.map((memory) => (
                <button
                  className={memory.path === selectedPath ? 'memory-link active' : 'memory-link'}
                  key={memory.id}
                  onClick={() => setSelectedPath(memory.path)}
                  type="button"
                >
                  {memory.path}
                </button>
              ))}
            </nav>
            <article className="memory-viewer">
              {selectedMemory ? (
                <>
                  <h3>{selectedMemory.path}</h3>
                  <pre>{selectedMemory.content}</pre>
                </>
              ) : (
                <p className="empty">No memories available yet.</p>
              )}
            </article>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <h2>Session browser</h2>
              <p>Inspect sessions and their event timelines.</p>
            </div>
          </div>
          <div className="session-layout">
            <div className="session-list">
              {sessions.map((session) => (
                <button
                  className={session.session_id === selectedSession ? 'session-card active' : 'session-card'}
                  key={session.session_id}
                  onClick={() => void loadSessionEvents(session.session_id)}
                  type="button"
                >
                  <strong>{session.client}</strong>
                  <span>{session.agent_name ?? 'agent'}</span>
                  <span>{session.event_count} events</span>
                </button>
              ))}
            </div>
            <div className="timeline">
              {sessionEvents.length === 0 ? (
                <p className="empty">No session selected.</p>
              ) : (
                sessionEvents.map((event) => (
                  <article className="timeline-item" key={event.id}>
                    <div>
                      <h3>{event.event_name}</h3>
                      <p>{event.user_prompt ?? event.tool_name ?? 'No prompt content'}</p>
                    </div>
                    <time>{new Date(event.occurred_at).toLocaleString()}</time>
                  </article>
                ))
              )}
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <article className="stat-card">
      <p>{label}</p>
      <strong>{value}</strong>
    </article>
  )
}

export default App
