import React, { useState, useEffect } from 'react';

export default function UserAnalytics() {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  const fetchUsers = async () => {
    try {
      const token = localStorage.getItem('token');
      const queryParam = search ? `?q=${encodeURIComponent(search)}` : '';
      const res = await fetch(`http://localhost:8000/api/users${queryParam}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      } else {
        setError('Failed to load user directory.');
      }
    } catch (err) {
      console.error(err);
      setError('Connection error.');
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [search]);

  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '15px' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700 }}>📊 Bot User Directory & Analytics</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Real-time tracking of users since they clicked Start, including metadata, coordinates, and activity logs.
          </p>
        </div>
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            className="input-field"
            placeholder="🔍 Search users..."
            style={{ width: '250px', padding: '8px 12px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white', borderRadius: '6px' }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {error && <div className="alert alert-danger" style={{ marginBottom: '15px' }}>{error}</div>}

      {users.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-secondary)' }}>
          🔍 No users matched your search criteria.
        </div>
      ) : (
        <div className="table-container" style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                <th style={{ padding: '12px' }}>User / Platform ID</th>
                <th style={{ padding: '12px' }}>Full Name</th>
                <th style={{ padding: '12px' }}>Language</th>
                <th style={{ padding: '12px' }}>Last Location (Coordinates)</th>
                <th style={{ padding: '12px' }}>Last Interaction</th>
                <th style={{ padding: '12px' }}>Last Active At</th>
                <th style={{ padding: '12px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', fontSize: '0.9rem' }}>
                  <td style={{ padding: '12px' }}>
                    <div style={{ fontWeight: 600 }}>@{u.username || 'unknown'}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {u.telegram_id ? `TG: ${u.telegram_id}` : u.whatsapp_number ? `WA: ${u.whatsapp_number}` : `ID: ${u.id.slice(0, 8)}...`}
                    </div>
                  </td>
                  <td style={{ padding: '12px', fontWeight: 500 }}>
                    {u.first_name || u.last_name ? `${u.first_name || ''} ${u.last_name || ''}`.strip() : 'N/A'}
                  </td>
                  <td style={{ padding: '12px', textTransform: 'uppercase', color: 'var(--primary)', fontWeight: 600, fontSize: '0.8rem' }}>
                    {u.language_code || 'en'}
                  </td>
                  <td style={{ padding: '12px' }}>
                    {u.latitude && u.longitude ? (
                      <a 
                        href={`https://www.google.com/maps?q=${u.latitude},${u.longitude}`} 
                        target="_blank" 
                        rel="noreferrer"
                        style={{ color: 'var(--primary)', textDecoration: 'underline', fontSize: '0.85rem' }}
                      >
                        📍 {u.latitude.toFixed(5)}, {u.longitude.toFixed(5)}
                      </a>
                    ) : (
                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No Location Sent</span>
                    )}
                  </td>
                  <td style={{ padding: '12px', fontStyle: 'italic', color: 'rgba(255,255,255,0.7)', fontSize: '0.85rem', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={u.last_interaction_text}>
                    {u.last_interaction_text || 'None'}
                  </td>
                  <td style={{ padding: '12px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    {new Date(u.last_active_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '12px' }}>
                    {u.is_banned ? (
                      <span className="badge badge-rejected" style={{ fontSize: '0.75rem' }}>Banned</span>
                    ) : u.is_muted ? (
                      <span className="badge badge-pending" style={{ fontSize: '0.75rem' }}>Muted</span>
                    ) : (
                      <span className="badge badge-approved" style={{ fontSize: '0.75rem' }}>Active</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
