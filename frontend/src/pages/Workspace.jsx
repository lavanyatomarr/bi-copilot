export default function Workspace() {
  return (
    <div className="page">
      <header className="page-head">
        <h1 className="page-title">Workspace</h1>
        <p className="page-sub">Ask questions about your data in plain English.</p>
      </header>
      <div className="empty-card">
        <div className="empty-mark">✓</div>
        <h2>You're signed in</h2>
        <p>
          The interface is connected to your backend. Next we'll add dataset upload,
          then the question box with charts and AI insights.
        </p>
      </div>
    </div>
  )
}
