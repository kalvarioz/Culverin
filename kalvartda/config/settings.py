from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from pathlib import Path

class PerseusConfig(BaseModel):
    executable_path: Path = Field(default="Perseus/perseusWin.exe")
    g: int = Field(default=0, description="Genus parameter")
    s: float = Field(default=0.05, description="Scale increment")
    n: int = Field(default=10, description="Filtration steps")
    c: int = Field(default=3, description="Connectivity parameter")
    timeout_seconds: int = Field(default=600)

class AnalysisConfig(BaseModel):
    analysis_radius_km: float = Field(default=30.0)
    fire_impact_buffer_km: float = Field(default=2.0)
    simulation_steps: int = Field(default=20)
    downsample_max_pts: int = Field(default=300)
    memory_limit_gb: int = Field(default=32)

class DataConfig(BaseModel):
    data_dir: Path = Field(default="data/")
    outputs_dir: Path = Field(default="outputs/")
    bus_data_file: str = Field(default="bus_data.csv")
    branch_data_file: str = Field(default="branch_data.csv")
    
class TDAConfig(BaseModel):
    perseus: PerseusConfig = Field(default_factory=PerseusConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    data: DataConfig = Field(default_factory=DataConfig)