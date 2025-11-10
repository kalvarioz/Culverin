import asyncio
import time
import pytest
from pathlib import Path
import numpy as np
from analysis.cached_workflow import CachedTDAWorkflow
from config.settings import TDAConfig

class PerformanceBenchmark:
    def __init__(self):
        self.config = TDAConfig()
        self.results = []
    
    async def benchmark_matrix_generation(self, bus_counts: list):
        """Benchmark matrix generation across different grid sizes"""
        
        for n_buses in bus_counts:
            # Generate synthetic bus data
            bus_data = self._generate_synthetic_buses(n_buses)
            
            start_time = time.time()
            
            # Call Rust engine
            import tda_engine
            engine = tda_engine.create_engine(bus_data, (2.0, 20, 30.0))
            engine.generate_power_matrix()
            
            end_time = time.time()
            
            self.results.append({
                'operation': 'matrix_generation',
                'n_buses': n_buses,
                'time_seconds': end_time - start_time,
                'memory_mb': self._get_memory_usage()
            })
            
            print(f"Matrix generation for {n_buses} buses: {end_time - start_time:.2f}s")
    
    def _generate_synthetic_buses(self, n: int) -> list:
        """Generate synthetic bus data for testing"""
        np.random.seed(42)
        
        return [
            (
                i,  # bus_i
                -120.0 + np.random.random() * 10,  # longitude
                35.0 + np.random.random() * 10,    # latitude
                np.random.random() * 100,          # total_gen
                np.random.random() * 80,           # load_mw
                0.95 + np.random.random() * 0.1,   # vm
                138.0,                             # base_kv
                "Load",                            # bus_type
                1                                  # zone
            )
            for i in range(n)
        ]
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        import psutil
        import os
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024

# Run benchmarks
if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    asyncio.run(benchmark.benchmark_matrix_generation([100, 500, 1000, 2000, 5000]))