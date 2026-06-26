import React, { useState, useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline, Polygon, useMap } from 'react-leaflet';
import * as L from 'leaflet';

// ── Color palette for each level ──
const LEVEL_CONFIG = {
  COUNTRY:      { color: '#10b981', label: '🌍 Countries',      emoji: '🌍', fillOpacity: 0.06, strokeOpacity: 0.35, defaultRadius: 100000 },
  DISTRICT:     { color: '#14b8a6', label: '🏛️ Districts',       emoji: '🏛️', fillOpacity: 0.07, strokeOpacity: 0.40, defaultRadius: 15000 },
  CITY:         { color: '#06b6d4', label: '🏙️ Cities',          emoji: '🏙️', fillOpacity: 0.08, strokeOpacity: 0.45, defaultRadius: 5000 },
  NEIGHBORHOOD: { color: '#a855f7', label: '🏘️ Neighborhoods',   emoji: '🏘️', fillOpacity: 0.10, strokeOpacity: 0.50, defaultRadius: 800 },
  STREET:       { color: '#f59e0b', label: '🛣️ Streets',         emoji: '🛣️', fillOpacity: 0.15, strokeOpacity: 0.70, defaultRadius: 200 },
  BUILDING:     { color: '#3b82f6', label: '🏢 Buildings',       emoji: '🏢', fillOpacity: 1.0,  strokeOpacity: 1.0,  defaultRadius: 0 },
};

// Rotating color palette for streets (each street gets a unique color)
const STREET_COLORS = [
  '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4',
  '#10b981', '#f97316', '#6366f1', '#14b8a6', '#e11d48',
  '#84cc16', '#d946ef', '#0ea5e9', '#f43f5e', '#a3e635',
];

// ── Helper: convert GeoJSON coordinates to Leaflet [lat, lng] ──
function geoJsonToLatLng(coordinates) {
  // GeoJSON uses [lng, lat], Leaflet uses [lat, lng]
  if (Array.isArray(coordinates[0]) && Array.isArray(coordinates[0][0])) {
    // Polygon: array of rings, each ring is array of [lng, lat]
    return coordinates.map(ring => ring.map(([lng, lat]) => [lat, lng]));
  }
  // LineString: array of [lng, lat]
  return coordinates.map(([lng, lat]) => [lat, lng]);
}

// ── Helper: compute bounding circle from descendant coordinates ──
function computeBoundingCircle(locations, nodeId, childrenMap) {
  const coords = [];
  
  function collectCoords(id) {
    const children = childrenMap[id] || [];
    for (const child of children) {
      if (child.latitude != null && child.longitude != null) {
        coords.push([child.latitude, child.longitude]);
      }
      collectCoords(child.id);
    }
  }
  
  collectCoords(nodeId);
  
  if (coords.length === 0) return null;
  
  const centerLat = coords.reduce((sum, c) => sum + c[0], 0) / coords.length;
  const centerLng = coords.reduce((sum, c) => sum + c[1], 0) / coords.length;
  
  let maxDist = 0;
  for (const [lat, lng] of coords) {
    const dLat = (lat - centerLat) * 111320;
    const dLng = (lng - centerLng) * 111320 * Math.cos(centerLat * Math.PI / 180);
    const dist = Math.sqrt(dLat * dLat + dLng * dLng);
    if (dist > maxDist) maxDist = dist;
  }
  
  return { center: [centerLat, centerLng], radius: Math.max(maxDist * 1.2, 100) };
}

// ── Helper component to auto-fit map bounds on initial data load ──
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

// ── Map Legend Component ──
function MapLegend({ visibleLayers, onToggleLayer, emergencyCount }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="map-legend-panel">
      <div className="map-legend-header" onClick={() => setCollapsed(!collapsed)}>
        <span>🗂️ Map Layers</span>
        <span className="legend-toggle-icon">{collapsed ? '▸' : '▾'}</span>
      </div>
      {!collapsed && (
        <div className="map-legend-body">
          <div className="legend-item">
            <label className="legend-label">
              <span className="legend-swatch" style={{ background: '#ef4444', boxShadow: '0 0 6px #ef4444' }}></span>
              🚨 Emergencies
              {emergencyCount > 0 && <span className="legend-count" style={{ color: '#ef4444' }}>{emergencyCount}</span>}
            </label>
          </div>
          <div className="legend-divider"></div>
          {Object.entries(LEVEL_CONFIG).map(([level, config]) => (
            <div className="legend-item" key={level}>
              <label className="legend-label">
                <input
                  type="checkbox"
                  checked={visibleLayers[level]}
                  onChange={() => onToggleLayer(level)}
                  className="legend-checkbox"
                />
                <span 
                  className="legend-swatch" 
                  style={{ 
                    background: config.color,
                    borderRadius: level === 'STREET' ? '2px' : '50%',
                    width: level === 'STREET' ? '16px' : '12px',
                    height: level === 'STREET' ? '4px' : '12px',
                  }}
                ></span>
                {config.label}
              </label>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Component ──
export default function MapDashboard() {
  const [locations, setLocations] = useState([]);
  const [emergencies, setEmergencies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [backfilling, setBackfilling] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [visibleLayers, setVisibleLayers] = useState({
    COUNTRY: true,
    DISTRICT: true,
    CITY: true,
    NEIGHBORHOOD: true,
    STREET: true,
    BUILDING: true,
  });

  // ── Leaflet Icons ──
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

  // ── Data Fetching ──
  const fetchData = async (manual = false) => {
    if (manual) setLoading(true);
    try {
      const token = localStorage.getItem('token');
      
      const locRes = await fetch('http://localhost:8000/api/locations', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const locationsData = locRes.ok ? await locRes.json() : [];
      setLocations(locationsData);

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

  const handleBackfillGeometry = async () => {
    setBackfilling(true);
    setActionMsg("⏳ Fetching boundary data from OpenStreetMap... This may take a minute.");
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:8000/api/locations/backfill-geometry', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setActionMsg(`✅ ${data.message}`);
        fetchData(true);
      } else {
        setActionMsg("❌ Failed to backfill geometry.");
      }
    } catch (err) {
      setActionMsg("❌ Error: " + err.message);
    } finally {
      setBackfilling(false);
      setTimeout(() => setActionMsg(''), 5000);
    }
  };

  const onToggleLayer = (level) => {
    setVisibleLayers(prev => ({ ...prev, [level]: !prev[level] }));
  };

  // ── Build parent→children map ──
  const childrenMap = useMemo(() => {
    const map = {};
    for (const loc of locations) {
      const pid = loc.parent_id || '__root__';
      if (!map[pid]) map[pid] = [];
      map[pid].push(loc);
    }
    return map;
  }, [locations]);

  // Count descendants by level
  function countDescendants(nodeId, targetLevel) {
    let count = 0;
    const children = childrenMap[nodeId] || [];
    for (const child of children) {
      if (child.level === targetLevel) count++;
      count += countDescendants(child.id, targetLevel);
    }
    return count;
  }

  // ── Check if any nodes are missing geometry ──
  const missingGeometry = useMemo(() => {
    return locations.some(l => 
      ['CITY', 'STREET'].includes(l.level) && !l.geometry
    );
  }, [locations]);

  // ── Process emergencies ──
  const activeEmergenciesWithCoords = emergencies
    .filter(emg => emg.status === 'ACTIVE')
    .map(emg => {
      const matchedLoc = locations.find(l => l.id === emg.location_id);
      if (matchedLoc && matchedLoc.latitude != null && matchedLoc.longitude != null) {
        return { ...emg, latitude: matchedLoc.latitude, longitude: matchedLoc.longitude, locName: matchedLoc.name };
      }
      return null;
    })
    .filter(Boolean);

  // ── Categorize locations by level ──
  const buildings = locations.filter(l => l.level === 'BUILDING' && l.latitude != null && l.longitude != null);

  // Streets: prefer real LineString geometry, fall back to connecting child buildings
  const streets = locations.filter(l => l.level === 'STREET').map((street, idx) => {
    const color = STREET_COLORS[idx % STREET_COLORS.length];
    const children = (childrenMap[street.id] || []).filter(c => c.latitude != null && c.longitude != null);
    
    // If we have real geometry from Nominatim, use it
    if (street.geometry && street.geometry.type === 'LineString') {
      const realCoords = geoJsonToLatLng(street.geometry.coordinates);
      return {
        ...street,
        polylineCoords: realCoords,
        hasRealGeometry: true,
        color,
        childCount: children.length,
      };
    }
    
    // Fallback: connect child building positions
    const polylineCoords = children.map(c => [c.latitude, c.longitude]);
    if (polylineCoords.length === 0 && street.latitude != null && street.longitude != null) {
      polylineCoords.push([street.latitude, street.longitude]);
    }
    
    return {
      ...street,
      polylineCoords,
      hasRealGeometry: false,
      color,
      childCount: children.length,
    };
  }).filter(s => s.polylineCoords.length > 0);

  // Circle/Polygon overlay levels
  const overlayLevels = ['NEIGHBORHOOD', 'CITY', 'DISTRICT', 'COUNTRY'];
  const overlays = overlayLevels.flatMap(level => {
    return locations
      .filter(l => l.level === level)
      .map(loc => {
        const config = LEVEL_CONFIG[level];
        
        // If real polygon geometry exists, use it
        if (loc.geometry && (loc.geometry.type === 'Polygon' || loc.geometry.type === 'MultiPolygon')) {
          let polygonPositions;
          if (loc.geometry.type === 'MultiPolygon') {
            // MultiPolygon: array of polygons
            polygonPositions = loc.geometry.coordinates.map(poly => geoJsonToLatLng(poly));
          } else {
            polygonPositions = geoJsonToLatLng(loc.geometry.coordinates);
          }
          return { ...loc, renderType: 'polygon', polygonPositions, config };
        }
        
        // Fallback: compute bounding circle from children
        let center, radius;
        if (loc.radius && loc.latitude != null && loc.longitude != null) {
          center = [loc.latitude, loc.longitude];
          radius = loc.radius;
        } else {
          const computed = computeBoundingCircle(locations, loc.id, childrenMap);
          if (computed) {
            center = computed.center;
            radius = computed.radius;
          } else if (loc.latitude != null && loc.longitude != null) {
            center = [loc.latitude, loc.longitude];
            radius = config.defaultRadius;
          } else {
            return null;
          }
        }
        
        return { ...loc, renderType: 'circle', center, radius, config };
      })
      .filter(Boolean);
  });

  // ── Collect all coordinates for auto-fit ──
  const allMapMarkers = [
    ...activeEmergenciesWithCoords.map(e => ({ latitude: e.latitude, longitude: e.longitude })),
    ...buildings.map(l => ({ latitude: l.latitude, longitude: l.longitude })),
    ...streets.flatMap(s => s.polylineCoords.map(coord => ({ latitude: coord[0], longitude: coord[1] }))),
    ...overlays.filter(c => c.renderType === 'circle').map(c => ({ latitude: c.center[0], longitude: c.center[1] })),
    ...overlays.filter(c => c.renderType === 'polygon' && c.latitude).map(c => ({ latitude: c.latitude, longitude: c.longitude })),
  ];

  return (
    <div className="fade-in">
      <div className="dashboard-header">
        <div className="header-title">
          <h1>🗺️ Real-Time Community Map</h1>
          <p>Live visual intelligence tracking verified buildings, resident distribution, and active crisis alerts.</p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {missingGeometry && (
            <button 
              onClick={handleBackfillGeometry} 
              className="btn btn-secondary" 
              disabled={backfilling}
              style={{ padding: '8px 16px', fontSize: '0.85rem', background: 'var(--accent-purple)', borderColor: 'var(--accent-purple)' }}
            >
              {backfilling ? '⏳ Loading...' : '🗺️ Load Boundaries'}
            </button>
          )}
          <button 
            onClick={() => fetchData(true)} 
            className="btn btn-secondary" 
            disabled={loading}
            style={{ padding: '8px 16px', fontSize: '0.85rem' }}
          >
            {loading ? 'Refreshing...' : '🔄 Live Sync'}
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className="glass-panel" style={{
          background: actionMsg.includes('❌') ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
          border: `1px solid ${actionMsg.includes('❌') ? 'var(--danger)' : 'var(--success)'}`,
          color: actionMsg.includes('❌') ? 'var(--danger)' : 'var(--success)',
          padding: '12px 20px',
          borderRadius: '12px',
          marginBottom: '20px',
          fontWeight: '500',
          fontSize: '0.9rem'
        }}>
          {actionMsg}
        </div>
      )}

      <div className="glass-panel map-wrapper" style={{ padding: '0', borderRadius: '16px', overflow: 'hidden', height: '650px', position: 'relative' }}>
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

          {/* ── Overlays: Country → District → City → Neighborhood ── */}
          {overlays
            .sort((a, b) => {
              // Sort by level hierarchy (largest first), then by radius
              const levelOrder = { COUNTRY: 0, DISTRICT: 1, CITY: 2, NEIGHBORHOOD: 3 };
              return (levelOrder[a.level] || 0) - (levelOrder[b.level] || 0);
            })
            .map(overlay => {
              if (!visibleLayers[overlay.level]) return null;
              const config = LEVEL_CONFIG[overlay.level];
              
              // Render as real polygon if geometry exists
              if (overlay.renderType === 'polygon') {
                return (
                  <Polygon
                    key={`polygon-${overlay.id}`}
                    positions={overlay.polygonPositions}
                    pathOptions={{
                      color: config.color,
                      weight: 2.5,
                      opacity: config.strokeOpacity + 0.1,
                      fillColor: config.color,
                      fillOpacity: config.fillOpacity,
                      dashArray: overlay.level === 'COUNTRY' ? '8 4' : null,
                    }}
                  >
                    <Popup>
                      <div>
                        <h4 style={{ margin: '0 0 6px 0', fontSize: '0.95rem', color: config.color }}>
                          {config.emoji} {overlay.name}
                        </h4>
                        <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                          Level: <span style={{ color: 'white', fontWeight: '600' }}>{overlay.level}</span>
                        </p>
                        <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                          Verified Residents: <span style={{ color: 'var(--success)', fontWeight: '700' }}>{overlay.verified_users_count}</span>
                        </p>
                        {overlay.level === 'CITY' && (
                          <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                            Neighborhoods: <span style={{ color: 'white', fontWeight: '600' }}>{countDescendants(overlay.id, 'NEIGHBORHOOD')}</span>
                          </p>
                        )}
                        {overlay.level === 'NEIGHBORHOOD' && (
                          <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                            Streets: <span style={{ color: 'white', fontWeight: '600' }}>{countDescendants(overlay.id, 'STREET')}</span>
                          </p>
                        )}
                        <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                          Buildings: <span style={{ color: 'white', fontWeight: '600' }}>{countDescendants(overlay.id, 'BUILDING')}</span>
                        </p>
                        <div style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '8px' }}>
                          <p style={{ margin: '0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            📐 Real boundary from OpenStreetMap
                          </p>
                        </div>
                      </div>
                    </Popup>
                  </Polygon>
                );
              }
              
              // Fallback: circle
              return (
                <Circle
                  key={`circle-${overlay.id}`}
                  center={overlay.center}
                  radius={overlay.radius}
                  pathOptions={{
                    color: config.color,
                    weight: 2,
                    opacity: config.strokeOpacity,
                    fillColor: config.color,
                    fillOpacity: config.fillOpacity,
                    dashArray: overlay.level === 'COUNTRY' ? '8 4' : overlay.level === 'DISTRICT' ? '6 3' : null,
                  }}
                >
                  <Popup>
                    <div>
                      <h4 style={{ margin: '0 0 6px 0', fontSize: '0.95rem', color: config.color }}>
                        {config.emoji} {overlay.name}
                      </h4>
                      <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                        Level: <span style={{ color: 'white', fontWeight: '600' }}>{overlay.level}</span>
                      </p>
                      <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                        Verified Residents: <span style={{ color: 'var(--success)', fontWeight: '700' }}>{overlay.verified_users_count}</span>
                      </p>
                      <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                        Buildings: <span style={{ color: 'white', fontWeight: '600' }}>{countDescendants(overlay.id, 'BUILDING')}</span>
                      </p>
                      <div style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '8px' }}>
                        <p style={{ margin: '0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Radius: {overlay.radius >= 1000 ? `${(overlay.radius / 1000).toFixed(1)} km` : `${Math.round(overlay.radius)} m`}
                        </p>
                      </div>
                    </div>
                  </Popup>
                </Circle>
              );
            })}

          {/* ── Street Lines ── */}
          {visibleLayers.STREET && streets.map(street => (
            <React.Fragment key={`street-${street.id}`}>
              {street.polylineCoords.length >= 2 ? (
                <Polyline
                  positions={street.polylineCoords}
                  pathOptions={{
                    color: street.color,
                    weight: street.hasRealGeometry ? 5 : 3,
                    opacity: street.hasRealGeometry ? 0.9 : 0.7,
                    lineCap: 'round',
                    lineJoin: 'round',
                  }}
                >
                  <Popup>
                    <div>
                      <h4 style={{ margin: '0 0 6px 0', fontSize: '0.95rem', color: street.color }}>
                        🛣️ {street.name}
                      </h4>
                      <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                        Buildings: <span style={{ color: 'white', fontWeight: '600' }}>{street.childCount}</span>
                      </p>
                      <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem' }}>
                        Verified Residents: <span style={{ color: 'var(--success)', fontWeight: '700' }}>{street.verified_users_count}</span>
                      </p>
                      {street.hasRealGeometry && (
                        <div style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '8px' }}>
                          <p style={{ margin: '0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            📐 Real street path from OpenStreetMap
                          </p>
                        </div>
                      )}
                    </div>
                  </Popup>
                </Polyline>
              ) : (
                // Single-point street: show as a small colored circle
                <Circle
                  center={street.polylineCoords[0]}
                  radius={30}
                  pathOptions={{
                    color: street.color,
                    weight: 3,
                    opacity: 0.85,
                    fillColor: street.color,
                    fillOpacity: 0.4,
                  }}
                >
                  <Popup>
                    <div>
                      <h4 style={{ margin: '0 0 6px 0', fontSize: '0.95rem', color: street.color }}>
                        🛣️ {street.name}
                      </h4>
                      <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                        No buildings registered yet
                      </p>
                    </div>
                  </Popup>
                </Circle>
              )}
            </React.Fragment>
          ))}

          {/* ── Active Emergencies ── */}
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

          {/* ── Building Markers ── */}
          {visibleLayers.BUILDING && buildings.map(loc => (
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

        {/* Legend / Layer Toggle */}
        <MapLegend 
          visibleLayers={visibleLayers} 
          onToggleLayer={onToggleLayer}
          emergencyCount={activeEmergenciesWithCoords.length}
        />
      </div>
    </div>
  );
}
