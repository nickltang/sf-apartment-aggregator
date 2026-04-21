const { useEffect, useState } = React;

function useApi(path) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    fetch(path)
      .then((r) => r.json())
      .then((d) => setItems(d.items || []))
      .catch(() => setItems([]));
  }, [path]);
  return items;
}

function App() {
  const listings = useApi('/api/listings?limit=100');
  const health = useApi('/api/source-health');
  const strictAlerts = useApi('/api/alerts?limit=30&alert_type=strict');
  const broadAlerts = useApi('/api/alerts?limit=30&alert_type=broad');

  return (
    <div className="wrap">
      <h1>SF Apartment Aggregator</h1>
      <p className="muted">Read-only dashboard for listing feed, source health, and alert history.</p>
      <div className="grid">
        <div className="card">
          <h3>Recent Listings</h3>
          <table>
            <thead>
              <tr>
                <th>Title</th><th>Price</th><th>Beds</th><th>Source</th><th>Match</th>
              </tr>
            </thead>
            <tbody>
              {listings.map((l) => (
                <tr key={l.canonical_url}>
                  <td><a href={l.listing_url} target="_blank" rel="noreferrer">{l.title}</a><br/><span className="muted">{l.location_text}</span></td>
                  <td>{l.price ?? 'N/A'}</td>
                  <td>{l.beds ?? 'N/A'}</td>
                  <td>{l.source}</td>
                  <td>{l.last_match_status ? 'matched' : l.last_match_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <div className="card" style={{marginBottom: '12px'}}>
            <h3>Source Health</h3>
            {health.map((h) => (
              <div key={h.source} style={{marginBottom: '8px'}}>
                <strong>{h.source}</strong>{' '}
                <span className={`pill ${h.success ? 'ok' : 'bad'}`}>{h.success ? 'ok' : 'error'}</span>
                <div className="muted">new: {h.new_count}, matched: {h.matched_count}, alerted: {h.alerted_count}</div>
                {!h.success && <div className="muted">{h.error_message}</div>}
              </div>
            ))}
          </div>
          <div className="card">
            <h3>Alert History</h3>
            <div style={{marginBottom: '10px'}}>
              <strong>Strict</strong>
              {strictAlerts.length === 0 && <div className="muted">No strict alerts yet.</div>}
              {strictAlerts.map((a) => (
                <div key={`strict-${a.id}`} style={{marginBottom: '8px'}}>
                  <strong>{a.title || a.canonical_url}</strong>
                  <div className="muted">{a.source} · {a.alerted_at}</div>
                </div>
              ))}
            </div>
            <div>
              <strong>Broad</strong>
              {broadAlerts.length === 0 && <div className="muted">No broad alerts yet.</div>}
              {broadAlerts.map((a) => (
                <div key={`broad-${a.id}`} style={{marginBottom: '8px'}}>
                  <strong>{a.title || a.canonical_url}</strong>
                  <div className="muted">{a.source} · {a.alerted_at}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('app')).render(<App />);
