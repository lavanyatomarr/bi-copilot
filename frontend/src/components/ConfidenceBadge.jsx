// Trust signal for the AI insight. Green >= 0.8, amber 0.5-0.8, red < 0.5.
export default function ConfidenceBadge({ value }) {
  if (value == null) return null
  const pct = Math.round(value * 100)
  let cls = 'conf-red'
  if (value >= 0.8) cls = 'conf-green'
  else if (value >= 0.5) cls = 'conf-amber'
  return <span className={`conf-badge ${cls}`}>confidence {pct}%</span>
}
