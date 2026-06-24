import React, { useState, useEffect } from 'react';

export default function UserAnalytics() {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  // User Message History Modal
  const [selectedUser, setSelectedUser] = useState(null);
  const [userMessages, setUserMessages] = useState([]);
  const [loadingUserMessages, setLoadingUserMessages] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const fetchUserMessages = async (userId) => {
    setLoadingUserMessages(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/chats/users/${userId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUserMessages(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingUserMessages(false);
    }
  };

  const openChatHistory = (u) => {
    setSelectedUser(u);
    setShowModal(true);
    fetchUserMessages(u.id);
  };

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

  const handleBanToggle = async (userId, isBanned) => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/users/${userId}/ban?ban=${!isBanned}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        fetchUsers();
      } else {
        const data = await res.json();
        setError(data.detail || 'Failed to update user ban status.');
      }
    } catch (err) {
      console.error(err);
      setError('Connection error.');
    }
  };

  const handleMuteToggle = async (userId, isMuted) => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/users/${userId}/mute?mute=${!isMuted}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        fetchUsers();
      } else {
        const data = await res.json();
        setError(data.detail || 'Failed to update user mute status.');
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
                <th style={{ padding: '12px' }}>Actions</th>
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
                    {u.first_name || u.last_name ? `${u.first_name || ''} ${u.last_name || ''}`.trim() : 'N/A'}
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
                  <td style={{ padding: '12px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button 
                        onClick={() => openChatHistory(u)}
                        className="btn btn-secondary"
                        style={{ padding: '6px 12px', fontSize: '0.75rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}
                      >
                        Logs
                      </button>
                      <button 
                        onClick={() => handleBanToggle(u.id, u.is_banned)}
                        className={`btn ${u.is_banned ? 'btn-success' : 'btn-danger'}`}
                        style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                      >
                        {u.is_banned ? 'Unban' : 'Ban'}
                      </button>
                      <button 
                        onClick={() => handleMuteToggle(u.id, u.is_muted)}
                        className="btn"
                        style={{ 
                          padding: '6px 12px', 
                          fontSize: '0.75rem', 
                          background: u.is_muted ? 'var(--success)' : '#e0a800', 
                          border: 'none', 
                          color: 'white' 
                        }}
                      >
                        {u.is_muted ? 'Unmute' : 'Mute'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}


      {showModal && selectedUser && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '20px'
        }}>
          <div className="glass-panel" style={{
            maxWidth: '600px',
            width: '100%',
            maxHeight: '85vh',
            display: 'flex',
            flexDirection: 'column',
            padding: '30px',
            position: 'relative',
            background: '#0d1117'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
              <h3 style={{ margin: 0, fontSize: '1.25rem' }}>
                💬 Chat Logs: @{selectedUser.username || 'unknown'}
              </h3>
              <button 
                onClick={() => { setShowModal(false); setSelectedUser(null); setUserMessages([]); }}
                className="btn btn-secondary"
                style={{ padding: '6px 12px', fontSize: '0.8rem' }}
              >
                Close
              </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', marginBottom: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {loadingUserMessages ? (
                <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '20px 0' }}>Loading user messages...</div>
              ) : userMessages.length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px 0' }}>No message history in the last 14 days.</div>
              ) : (
                userMessages.map(msg => (
                  <div key={msg.id} style={{ padding: '12px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                      <span style={{ fontWeight: 600, color: msg.platform === 'TELEGRAM' ? '#24A1DE' : '#25D366' }}>
                        {msg.platform === 'TELEGRAM' ? 'Telegram' : 'WhatsApp'} &bull; {msg.location_name}
                      </span>
                      <span>{new Date(msg.timestamp).toLocaleString()}</span>
                    </div>
                    <div style={{ color: 'white', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: '0.875rem' }}>{msg.message_text}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
