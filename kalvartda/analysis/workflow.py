import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import logging
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

@dataclass
class AnalysisResult:
    fire_name: str
    wasserstein_distance: float
    before_features: int
    after_features: int
    cascade_impact: Dict[str, Any]
    execution_time: float
    success: bool
    error_message: Optional[str] = None

class TDAWorkflow:
    def __init__(self, config: TDAConfig):
        self.config = config
        self.data_loader = DataLoader(config.data)
        
    async def run_full_analysis(self, fire_data_path: Path) -> AnalysisResult:
        """Main analysis pipeline with async execution"""
        start_time = asyncio.get_event_loop().time()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            try:
                # Load data
                task1 = progress.add_task("Loading electrical grid data...", total=None)
                buses_df = self.data_loader.load_bus_data()
                fire_gdf = self.data_loader.load_fire_data(fire_data_path)
                progress.update(task1, completed=True)
                
                # Create spatial analysis area
                task2 = progress.add_task("Defining analysis area...", total=None)
                local_buses = await self._get_local_area_async(buses_df, fire_gdf)
                progress.update(task2, completed=True)
                
                # Generate matrices
                task3 = progress.add_task("Generating power matrices...", total=None)
                before_matrix, after_matrix = await self._generate_matrices_async(local_buses)
                progress.update(task3, completed=True)
                
                # Run TDA analysis
                task4 = progress.add_task("Running TDA analysis...", total=None)
                results = await self._run_tda_analysis_async(before_matrix, after_matrix)
                progress.update(task4, completed=True)
                
                execution_time = asyncio.get_event_loop().time() - start_time
                
                return AnalysisResult(
                    fire_name=fire_gdf.iloc[0].get('name', 'Unknown'),
                    wasserstein_distance=results['wasserstein_distance'],
                    before_features=results['before_features'],
                    after_features=results['after_features'],
                    cascade_impact=results['cascade_impact'],
                    execution_time=execution_time,
                    success=True
                )
                
            except Exception as e:
                logger.error(f"Analysis failed: {e}")
                return AnalysisResult(
                    fire_name="Failed",
                    wasserstein_distance=0.0,
                    before_features=0,
                    after_features=0,
                    cascade_impact={},
                    execution_time=asyncio.get_event_loop().time() - start_time,
                    success=False,
                    error_message=str(e)
                )
    
    async def _get_local_area_async(self, buses_df: pl.DataFrame, fire_gdf: gpd.GeoDataFrame):
        """Async spatial filtering"""
        # Run CPU-intensive spatial operations in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_local_area_sync, buses_df, fire_gdf)
    
    def _get_local_area_sync(self, buses_df: pl.DataFrame, fire_gdf: gpd.GeoDataFrame):
        """Synchronous spatial filtering"""
        buses_gdf = self.data_loader.create_spatial_dataframe(buses_df)
        
        # Create buffer around fire
        fire_union = fire_gdf.geometry.unary_union
        buffer_m = self.config.analysis.analysis_radius_km * 1000
        analysis_area = fire_union.buffer(buffer_m)
        
        # Filter buses within analysis area
        local_buses = buses_gdf[buses_gdf.geometry.within(analysis_area)]
        
        logger.info(f"Found {len(local_buses)} buses in analysis area")
        return local_buses
    
    async def _generate_matrices_async(self, local_buses):
        """Async matrix generation using Rust engine"""
        # Convert to format expected by Rust
        bus_data = [
            (
                int(row.bus_i), 
                float(row.longitude), 
                float(row.latitude),
                float(row.get('total_gen', 0)),
                float(row.get('load_mw', 0)),
                float(row.get('vm', 1.0)),
                float(row.get('base_kv', 138)),
                str(row.get('bus_type', 'Load')),
                int(row.get('zone', 1))
            )
            for _, row in local_buses.iterrows()
        ]
        
        config_tuple = (
            self.config.analysis.fire_impact_buffer_km,
            self.config.analysis.simulation_steps,
            self.config.analysis.analysis_radius_km
        )
        
        # Call Rust engine
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self._call_rust_engine, 
            bus_data, 
            config_tuple
        )
    
    def _call_rust_engine(self, bus_data, config_tuple):
        """Synchronous call to Rust engine"""
        import tda_engine
        
        engine = tda_engine.create_engine(bus_data, config_tuple)
        engine.generate_power_matrix()
        
        # Run Perseus analysis
        output_dir = self.config.data.outputs_dir / "temp_analysis"
        output_dir.mkdir(exist_ok=True)
        
        before_features = engine.run_perseus_analysis(str(output_dir / "before"))
        # Simulate cascade and get after state
        after_features = engine.run_perseus_analysis(str(output_dir / "after"))
        
        return before_features, after_features
    
    async def _run_tda_analysis_async(self, before_matrix, after_matrix):
        """Async TDA computation"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self._compute_tda_metrics, 
            before_matrix, 
            after_matrix
        )
    
    def _compute_tda_metrics(self, before_features, after_features):
        """Compute TDA metrics"""
        import tda_engine
        
        engine = tda_engine.TDAEngine()  # Temporary instance for computation
        wasserstein_dist = engine.compute_wasserstein_distance(before_features, after_features)
        
        return {
            'wasserstein_distance': wasserstein_dist,
            'before_features': len(before_features),
            'after_features': len(after_features),
            'cascade_impact': {'total_buses_affected': 0}  # Placeholder
        }