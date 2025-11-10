import asyncio
from typing import Dict, List, Optional, Callable
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import json
import time

logger = logging.getLogger(__name__)

class CascadeStatus(Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    ANALYZING_FIRE_IMPACT = "analyzing_fire_impact"
    RUNNING_SIMULATION = "running_simulation"
    GENERATING_MATRICES = "generating_matrices"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class CascadeProgress:
    status: CascadeStatus
    progress_percent: float
    current_step: int
    total_steps: int
    current_task: str
    start_time: float
    estimated_completion: Optional[float] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

@dataclass
class CascadeConfig:
    buffer_km: float = 5.0
    max_steps: int = 20
    enable_parallel: bool = True
    max_workers: int = 4
    generate_matrices: bool = True
    
@dataclass
class CascadeResults:
    config: CascadeConfig
    cascade_steps: List[Dict]
    fire_impact_results: List[Dict]
    total_buses_affected: int
    cascade_amplification: float
    execution_time: float
    final_grid_size: int
    before_matrix: Optional[str] = None  # Path to matrix file
    after_matrix: Optional[str] = None   # Path to matrix file

class CascadeOrchestrator:
    """Orchestrates the entire cascade analysis pipeline"""
    
    def __init__(self):
        self.progress = CascadeProgress(
            status=CascadeStatus.IDLE,
            progress_percent=0.0,
            current_step=0,
            total_steps=0,
            current_task="Ready",
            start_time=time.time()
        )
        self.subscribers: List[Callable[[CascadeProgress], None]] = []
        self.current_task: Optional[asyncio.Task] = None
    
    def subscribe_to_progress(self, callback: Callable[[CascadeProgress], None]):
        """Subscribe to progress updates"""
        self.subscribers.append(callback)
    
    def _notify_progress(self, status: CascadeStatus, progress: float, 
                        current_step: int, task: str):
        """Notify subscribers of progress updates"""
        self.progress.status = status
        self.progress.progress_percent = progress
        self.progress.current_step = current_step
        self.progress.current_task = task
        
        # Estimate completion time
        if progress > 0:
            elapsed = time.time() - self.progress.start_time
            estimated_total = elapsed / (progress / 100.0)
            self.progress.estimated_completion = self.progress.start_time + estimated_total
        
        # Notify all subscribers
        for callback in self.subscribers:
            try:
                callback(self.progress)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    async def run_cascade_analysis(
        self,
        fire_data: 'gpd.GeoDataFrame',
        buses_gdf: 'gpd.GeoDataFrame',
        graph_data: Dict,
        config: CascadeConfig
    ) -> CascadeResults:
        """Run complete cascade analysis pipeline"""
        
        self.progress.start_time = time.time()
        
        try:
            # Phase 1: Initialize (0-10%)
            self._notify_progress(CascadeStatus.INITIALIZING, 5.0, 0, "Initializing cascade engine...")
            
            cascade_engine = await self._initialize_cascade_engine(graph_data, buses_gdf)
            
            # Phase 2: Fire Impact Analysis (10-40%)
            self._notify_progress(CascadeStatus.ANALYZING_FIRE_IMPACT, 15.0, 0, "Analyzing fire impact timeline...")
            
            fire_processor = FireDataProcessor()
            fire_steps = await fire_processor.prepare_fire_timeline(fire_data)
            
            fire_analyzer = FireImpactAnalyzer(max_workers=config.max_workers)
            fire_impact_results = await fire_analyzer.analyze_fire_impact_timeline(
                fire_steps, buses_gdf, config.buffer_km
            )
            
            # Phase 3: Cascade Simulation (40-80%)
            self._notify_progress(CascadeStatus.RUNNING_SIMULATION, 40.0, 0, "Running cascade simulation...")
            
            # Extract fire-affected buses by step
            fire_affected_by_step = [
                result.fire_affected for result in fire_impact_results
            ]
            
            # Run Rust cascade engine
            cascade_steps = await self._run_cascade_simulation(
                cascade_engine, fire_affected_by_step, config.max_steps
            )
            
            # Phase 4: Matrix Generation (80-100%)
            before_matrix_path = None
            after_matrix_path = None
            
            if config.generate_matrices:
                self._notify_progress(CascadeStatus.GENERATING_MATRICES, 85.0, 0, "Generating TDA matrices...")
                
                before_matrix_path, after_matrix_path = await self._generate_matrices(
                    buses_gdf, cascade_steps
                )
            
            # Calculate summary metrics
            total_affected = sum(len(result.fire_affected) for result in fire_impact_results)
            total_cascade = sum(len(step.get('deenergized', [])) for step in cascade_steps)
            cascade_amplification = total_cascade / total_affected if total_affected > 0 else 0
            
            final_grid_size = cascade_steps[-1]['vertices_remaining'] if cascade_steps else len(buses_gdf)
            
            # Complete
            self._notify_progress(CascadeStatus.COMPLETED, 100.0, len(cascade_steps), "Analysis complete")
            
            execution_time = time.time() - self.progress.start_time
            
            return CascadeResults(
                config=config,
                cascade_steps=[asdict(step) for step in cascade_steps],
                fire_impact_results=[asdict(result) for result in fire_impact_results],
                total_buses_affected=total_affected,
                cascade_amplification=cascade_amplification,
                execution_time=execution_time,
                final_grid_size=final_grid_size,
                before_matrix=before_matrix_path,
                after_matrix=after_matrix_path
            )
            
        except Exception as e:
            logger.error(f"Cascade analysis failed: {e}")
            self.progress.status = CascadeStatus.FAILED
            self.progress.errors.append(str(e))
            raise
    
    async def _initialize_cascade_engine(self, graph_data: Dict, buses_gdf) -> 'CascadeEngine':
        """Initialize the Rust cascade engine"""
        import cascade_engine
        
        # Convert bus data to format expected by Rust
        buses = [
            (
                int(row['bus_i']),
                float(row.get('longitude', 0)),
                float(row.get('latitude', 0)),
                str(row.get('bus_type', 'Load')),
                float(row.get('total_gen', 0)),
                float(row.get('load_mw', 0))
            )
            for _, row in buses_gdf.iterrows()
        ]
        
        # Convert edge data
        edges = graph_data.get('edges', [])
        
        return cascade_engine.create_cascade_engine(buses, edges)
    
    async def _run_cascade_simulation(
        self,
        cascade_engine,
        fire_affected_by_step: List[List[int]],
        max_steps: int
    ) -> List[Dict]:
        """Run the cascade simulation"""
        import cascade_engine
        
        # Update progress during simulation
        for step in range(min(len(fire_affected_by_step), max_steps)):
            progress = 40.0 + (40.0 * step / max_steps)
            self._notify_progress(
                CascadeStatus.RUNNING_SIMULATION, 
                progress, 
                step + 1, 
                f"Simulating cascade step {step + 1}/{max_steps}"
            )
            await asyncio.sleep(0.1)  # Allow other tasks to run
        
        # Run the actual simulation
        cascade_steps = await cascade_engine.run_cascade_py(
            cascade_engine, fire_affected_by_step, max_steps
        )
        
        return cascade_steps
    
    async def _generate_matrices(self, buses_gdf, cascade_steps) -> Tuple[str, str]:
        """Generate before/after matrices for TDA analysis"""
        # This would integrate with your TDA engine
        # For now, return placeholder paths
        before_path = "matrices/before_cascade.csv"
        after_path = "matrices/after_cascade.csv"
        
        # TODO: Implement actual matrix generation
        
        return before_path, after_path
    
    def get_progress(self) -> Dict:
        """Get current progress as dictionary"""
        return asdict(self.progress)
    
    def cancel_analysis(self):
        """Cancel running analysis"""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            self.progress.status = CascadeStatus.IDLE
            self.progress.current_task = "Cancelled"