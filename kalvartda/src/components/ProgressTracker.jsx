import React from 'react';
import { Card, Progress, Steps, Typography } from 'antd';
import { LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;
const { Step } = Steps;

const ProgressTracker = ({ progress, visible }) => {
  if (!visible) return null;

  const getStepStatus = (status) => {
    const statusMap = {
      'idle': 0,
      'ready': 0,
      'initializing': 1,
      'analyzing_fire_impact': 2,
      'running_simulation': 3,
      'generating_matrices': 4,
      'cascade_complete': 5,
      'analysis_complete': 5,
      'error': -1
    };
    return statusMap[status] || 0;
  };

  const currentStep = getStepStatus(progress.status);
  const isError = progress.status === 'error';
  const isComplete = progress.status === 'cascade_complete' || progress.status === 'analysis_complete';

  const getProgressStatus = () => {
    if (isError) return 'exception';
    if (isComplete) return 'success';
    return 'active';
  };

  return (
    <Card
      style={{
        position: 'fixed',
        bottom: 20,
        left: '50%',
        transform: 'translateX(-50%)',
        width: 600,
        maxWidth: '90vw',
        zIndex: 1000,
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
      }}
      bodyStyle={{ padding: 16 }}
    >
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ fontSize: 16 }}>
          {isError ? 'Analysis Error' : isComplete ? 'Analysis Complete' : 'Analysis in Progress'}
        </Text>
      </div>

      <Progress 
        percent={Math.round(progress.percent || 0)} 
        status={getProgressStatus()}
        strokeColor={{
          '0%': '#108ee9',
          '100%': '#87d068',
        }}
      />

      <div style={{ marginTop: 12, marginBottom: 12 }}>
        <Text type="secondary">{progress.message || 'Processing...'}</Text>
      </div>

      <Steps 
        current={currentStep} 
        status={isError ? 'error' : 'process'}
        size="small"
      >
        <Step 
          title="Initialize" 
          icon={currentStep === 1 ? <LoadingOutlined /> : undefined}
        />
        <Step 
          title="Fire Impact" 
          icon={currentStep === 2 ? <LoadingOutlined /> : undefined}
        />
        <Step 
          title="Cascade Sim" 
          icon={currentStep === 3 ? <LoadingOutlined /> : undefined}
        />
        <Step 
          title="Matrices" 
          icon={currentStep === 4 ? <LoadingOutlined /> : undefined}
        />
        <Step 
          title="Complete" 
          icon={isComplete ? <CheckCircleOutlined /> : isError ? <CloseCircleOutlined /> : undefined}
        />
      </Steps>

      {progress.step > 0 && (
        <div style={{ marginTop: 8, textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Step {progress.step}
          </Text>
        </div>
      )}
    </Card>
  );
};

export default ProgressTracker;
