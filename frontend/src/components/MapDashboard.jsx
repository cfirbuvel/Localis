import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import * as L from 'leaflet';

// Helper component to auto-fit map view boundaries only on initial data load
function AutoFitBounds({ markers }) {
  const map = useMap();
  const hasFitted = useRef(false);
  useEffect(() => {
    if (!hasFitted.current && markers && markers.length > 0) {
      const bounds = markers.map(m => [m.latitude, m.longitude]);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
      hasFitted.current = true;
    }
  }, [markers, map]);
  return null;
}

export default function MapDashboard() {
  const [locations, setLocations] = useState([]);
  const [emergencies, setEmergencies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState('');

  // Define custom Leaflet divIcons inside the component to prevent evaluation crashes
  const emergencyIcon = L.divIcon({
    className: 'custom-gps-marker emergency-marker',
    html: '<div class="pulse-ring"></div><div class="marker-dot">🚨</div>',
    iconSize: [30, 30],
    iconAnchor: [15, 15]
  });

  const buildingIcon = (citizenCount) => L.divIcon({
    className: 'custom-gps-marker building-marker',
    html: `<div class="building-pin">🏢</div><span class="citizen-badge">${citizenCount}</span>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20]
  });

  const fetchData = async (manual = false) => {
    if (manual) setLoading(true);
    try {
      const token = localStorage.getItem('token');
      
      // Fetch Locations
      const locRes = await fetch('http://localhost:8000/api/locations', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const locationsData = locRes.ok ? await locRes.json() : [];
      setLocations(locationsData);

      // Fetch Emergencies
      const emRes = await fetch('http://localhost:8000/api/emergencies', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const emergenciesData = emRes.ok ? await emRes.json() : [];
      setEmergencies(emergenciesData);
    } catch (err) {
      console.error("Error fetching map dashboard data:", err);
    } finally {
      if (manual) setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Poll data every 5 seconds for live real-time updates
    const interval = setInterval(() => fetchData(), 5000);
    return () => clearInterval(interval);
  }, []);

  const handleResolveEmergency = async (id) => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:8000/api/emergencies/resolve/${id}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setActionMsg("Emergency resolved successfully!");
        setTimeout(() => setActionMsg(''), 3000);
        fetchData();
      } else {
        const error = await res.json();
        alert(`Failed to resolve: ${error.detail || 'Access denied'}`);
      }
    } catch (err) {
      console.error("Failed to resolve emergency:", err);
    }
  };

  // 1. Process active emergencies that have coordinates (matching their location node)
  const activeEmergenciesWithCoords = emergencies
    .filter(emg => emg.status === 'ACTIVE')
    .map(emg => {
      const matchedLoc = locations.find(l => l.id === emg.location_id);
      if (matchedLoc && matchedLoc.latitude !== null && matchedLoc.longitude !== null) {
        return {
          ...emg,
          latitude: matchedLoc.latitude,
          longitude: matchedLoc.longitude,
          locName: matchedLoc.name
        };
      }
      return null;
    })
    .filter(Boolean);

  // 2. Filter location nodes that represent physical spots (e.g. BUILDING / STREET) with valid coordinates
  const physicalNodesWithCoords = locations.filter(loc => 
    loc.latitude !== null && 
    loc.longitude !== null && 
    (loc.level === 'BUILDING' || loc.level === 'STREET' || loc.level === 'NEIGHBORHOOD')
  );

  // 3. Combine coordinates for map auto-fitting
  const allMapMarkers = [
    ...activeEmergenciesWithCoords.map(e => ({ latitude: e.latitude, longitude: e.longitude })),
    ...physicalNodesWithCoords.map(l => ({ latitude: l.latitude, longitude: l.longitude }))
  ];

  return (
    <div className="fade-in">
      <div className="dashboard-header">
        <div className="header-title">
          <h1>🗺️ Real-Time Community Map</h1>
          <p>Live visual intelligence tracking verified buildings, resident distribution, and active crisis alerts.</p>
        </div>
        <button 
          onClick={() => fetchData(true)} 
          className="btn btn-secondary" 
          disabled={loading}
          style={{ padding: '8px 16px', fontSize: '0.85rem' }}
        >
          {loading ? 'Refreshing...' : '🔄 Live Sync'}
        </button>
      </div>

      {actionMsg && (
        <div className="glass-panel" style={{
          background: 'rgba(16, 185, 129, 0.1)',
          border: '1px solid var(--success)',
          color: 'var(--success)',
          padding: '12px 20px',
          borderRadius: '12px',
          marginBottom: '20px',
          fontWeight: '500',
          fontSize: '0.9rem'
        }}>
          {actionMsg}
        </div>
      )}

      <div className="glass-panel map-wrapper" style={{ padding: '0', borderRadius: '16px', overflow: 'hidden', height: '650px' }}>
        <MapContainer 
          center={[32.0853, 34.7818]} 
          zoom={13} 
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            subdomains="abcd"
            maxZoom={20}
          />

          {/* Active Emergencies Layer */}
          {activeEmergenciesWithCoords.map(emg => (
            <Marker 
              key={`emergency-${emg.id}`} 
              position={[emg.latitude, emg.longitude]} 
              icon={emergencyIcon}
            >
              <Popup>
                <div>
                  <h4 style={{ color: 'var(--danger)', margin: '0 0 6px 0', fontSize: '0.95rem' }}>
                    🚨 Active Emergency
                  </h4>
                  <p style={{ margin: '0 0 4px 0', fontWeight: 'bold' }}>
                    Location: {emg.location_name}
                  </p>
                  <p style={{ margin: '0 0 8px 0', fontStyle: 'italic', color: 'var(--text-primary)' }}>
                    "{emg.message}"
                  </p>
                  <p style={{ margin: '0 0 10px 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    Reported by: @{emg.user.username} ({new Date(emg.created_at).toLocaleTimeString()})
                  </p>
                  <button 
                    onClick={() => handleResolveEmergency(emg.id)}
                    className="btn btn-secondary popup-btn"
                    style={{ 
                      background: 'var(--danger)', 
                      borderColor: 'var(--danger)', 
                      color: 'white',
                      width: '100%',
                      padding: '6px 12px',
                      fontSize: '0.8rem',
                      fontWeight: '600'
                    }}
                  >
                    Mark Resolved
                  </button>
                </div>
              </Popup>
            </Marker>
          ))}

          {/* Location Nodes Layer */}
          {physicalNodesWithCoords.map(loc => (
            <Marker 
              key={`location-${loc.id}`} 
              position={[loc.latitude, loc.longitude]} 
              icon={buildingIcon(loc.verified_users_count)}
            >
              <Popup>
                <div>
                  <h4 style={{ margin: '0 0 6px 0', fontSize: '0.95rem', color: 'var(--accent-blue)' }}>
                    🏢 {loc.name}
                  </h4>
                  <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                    Level: <span style={{ color: 'white', fontWeight: '600' }}>{loc.level}</span>
                  </p>
                  <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                    Verified Residents: <span style={{ color: 'var(--success)', fontWeight: '700' }}>{loc.verified_users_count}</span>
                  </p>
                  <div style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '8px' }}>
                    <p style={{ margin: '0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      ID: {loc.id} | Coordinates: {loc.latitude.toFixed(5)}, {loc.longitude.toFixed(5)}
                    </p>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}

          <AutoFitBounds markers={allMapMarkers} />
        </MapContainer>
      </div>
    </div>
  );
}
