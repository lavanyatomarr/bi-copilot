import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { useDatasets } from '../datasets.jsx'

export default function History() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const { selectDataset } = useDatasets()
  const nav = useNavigate()

  async function load() {
    setLoading(true)
    try {
      const r = await api.get('/history')
      setItems(r.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function reask(item) {
    // switch to that dataset, then go to the workspace and pre-fill the question
    selectDataset(item.dataset_id)
    nav('/', { state: { prefill: item.question } })
  }

  async function clearAll() {
    if (!confirm('Clear all history?')) return
    await api.delete('/history')
    setItems([])
  }

  return (
    <div className="page">
      <header className="page-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 className="page-title">History</h1>
          <p className="page-sub">Your past questions. Click any to ask it again.</p>
        </div>
        {items.length > 0 && <button className="btn-ghost" onClick={clearAll}>Clear all</button>}
      </header>

      {loading ? (
        <div className="empty-card"><p>Loading…</p></div>
      ) : items.length === 0 ? (
        <div className="empty-card"><p>No questions yet. Ask something in the Workspace.</p></div>
      ) : (
        <div className="hist-list">
          {items.map((it) => (
            <button key={it.id} className="hist-item" onClick={() => reask(it)}>
              <div className="hist-q">{it.question}</div>
              <div className="hist-meta mono">
                <span>{it.dataset_name}</span>
                <span>·</span>
                <span>{it.chart_type}</span>
                <span>·</span>
                <span>{it.row_count} rows</span>
                {it.from_cache && <span className="hist-cache">⚡ cached</span>}
                <span className="hist-time">{new Date(it.created_at).toLocaleString()}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
