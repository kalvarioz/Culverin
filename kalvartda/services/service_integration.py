from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
import asyncio

class ServiceInterface(ABC):
    """Common interface for all services"""
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        pass
    
    @abstractmethod
    async def cleanup(self) -> bool:
        pass

class IntegratedTDAService(ServiceInterface):
    """TDA Service with integration capabilities"""
    
    def __init__(self):
        self.rust_engine = None
        self.ready = False
    
    async def initialize(self) -> bool:
        """Initialize TDA engine and verify connectivity"""
        try:
            # Import and initialize Rust TDA engine
            import tda_engine
            self.rust_engine = tda_engine
            
            # Test basic functionality
            test_result = await self.run_basic_test()
            self.ready = test_result
            
            return self.ready
        except Exception as e:
            logger.error(f"TDA service initialization failed: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        if not self.ready:
            return {"status": "unhealthy", "error": "Service not initialized"}
        
        try:
            # Test Rust engine connectivity
            test_matrix = [[0, 1], [1, 0]]
            result = self.rust_engine.test_perseus_analysis(test_matrix)
            
            return {
                "status": "healthy",
                "engine": "rust",
                "version": getattr(self.rust_engine, "__version__", "unknown")
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def run_complete_tda_workflow(self, cascade_results: Dict, config: Dict, 
                                      progress_callback: Optional[Callable] = None) -> Dict:
        """Run complete TDA workflow integrated with cascade results"""
        
        if progress_callback:
            await progress_callback(10)
        
        # Extract matrices from cascade results
        before_matrix = await self._extract_before_matrix(cascade_results)
        after_matrix = await self._extract_after_matrix(cascade_results)
        
        if progress_callback:
            await progress_callback(30)
        
        # Run Perseus analysis on both matrices
        before_features = await self._run_perseus_analysis(before_matrix)
        after_features = await self._run_perseus_analysis(after_matrix)
        
        if progress_callback:
            await progress_callback(70)
        
        # Calculate Wasserstein distance
        wasserstein_distance = await self._calculate_wasserstein_distance(
            before_features, after_features
        )
        
        # Generate visualizations
        plots = await self._generate_tda_visualizations(
            before_features, after_features, wasserstein_distance
        )
        
        if progress_callback:
            await progress_callback(100)
        
        return {
            "success": True,
            "before_features": before_features,
            "after_features": after_features,
            "wasserstein_distance": wasserstein_distance,
            "feature_counts": {
                "before": len(before_features),
                "after": len(after_features)
            },
            "visualizations": plots,
            "before_matrix_path": before_matrix.get("file_path"),
            "after_matrix_path": after_matrix.get("file_path")
        }

class IntegratedCascadeService(ServiceInterface):
    """Cascade Service with integration capabilities"""
    
    def __init__(self):
        self.rust_engine = None
        self.ready = False
    
    async def initialize(self) -> bool:
        try:
            import cascade_engine
            self.rust_engine = cascade_engine
            self.ready = True
            return True
        except Exception as e:
            logger.error(f"Cascade service initialization failed: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        if not self.ready:
            return {"status": "unhealthy", "error": "Service not initialized"}
        
        try:
            # Test basic cascade functionality
            test_buses = [(1, -120.0, 35.0, "Load", 0.0, 10.0)]
            test_edges = [(1, 2, 1.0)]
            engine = self.rust_engine.create_cascade_engine(test_buses, test_edges)
            
            return {"status": "healthy", "engine": "rust"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def run_enhanced_cascade(self, grid_data: Dict, fire_data: Dict, config: Dict,
                                 progress_callback: Optional[Callable] = None) -> Dict:
        """Run enhanced cascade analysis integrated with other services"""
        
        # Initialize cascade engine with grid data
        engine = await self._create_cascade_engine(grid_data)
        
        if progress_callback:
            await progress_callback(10)
        
        # Process fire impact timeline
        fire_timeline = await self._process_fire_timeline(fire_data)
        
        if progress_callback:
            await progress_callback(25)
        
        # Run cascade simulation
        cascade_steps = []
        total_steps = len(fire_timeline)
        
        for i, fire_step in enumerate(fire_timeline):
            step_result = await self._run_cascade_step(engine, fire_step, i + 1)
            cascade_steps.append(step_result)
            
            if progress_callback:
                progress = 25 + (i + 1) / total_steps * 65
                await progress_callback(progress)
        
        # Compile final results
        final_results = {
            "success": True,
            "cascade_steps": cascade_steps,
            "final_grid_size": cascade_steps[-1]["vertices_remaining"] if cascade_steps else 0,
            "total_buses_affected": sum(len(step["fire_affected"]) for step in cascade_steps),
            "cascade_amplification": self._calculate_cascade_amplification(cascade_steps),
            "execution_metadata": {
                "total_steps": total_steps,
                "config": config
            }
        }
        
        if progress_callback:
            await progress_callback(100)
        
        return {"success": True, "data": final_results}

class IntegratedDataService(ServiceInterface):
    """Data Service with caching and integration capabilities"""
    
    def __init__(self):
        self.cache = None
        self.db = None
        self.ready = False
    
    async def initialize(self) -> bool:
        try:
            # Initialize database and cache connections
            await self._setup_database()
            await self._setup_cache()
            self.ready = True
            return True
        except Exception as e:
            logger.error(f"Data service initialization failed: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        if not self.ready:
            return {"status": "unhealthy", "error": "Service not initialized"}
        
        try:
            # Test database connectivity
            db_status = await self._test_database()
            cache_status = await self._test_cache()
            
            return {
                "status": "healthy" if db_status and cache_status else "degraded",
                "database": "connected" if db_status else "error",
                "cache": "connected" if cache_status else "error"
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_complete_grid_data(self) -> Dict:
        """Get complete grid dataset with caching"""
        cache_key = "complete_grid_data"
        
        # Try cache first
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return {"success": True, "data": cached_data, "source": "cache"}
        
        # Load from database
        grid_data = await self._load_complete_grid_from_db()
        
        # Cache for future use
        await self.cache.set(cache_key, grid_data, ttl=3600)  # 1 hour TTL
        
        return {"success": True, "data": grid_data, "source": "database"}