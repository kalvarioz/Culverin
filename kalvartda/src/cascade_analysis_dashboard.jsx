import React, { useState, useEffect, useCallback } from 'react';
import { 
  Card, Row, Col, Progress, Button, Steps, Table, 
  Statistic, Alert, Spin, Upload, Select 
} from 'antd';
import { 
  PlayCircleOutlined, PauseCircleOutlined, DownloadOutlined,
  FireOutlined, ThunderboltOutlined, NodeIndexOutlined 
} from '@ant-design/icons';
import Plot from 'react-plotly.js';
import axios from 'axios';

const { Step } = Steps;
const { Option } = Select;

const CascadeAnalysisDashboard = () => {
  const [analysisState, setAnalysisState] = useState({
    status: 'idle',
    progress: 0,
    currentStep: 0,
    totalSteps: 0,
    currentTask: 'Ready',
    estimatedCompletion: null
  });
  
  const [analysisId, setAnalysisId] = useState(null);
  const [results, setResults] = useState(null);
  const [config, setConfig] = useState({
    buffer_km: 5.0,
    max_steps: 20,
    enable_parallel: true,
    max_workers: 4,
    generate_matrices: true
  });
  const [selectedFireData, setSelectedFireData] = useState(null);

  // WebSocket connection for real-time updates
  useEffect(() => {
    if (!analysisId) return;

    const ws = new WebSocket(`ws://localhost:8000/ws/cascade/${analysisId}/progress`);
    
    ws.onmessage = (event) => {
      const progress = JSON.parse(event.data);
      setAnalysisState(progress);
      
      // Fetch results when completed
      if (progress.status === 'completed') {
        fetchResults();
      }
    };

    return () => ws.close();
  }, [analysisId]);

  const startAnalysis = async () => {
    if (!selectedFireData) {
      alert('Please select fire data first');
      return;
    }

    try {
      const response = await axios.post('/api/cascade/start', {
        config,
        fire_data_id: selectedFireData
      });
      
      setAnalysisId(response.data.analysis_id);
      setResults(null);
    } catch (error) {
      console.error('Failed to start analysis:', error);
    }
  };

  const fetchResults = async () => {
    if (!analysisId) return;

    try {
      const response = await axios.get(`/api/cascade/${analysisId}/result`);
      setResults(response.data);
    } catch (error) {
      console.error('Failed to fetch results:', error);
    }
  };

  const downloadMatrix = async (matrixType) => {
    if (!analysisId) return;

    try {
      const response = await axios.get(
        `/api/cascade/${analysisId}/matrix/${matrixType}`,
        { responseType: 'blob' }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${matrixType}_cascade_matrix.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download matrix:', error);
    }
  };

  const renderCascadeVisualization = () => {
    if (!results || !results.cascade_steps.length) return null;

    const steps = results.cascade_steps.map(step => step.step);
    const fireAffected = results.cascade_steps.map(step => step.fire_affected.length);
    const deenergized = results.cascade_steps.map(step => step.deenergized.length);
    const remaining = results.cascade_steps.map(step => step.vertices_remaining);

    return (
      <Card title="Cascade Progression">
        <Plot
          data={[
            {
              x: steps,
              y: fireAffected,
              type: 'scatter',
              mode: 'lines+markers',
              name: 'Fire Affected',
              marker: { color: '#ff4d4f' }
            },
            {
              x: steps,
              y: deenergized,
              type: 'scatter',
              mode: 'lines+markers',
              name: 'Cascade Failures',
              marker: { color: '#1890ff' }
            },
            {
              x: steps,
              y: remaining,
              type: 'scatter',
              mode: 'lines+markers',
              name: 'Buses Remaining',
              marker: { color: '#52c41a' },
              yaxis: 'y2'
            }
          ]}
          layout={{
            title: 'Cascade Analysis Results',
            xaxis: { title: 'Simulation Step' },
            yaxis: { title: 'Buses Affected' },
            yaxis2: {
              title: 'Buses Remaining',
              overlaying: 'y',
              side: 'right'
            },
            height: 400
          }}
          style={{ width: '100%', height: '400px' }}
        />
      </Card>
    );
  };

  const renderSummaryStatistics = () => {
    if (!results) return null;

    return (
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Total Buses Affected"
              value={results.total_buses_affected}
              prefix={<FireOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Cascade Amplification"
              value={results.cascade_amplification}
              precision={2}
              prefix={<ThunderboltOutlined />}
              suffix="x"
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Final Grid Size"
              value={results.final_grid_size}
              prefix={<NodeIndexOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Execution Time"
              value={results.execution_time}
              precision={1}
              suffix="s"
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>
    );
  };

  const renderProgressSteps = () => {
    const stepMapping = {
      'idle': 0,
      'initializing': 1,
      'analyzing_fire_impact': 2,
      'running_simulation': 3,
      'generating_matrices': 4,
      'completed': 5,
      'failed': -1
    };

    const currentStepIndex = stepMapping[analysisState.status] || 0;

    return (
      <Steps current={currentStepIndex} status={analysisState.status === 'failed' ? 'error' : 'process'}>
        <Step title="Initialize" description="Setting up analysis" />
        <Step title="Fire Impact" description="Analyzing fire-grid intersections" />
        <Step title="Cascade Simulation" description="Running cascade model" />
        <Step title="Matrix Generation" description="Creating TDA matrices" />
        <Step title="Complete" description="Analysis finished" />
      </Steps>
    );
  };

  return (
    <div style={{ padding: '24px' }}>
      <Row gutter={16}>
        <Col span={16}>
          <Card title="Cascade Analysis Configuration">
            <Row gutter={16}>
              <Col span={8}>
                <label>Buffer Distance (km):</label>
                <input
                  type="number"
                  value={config.buffer_km}
                  onChange={(e) => setConfig({...config, buffer_km: parseFloat(e.target.value)})}
                  style={{ width: '100%', marginTop: 4 }}
                />
              </Col>
              <Col span={8}>
                <label>Max Simulation Steps:</label>
                <input
                  type="number"
                  value={config.max_steps}
                  onChange={(e) => setConfig({...config, max_steps: parseInt(e.target.value)})}
                  style={{ width: '100%', marginTop: 4 }}
                />
              </Col>
              <Col span={8}>
                <label>Parallel Workers:</label>
                <input
                  type="number"
                  value={config.max_workers}
                  onChange={(e) => setConfig({...config, max_workers: parseInt(e.target.value)})}
                  style={{ width: '100%', marginTop: 4 }}
                />
              </Col>
            </Row>
            
            <div style={{ marginTop: 16 }}>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={startAnalysis}
                disabled={analysisState.status === 'running'}
                loading={analysisState.status !== 'idle' && analysisState.status !== 'completed'}
              >
                Start Cascade Analysis
              </Button>
            </div>
          </Card>
        </Col>
        
        <Col span={8}>
          <Card title="Analysis Progress">
            <Progress 
              percent={analysisState.progress} 
              status={analysisState.status === 'failed' ? 'exception' : 'active'}
            />
            <div style={{ marginTop: 16 }}>
              <p><strong>Status:</strong> {analysisState.currentTask}</p>
              <p><strong>Step:</strong> {analysisState.currentStep} / {analysisState.totalSteps}</p>
              {analysisState.estimatedCompletion && (
                <p><strong>ETA:</strong> {new Date(analysisState.estimatedCompletion * 1000).toLocaleTimeString()}</p>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      <Card style={{ marginTop: 24 }}>
        {renderProgressSteps()}
      </Card>

      {analysisState.errors && analysisState.errors.length > 0 && (
        <Alert
          message="Analysis Errors"
          description={
            <ul>
              {analysisState.errors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          }
          type="error"
          style={{ marginTop: 24 }}
        />
      )}

      {results && (
        <>
          {renderSummaryStatistics()}
          {renderCascadeVisualization()}
          
          <Row gutter={16} style={{ marginTop: 24 }}>
            <Col span={12}>
              <Card title="Download Results">
                <Button 
                  icon={<DownloadOutlined />}
                  onClick={() => downloadMatrix('before')}
                  style={{ marginRight: 8 }}
                >
                  Before Matrix
                </Button>
                <Button 
                  icon={<DownloadOutlined />}
                  onClick={() => downloadMatrix('after')}
                >
                  After Matrix
                </Button>
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
};

export default CascadeAnalysisDashboard;