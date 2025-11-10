import React, { useState, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, useMap } from 'react-leaflet';
import { message, Spin } from 'antd';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default marker icons in React Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const MapComponent = ({ 
  selectedFire, 
  availableFires, 
  cascadeResults, 
  gridData,
  onFireSelect 
}) => {
  const [mapData, setMapData] = useState({
    buses: [],
    states: null,
    fires: [],
    transmissionLines: []
  });
  const [loading, setLoading] = useState(true);

  // Load initial map data
  useEffect(() => {
    const loadMapData = async () => {
      try {
        const response = await fetch('/api/map/initial-data');
        if (!response.ok) {
          throw new Error('Failed to fetch map data');
        }
        const data = await response.json();
        setMapData({
          buses: data.buses || [],
          states: data.states || null,
          fires: data.fires || [],
          transmissionLines: data.transmissionLines || []
        });
      } catch (error) {
        console.error('Error loading map data:', error);
        message.error('Failed to load map data. Using mock data.');
        // Use mock data for development
        setMapData({
          buses: [],
          states: null,
          fires: [],
          transmissionLines: []
        });
      } finally {
        setLoading(false);
      }
    };

    loadMapData();
  }, []);

  // Update fires when availableFires changes
  useEffect(() => {
    if (availableFires && availableFires.length > 0) {
      setMapData(prev => ({
        ...prev,
        fires: availableFires
      }));
    }
  }, [availableFires]);

  // Update grid data when it changes
  useEffect(() => {
    if (gridData) {
      setMapData(prev => ({
        ...prev,
        buses: gridData.buses || prev.buses,
        transmissionLines: gridData.transmissionLines || prev.transmissionLines
      }));
    }
  }, [gridData]);

  // Style functions for different layers
  const getBusStyle = useCallback((bus) => {
    const baseStyle = {
      radius: 3,
      fillOpacity: 0.8,
      weight: 1
    };

    switch (bus.bus_type) {
      case 'Generator':
      case 'Gen':
        return { ...baseStyle, fillColor: '#e41a1c', color: '#a41e22' };
      case 'Load':
        return { ...baseStyle, fillColor: '#377eb8', color: '#2a5d87' };
      case 'Gen + Load':
        return { ...baseStyle, fillColor: '#4daf4a', color: '#3a8a3a' };
      default:
        return { ...baseStyle, fillColor: '#999999', color: '#666666' };
    }
  }, []);

  const getFireStyle = useCallback((fire) => {
    const baseStyle = {
      weight: 2,
      fillOpacity: 0.6,
      color: '#fff'
    };

    // Highlight selected fire
    if (selectedFire && (fire.properties?.id === selectedFire.id || fire.id === selectedFire.id)) {
      return {
        ...baseStyle,
        fillColor: '#ff0000',
        weight: 3,
        fillOpacity: 0.8
      };
    }

    // Style by intensity
    const intensity = fire.properties?.fire_intensity || fire.fire_intensity;
    switch (intensity) {
      case 'Extreme':
        return { ...baseStyle, fillColor: '#8b0000' };
      case 'High':
        return { ...baseStyle, fillColor: '#ff4500' };
      case 'Moderate':
        return { ...baseStyle, fillColor: '#ffa500' };
      case 'Low':
        return { ...baseStyle, fillColor: '#ffff00' };
      default:
        return { ...baseStyle, fillColor: '#cccccc' };
    }
  }, [selectedFire]);

  const handleFireClick = useCallback((fire) => {
    if (onFireSelect) {
      const fireId = fire.properties?.id || fire.id;
      onFireSelect(fireId);
    }
  }, [onFireSelect]);

  // Cascade results overlay
  const renderCascadeResults = useCallback(() => {
    if (!cascadeResults || !cascadeResults.cascade_steps || !mapData.buses || mapData.buses.length === 0) {
      return null;
    }

    // Render only the last step for clarity
    const lastStep = cascadeResults.cascade_steps[cascadeResults.cascade_steps.length - 1];
    
    return (
      <React.Fragment>
        {/* Fire-affected buses in red */}
        {lastStep.fire_affected?.map(busId => {
          const bus = mapData.buses.find(b => b.bus_i === busId || b.id === busId);
          if (!bus) return null;
          
          return (
            <CircleMarker
              key={`fire-affected-${busId}`}
              center={[bus.latitude || bus.lat, bus.longitude || bus.lon]}
              radius={8}
              fillColor="#ff0000"
              color="#fff"
              weight={2}
              fillOpacity={0.9}
            >
              <Popup>
                <div>
                  <strong>Fire Affected Bus {busId}</strong><br/>
                  Status: Deenergized by wildfire
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
        
        {/* Cascade-affected buses in blue */}
        {lastStep.deenergized?.map(busId => {
          const bus = mapData.buses.find(b => b.bus_i === busId || b.id === busId);
          if (!bus) return null;
          
          return (
            <CircleMarker
              key={`cascade-affected-${busId}`}
              center={[bus.latitude || bus.lat, bus.longitude || bus.lon]}
              radius={6}
              fillColor="#1890ff"
              color="#fff"
              weight={1}
              fillOpacity={0.8}
            >
              <Popup>
                <div>
                  <strong>Cascade Affected Bus {busId}</strong><br/>
                  Status: Deenergized by cascade failure
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </React.Fragment>
    );
  }, [cascadeResults, mapData.buses]);

  if (loading) {
    return (
      <div style={{ 
        height: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: '#f0f2f5'
      }}>
        <Spin size="large" tip="Loading map data..." />
      </div>
    );
  }

  return (
    <MapContainer
      center={[39.8283, -98.5795]}
      zoom={6}
      style={{ height: '100vh', width: '100%' }}
      zoomControl={true}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      
      {/* State boundaries */}
      {mapData.states && (
        <GeoJSON
          data={mapData.states}
          style={{
            fillColor: 'transparent',
            weight: 2,
            color: '#666',
            fillOpacity: 0,
            dashArray: '5, 5'
          }}
        />
      )}
      
      {/* Fire polygons */}
      {mapData.fires && mapData.fires.length > 0 && (
        <GeoJSON
          key={`fires-${selectedFire?.id}`}
          data={{
            type: 'FeatureCollection',
            features: mapData.fires
          }}
          style={getFireStyle}
          onEachFeature={(feature, layer) => {
            layer.on('click', () => handleFireClick(feature));
            
            const props = feature.properties;
            layer.bindPopup(`
              <div style="min-width: 150px;">
                <strong>${props?.attr_IncidentName || props?.name || 'Unknown Fire'}</strong><br/>
                Intensity: ${props?.fire_intensity || 'Unknown'}<br/>
                Area: ${(props?.fire_acres || 0).toLocaleString()} acres<br/>
                Year: ${props?.attr_FireDiscoveryDateTime?.split('/')[2] || 'Unknown'}
              </div>
            `);
          }}
        />
      )}
      
      {/* Bus locations */}
      {mapData.buses && mapData.buses.length > 0 && mapData.buses.map(bus => {
        const lat = bus.latitude || bus.lat;
        const lon = bus.longitude || bus.lon;
        
        if (!lat || !lon) return null;
        
        return (
          <CircleMarker
            key={bus.bus_i || bus.id}
            center={[lat, lon]}
            {...getBusStyle(bus)}
          >
            <Popup>
              <div>
                <strong>Bus {bus.bus_i || bus.id}</strong><br/>
                Type: {bus.bus_type || 'Unknown'}<br/>
                {bus.total_gen && `Generation: ${bus.total_gen.toFixed(1)} MW`}<br/>
                {bus.load_mw && `Load: ${bus.load_mw.toFixed(1)} MW`}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
      
      {/* Cascade results overlay */}
      {renderCascadeResults()}
    </MapContainer>
  );
};

export default MapComponent;
