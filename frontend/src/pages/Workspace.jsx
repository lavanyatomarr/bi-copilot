import { useEffect, useRef, useState } from 'react'
import api from '../api'
import { useDatasets } from '../datasets.jsx'
import AnswerCard from '../components/AnswerCard.jsx'

export default function Workspace() {
  const { datasets, active, activeId, selectDataset } = useDatasets()
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState([])     // conversation history (newest last)
  const [suggested, setSuggested] = useState([])
  const threadRef = useRef(null)

  // load the active dataset's suggested questions as starter prompts
  useEffect(() => {
    if (!activeId) return
    api.get(`/datasets/${activeId}/profile`)
      .then((r) => setSuggested(r.data.suggested_questions || []))
      .catch(() => setSuggested([]))
    setTurns([])   // reset conversation when dataset changes
  }, [activeId])

  // auto-scroll to the newest turn
  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns])

  async function ask(q) {
    const text = (q ?? question).trim()
    if (!text || !activeId) return
    setQuestion('')

    const turn = { id: Date.now(), question: text, loading: true, answer: null, error: null }
    setTurns((t) => [...t, turn])

    try {
      const r = await api.post('/query', { dataset_id: activeId, question: text })
      setTurns((t) => t.map((x) => x.id === turn.id ? { ...x, loading: false, answer: r.data } : x))
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Something went wrong answering that.'
      setTurns((t) => t.map((x) => x.id === turn.id ? { ...x, loading: false, error: msg } : x))
    }
  }

  function onSubmit(e) { e.preventDefault(); ask() }

  if (!datasets.length) {
    return (
      <div className="page">
        <header className="page-head"><h1 className="page-title">Workspace</h1></header>
        <div className="empty-card">
          <p>Upload a dataset first, then come back here to ask it questions.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="workspace">
      <header className="ws-head">
        <div>
          <h1 className="page-title">Workspace</h1>
          <p className="page-sub">Ask questions about your data in plain English.</p>
        </div>
        <label className="ds-picker">
          <span>Dataset</span>
          <select value={activeId || ''} onChange={(e) => selectDataset(Number(e.target.value))}>
            {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
      </header>

      <div className="thread" ref={threadRef}>
        {turns.length === 0 && (
          <div className="starter">
            <p className="starter-title">Try asking{active ? ` about ${active.name}` : ''}:</p>
            <div className="chips">
              {suggested.map((q, i) => (
                <button key={i} className="chip chip-btn" onClick={() => ask(q)}>{q}</button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t) => (
          <AnswerCard key={t.id} turn={t} onFollowUp={(q) => ask(q)} />
        ))}
      </div>

      <form className="ask-bar" onSubmit={onSubmit}>
        <input
          className="ask-input"
          placeholder="Ask anything — e.g. which plan has the highest revenue?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="btn-primary" type="submit" disabled={!question.trim()}>Ask</button>
      </form>
    </div>
  )
}
