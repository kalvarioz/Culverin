import hashlib
from .workflow import TDAWorkflow
from database.cache import AnalysisCache
from database.models import AnalysisRun
from sqlalchemy.orm import Session

class CachedTDAWorkflow(TDAWorkflow):
    def __init__(self, config: TDAConfig, db_session: Session):
        super().__init__(config)
        self.cache = AnalysisCache()
        self.db = db_session
    
    async def run_full_analysis(self, fire_data_path: Path) -> AnalysisResult:
        """Analysis with intelligent caching"""
        
        # Generate cache keys
        fire_hash = self._hash_file(fire_data_path)
        config_dict = self.config.dict()
        
        # Check for cached result
        cached_result = self.cache.get_analysis_result(fire_hash, config_dict)
        if cached_result:
            logger.info("Using cached analysis result")
            return AnalysisResult(**cached_result)
        
        # Check database for similar analysis
        similar_run = self._find_similar_analysis(fire_hash, config_dict)
        if similar_run and similar_run.status == "completed":
            logger.info("Using database cached result")
            return self._analysis_run_to_result(similar_run)
        
        # Run new analysis
        result = await super().run_full_analysis(fire_data_path)
        
        # Cache the result
        if result.success:
            self.cache.set_analysis_result(fire_hash, config_dict, result.__dict__)
            self._save_analysis_run(fire_hash, config_dict, result)
        
        return result
    
    def _hash_file(self, file_path: Path) -> str:
        """Generate hash of file content"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _find_similar_analysis(self, fire_hash: str, config: dict) -> Optional[AnalysisRun]:
        """Find similar analysis in database"""
        config_hash = hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()
        
        return self.db.query(AnalysisRun).filter(
            AnalysisRun.config_hash == config_hash,
            AnalysisRun.status == "completed"
        ).first()
    
    def _save_analysis_run(self, fire_hash: str, config: dict, result: AnalysisResult) -> None:
        """Save analysis run to database"""
        config_hash = hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()
        
        run = AnalysisRun(
            fire_name=result.fire_name,
            config_hash=config_hash,
            status="completed" if result.success else "failed",
            analysis_radius_km=config.get('analysis_radius_km'),
            fire_buffer_km=config.get('fire_buffer_km'),
            simulation_steps=config.get('simulation_steps'),
            wasserstein_distance=result.wasserstein_distance,
            before_features_count=result.before_features,
            after_features_count=result.after_features,
            execution_time_seconds=result.execution_time,
            error_message=result.error_message
        )
        
        self.db.add(run)
        self.db.commit()