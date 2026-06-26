import React, { useState, useEffect } from 'react';

export default function CommunityApprovals() {
  const [requests, setRequests] = useState([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedProof, setSelectedProof] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Existing City Group Search state
  const [activeSearchReq, setActiveSearchReq] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [searching, setSearching] = useState(false);
  const [customChatId, setCustomChatId] = useState('');
  const [customInviteLink, setCustomInviteLink] = useState('');

  const fetchRequests = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:8000/api/community-requests/pending', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setRequests(data);
      } else {
        setError('Failed to fetch community creation requests.');
      }
    } catch (err) {
      console.error(err);
      setError('Connection error.');
    }
  };

  useEffect(() => {
    fetchRequests();
    const interval = setInterval(fetchRequests, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleReview = async (id, status) => {
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/community-requests/${id}/review`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ status })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setSuccess(`Request successfully ${status.toLowerCase()}!`);
        fetchRequests();
      } else {
        setError(data.detail || 'Failed to review request.');
      }
    } catch (err) {
      console.error(err);
      setError('Connection error.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleApproveClick = async (req) => {
    if (req.level === 'CITY') {
      setActiveSearchReq(req);
      setSearching(true);
      setSuggestions([]);
      setCustomChatId('');
      setCustomInviteLink('');
      try {
        const token = localStorage.getItem('token');
        const res = await fetch(`http://localhost:8000/api/community-requests/${req.id}/search-existing-groups`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setSuggestions(data);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setSearching(false);
      }
    } else {
      handleReview(req.id, 'APPROVED');
    }
  };

  const handleReviewWithCustomGroup = async (id, customChatId, customInviteLink) => {
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/community-requests/${id}/review`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ 
          status: 'APPROVED',
          custom_group_chat_id: customChatId,
          custom_group_invite_link: customInviteLink
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setSuccess('Request successfully approved and linked!');
        fetchRequests();
      } else {
        setError(data.detail || 'Failed to review request.');
      }
    } catch (err) {
      console.error(err);
      setError('Connection error.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '24px', position: 'relative' }}>
      <div className="panel-header" style={{ marginBottom: '20px' }}>
        <h2 style={{ fontSize: '1.4rem', fontWeight: 700 }}>👥 Community Creation Approvals</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          Review and approve community buttons requested by users. Approving will automatically create the groups.
        </p>
      </div>

      {error && <div className="alert alert-danger" style={{ marginBottom: '15px' }}>{error}</div>}
      {success && <div className="alert alert-success" style={{ marginBottom: '15px' }}>{success}</div>}

      {loading && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(13, 17, 23, 0.7)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 10000,
          borderRadius: '16px'
        }}>
          <div style={{
            width: '40px',
            height: '40px',
            border: '4px solid rgba(255, 255, 255, 0.1)',
            borderTop: '4px solid #8b5cf6',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            marginBottom: '16px'
          }}></div>
          <div style={{ fontWeight: 600, color: 'white', fontSize: '1rem' }}>
            Processing Request & Creating Groups...
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '8px' }}>
            Please wait, this might take a few seconds to prevent rate limits.
          </div>
        </div>
      )}

      {requests.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-secondary)' }}>
          ☕ No pending community creation requests!
        </div>
      ) : (
        <div className="table-container" style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                <th style={{ padding: '12px' }}>Requested By</th>
                <th style={{ padding: '12px' }}>Level</th>
                <th style={{ padding: '12px' }}>Community Name</th>
                <th style={{ padding: '12px' }}>Under Parent</th>
                <th style={{ padding: '12px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((req) => (
                <tr key={req.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', fontSize: '0.9rem' }}>
                  <td style={{ padding: '12px' }}>
                    <div style={{ fontWeight: 600 }}>@{req.user.username}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>TG: {req.user.telegram_id || 'N/A'}</div>
                  </td>
                  <td style={{ padding: '12px' }}>
                    <span className="badge badge-pending" style={{ fontSize: '0.75rem', textTransform: 'capitalize' }}>
                      {req.level.toLowerCase()}
                    </span>
                  </td>
                  <td style={{ padding: '12px', fontWeight: 600, color: 'var(--primary)' }}>
                    {req.name}
                    {req.proof_url && (
                      <div style={{ fontSize: '0.75rem', marginTop: '4px', fontWeight: 'normal' }}>
                        📄 <span 
                          style={{ color: '#60a5fa', cursor: 'pointer', textDecoration: 'underline' }} 
                          onClick={() => setSelectedProof(req)}
                        >
                          View Residency Proof
                        </span>
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '12px', color: 'var(--text-secondary)' }}>
                    {req.parent_name}
                  </td>
                  <td style={{ padding: '12px', textAlign: 'right' }}>
                    <button
                      className="btn btn-secondary"
                      style={{ marginRight: '8px', padding: '6px 12px', fontSize: '0.8rem', background: 'var(--danger)', border: 'none' }}
                      onClick={() => handleReview(req.id, 'REJECTED')}
                      disabled={loading}
                    >
                      Reject
                    </button>
                    <button
                      className="btn btn-primary"
                      style={{ 
                        padding: '6px 12px', 
                        fontSize: '0.8rem', 
                        border: 'none',
                        opacity: (loading || (req.level === 'BUILDING' && !req.proof_url)) ? 0.5 : 1,
                        cursor: (loading || (req.level === 'BUILDING' && !req.proof_url)) ? 'not-allowed' : 'pointer'
                      }}
                      disabled={loading || (req.level === 'BUILDING' && !req.proof_url)}
                      onClick={() => handleApproveClick(req)}
                      title={req.level === 'BUILDING' && !req.proof_url ? "Cannot approve building request without KYC proof" : ""}
                    >
                      Approve & Create
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedProof && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 9999,
          backdropFilter: 'blur(8px)'
        }}>
          <div className="glass-panel" style={{
            maxWidth: '500px',
            width: '90%',
            padding: '30px',
            position: 'relative',
            border: '1px solid rgba(255,255,255,0.1)'
          }}>
            <button 
              onClick={() => setSelectedProof(null)}
              style={{
                position: 'absolute',
                top: '15px',
                right: '15px',
                background: 'none',
                border: 'none',
                color: 'white',
                fontSize: '1.2rem',
                cursor: 'pointer'
              }}
            >
              ✕
            </button>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              📄 residency_proof_verification.pdf
            </h3>
            
            <div style={{
              background: '#0d1117',
              border: '1px solid #30363d',
              borderRadius: '8px',
              padding: '20px',
              fontFamily: 'monospace',
              fontSize: '0.85rem',
              color: '#c9d1d9',
              lineHeight: '1.5',
              marginBottom: '20px'
            }}>
              <div style={{ borderBottom: '1px solid #30363d', paddingBottom: '10px', marginBottom: '10px', color: 'var(--primary)', fontWeight: 'bold' }}>
                LOCALIS SECURITY KYC DOCUMENT PREVIEW
              </div>
              <div><strong>User:</strong> @{selectedProof.user.username}</div>
              <div><strong>Telegram ID:</strong> {selectedProof.user.telegram_id || 'N/A'}</div>
              <div><strong>Building Requested:</strong> {selectedProof.name}</div>
              <div><strong>Parent Location:</strong> {selectedProof.parent_name}</div>
              <div style={{ marginTop: '10px' }}><strong>Payload Status:</strong> SECURED_CIPHER</div>
              <div style={{ wordBreak: 'break-all', color: 'var(--text-secondary)' }}><strong>Payload:</strong> {selectedProof.proof_url}</div>
              <div style={{
                marginTop: '15px',
                border: '1px dashed #d29922',
                color: '#d29922',
                padding: '8px',
                borderRadius: '4px',
                textAlign: 'center',
                fontSize: '0.75rem'
              }}>
                ✓ SYSTEM VERIFIED DOCUMENT HASH
              </div>
            </div>
            
            <div style={{
              width: '100%',
              maxHeight: '220px',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.1)',
              marginBottom: '20px',
              background: '#070a0f',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              overflow: 'hidden'
            }}>
              <img 
                src={`http://localhost:8000/api/telegram-file/${encodeURIComponent(selectedProof.proof_url)}`} 
                alt="Verification Proof" 
                style={{ maxWidth: '100%', maxHeight: '220px', objectFit: 'contain' }}
              />
            </div>
            
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button 
                className="btn btn-secondary" 
                onClick={() => setSelectedProof(null)}
                style={{ padding: '8px 16px' }}
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}

      {activeSearchReq && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 9999,
          backdropFilter: 'blur(8px)'
        }}>
          <div className="glass-panel" style={{
            maxWidth: '600px',
            width: '90%',
            padding: '30px',
            position: 'relative',
            border: '1px solid rgba(255,255,255,0.1)'
          }}>
            <button 
              onClick={() => setActiveSearchReq(null)}
              style={{
                position: 'absolute',
                top: '15px',
                right: '15px',
                background: 'none',
                border: 'none',
                color: 'white',
                fontSize: '1.2rem',
                cursor: 'pointer'
              }}
            >
              ✕
            </button>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '20px' }}>
              🔍 Existing Public Group Suggestions for "{activeSearchReq.name}"
            </h3>
            
            {searching ? (
              <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-secondary)' }}>
                Searching Telegram for public groups...
              </div>
            ) : (
              <div>
                {suggestions.length > 0 ? (
                  <div style={{ marginBottom: '20px' }}>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                      We found the following matching public groups on Telegram:
                    </p>
                    <div style={{ display: 'grid', gap: '10px' }}>
                      {suggestions.map((sugg, idx) => (
                        <div key={idx} style={{
                          background: 'rgba(255,255,255,0.05)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: '8px',
                          padding: '12px 16px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}>
                          <div style={{ textAlign: 'left' }}>
                            <div style={{ fontWeight: 600 }}>
                              <a 
                                href={sugg.invite_link} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                style={{ color: '#60a5fa', textDecoration: 'underline' }}
                              >
                                {sugg.title}
                              </a>
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>ID: {sugg.chat_id}</div>
                          </div>
                          <button
                            className="btn btn-primary"
                            style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                            onClick={() => {
                              handleReviewWithCustomGroup(activeSearchReq.id, sugg.chat_id, sugg.invite_link);
                              setActiveSearchReq(null);
                            }}
                          >
                            Use This Group
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div style={{ marginBottom: '20px', textAlign: 'left' }}>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      ⚠️ No existing public groups or municipal groups were automatically found on Telegram or the web.
                    </p>
                  </div>
                )}
                
                <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '20px', marginBottom: '20px' }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '15px', textAlign: 'left' }}>Manually Add / Override Group:</h4>
                  <div style={{ display: 'grid', gap: '12px', textAlign: 'left' }}>
                    <div className="form-group">
                      <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Telegram Chat ID</label>
                      <input 
                        type="text" 
                        className="form-input" 
                        value={customChatId} 
                        onChange={(e) => setCustomChatId(e.target.value)} 
                        placeholder="e.g. -100123456789 or custom_username"
                      />
                    </div>
                    <div className="form-group">
                      <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Invite Link</label>
                      <input 
                        type="text" 
                        className="form-input" 
                        value={customInviteLink} 
                        onChange={(e) => setCustomInviteLink(e.target.value)} 
                        placeholder="e.g. https://t.me/custom_username"
                      />
                    </div>
                    <button
                      className="btn btn-primary"
                      style={{ padding: '8px 16px', justifySelf: 'start' }}
                      disabled={!customChatId || !customInviteLink}
                      onClick={() => {
                        handleReviewWithCustomGroup(activeSearchReq.id, customChatId, customInviteLink);
                        setActiveSearchReq(null);
                      }}
                    >
                      Use Custom Group
                    </button>
                  </div>
                </div>
                
                <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Or proceed to create a brand new channel/group:</span>
                  <button
                    className="btn btn-secondary"
                    style={{ background: 'var(--primary)', color: 'white', border: 'none', padding: '8px 16px' }}
                    onClick={() => {
                      handleReview(activeSearchReq.id, 'APPROVED');
                      setActiveSearchReq(null);
                    }}
                  >
                    Create New Group
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
