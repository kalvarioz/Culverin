from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String(36), unique=True, index=True)
    fire_name = Column(String(255))
    config_hash = Column(String(64), index=True)  # For caching similar configs
    status = Column(String(50), default="pending")
    
    # Input parameters
    analysis_radius_km = Column(Float)
    fire_buffer_km = Column(Float)
    simulation_steps = Column(Integer)
    
    # Results
    wasserstein_distance = Column(Float)
    before_features_count = Column(Integer)
    after_features_count = Column(Integer)
    execution_time_seconds = Column(Float)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Cached data
    before_features_json = Column(JSON)
    after_features_json = Column(JSON)
    cascade_results_json = Column(JSON)

class GridSnapshot(Base):
    __tablename__ = "grid_snapshots"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    description = Column(Text)
    
    # Grid data
    bus_count = Column(Integer)
    branch_count = Column(Integer)
    generation_total_mw = Column(Float)
    load_total_mw = Column(Float)
    
    # File references
    bus_data_file = Column(String(255))
    branch_data_file = Column(String(255))
    matrix_file = Column(String(255))  # Cached matrix
    
    created_at = Column(DateTime, default=datetime.utcnow)