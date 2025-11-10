import React, { useState, useCallback } from 'react';
import { Layout, message } from 'antd';
import MapComponent from './components/MapComponent';
import ControlPanel from './components/ControlPanel';
import ProgressTracker from './components/ProgressTracker';
import ResultsVisualization from './components/ResultsVisualization';
import { useWebSocket } from './hooks/useWebSocket';
import './styles/App.css';

const { Content } = Layout;

const App = () => {
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  const [appState, setAppState] = useState({
    selectedFire: null,
    filters: {},
    cascadeResults: null,
    tdaResults: null,
    progress: { status: 'ready', percent: 0 }
  });
  const handleWebSocketMessage = useCallback((data) => {
    switch (data.type) {
      case 'fire_selected':
        setAppState(prev => ({ ...prev, selectedFire: data.data }));
        break;
      case 'fires_filtered':
        setAppState(prev => ({ ...prev, filteredFires: data.data }));
        break;
      case 'cascade_progress':
        setAppState(prev => ({ ...prev, progress: data.data }));
        break;
      case 'cascade_complete':
        setAppState(prev => ({
          ...prev,
          cascadeResults: data.data,
          progress: { status: 'cascade_complete', percent: 100 }
        }));
        message.success('Cascade analysis completed!');
        break;
      case 'tda_complete':
        setAppState(prev => ({
          ...prev,
          tdaResults: data.data,
          progress: { status: 'analysis_complete', percent: 100 }
        }));
        message.success('TDA analysis completed!');
        break;
      case 'cascade_error':
      case 'tda_error':
        message.error('Analysis error: ' + data.error);
        setAppState(prev => ({ ...prev, progress: { status: 'error', percent: 0 } }));
        break;
    }
  }, []);
  const { sendMessage, isConnected } = useWebSocket(
    `ws://localhost:8000/ws/session/${sessionId}`,
    {
      onMessage: handleWebSocketMessage,
      onError: (error) => {
        message.error('Connection error: ' + error.message);
      }
    }
  );

  const handleFireSelect = useCallback((fireId) => {
    sendMessage({
      action: 'select_fire',
      fire_id: fireId
    });
  }, [sendMessage]);

  const handleFiltersChange = useCallback((filters) => {
    setAppState(prev => ({ ...prev, filters }));
    sendMessage({
      action: 'update_filters',
      filters
    });
  }, [sendMessage]);

  const handleStartCascade = useCallback((config) => {
    sendMessage({
      action: 'start_cascade',
      config
    });
  }, [sendMessage]);

  const handleStartTDA = useCallback(() => {
    sendMessage({
      action: 'start_tda'
    });
  }, [sendMessage]);

  return (
    <Layout style={{ height: '100vh' }}>
      <Content style={{ position: 'relative', padding: 0 }}>
        <MapComponent 
          selectedFire={appState.selectedFire}
          filteredFires={appState.filteredFires}
          cascadeResults={appState.cascadeResults}
          onFireSelect={handleFireSelect}
        />
        
        <ControlPanel
          selectedFire={appState.selectedFire}
          filters={appState.filters}
          onFiltersChange={handleFiltersChange}
          onStartCascade={handleStartCascade}
          onStartTDA={handleStartTDA}
          cascadeResults={appState.cascadeResults}
          disabled={!isConnected}
        />
        
        <ProgressTracker 
          progress={appState.progress}
          visible={appState.progress.status !== 'ready'}
        />
        
        {(appState.cascadeResults || appState.tdaResults) && (
          <ResultsVisualization
            cascadeResults={appState.cascadeResults}
            tdaResults={appState.tdaResults}
            sessionId={sessionId}
          />
        )}
      </Content>
    </Layout>
  );
};

export default App;