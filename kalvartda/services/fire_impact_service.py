import asyncio
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass
class FireImpactResult:
    step: int
    fire_affected: List[int]
    direct_contact: List[int]
    proximity_contact: List[int]
    fire_names: List[str]
    is_compound_event: bool
    total_area_acres: float

class FireImpactAnalyzer:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def analyze_fire_impact_timeline(
        self,
        fire_data_by_step: List[gpd.GeoDataFrame],
        buses_gdf: gpd.GeoDataFrame,
        buffer_km: float = 5.0
    ) -> List[FireImpactResult]:
        """Analyze fire impact across multiple time steps"""
        
        # Process all steps concurrently
        tasks = [
            self._analyze_single_step(step_num, fire_data, buses_gdf, buffer_km)
            for step_num, fire_data in enumerate(fire_data_by_step)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return valid results
        valid_results = [
            result for result in results 
            if not isinstance(result, Exception)
        ]
        
        return valid_results
    
    async def _analyze_single_step(
        self,
        step: int,
        fire_data: gpd.GeoDataFrame,
        buses_gdf: gpd.GeoDataFrame,
        buffer_km: float
    ) -> FireImpactResult:
        """Analyze fire impact for a single time step"""
        
        if fire_data.empty:
            return FireImpactResult(
                step=step,
                fire_affected=[],
                direct_contact=[],
                proximity_contact=[],
                fire_names=[],
                is_compound_event=False,
                total_area_acres=0.0
            )
        
        # Run spatial operations in thread pool
        loop = asyncio.get_event_loop()
        
        # Direct contact analysis
        direct_contact = await loop.run_in_executor(
            self.executor,
            self._find_direct_contact,
            fire_data, buses_gdf
        )
        
        # Proximity analysis
        proximity_contact = await loop.run_in_executor(
            self.executor,
            self._find_proximity_contact,
            fire_data, buses_gdf, buffer_km
        )
        
        # Combine results
        all_affected = list(set(direct_contact + proximity_contact))
        
        return FireImpactResult(
            step=step,
            fire_affected=all_affected,
            direct_contact=direct_contact,
            proximity_contact=proximity_contact,
            fire_names=fire_data['attr_IncidentName'].unique().tolist(),
            is_compound_event=len(fire_data['attr_IncidentName'].unique()) > 1,
            total_area_acres=fire_data.get('fire_acres', 0).sum()
        )
    
    def _find_direct_contact(
        self,
        fire_data: gpd.GeoDataFrame,
        buses_gdf: gpd.GeoDataFrame
    ) -> List[int]:
        """Find buses in direct contact with fire polygons"""
        try:
            # Ensure valid geometries
            fire_data = fire_data.loc[fire_data.is_valid]
            buses_gdf = buses_gdf.loc[buses_gdf.is_valid]
            
            # Spatial intersection
            intersecting = gpd.sjoin(
                buses_gdf, fire_data, 
                how='inner', predicate='intersects'
            )
            
            return intersecting['bus_i'].unique().tolist()
        except Exception as e:
            logger.error(f"Direct contact analysis failed: {e}")
            return []
    
    def _find_proximity_contact(
        self,
        fire_data: gpd.GeoDataFrame,
        buses_gdf: gpd.GeoDataFrame,
        buffer_km: float
    ) -> List[int]:
        """Find buses within buffer distance of fire centers"""
        try:
            # Get fire center points
            fire_centers = fire_data.copy()
            if 'attr_InitialLatitude' in fire_data.columns:
                # Use initial fire coordinates if available
                valid_centers = fire_data.dropna(subset=['attr_InitialLatitude', 'attr_InitialLongitude'])
                if not valid_centers.empty:
                    fire_centers = gpd.GeoDataFrame(
                        valid_centers,
                        geometry=gpd.points_from_xy(
                            valid_centers['attr_InitialLongitude'],
                            valid_centers['attr_InitialLatitude']
                        ),
                        crs=fire_data.crs
                    )
            else:
                # Use polygon centroids
                fire_centers['geometry'] = fire_centers.geometry.centroid
            
            # Create buffers
            buffer_m = buffer_km * 1000  # Convert to meters
            fire_buffers = fire_centers.copy()
            fire_buffers['geometry'] = fire_centers.to_crs('EPSG:3857').buffer(buffer_m).to_crs(fire_data.crs)
            
            # Find buses in buffers
            within_buffer = gpd.sjoin(
                buses_gdf, fire_buffers,
                how='inner', predicate='intersects'
            )
            
            return within_buffer['bus_i'].unique().tolist()
        except Exception as e:
            logger.error(f"Proximity analysis failed: {e}")
            return []

class FireDataProcessor:
    """Processes fire data into time-stepped format"""
    
    def __init__(self):
        pass
    
    async def prepare_fire_timeline(
        self,
        fire_data: gpd.GeoDataFrame
    ) -> List[gpd.GeoDataFrame]:
        """Prepare fire data organized by time steps"""
        
        if fire_data.empty:
            return []
        
        # Group by time step
        if 'step' not in fire_data.columns:
            # Create single step if no temporal data
            return [fire_data]
        
        # Group by step and create list
        fire_steps = []
        for step_num in sorted(fire_data['step'].unique()):
            step_data = fire_data[fire_data['step'] == step_num].copy()
            fire_steps.append(step_data)
        
        return fire_steps
    
    def validate_fire_data(self, fire_data: gpd.GeoDataFrame) -> Dict[str, any]:
        """Validate fire data quality"""
        validation_result = {
            'valid': True,
            'warnings': [],
            'info': []
        }
        
        if fire_data.empty:
            validation_result['valid'] = False
            validation_result['warnings'].append("Fire data is empty")
            return validation_result
        
        # Check geometry validity
        invalid_geom = ~fire_data.is_valid
        if invalid_geom.any():
            validation_result['warnings'].append(
                f"{invalid_geom.sum()} invalid geometries found"
            )
        
        # Check for required columns
        required_cols = ['attr_IncidentName']
        missing_cols = [col for col in required_cols if col not in fire_data.columns]
        if missing_cols:
            validation_result['warnings'].append(
                f"Missing columns: {missing_cols}"
            )
        
        # Check temporal data
        if 'step' in fire_data.columns:
            step_count = fire_data['step'].nunique()
            validation_result['info'].append(f"Found {step_count} time steps")
        
        return validation_result