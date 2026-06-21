import React, { useState, useEffect } from 'react';

export default function CrisisFeed() {
  const [emergencies, setEmergencies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const fetchEmergencies = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:8000/api/emergencies', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setEmergencies(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmergencies();
  }, []);

  const handleResolve = async (id) => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/emergencies/resolve/${id}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setSuccessMsg("Crisis alert resolved successfully!");
        setTimeout(() => setSuccessMsg(''), 3000);
        fetchEmergencies();
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div>
      <div className="dashboard-header">
        <div className="header-title">
          <h1>🚨 Crisis Control Feed</h1>
          <p>Real-time neighborhood emergency ticker. Regional admins and AI collaborate on response.</p>
        </div>
      </div>

      {successMsg && (
        <div style={{
          background: 'rgba(16, 185, 129, 0.1)',
          border: '1px solid var(--success)',
          color: 'var(--text-primary)',
          padding: '16px 24px',
          borderRadius: '12px',
          marginBottom: '28px',
          fontSize: '0.95rem',
          fontWeight: 600
        }}>
          ✓ {successMsg}
        </div>
      )}

      {loading ? (
        <div className="glass-panel" style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Loading crisis feed...
        </div>
      ) : emergencies.length === 0 ? (
        <div className="glass-panel" style={{ padding: '60px', textAlign: 'center' }}>
          <span style={{ fontSize: '3rem', display: 'block', marginBottom: '16px' }}>🛡️</span>
          <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>All Clear</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>No active neighborhood crisis alerts at this moment.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {emergencies.map((e) => (
            <div 
              key={e.id} 
              className="glass-panel" 
              style={{
                padding: '24px',
                borderLeft: e.status === 'ACTIVE' ? '4px solid var(--danger)' : '4px solid var(--success)',
                background: e.status === 'ACTIVE' ? 'rgba(239, 68, 68, 0.05)' : 'rgba(16, 185, 129, 0.03)'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>CRISIS AREA</span>
                  <strong style={{ fontSize: '1.1rem', color: 'var(--text-primary)' }}>🚨 {e.location_name}</strong>
                </div>
                <span className={`badge ${e.status === 'ACTIVE' ? 'badge-rejected' : 'badge-approved'}`}>
                  {e.status}
                </span>
              </div>

              <div style={{
                background: 'rgba(2, 6, 23, 0.4)',
                padding: '16px',
                borderRadius: '8px',
                marginBottom: '16px',
                border: '1px solid var(--glass-border)',
                fontStyle: 'italic',
                color: 'var(--text-primary)'
              }}>
                "{e.message}"
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Reported by: <strong>{e.user.username}</strong> | {new Date(e.created_at).toLocaleString()}
                </span>
                
                {e.status === 'ACTIVE' && (
                  <button 
                    className="btn btn-success" 
                    style={{ padding: '8px 16px', fontSize: '0.8rem' }}
                    onClick={() => handleResolve(e.id)}
                  >
                    Mark as Resolved
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
