import React, { useState, useCallback } from 'react';
import { 
  Card, 
  Form, 
  Select, 
  Slider, 
  Button, 
  Space, 
  Divider, 
  Typography,
  Badge,
  Collapse,
  message
} from 'antd';
import { 
  PlayCircleOutlined, 
  SettingOutlined, 
  FilterOutlined,
  ClearOutlined,
  WifiOutlined,
  DisconnectOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;
const { Panel } = Collapse;

const ControlPanel = ({
  selectedFire,
  filters,
  onFiltersChange,
  onStartCascade,
  onStartTDA,
  cascadeResults,
  disabled,
  isConnected
}) => {
  const [cascadeConfig, setCascadeConfig] = useState({
    buffer_km: 5.0,
    max_steps: 20,
    max_workers: 4,
    enable_parallel: true,
    generate_matrices: true
  });

  const [activeFilters, setActiveFilters] = useState({});

  const handleFilterChange = useCallback((filterType, value) => {
    const newFilters = { ...activeFilters, [filterType]: value };
    if (!value || (Array.isArray(value) && value.length === 0)) {
      delete newFilters[filterType];
    }
    setActiveFilters(newFilters);
    onFiltersChange(newFilters);
  }, [activeFilters, onFiltersChange]);

  const clearAllFilters = useCallback(() => {
    setActiveFilters({});
    onFiltersChange({});
  }, [onFiltersChange]);

  const handleStartCascade = useCallback(() => {
    if (!selectedFire) {
      message.warning('Please select a fire first');
      return;
    }
    onStartCascade(cascadeConfig);
  }, [selectedFire, cascadeConfig, onStartCascade]);

  const getFilterBadgeCount = () => {
    return Object.keys(activeFilters).length;
  };

  return (
    <div
      style={{
        position: 'absolute',
        top: 10,
        right: 10,
        width: 400,
        zIndex: 1000,
        maxHeight: 'calc(100vh - 20px)',
        overflowY: 'auto'
      }}
    >
      <Card size="small" style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={4} style={{ margin: 0 }}>
            🔥 KALVARTDA
          </Title>
          <Badge 
            status={isConnected ? "success" : "error"} 
            text={isConnected ? "Connected" : "Disconnected"}
          />
        </div>
      </Card>

      {/* Fire Selection Status */}
      <Card size="small" style={{ marginBottom: 8 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text strong>Selected Fire:</Text>
          {selectedFire ? (
            <div style={{ 
              padding: 8, 
              background: '#f6ffed', 
              border: '1px solid #b7eb8f',
              borderRadius: 4 
            }}>
              <Text strong>{selectedFire.attr_IncidentName || selectedFire.name}</Text><br/>
              <Text type="secondary">
                {selectedFire.fire_intensity && `Intensity: ${selectedFire.fire_intensity}`}
                {selectedFire.fire_acres && `\nArea: ${selectedFire.fire_acres?.toLocaleString()} acres`}
              </Text>
            </div>
          ) : (
            <div style={{ 
              padding: 8, 
              background: '#fff7e6', 
              border: '1px solid #ffd591',
              borderRadius: 4 
            }}>
              <Text type="secondary">Click on a fire polygon to select</Text>
            </div>
          )}
        </Space>
      </Card>

      {/* Filters */}
      <Card 
        size="small" 
        style={{ marginBottom: 8 }}
        title={
          <Space>
            <FilterOutlined />
            <span>Filters</span>
            {getFilterBadgeCount() > 0 && (
              <Badge count={getFilterBadgeCount()} />
            )}
          </Space>
        }
        extra={
          getFilterBadgeCount() > 0 && (
            <Button 
              size="small" 
              icon={<ClearOutlined />} 
              onClick={clearAllFilters}
            >
              Clear
            </Button>
          )
        }
      >
        <Collapse size="small" ghost>
          <Panel header="Fire Characteristics" key="fire">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text strong>Intensity:</Text>
                <Select
                  mode="multiple"
                  placeholder="Select intensity levels"
                  value={activeFilters.intensity || []}
                  onChange={(value) => handleFilterChange('intensity', value)}
                  style={{ width: '100%', marginTop: 4 }}
                >
                  <Option value="Very Low">Very Low</Option>
                  <Option value="Low">Low</Option>
                  <Option value="Moderate">Moderate</Option>
                  <Option value="High">High</Option>
                  <Option value="Extreme">Extreme</Option>
                </Select>
              </div>

              <div>
                <Text strong>Year Range:</Text>
                <Slider
                  range
                  min={2010}
                  max={2024}
                  value={activeFilters.yearRange || [2018, 2023]}
                  onChange={(value) => handleFilterChange('yearRange', value)}
                  marks={{
                    2010: '2010',
                    2015: '2015',
                    2020: '2020',
                    2024: '2024'
                  }}
                />
              </div>

              <div>
                <Text strong>State:</Text>
                <Select
                  mode="multiple"
                  placeholder="Select states"
                  value={activeFilters.state || []}
                  onChange={(value) => handleFilterChange('state', value)}
                  style={{ width: '100%', marginTop: 4 }}
                >
                  <Option value="california">California</Option>
                  <Option value="oregon">Oregon</Option>
                  <Option value="washington">Washington</Option>
                  <Option value="idaho">Idaho</Option>
                  <Option value="nevada">Nevada</Option>
                  <Option value="montana">Montana</Option>
                  <Option value="wyoming">Wyoming</Option>
                  <Option value="utah">Utah</Option>
                  <Option value="colorado">Colorado</Option>
                  <Option value="arizona">Arizona</Option>
                  <Option value="new mexico">New Mexico</Option>
                </Select>
              </div>
            </Space>
          </Panel>

          <Panel header="Fuel & Landowner" key="fuel">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text strong>Fuel Category:</Text>
                <Select
                  mode="multiple"
                  placeholder="Select fuel categories"
                  value={activeFilters.fuel_category || []}
                  onChange={(value) => handleFilterChange('fuel_category', value)}
                  style={{ width: '100%', marginTop: 4 }}
                >
                  <Option value="Timber (Litter and Understory)">Timber</Option>
                  <Option value="Grass">Grass</Option>
                  <Option value="Grass-Shrub">Grass-Shrub</Option>
                  <Option value="Shrub">Shrub</Option>
                  <Option value="Hardwood">Hardwood</Option>
                  <Option value="Slash-Blowdown">Slash-Blowdown</Option>
                </Select>
              </div>

              <div>
                <Text strong>Landowner:</Text>
                <Select
                  mode="multiple"
                  placeholder="Select landowner types"
                  value={activeFilters.landowner || []}
                  onChange={(value) => handleFilterChange('landowner', value)}
                  style={{ width: '100%', marginTop: 4 }}
                >
                  <Option value="Federal">Federal</Option>
                  <Option value="State">State</Option>
                  <Option value="Private">Private</Option>
                  <Option value="Local Government">Local Government</Option>
                  <Option value="Tribal">Tribal</Option>
                </Select>
              </div>
            </Space>
          </Panel>
        </Collapse>
      </Card>

      {/* Analysis Configuration */}
      <Card 
        size="small" 
        style={{ marginBottom: 8 }}
        title={
          <Space>
            <SettingOutlined />
            <span>Analysis Configuration</span>
          </Space>
        }
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>Buffer Distance: {cascadeConfig.buffer_km} km</Text>
            <Slider
              min={1}
              max={20}
              step={0.5}
              value={cascadeConfig.buffer_km}
              onChange={(value) => setCascadeConfig(prev => ({ 
                ...prev, 
                buffer_km: value 
              }))}
              marks={{
                1: '1km',
                5: '5km', 
                10: '10km',
                20: '20km'
              }}
            />
          </div>

          <div>
            <Text strong>Max Simulation Steps: {cascadeConfig.max_steps}</Text>
            <Slider
              min={5}
              max={50}
              step={5}
              value={cascadeConfig.max_steps}
              onChange={(value) => setCascadeConfig(prev => ({ 
                ...prev, 
                max_steps: value 
              }))}
              marks={{
                5: '5',
                20: '20',
                35: '35',
                50: '50'
              }}
            />
          </div>

          <div>
            <Text strong>Parallel Workers: {cascadeConfig.max_workers}</Text>
            <Slider
              min={1}
              max={8}
              step={1}
              value={cascadeConfig.max_workers}
              onChange={(value) => setCascadeConfig(prev => ({ 
                ...prev, 
                max_workers: value 
              }))}
              marks={{
                1: '1',
                4: '4',
                8: '8'
              }}
            />
          </div>
        </Space>
      </Card>

      {/* Analysis Actions */}
      <Card size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleStartCascade}
            disabled={disabled || !selectedFire || !isConnected}
            block
            size="large"
          >
            Run Cascade Analysis
          </Button>

          {cascadeResults && (
            <Button
              type="default"
              onClick={onStartTDA}
              disabled={disabled || !isConnected}
              block
            >
              Run TDA Analysis
            </Button>
          )}

          {!selectedFire && (
            <Text type="secondary" style={{ textAlign: 'center', display: 'block' }}>
              Select a fire to begin analysis
            </Text>
          )}
        </Space>
      </Card>
    </div>
  );
};

export default ControlPanel;