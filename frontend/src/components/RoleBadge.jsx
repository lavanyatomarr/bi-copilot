// Small coloured pill showing what a column is: measure / dimension / datetime / id.
const ROLE_STYLES = {
  measure: { bg: '#e6f1ec', fg: '#0e4f3e', label: 'measure' },
  dimension: { bg: '#eef1f4', fg: '#5b6573', label: 'dimension' },
  datetime: { bg: '#eaf0fb', fg: '#2b5797', label: 'datetime' },
  id: { bg: '#f4eef4', fg: '#7a4f7a', label: 'id' },
}

export default function RoleBadge({ role }) {
  const s = ROLE_STYLES[role] || ROLE_STYLES.dimension
  return (
    <span className="role-badge" style={{ background: s.bg, color: s.fg }}>
      {s.label}
    </span>
  )
}
