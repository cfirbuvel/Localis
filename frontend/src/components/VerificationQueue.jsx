import React, { useState, useEffect } from 'react';

export default function VerificationQueue() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [rejectionReasons, setRejectionReasons] = useState({}); // {requestId: reasonText}
  const [activeRejectId, setActiveRejectId] = useState(null);
  const [successMsg, setSuccessMsg] = useState('');

  const fetchPending = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:8000/api/verifications/pending', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setRequests(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPending();
  }, []);

  const handleReview = async (id, status, reason = '') => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/verifications/${id}/review`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          status: status,
          rejection_reason: reason || undefined
        })
      });

      if (res.ok) {
        setSuccessMsg(`Request successfully ${status.toLowerCase()}!`);
        setTimeout(() => setSuccessMsg(''), 3000);
        
        // Reset states
        setActiveRejectId(null);
        setRejectionReasons(prev => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
        
        fetchPending();
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div>
      <div className="dashboard-header">
        <div className="header-title">
          <h1>Building Verification Queue</h1>
          <p>Review uploaded residency proofs and approve or deny access to private building chats.</p>
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
          Loading verification queue...
        </div>
      ) : requests.length === 0 ? (
        <div className="glass-panel" style={{ padding: '60px', textAlign: 'center' }}>
          <span style={{ fontSize: '3rem', display: 'block', marginBottom: '16px' }}>🎉</span>
          <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Queue is Empty!</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>All building residency verification requests have been reviewed.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '24px' }}>
          {requests.map((req) => (
            <div key={req.id} className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '18px' }}>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>{req.user.username}</h3>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    Phone: {req.user.phone_number || req.user.whatsapp_number || 'N/A'}
                  </span>
                </div>
                <span className="badge badge-pending">Pending</span>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', display: 'block' }}>REQUESTED ACCESS TO</span>
                <strong style={{ fontSize: '1.05rem', color: 'var(--accent-purple)' }}>🏢 {req.building_name}</strong>
              </div>

              {/* Styled Mock Document Preview */}
              <div style={{
                background: 'rgba(2, 6, 23, 0.7)',
                border: '1px dashed var(--glass-border)',
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}>
                <span style={{ fontSize: '2.2rem' }}>📄</span>
                <div style={{ flexGrow: 1, overflow: 'hidden' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {req.proof_url.replace('telegram_file_id:', 'bill_proof_').replace('whatsapp_media_id:', 'bill_proof_')}.png
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Residency Document Proof</span>
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--accent-blue)', cursor: 'pointer', textDecoration: 'underline' }} onClick={() => alert(`Reviewing Proof payload:\n${req.proof_url}`)}>
                  View Raw
                </span>
              </div>

              {/* Review Buttons */}
              {activeRejectId === req.id ? (
                <div style={{ marginTop: 'auto' }}>
                  <div className="form-group" style={{ marginBottom: '12px' }}>
                    <input
                      type="text"
                      className="form-input"
                      value={rejectionReasons[req.id] || ''}
                      onChange={(e) => setRejectionReasons({ ...rejectionReasons, [req.id]: e.target.value })}
                      placeholder="Reason for rejection..."
                      required
                    />
                  </div>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button 
                      className="btn btn-danger" 
                      style={{ flexGrow: 1, padding: '8px 0' }}
                      onClick={() => handleReview(req.id, 'REJECTED', rejectionReasons[req.id])}
                    >
                      Confirm Reject
                    </button>
                    <button 
                      className="btn btn-secondary" 
                      style={{ padding: '8px 16px' }}
                      onClick={() => setActiveRejectId(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: '12px', marginTop: 'auto' }}>
                  <button 
                    className="btn btn-success" 
                    style={{ flexGrow: 1 }}
                    onClick={() => handleReview(req.id, 'APPROVED')}
                  >
                    Approve Entry
                  </button>
                  <button 
                    className="btn btn-danger" 
                    style={{ padding: '10px 16px' }}
                    onClick={() => setActiveRejectId(req.id)}
                  >
                    Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
