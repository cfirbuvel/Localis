import React, { useState, useEffect } from 'react';

export default function RoleManager() {
  const [searchQuery, setSearchQuery] = useState('');
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  
  // Role Creation Form
  const [locations, setLocations] = useState([]);
  const [selectedLocId, setSelectedLocId] = useState('');
  const [roleType, setRoleType] = useState('MODERATOR');
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [formMsg, setFormMsg] = useState({ type: '', text: '' });

  const fetchUsers = async () => {
    if (!searchQuery.trim()) return;
    setLoadingUsers(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/users?q=${searchQuery}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadAllLocations = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:8000/api/locations', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setLocations(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadAllLocations();
  }, []);

  const handleAssignRole = async (e) => {
    e.preventDefault();
    if (!selectedUser || !selectedLocId) return;
    setFormMsg({ type: '', text: '' });

    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:8000/api/roles/assign', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          user_id: selectedUser.id,
          location_id: parseInt(selectedLocId),
          role: roleType
        })
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setFormMsg({ type: 'success', text: 'Role assigned successfully!' });
        // Refresh users search list
        fetchUsers();
        // Clear selected user highlight or reload user details
        setSelectedUser(null);
        setSelectedLocId('');
      } else {
        throw new Error(data.detail || 'Failed to assign role.');
      }
    } catch (err) {
      setFormMsg({ type: 'error', text: err.message });
    }
  };

  return (
    <div>
      <div className="dashboard-header">
        <div className="header-title">
          <h1>Hierarchy Role Management</h1>
          <p>Search citizens and assign MANAGER or MODERATOR roles to specific location nodes.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '30px', alignItems: 'start' }}>
        
        {/* Left Side: Search Panel */}
        <div className="glass-panel" style={{ padding: '32px' }}>
          <h3 style={{ fontSize: '1.25rem', marginBottom: '20px' }}>Citizen Directory</h3>
          
          <div style={{ display: 'flex', gap: '12px', marginBottom: '24px' }}>
            <input
              type="text"
              className="form-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by username, phone number, or Telegram ID..."
              onKeyDown={(e) => e.key === 'Enter' && fetchUsers()}
            />
            <button className="btn btn-primary" onClick={fetchUsers}>Search</button>
          </div>

          {loadingUsers ? (
            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>Searching directory...</div>
          ) : users.length === 0 ? (
            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Search user by name to view and manage roles.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {users.map((u) => (
                <div 
                  key={u.id}
                  className="glass-panel"
                  style={{
                    padding: '20px',
                    borderLeft: selectedUser?.id === u.id ? '4px solid var(--accent-purple)' : '1px solid var(--glass-border)',
                    background: selectedUser?.id === u.id ? 'rgba(139,92,246,0.06)' : 'var(--glass-bg)'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                    <div>
                      <h4 style={{ fontSize: '1.1rem' }}>{u.username || 'Anonymous User'}</h4>
                      <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginTop: '2px' }}>
                        TG ID: {u.telegram_id || 'N/A'} | WA Num: {u.whatsapp_number || 'N/A'}
                      </p>
                    </div>
                    <button 
                      className="btn btn-secondary" 
                      style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                      onClick={() => {
                        setSelectedUser(u);
                        setFormMsg({ type: '', text: '' });
                      }}
                    >
                      Select
                    </button>
                  </div>

                  {/* Active Roles list */}
                  {u.roles && u.roles.length > 0 ? (
                    <div style={{ marginTop: '12px' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
                        ACTIVE ROLES
                      </span>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {u.roles.map((r, idx) => (
                          <span key={idx} className="badge badge-approved" style={{ fontSize: '0.7rem' }}>
                            {r.role} @ {r.location_name}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '8px' }}>
                      No active manager/moderator roles (Standard Citizen).
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Side: Assignment Panel */}
        <div className="glass-panel" style={{ padding: '32px' }}>
          <h3 style={{ fontSize: '1.15rem', marginBottom: '24px', borderBottom: '1px solid var(--glass-border)', paddingBottom: '10px' }}>
            Assign Hierarchy Role
          </h3>

          {selectedUser ? (
            <form onSubmit={handleAssignRole}>
              <div style={{ marginBottom: '20px' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>ASSIGNING TO:</span>
                <strong style={{ display: 'block', fontSize: '1.15rem', marginTop: '2px' }}>{selectedUser.username}</strong>
              </div>

              {formMsg.text && (
                <div style={{
                  background: formMsg.type === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                  border: `1px solid ${formMsg.type === 'success' ? 'var(--success)' : 'var(--danger)'}`,
                  color: 'var(--text-primary)',
                  padding: '12px',
                  borderRadius: '8px',
                  marginBottom: '20px',
                  fontSize: '0.85rem'
                }}>
                  {formMsg.type === 'success' ? '✓' : '⚠️'} {formMsg.text}
                </div>
              )}

              <div className="form-group">
                <label className="form-label">SELECT ROLE</label>
                <select 
                  className="form-input" 
                  value={roleType} 
                  onChange={(e) => setRoleType(e.target.value)}
                  style={{ appearance: 'none', background: 'rgba(2, 6, 23, 0.8) url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\' fill=\'white\'%3E%3Cpath d=\'M7 10l5 5 5-5H7z\'/%3E%3C/svg%3E") no-repeat right 12px center', backgroundSize: '16px' }}
                >
                  <option value="MANAGER">MANAGER (Full control of node & children)</option>
                  <option value="MODERATOR">MODERATOR (Local chat moderate only)</option>
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: '28px' }}>
                <label className="form-label">ASSIGNED LOCATION NODE</label>
                <select 
                  className="form-input" 
                  value={selectedLocId} 
                  onChange={(e) => setSelectedLocId(e.target.value)}
                  required
                  style={{ appearance: 'none', background: 'rgba(2, 6, 23, 0.8) url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\' fill=\'white\'%3E%3Cpath d=\'M7 10l5 5 5-5H7z\'/%3E%3C/svg%3E") no-repeat right 12px center', backgroundSize: '16px' }}
                >
                  <option value="">-- Select Location Node --</option>
                  {locations.map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.name} ({loc.level})
                    </option>
                  ))}
                </select>
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: '100%' }}>
                Confirm Role Assignment
              </button>
            </form>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem', textAlign: 'center', padding: '40px 0' }}>
              Please select a user from the directory search results first.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
