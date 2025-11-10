import React, { useState } from 'react';
import { Card, Row, Col, Statistic, Tabs, Button, Modal } from 'antd';
import { 
  FireOutlined, 
  ThunderboltOutlined, 
  NodeIndexOutlined,
  DownloadOutlined,
  LineChartOutlined,
  FundProjectionScreenOutlined
} from '@ant-design/icons';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import axios from 'axios';

const { TabPane } = Tabs;

const ResultsVisualization = ({ cascadeResults, tdaResults, sessionId }) => {
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  const downloadMatrix = async (matrixType) => {
    try {
      const response = await axios.get(
        `/api/cascade/${sessionId}/matrix/${matrixType}`,
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

  const renderCascadeSteps = () => {
    if (!cascadeResults || !cascadeResults.cascade_steps) return null;

    const chartData = cascadeResults.cascade_steps.map((step, index) => ({
      step: index + 1,
      fireAffected: step.fire_affected?.length || 0,
      cascadeAffected: step.deenergized?.length || 0,
      totalAffected: (step.fire_affected?.length || 0) + (step.deenergized?.length || 0),
      verticesRemaining: step.vertices_remaining || 0
    }));

    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="step" label={{ value: 'Simulation Step', position: 'insideBottom', offset: -5 }} />
          <YAxis label={{ value: 'Number of Buses', angle: -90, position: 'insideLeft' }} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="fireAffected" stroke="#ff4d4f" name="Fire Affected" strokeWidth={2} />
          <Line type="monotone" dataKey="cascadeAffected" stroke="#1890ff" name="Cascade Affected" strokeWidth={2} />
          <Line type="monotone" dataKey="verticesRemaining" stroke="#52c41a" name="Vertices Remaining" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    );
  };

  const renderImpactDistribution = () => {
    if (!cascadeResults || !cascadeResults.cascade_steps) return null;

    const chartData = cascadeResults.cascade_steps.map((step, index) => ({
      step: index + 1,
      fireImpact: step.fire_affected?.length || 0,
      cascadeImpact: step.deenergized?.length || 0
    }));

    return (
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="step" label={{ value: 'Step', position: 'insideBottom', offset: -5 }} />
          <YAxis label={{ value: 'Buses Affected', angle: -90, position: 'insideLeft' }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="fireImpact" fill="#ff4d4f" name="Fire Impact" />
          <Bar dataKey="cascadeImpact" fill="#1890ff" name="Cascade Impact" />
        </BarChart>
      </ResponsiveContainer>
    );
  };

  const renderTDAResults = () => {
    if (!tdaResults) return <div>No TDA results available</div>;

    return (
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card>
            <h3>Topological Features</h3>
            <p>TDA analysis visualization will be displayed here</p>
            {/* Add TDA-specific visualizations */}
          </Card>
        </Col>
      </Row>
    );
  };

  return (
    <>
      <Button
        type="primary"
        icon={<FundProjectionScreenOutlined />}
        onClick={() => setIsModalVisible(true)}
        style={{
          position: 'fixed',
          bottom: 20,
          right: 20,
          zIndex: 999,
          height: 48,
          fontSize: 16
        }}
      >
        View Results
      </Button>

      <Modal
        title="Analysis Results"
        visible={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        width={1000}
        footer={null}
      >
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="Overview" key="overview">
            <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Total Buses Affected"
                    value={cascadeResults?.total_buses_affected || 0}
                    prefix={<FireOutlined />}
                    valueStyle={{ color: '#cf1322' }}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Cascade Amplification"
                    value={cascadeResults?.cascade_amplification || 0}
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
                    value={cascadeResults?.final_grid_size || 0}
                    prefix={<NodeIndexOutlined />}
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Execution Time"
                    value={cascadeResults?.execution_time || 0}
                    precision={1}
                    suffix="s"
                    valueStyle={{ color: '#722ed1' }}
                  />
                </Card>
              </Col>
            </Row>

            <Card title="Cascade Progression Over Time">
              {renderCascadeSteps()}
            </Card>
          </TabPane>

          <TabPane tab="Impact Analysis" key="impact">
            <Card title="Fire vs Cascade Impact Distribution">
              {renderImpactDistribution()}
            </Card>
          </TabPane>

          {tdaResults && (
            <TabPane tab="TDA Results" key="tda">
              {renderTDAResults()}
            </TabPane>
          )}

          <TabPane tab="Download" key="download">
            <Card>
              <h3>Download Analysis Data</h3>
              <Row gutter={[16, 16]}>
                <Col span={12}>
                  <Button 
                    block 
                    icon={<DownloadOutlined />}
                    onClick={() => downloadMatrix('before')}
                  >
                    Download Before Matrix
                  </Button>
                </Col>
                <Col span={12}>
                  <Button 
                    block 
                    icon={<DownloadOutlined />}
                    onClick={() => downloadMatrix('after')}
                  >
                    Download After Matrix
                  </Button>
                </Col>
              </Row>
            </Card>
          </TabPane>
        </Tabs>
      </Modal>
    </>
  );
};

export default ResultsVisualization;