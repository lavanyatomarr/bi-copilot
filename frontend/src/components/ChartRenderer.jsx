import Plot from 'react-plotly.js'

// The backend sends a Plotly-shaped chart_spec. We just render it.
// If it's a table (or no chart fits), we render the rows as a simple table.
export default function ChartRenderer({ chartSpec, rows }) {
  const type = chartSpec?.type

  if (!type || type === 'table' || !chartSpec?.data?.length) {
    if (!rows?.length) return <div className="chart-empty">No rows to display.</div>
    const cols = Object.keys(rows[0])
    return (
      <div className="table-wrap">
        <table className="data-table mono">
          <thead>
            <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {rows.slice(0, 100).map((r, i) => (
              <tr key={i}>{cols.map((c) => <td key={c}>{format(r[c])}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  // green-tinted theme to match the app
  const layout = {
    ...chartSpec.layout,
    autosize: true,
    margin: { t: 36, r: 16, b: 48, l: 56 },
    colorway: ['#15725a', '#b5791c', '#2b5797', '#7a4f7a', '#c0392b'],
    font: { family: 'Inter, sans-serif', size: 12, color: '#161b22' },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
  }

  return (
    <Plot
      data={chartSpec.data}
      layout={layout}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%', height: '340px' }}
      useResizeHandler
    />
  )
}

function format(v) {
  if (typeof v === 'number') return v.toLocaleString()
  return String(v ?? '')
}
