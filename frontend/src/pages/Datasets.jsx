import { useRef, useState } from 'react'
import api from '../api'
import { useDatasets } from '../datasets.jsx'
import RoleBadge from '../components/RoleBadge.jsx'

export default function Datasets() {
  const { datasets, activeId, selectDataset, refresh } = useDatasets()
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [profile, setProfile] = useState(null)
  const [profileFor, setProfileFor] = useState(null)
  const fileRef = useRef(null)

  async function onUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setError(''); setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const r = await api.post('/datasets/upload', form)
      await refresh()
      selectDataset(r.data.dataset.id)
      setProfile(r.data)
      setProfileFor(r.data.dataset.id)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Upload failed. Use a CSV or Excel file.')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function viewProfile(id) {
    setError('')
    try {
      const r = await api.get(`/datasets/${id}/profile`)
      setProfile(r.data)
      setProfileFor(id)
    } catch {
      setError('Could not load that dataset.')
    }
  }

  async function deleteDataset(id, name, e) {
    e.stopPropagation()   // don't also trigger the row click
    if (!confirm(`Delete "${name}"? This removes the dataset and its data.`)) return
    try {
      await api.delete(`/datasets/${id}`)
      if (profileFor === id) { setProfile(null); setProfileFor(null) }
      await refresh()
    } catch {
      setError('Could not delete that dataset.')
    }
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1 className="page-title">Datasets</h1>
        <p className="page-sub">Upload a CSV or Excel file. The copilot reads its structure automatically.</p>
      </header>

      <div className="upload-row">
        <button className="btn-primary" disabled={uploading} onClick={() => fileRef.current?.click()}>
          {uploading ? 'Reading your file…' : 'Upload dataset'}
        </button>
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" hidden onChange={onUpload} />
        <span className="upload-hint">CSV or Excel, up to 25 MB</span>
      </div>
      {error && <div className="auth-error" style={{ marginTop: 12 }}>{error}</div>}

      {datasets.length === 0 ? (
        <div className="empty-card" style={{ marginTop: 24 }}>
          <p>No datasets yet. Upload one to get started.</p>
        </div>
      ) : (
        <div className="ds-list">
          {datasets.map((d) => (
            <button
              key={d.id}
              className={'ds-item' + (d.id === activeId ? ' ds-item--active' : '')}
              onClick={() => { selectDataset(d.id); viewProfile(d.id) }}
            >
              <div className="ds-name">{d.name}</div>
              <div className="ds-meta">
                <span className="mono">#{d.id} · {d.row_count.toLocaleString()} rows</span>
                {d.id === activeId && <span className="ds-active-tag">active</span>}
                <span className="ds-delete" onClick={(e) => deleteDataset(d.id, d.name, e)} title="Delete dataset">✕</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {profile && profile.dataset.id === profileFor && (
        <section className="profile">
          <h2 className="section-title">Columns in {profile.dataset.name}</h2>
          <div className="col-grid">
            {profile.columns.map((c) => (
              <div key={c.column_name} className="col-card">
                <div className="col-head">
                  <span className="mono col-name">{c.column_name}</span>
                  {c.is_kpi && <span className="kpi-tag">KPI</span>}
                </div>
                <RoleBadge role={c.semantic_role} />
                <div className="col-stats mono">
                  {c.distinct_count?.toLocaleString()} distinct · {c.null_pct}% null
                </div>
              </div>
            ))}
          </div>

          {profile.suggested_questions?.length > 0 && (
            <>
              <h2 className="section-title">Suggested questions</h2>
              <div className="chips">
                {profile.suggested_questions.map((q, i) => (
                  <span key={i} className="chip">{q}</span>
                ))}
              </div>
              <p className="page-sub" style={{ marginTop: 12 }}>
                These become clickable in the Workspace (next step).
              </p>
            </>
          )}
        </section>
      )}
    </div>
  )
}
