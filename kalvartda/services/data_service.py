import asyncio
import polars as pl
import geopandas as gpd
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

@dataclass
class DataLoadResult:
    success: bool
    data: Optional[Any] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

class DataLoader(ABC):
    """Abstract base class for data loaders"""
    
    @abstractmethod
    async def load(self, **kwargs) -> DataLoadResult:
        pass
    
    @abstractmethod
    def validate(self, data: Any) -> bool:
        pass

class BusDataLoader(DataLoader):
    """Loads and validates electrical bus data"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        
    async def load(self, **kwargs) -> DataLoadResult:
        try:
            # Load bus coordinate data
            bus_file = self.config.database.parsed_dir / "bus_data.csv"
            mpc_file = self.config.database.data_dir / "mpc_bus.csv"
            
            if not bus_file.exists() or not mpc_file.exists():
                return DataLoadResult(
                    success=False,
                    error_message=f"Missing bus data files: {bus_file}, {mpc_file}"
                )
            
            # Use Polars for fast loading
            bus_coords = pl.read_csv(bus_file)
            mpc_data = pl.read_csv(mpc_file)
            
            # Coordinate detection (port from your R function)
            coord_result = await self._detect_coordinates(bus_coords)
            if not coord_result.success:
                return coord_result
            
            # Merge datasets
            merged_data = await self._merge_bus_data(bus_coords, mpc_data)
            
            # Convert to GeoDataFrame for spatial operations
            gdf = await self._create_spatial_dataframe(merged_data)
            
            return DataLoadResult(
                success=True,
                data=gdf,
                metadata={
                    "bus_count": len(gdf),
                    "coordinate_source": coord_result.metadata.get("source"),
                    "coordinate_quality": coord_result.metadata.get("quality")
                }
            )
            
        except Exception as e:
            logger.error(f"Bus data loading failed: {e}")
            return DataLoadResult(
                success=False,
                error_message=str(e)
            )
    
    async def _detect_coordinates(self, data: pl.DataFrame) -> DataLoadResult:
        """Port of your coordinate detection logic"""
        # Detect coordinate columns by name patterns
        lon_patterns = ["longitude", "lon", "lng", "x"]
        lat_patterns = ["latitude", "lat", "y"]
        
        lon_col = None
        lat_col = None
        
        for col in data.columns:
            col_lower = col.lower()
            if any(pattern in col_lower for pattern in lon_patterns):
                lon_col = col
            if any(pattern in col_lower for pattern in lat_patterns):
                lat_col = col
        
        if not lon_col or not lat_col:
            # Analyze data patterns (port your numeric range detection)
            return await self._detect_by_values(data)
        
        return DataLoadResult(
            success=True,
            metadata={
                "lon_col": lon_col,
                "lat_col": lat_col,
                "source": "column_names",
                "quality": "high"
            }
        )
    
    async def _detect_by_values(self, data: pl.DataFrame) -> DataLoadResult:
        """Detect coordinates by analyzing value ranges"""
        numeric_cols = [col for col in data.columns 
                       if data[col].dtype in [pl.Float64, pl.Int64]]
        
        candidates = {"longitude": [], "latitude": []}
        
        for col in numeric_cols:
            values = data[col].drop_nulls()
            if len(values) == 0:
                continue
                
            min_val = values.min()
            max_val = values.max()
            mean_val = values.mean()
            
            # Western US longitude range: -130 to -100
            if -130 <= min_val and max_val <= -95 and abs(mean_val) > 100:
                candidates["longitude"].append(col)
            
            # Western US latitude range: 30 to 50
            if 25 <= min_val and max_val <= 55 and 25 < mean_val < 55:
                candidates["latitude"].append(col)
        
        if candidates["longitude"] and candidates["latitude"]:
            return DataLoadResult(
                success=True,
                metadata={
                    "lon_col": candidates["longitude"][0],
                    "lat_col": candidates["latitude"][0],
                    "source": "value_analysis",
                    "quality": "medium"
                }
            )
        
        return DataLoadResult(
            success=False,
            error_message="Could not detect coordinate columns"
        )
    
    def validate(self, data: gpd.GeoDataFrame) -> bool:
        """Validate loaded bus data"""
        if len(data) == 0:
            return False
        
        # Check required columns
        required_cols = ["bus_i", "geometry"]
        if not all(col in data.columns for col in required_cols):
            return False
        
        # Check coordinate validity
        bounds = data.total_bounds
        # Western US bounds: lon [-130, -95], lat [25, 55]
        if not (-130 <= bounds[0] and bounds[2] <= -95 and 
                25 <= bounds[1] and bounds[3] <= 55):
            logger.warning("Bus coordinates outside expected western US range")
        
        return True

class WildfireDataLoader(DataLoader):
    """Loads and processes wildfire data"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        
    async def load(self, **kwargs) -> DataLoadResult:
        try:
            # Try multiple file formats
            shp_file = Path("WFIGS_Interagency_Perimeters_-8845918407708086874/Perimeters.shp")
            csv_file = self.config.database.data_dir / "WFIGS_Interagency_Perimeters_-3500393626074286023.csv"
            
            if shp_file.exists():
                gdf = gpd.read_file(shp_file)
                source = "shapefile"
            elif csv_file.exists():
                # Load CSV and convert to GeoDataFrame
                df = pl.read_csv(csv_file).to_pandas()
                gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df.get('geometry', [])))
                source = "csv"
            else:
                return DataLoadResult(
                    success=False,
                    error_message="No wildfire data files found"
                )
            
            # Process the data (port your processing functions)
            processed_gdf = await self._process_wildfire_data(gdf)
            
            return DataLoadResult(
                success=True,
                data=processed_gdf,
                metadata={
                    "source": source,
                    "fire_count": len(processed_gdf),
                    "date_range": self._get_date_range(processed_gdf)
                }
            )
            
        except Exception as e:
            logger.error(f"Wildfire data loading failed: {e}")
            return DataLoadResult(
                success=False,
                error_message=str(e)
            )
    
    async def _process_wildfire_data(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Port of your wildfire processing pipeline"""
        # Standardize column names
        gdf = self._standardize_columns(gdf)
        
        # Filter by western states
        if "attr_POOState" in gdf.columns:
            gdf = gdf[gdf["attr_POOState"].str.lower().isin(self.config.grid.western_states)]
        
        # Process fuel and landowner data
        gdf = self._process_fuel_data(gdf)
        gdf = self._process_landowner_data(gdf)
        
        # Add time information
        gdf = self._process_time_data(gdf)
        
        # Classify fire intensity
        gdf = self._classify_fire_intensity(gdf)
        
        return gdf
    
    def validate(self, data: gpd.GeoDataFrame) -> bool:
        """Validate wildfire data"""
        return len(data) > 0 and "geometry" in data.columns

class DataService:
    """Central service for managing all data loading"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.loaders = {
            "buses": BusDataLoader(config),
            "wildfire": WildfireDataLoader(config),
            # Add more loaders as needed
        }
        self._cache = {}
        
    async def load_all_data(self) -> Dict[str, DataLoadResult]:
        """Load all required data concurrently"""
        tasks = {
            name: loader.load() 
            for name, loader in self.loaders.items()
        }
        
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        return {
            name: result if not isinstance(result, Exception) 
                         else DataLoadResult(success=False, error_message=str(result))
            for name, result in zip(tasks.keys(), results)
        }
    
    async def get_data(self, data_type: str, force_reload: bool = False) -> DataLoadResult:
        """Get specific data type with caching"""
        if not force_reload and data_type in self._cache:
            return self._cache[data_type]
        
        if data_type not in self.loaders:
            return DataLoadResult(
                success=False,
                error_message=f"Unknown data type: {data_type}"
            )
        
        result = await self.loaders[data_type].load()
        if result.success:
            self._cache[data_type] = result
        
        return result