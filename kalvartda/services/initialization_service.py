import asyncio
from typing import Dict, Any, Optional
import logging
from dataclasses import dataclass
from .data_service import DataService
from .cache_service import CacheService

logger = logging.getLogger(__name__)

@dataclass
class InitializationStatus:
    complete: bool = False
    progress: float = 0.0
    current_task: str = ""
    errors: list = None
    data_status: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.data_status is None:
            self.data_status = {}

class InitializationService:
    """Manages async system initialization"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.data_service = DataService(config)
        self.cache_service = CacheService(config)
        self.status = InitializationStatus()
        self._subscribers = []
    
    def subscribe_to_progress(self, callback):
        """Subscribe to initialization progress updates"""
        self._subscribers.append(callback)
    
    def _notify_progress(self, progress: float, task: str):
        """Notify subscribers of progress"""
        self.status.progress = progress
        self.status.current_task = task
        
        for callback in self._subscribers:
            try:
                callback(self.status)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    async def initialize_system(self) -> InitializationStatus:
        """Initialize the entire system asynchronously"""
        try:
            self._notify_progress(0.0, "Starting initialization...")
            
            # Step 1: Check cache (10%)
            self._notify_progress(0.1, "Checking cache...")
            cache_valid = await self.cache_service.validate_cache()
            
            if cache_valid:
                self._notify_progress(0.5, "Loading from cache...")
                data_results = await self.cache_service.load_from_cache()
            else:
                # Step 2: Create directories (20%)
                self._notify_progress(0.2, "Creating directories...")
                await self._create_directories()
                
                # Step 3: Load data (20-80%)
                self._notify_progress(0.3, "Loading electrical grid data...")
                data_results = await self.data_service.load_all_data()
                
                # Step 4: Cache results (80-90%)
                self._notify_progress(0.8, "Caching processed data...")
                await self.cache_service.save_to_cache(data_results)
            
            # Step 5: Initialize TDA baseline (90-95%)
            self._notify_progress(0.9, "Initializing TDA baseline...")
            await self._initialize_tda_baseline()
            
            # Step 6: Create color palettes (95-100%)
            self._notify_progress(0.95, "Creating visualization palettes...")
            await self._create_color_palettes()
            
            # Final validation
            self.status.data_status = {
                name: result.success for name, result in data_results.items()
            }
            
            all_success = all(self.status.data_status.values())
            
            self.status.complete = all_success
            self.status.progress = 1.0
            self.status.current_task = "Initialization complete" if all_success else "Initialization completed with errors"
            
            if not all_success:
                self.status.errors.extend([
                    f"{name}: {result.error_message}" 
                    for name, result in data_results.items() 
                    if not result.success
                ])
            
            return self.status
            
        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            self.status.complete = False
            self.status.errors.append(str(e))
            self.status.current_task = f"Initialization failed: {e}"
            return self.status
    
    async def _create_directories(self):
        """Create required directories"""
        directories = [
            self.config.output.outputs_dir,
            self.config.output.attacked_dir,
            self.config.output.diagnostic_dir,
            self.config.database.cache_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    async def _initialize_tda_baseline(self):
        """Initialize the TDA baseline matrix"""
        # This would call your Rust TDA engine
        pass
    
    async def _create_color_palettes(self):
        """Create visualization color palettes"""
        # Port your color palette creation
        pass