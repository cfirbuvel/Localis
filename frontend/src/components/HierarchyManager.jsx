import React, { useState, useEffect } from 'react';

export default function HierarchyManager() {
  const [locations, setLocations] = useState([]);
  const [currentPath, setCurrentPath] = useState([]); // Array of {id, name, level}
  const [parentId, setParentId] = useState(null);
  const [level, setLevel] = useState('COUNTRY');
  const [loading, setLoading] = useState(false);
  
  // Creation Form
  const [newName, setNewName] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [error, setError] = useState('');

  const fetchLocations = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      let url = 'http://localhost:8000/api/locations';
      const params = [];
      if (parentId) params.push(`parent_id=${parentId}`);
      else params.push('level=COUNTRY');
      
      if (params.length) url += `?${params.join('&')}`;

      const res = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setLocations(data);
      }
    } catch (err) {
      console.error("Error loading locations:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLocations();
  }, [parentId]);

  const navigateToNode = (node) => {
    // Determine next level
    const levelMap = {
      'COUNTRY': 'CITY',
      'CITY': 'NEIGHBORHOOD',
      'NEIGHBORHOOD': 'STREET',
      'STREET': 'BUILDING',
      'BUILDING': 'DONE'
    };
    
    if (levelMap[node.level] === 'DONE') return; // Building is final node

    setCurrentPath([...currentPath, node]);
    setParentId(node.id);
    setLevel(levelMap[node.level]);
    setShowAddForm(false);
    setNewName('');
  };

  const navigateBackTo = (index) => {
    if (index === -1) {
      setCurrentPath([]);
      setParentId(null);
      setLevel('COUNTRY');
    } else {
      const targetNode = currentPath[index];
      const newPath = currentPath.slice(0, index + 1);
      
      const levelMap = {
        'COUNTRY': 'CITY',
        'CITY': 'NEIGHBORHOOD',
        'NEIGHBORHOOD': 'STREET',
        'STREET': 'BUILDING'
      };
      
      setCurrentPath(newPath);
      setParentId(targetNode.id);
      setLevel(levelMap[targetNode.level]);
    }
    setShowAddForm(false);
    setNewName('');
  };

  const handleCreateLocation = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setError('');

    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:8000/api/locations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          name: newName.trim(),
          level: level,
          parent_id: parentId
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to create location.");
      }

      setNewName('');
      setShowAddForm(false);
      fetchLocations();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <div className="dashboard-header">
        <div className="header-title">
          <h1>Location Tree Manager</h1>
          <p>Browse and build the Country → City → Neighborhood → Street → Building hierarchy.</p>
        </div>
      </div>

      {/* Breadcrumbs Navigation */}
      <div className="glass-panel" style={{
        padding: '16px 24px',
        marginBottom: '28px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        fontSize: '0.95rem',
        fontWeight: 600
      }}>
        <span 
          style={{ cursor: 'pointer', color: parentId ? 'var(--accent-purple)' : 'inherit' }}
          onClick={() => navigateBackTo(-1)}
        >
          🌍 Global Roots
        </span>
        {currentPath.map((node, idx) => (
          <React.Fragment key={node.id}>
            <span style={{ color: 'var(--text-muted)' }}>/</span>
            <span 
              style={{ 
                cursor: idx < currentPath.length - 1 ? 'pointer' : 'default', 
                color: idx < currentPath.length - 1 ? 'var(--accent-purple)' : 'inherit' 
              }}
              onClick={() => idx < currentPath.length - 1 && navigateBackTo(idx)}
            >
              {node.name} <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400 }}>({node.level.title()})</span>
            </span>
          </React.Fragment>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '30px', alignItems: 'start' }}>
        
        {/* Left Side: Child List */}
        <div className="glass-panel" style={{ padding: '32px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h3 style={{ fontSize: '1.25rem' }}>
              Subnodes at this level
              <span style={{ color: 'var(--accent-blue)', fontSize: '0.85rem', marginLeft: '12px', fontWeight: 500 }}>
                {locations.length} items found
              </span>
            </h3>
            {level !== 'DONE' && (
              <button 
                className="btn btn-primary" 
                style={{ padding: '8px 16px', fontSize: '0.85rem' }}
                onClick={() => setShowAddForm(!showAddForm)}
              >
                {showAddForm ? 'Cancel' : `➕ Add ${level.toLowerCase().replace('_', ' ')}`}
              </button>
            )}
          </div>

          {showAddForm && (
            <form onSubmit={handleCreateLocation} className="glass-panel" style={{
              padding: '20px',
              marginBottom: '24px',
              background: 'rgba(2, 6, 23, 0.4)'
            }}>
              <h4 style={{ marginBottom: '12px', fontSize: '0.95rem' }}>Create New {level.title()}</h4>
              {error && <div style={{ color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '12px' }}>⚠️ {error}</div>}
              <div className="form-group" style={{ display: 'flex', gap: '12px', marginBottom: 0 }}>
                <input
                  type="text"
                  className="form-input"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={`Enter ${level.toLowerCase()} name...`}
                  required
                />
                <button type="submit" className="btn btn-success" style={{ padding: '0 24px' }}>Save</button>
              </div>
            </form>
          )}

          {loading ? (
            <div style={{ padding: '40px 0', color: 'var(--text-secondary)', textAlign: 'center' }}>Loading subnodes...</div>
          ) : locations.length === 0 ? (
            <div style={{ padding: '40px 0', color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.9rem' }}>
              No children exist in this path. Click the button to add the first one!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {locations.map((loc) => (
                <div 
                  key={loc.id} 
                  className="glass-panel glass-panel-hover" 
                  style={{
                    padding: '16px 20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: loc.level === 'BUILDING' ? 'default' : 'pointer'
                  }}
                  onClick={() => loc.level !== 'BUILDING' && navigateToNode(loc)}
                >
                  <div>
                    <span style={{ fontSize: '1.05rem', fontWeight: 600 }}>{loc.name}</span>
                    <span className="badge" style={{ 
                      marginLeft: '12px', 
                      background: 'rgba(255,255,255,0.05)',
                      color: 'var(--text-secondary)'
                    }}>
                      {loc.level}
                    </span>
                  </div>
                  {loc.level !== 'BUILDING' && (
                    <span style={{ color: 'var(--accent-purple)', fontSize: '0.9rem', fontWeight: 600 }}>Browse ➔</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Side: Active Node Details */}
        <div className="glass-panel" style={{ padding: '28px' }}>
          <h3 style={{ fontSize: '1.1rem', marginBottom: '18px', borderBottom: '1px solid var(--glass-border)', paddingBottom: '10px' }}>
            Current Level Info
          </h3>
          
          {currentPath.length > 0 ? (
            <div>
              <div style={{ marginBottom: '16px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', display: 'block' }}>LEVEL TYPE</span>
                <strong style={{ color: 'var(--accent-purple)' }}>{currentPath[currentPath.length - 1].level}</strong>
              </div>
              <div style={{ marginBottom: '20px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', display: 'block' }}>LOCATION NAME</span>
                <strong style={{ fontSize: '1.2rem' }}>{currentPath[currentPath.length - 1].name}</strong>
              </div>

              <div style={{ marginTop: '24px' }}>
                <h4 style={{ fontSize: '0.9rem', marginBottom: '12px', color: 'var(--text-secondary)' }}>PLATFORM GROUPS</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem' }}>
                    <span style={{ fontSize: '1.1rem' }}>💬</span>
                    <span>Telegram Group:</span>
                    <span style={{ color: 'var(--accent-blue)', fontWeight: 600 }}>Auto-Generated</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem' }}>
                    <span style={{ fontSize: '1.1rem' }}>🟢</span>
                    <span>WhatsApp Group:</span>
                    <span style={{ color: 'var(--accent-blue)', fontWeight: 600 }}>Auto-Generated</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Select a Country node on the left to view active node details.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

// Simple Helper to capitalize strings
String.prototype.title = function() {
  return this.charAt(0).toUpperCase() + this.slice(1).toLowerCase();
}
