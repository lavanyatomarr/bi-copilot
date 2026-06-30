import { useState } from 'react'
import ChartRenderer from './ChartRenderer.jsx'
import ConfidenceBadge from './ConfidenceBadge.jsx'

export default function AnswerCard({ turn, onFollowUp }) {
  const [showSql, setShowSql] = useState(false)
  const { question, answer, error, loading } = turn

  return (
    <div className="answer-card">
      <div className="qa-question">
        <span className="qa-q-mark">Q</span>
        <span>{question}</span>
      </div>

      {loading && <div className="qa-loading">Thinking…</div>}
      {error && <div className="auth-error">{error}</div>}

      {answer && (
        <div className="qa-answer">
          {answer.from_cache && (
            <div className="cache-flag">⚡ answered from cache (similarity {Math.round((answer.cache_similarity || 0) * 100)}%)</div>
          )}

          {answer.insight && (
            <div className="insight">
              <p className="insight-text">{answer.insight}</p>
              <ConfidenceBadge value={answer.confidence} />
            </div>
          )}

          {(answer.chart_spec || answer.rows?.length > 0) && (
            <div className="chart-box">
              <ChartRenderer chartSpec={answer.chart_spec} rows={answer.rows} />
            </div>
          )}

          {answer.sql && (
            <div className="sql-panel">
              <button className="sql-toggle" onClick={() => setShowSql((s) => !s)}>
                {showSql ? '▾ Hide SQL' : '▸ Show generated SQL'}
              </button>
              {showSql && (
                <>
                  <pre className="sql-code mono">{answer.sql}</pre>
                  {answer.explanation && <p className="sql-explain">{answer.explanation}</p>}
                </>
              )}
            </div>
          )}

          {answer.follow_ups?.length > 0 && (
            <div className="followups">
              <span className="followups-label">Follow up:</span>
              {answer.follow_ups.map((q, i) => (
                <button key={i} className="chip chip-btn" onClick={() => onFollowUp(q)}>{q}</button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
