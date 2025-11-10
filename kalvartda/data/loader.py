import polars as pl
import geopandas as gpd
from shapely.geometry import Point, Polygon
from typing import List, Tuple, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self, config: DataConfig):
        self.config = config
        self.data_dir = Path(config.data_dir)
        
    def load_bus_data(self) -> pl.DataFrame:
        """Load and validate bus data with enhanced error handling"""
        bus_file = self.data_dir / self.config.bus_data_file
        
        if not bus_file.exists():
            raise FileNotFoundError(f"Bus data file not found: {bus_file}")
        
        try:
            # Use Polars for faster loading
            df = pl.read_csv(bus_file)
            
            # Validate required columns
            required_cols = ['bus_i', 'longitude', 'latitude']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                logger.warning(f"Missing columns: {missing_cols}")
                # Attempt column detection
                df = self._detect_and_fix_columns(df)
            
            # Clean and validate data
            df = df.filter(
                pl.col("longitude").is_not_null() & 
                pl.col("latitude").is_not_null() &
                pl.col("bus_i").is_not_null()
            )
            
            logger.info(f"Loaded {df.height} buses with {df.width} attributes")
            return df
            
        except Exception as e:
            logger.error(f"Error loading bus data: {e}")
            raise
    
    def _detect_and_fix_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        """Intelligent column detection and renaming"""
        column_mapping = {}
        
        # Common patterns for column names
        patterns = {
            'bus_i': ['busnum', 'bus_id', 'bus_number', 'id'],
            'longitude': ['lon', 'lng', 'x', 'coord_x'],
            'latitude': ['lat', 'y', 'coord_y'],
            'total_gen': ['generation', 'gen_mw', 'gen'],
            'load_mw': ['load', 'demand', 'load_mw']
        }
        
        for target_col, candidates in patterns.items():
            for col in df.columns:
                if col.lower() in candidates:
                    column_mapping[col] = target_col
                    break
        
        if column_mapping:
            df = df.rename(column_mapping)
            logger.info(f"Renamed columns: {column_mapping}")
        
        return df
    
    def create_spatial_dataframe(self, df: pl.DataFrame) -> gpd.GeoDataFrame:
        """Convert to spatial dataframe for geographic operations"""
        # Convert to pandas for geopandas compatibility
        pdf = df.to_pandas()
        
        # Create geometry column
        geometry = [Point(xy) for xy in zip(pdf.longitude, pdf.latitude)]
        gdf = gpd.GeoDataFrame(pdf, geometry=geometry, crs='EPSG:4326')
        
        return gdf
    
    def load_fire_data(self, fire_file: Path) -> gpd.GeoDataFrame:
        """Load wildfire data from shapefile or geojson"""
        if fire_file.suffix.lower() == '.shp':
            return gpd.read_file(fire_file)
        elif fire_file.suffix.lower() in ['.geojson', '.json']:
            return gpd.read_file(fire_file)
        else:
            raise ValueError(f"Unsupported fire data format: {fire_file.suffix}")