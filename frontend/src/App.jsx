import React, { useState, useEffect } from 'react';
import Login from './components/Login';
import HierarchyManager from './components/HierarchyManager';
import RoleManager from './components/RoleManager';
import VerificationQueue from './components/VerificationQueue';
import CrisisFeed from './components/CrisisFeed';
import ModeratorFeed from './components/ModeratorFeed';
import CommunityApprovals from './components/CommunityApprovals';
import UserAnalytics from './components/UserAnalytics';


export default function App() {
  const [user, setUser] = useState(null);
  const [role, setRole] = useState(null);
  const [activeTab, setActiveTab] = useState('hierarchy');
  
  // Dashboard Stats
  const [stats, setStats] = useState({
    locationsCount: 0,
    pendingVerifications: 0,
    activeEmergencies: 0,
    flaggedLogs: 0
  });

  // Load user session from localstorage
  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    const storedRole = localStorage.getItem('role');
    const token = localStorage.getItem('token');
    
    if (storedUser && storedRole && token) {
      setUser(JSON.parse(storedUser));
      setRole(storedRole);
    }
  }, []);

  const fetchStats = async () => {
    if (!user) return;
    try {
      const token = localStorage.getItem('token');
      // Fetch Locations
      const locRes = await fetch('http://localhost:8000/api/locations', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const locations = locRes.ok ? await locRes.json() : [];

      // Fetch Pending Verifications
      const verRes = await fetch('http://localhost:8000/api/verifications/pending', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const verifs = verRes.ok ? await verRes.json() : [];

      // Fetch Emergencies
      const emRes = await fetch('http://localhost:8000/api/emergencies', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const emergencies = emRes.ok ? await emRes.json() : [];
      const activeEmCount = emergencies.filter(e => e.status === 'ACTIVE').length;

      // Fetch Moderation Logs
      const modRes = await fetch('http://localhost:8000/api/moderation/logs', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const logs = modRes.ok ? await modRes.json() : [];

      setStats({
        locationsCount: locations.length,
        pendingVerifications: verifs.length,
        activeEmergencies: activeEmCount,
        flaggedLogs: logs.length
      });
    } catch (err) {
      console.error("Error fetching stats:", err);
    }
  };

  useEffect(() => {
    fetchStats();
    // Poll stats every 5 seconds for live dashboard updates
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, [user]);

  const handleLoginSuccess = (usr, rl) => {
    setUser(usr);
    setRole(rl);
  };

  const handleLogout = () => {
    localStorage.removeItem('user');
    localStorage.removeItem('role');
    localStorage.removeItem('token');
    setUser(null);
    setRole(null);
  };

  if (!user) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  const renderContent = () => {
    switch (activeTab) {
      case 'hierarchy':
        return <HierarchyManager />;
      case 'roles':
        return <RoleManager />;
      case 'verifications':
        return <VerificationQueue />;
      case 'crisis':
        return <CrisisFeed />;
      case 'moderation':
        return <ModeratorFeed />;
      case 'approvals':
        return <CommunityApprovals />;
      case 'users':
        return <UserAnalytics />;
      default:
        return <HierarchyManager />;
    }
  };


  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">🌍</div>
          <span className="brand-name">BotOS Panel</span>
        </div>

        <nav className="nav-menu">
          <div 
            className={`nav-item ${activeTab === 'hierarchy' ? 'active' : ''}`}
            onClick={() => setActiveTab('hierarchy')}
          >
            <span>🗺️</span> Location Tree
          </div>

          <div 
            className={`nav-item ${activeTab === 'verifications' ? 'active' : ''}`}
            onClick={() => setActiveTab('verifications')}
          >
            <span>🔑</span> Verifications
            {stats.pendingVerifications > 0 && (
              <span className="badge badge-pending" style={{ marginLeft: 'auto' }}>
                {stats.pendingVerifications}
              </span>
            )}
          </div>

          {(role === 'SUPER_ADMIN' || role === 'MANAGER') && (
            <div 
              className={`nav-item ${activeTab === 'roles' ? 'active' : ''}`}
              onClick={() => setActiveTab('roles')}
            >
              <span>👥</span> Manage Roles
            </div>
          )}

          <div 
            className={`nav-item ${activeTab === 'crisis' ? 'active' : ''}`}
            onClick={() => setActiveTab('crisis')}
          >
            <span>🚨</span> Crisis Board
            {stats.activeEmergencies > 0 && (
              <span className="badge badge-rejected" style={{ marginLeft: 'auto' }}>
                {stats.activeEmergencies}
              </span>
            )}
          </div>

          <div 
            className={`nav-item ${activeTab === 'moderation' ? 'active' : ''}`}
            onClick={() => setActiveTab('moderation')}
          >
            <span>🤖</span> AI Moderation
          </div>

          {(role === 'SUPER_ADMIN' || role === 'MANAGER') && (
            <div 
              className={`nav-item ${activeTab === 'approvals' ? 'active' : ''}`}
              onClick={() => setActiveTab('approvals')}
            >
              <span>✅</span> Approvals Queue
            </div>
          )}

          <div 
            className={`nav-item ${activeTab === 'users' ? 'active' : ''}`}
            onClick={() => setActiveTab('users')}
          >
            <span>📊</span> Users Directory
          </div>
        </nav>


        <div className="user-profile">
          <div className="avatar">
            {user.username.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <span style={{ fontSize: '0.9rem', fontWeight: 600, display: 'block' }}>{user.username}</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{role}</span>
          </div>
          <button className="logout-btn" onClick={handleLogout}>Exit</button>
        </div>
      </aside>

      {/* Main Panel Content */}
      <main className="main-content">
        
        {/* Blinking Critical Alert Banner */}
        {stats.activeEmergencies > 0 && (
          <div className="emergency-banner">
            <span style={{ fontSize: '1.8rem' }}>⚠️</span>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'white' }}>CRITICAL EMERGENCY ALERT ONGOING</h3>
              <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.85)', marginTop: '2px' }}>
                There are {stats.activeEmergencies} active crisis alerts needing immediate attention. Check the Crisis Board tab.
              </p>
            </div>
            <button 
              className="btn btn-secondary" 
              style={{ marginLeft: 'auto', background: 'white', color: 'black', padding: '6px 12px', fontSize: '0.8rem', border: 'none' }}
              onClick={() => setActiveTab('crisis')}
            >
              View Board
            </button>
          </div>
        )}

        {/* Global Statistics Cards */}
        <section className="grid-stats">
          <div className="glass-panel stat-card">
            <div className="stat-icon icon-purple">📍</div>
            <div>
              <div className="stat-value">{stats.locationsCount}</div>
              <div className="stat-label">Total Location Nodes</div>
            </div>
          </div>

          <div className="glass-panel stat-card">
            <div className="stat-icon icon-emerald">🔑</div>
            <div>
              <div className="stat-value">{stats.pendingVerifications}</div>
              <div className="stat-label">Pending Verifications</div>
            </div>
          </div>

          <div className="glass-panel stat-card">
            <div className="stat-icon icon-red">🚨</div>
            <div>
              <div className="stat-value" style={{ color: stats.activeEmergencies > 0 ? 'var(--danger)' : 'inherit' }}>
                {stats.activeEmergencies}
              </div>
              <div className="stat-label">Active Emergencies</div>
            </div>
          </div>

          <div className="glass-panel stat-card">
            <div className="stat-icon icon-blue">🤖</div>
            <div>
              <div className="stat-value">{stats.flaggedLogs}</div>
              <div className="stat-label">AI Flagged Messages</div>
            </div>
          </div>
        </section>

        {/* Panel View */}
        <div style={{ marginTop: '20px' }}>
          {renderContent()}
        </div>

      </main>
    </div>
  );
}
