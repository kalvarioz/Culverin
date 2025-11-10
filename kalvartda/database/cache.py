import redis
import pickle
import hashlib
from typing import Optional, Any
import json

class AnalysisCache:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_client = redis.from_url(redis_url)
        self.default_ttl = 3600 * 24 * 7  # 1 week
    
    def _make_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key from parameters"""
        # Sort parameters for consistent hashing
        sorted_params = sorted(kwargs.items())
        param_str = json.dumps(sorted_params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        return f"{prefix}:{param_hash}"
    
    def get_matrix(self, bus_ids: list, config: dict) -> Optional[Any]:
        """Get cached power matrix"""
        key = self._make_key("matrix", bus_ids=sorted(bus_ids), **config)
        cached = self.redis_client.get(key)
        if cached:
            return pickle.loads(cached)
        return None
    
    def set_matrix(self, bus_ids: list, config: dict, matrix: Any) -> None:
        """Cache power matrix"""
        key = self._make_key("matrix", bus_ids=sorted(bus_ids), **config)
        self.redis_client.setex(key, self.default_ttl, pickle.dumps(matrix))
    
    def get_perseus_result(self, matrix_hash: str, perseus_config: dict) -> Optional[list]:
        """Get cached Perseus analysis result"""
        key = self._make_key("perseus", matrix_hash=matrix_hash, **perseus_config)
        cached = self.redis_client.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    def set_perseus_result(self, matrix_hash: str, perseus_config: dict, features: list) -> None:
        """Cache Perseus analysis result"""
        key = self._make_key("perseus", matrix_hash=matrix_hash, **perseus_config)
        self.redis_client.setex(key, self.default_ttl, json.dumps(features))
    
    def get_analysis_result(self, fire_data_hash: str, config: dict) -> Optional[dict]:
        """Get cached full analysis result"""
        key = self._make_key("analysis", fire_hash=fire_data_hash, **config)
        cached = self.redis_client.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    def set_analysis_result(self, fire_data_hash: str, config: dict, result: dict) -> None:
        """Cache full analysis result"""
        key = self._make_key("analysis", fire_hash=fire_data_hash, **config)
        # Longer TTL for complete analyses
        self.redis_client.setex(key, self.default_ttl * 4, json.dumps(result))