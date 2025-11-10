import React, { useState, useEffect } from 'react';
import { Progress, Card, List, Spin, Alert } from 'antd';
import { CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons';

const InitializationProgress = ({ onComplete }) => {
  const [status, setStatus] = useState({
    complete: false,
    progress: 0,
    current_task: "Waiting to start...",
    errors: [],
    data_status: {}
  });

  useEffect(() => {
    // Start initialization
    fetch('/api/initialize', { method: 'POST' });

    // Connect to WebSocket for real-time updates
    const ws = new WebSocket('ws://localhost:8000/ws/initialization');
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus(data);
      
      if (data.complete && onComplete) {
        onComplete();
      }
    };

    return () => ws.close();
  }, [onComplete]);

  const getStatusIcon = (success) => {
    return success ? 
      <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
      <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
  };

  return (
    <Card title="System Initialization">
      <Progress 
        percent={Math.round(status.progress * 100)} 
        status={status.complete ? "success" : "active"}
      />
      
      <div style={{ margin: '16px 0' }}>
        <Spin spinning={!status.complete} />
        <span style={{ marginLeft: 8 }}>{status.current_task}</span>
      </div>

      {Object.keys(status.data_status).length > 0 && (
        <Card size="small" title="Data Loading Status">
          <List
            size="small"
            dataSource={Object.entries(status.data_status)}
            renderItem={([name, success]) => (
              <List.Item>
                {getStatusIcon(success)}
                <span style={{ marginLeft: 8 }}>{name}</span>
              </List.Item>
            )}
          />
        </Card>
      )}

      {status.errors.length > 0 && (
        <Alert
          message="Initialization Errors"
          description={
            <ul>
              {status.errors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          }
          type="error"
          style={{ marginTop: 16 }}
        />
      )}
    </Card>
  );
};

export default InitializationProgress;