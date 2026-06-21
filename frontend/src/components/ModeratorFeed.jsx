import React, { useState, useEffect } from 'react';

export default function ModeratorFeed() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:8000/api/moderation/logs', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const handleMute = async (userId, mute = true) => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/users/${userId}/mute?mute=${mute}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setSuccessMsg(`User successfully ${mute ? 'muted' : 'unmuted'}!`);
        setTimeout(() => setSuccessMsg(''), 3000);
        // Refresh logs list and recheck state
        fetchLogs();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleBan = async (userId, ban = true) => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/users/${userId}/ban?ban=${ban}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setSuccessMsg(`User successfully ${ban ? 'banned' : 'unbanned'}!`);
        setTimeout(() => setSuccessMsg(''), 3000);
        fetchLogs();
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div>
      <div className="dashboard-header">
        <div className="header-title">
          <h1>🤖 AI Moderation Dashboard</h1>
          <p>Analyze messages flagged by AI and execute citizen moderation actions (Mute, Ban).</p>
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
          Loading AI logs...
        </div>
      ) : logs.length === 0 ? (
        <div className="glass-panel" style={{ padding: '60px', textAlign: 'center' }}>
          <span style={{ fontSize: '3rem', display: 'block', marginBottom: '16px' }}>🛡️</span>
          <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Chat Feed is Clean</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>No messages flagged by AI moderation filters.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {logs.map((log) => (
            <div key={log.id} className="glass-panel" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>FLAGGED CONTEXT</span>
                  <strong style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>
                    📍 {log.location_name}
                  </strong>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <span className="badge badge-rejected" style={{ background: 'rgba(239, 68, 68, 0.15)', color: 'var(--danger)' }}>
                    {log.ai_analysis?.category || 'SPAM'}
                  </span>
                  <span className="badge badge-pending">
                    Score: {((log.ai_analysis?.score || 0) * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Message text */}
              <div style={{
                background: 'rgba(2, 6, 23, 0.5)',
                padding: '16px',
                borderRadius: '8px',
                marginBottom: '16px',
                border: '1px solid var(--glass-border)',
                color: '#f8fafc'
              }}>
                "{log.message_text}"
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  User: <strong>{log.user?.username || 'Anonymous'}</strong>
                  {log.user?.is_muted && <span style={{ color: 'var(--warning)', marginLeft: '10px' }}>(Muted)</span>}
                  {log.user?.is_banned && <span style={{ color: 'var(--danger)', marginLeft: '10px' }}>(Banned)</span>}
                  <br />
                  Flagged: {new Date(log.flagged_at).toLocaleString()}
                </div>

                {log.user && (
                  <div style={{ display: 'flex', gap: '10px' }}>
                    {log.user.is_muted ? (
                      <button 
                        className="btn btn-secondary" 
                        style={{ padding: '8px 14px', fontSize: '0.8rem' }}
                        onClick={() => handleMute(log.user.id, false)}
                      >
                        🔊 Unmute User
                      </button>
                    ) : (
                      <button 
                        className="btn btn-secondary" 
                        style={{ padding: '8px 14px', fontSize: '0.8rem', border: '1px solid var(--warning)' }}
                        onClick={() => handleMute(log.user.id, true)}
                      >
                        🔇 Mute User
                      </button>
                    )}

                    {log.user.is_banned ? (
                      <button 
                        className="btn btn-success" 
                        style={{ padding: '8px 14px', fontSize: '0.8rem' }}
                        onClick={() => handleBan(log.user.id, false)}
                      >
                        🛡️ Unban User
                      </button>
                    ) : (
                      <button 
                        className="btn btn-danger" 
                        style={{ padding: '8px 14px', fontSize: '0.8rem' }}
                        onClick={() => handleBan(log.user.id, true)}
                      >
                        🚫 Ban User
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
