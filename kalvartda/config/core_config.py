from pydantic import BaseModel, Field
from pathlib import Path
from typing import List, Dict, Any, Optional
import os

class DatabaseConfig(BaseModel):
    data_dir: Path = Field(default="databases/")
    parsed_dir: Path = Field(default="parsed_csv/")
    cache_dir: Path = Field(default="cache/")
    
class OutputConfig(BaseModel):
    outputs_dir: Path = Field(default="outputs/")
    attacked_dir: Path = Field(default="outputsAttacked/")
    diagnostic_dir: Path = Field(default="diagnostic_output/")
    
class GridConfig(BaseModel):
    western_states: List[str] = Field(default=[
        "washington", "oregon", "california", "idaho", "nevada", 
        "montana", "wyoming", "utah", "colorado", "arizona", "new mexico"
    ])
    simulation_steps: int = Field(default=20)
    max_fire_events: int = Field(default=100)
    
class ParallelConfig(BaseModel):
    enabled: bool = Field(default=True)
    method: str = Field(default="async")
    max_workers: int = Field(default=4)
    memory_limit_gb: int = Field(default=32)

class AppConfig(BaseModel):
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    grid: GridConfig = Field(default_factory=GridConfig)
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)
    
    # Perseus configuration
    perseus_exe: Path = Field(default="Perseus/perseusWin.exe")
    
    @classmethod
    def load_from_env(cls) -> 'AppConfig':
        """Load configuration from environment variables"""
        return cls(
            database=DatabaseConfig(
                data_dir=Path(os.getenv('DATA_DIR', 'databases/')),
                cache_dir=Path(os.getenv('CACHE_DIR', 'cache/'))
            ),
            parallel=ParallelConfig(
                max_workers=int(os.getenv('MAX_WORKERS', '4')),
                memory_limit_gb=int(os.getenv('MEMORY_LIMIT', '32'))
            )
        )

# Global config instance
config = AppConfig.load_from_env()