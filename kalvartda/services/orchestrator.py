import asyncio
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
import time
import json

logger = logging.getLogger(__name__)

@dataclass
class AnalysisProgress:
    session_id: str
    stage: str  # "data_loading", "cascade", "tda", "complete"
    progress_percent: float
    current_task: str
    start_time: float
    errors: list
    intermediate_results: Dict[str, Any]

class AnalysisOrchestrator:
    """Coordinates the complete analysis workflow across all services"""
    
    def __init__(self, data_service, cascade_service, tda_service):
        self.data_service = data_service
        self.cascade_service = cascade_service
        self.tda_service = tda_service
        self.active_sessions: Dict[str, Dict] = {}
        self.websockets: Dict[str, Any] = {}
    
    def register_session(self, session_id: str, websocket):
        """Register a WebSocket for progress updates"""
        self.websockets[session_id] = websocket
        self.active_sessions[session_id] = {
            "start_time": time.time(),
            "stage": "idle",
            "progress": 0.0
        }
    
    def unregister_session(self, session_id: str):
        """Clean up session resources"""
        self.websockets.pop(session_id, None)
        self.active_sessions.pop(session_id, None)
    
    async def _notify_progress(self, session_id: str, stage: str, progress: float, task: str, **kwargs):
        """Send progress update to client"""
        if session_id not in self.websockets:
            return
            
        session = self.active_sessions[session_id]
        session.update({
            "stage": stage,
            "progress": progress,
            "current_task": task
        })
        
        update = {
            "type": "progress",
            "session_id": session_id,
            "stage": stage,
            "progress": progress,
            "current_task": task,
            **kwargs
        }
        
        try:
            await self.websockets[session_id].send_text(json.dumps(update))
        except:
            logger.warning(f"Failed to send progress to session {session_id}")
    
    async def run_complete_analysis(self, session_id: str, config: Dict[str, Any]) -> Dict:
        """Run the complete end-to-end analysis workflow"""
        try:
            await self._notify_progress(session_id, "initializing", 5, "Starting analysis pipeline...")
            
            # Stage 1: Data Loading & Preparation (5-15%)
            await self._notify_progress(session_id, "data_loading", 10, "Loading electrical grid data...")
            
            grid_data = await self.data_service.get_complete_grid_data()
            if not grid_data.success:
                raise Exception(f"Data loading failed: {grid_data.error_message}")
            
            fire_data = await self.data_service.get_fire_data(config.get("fire_id"))
            if not fire_data.success:
                raise Exception(f"Fire data loading failed: {fire_data.error_message}")
            
            # Stage 2: Cascade Analysis (15-60%)
            await self._notify_progress(session_id, "cascade", 20, "Running cascade simulation...")
            
            cascade_results = await self.cascade_service.run_enhanced_cascade(
                grid_data=grid_data.data,
                fire_data=fire_data.data,
                config=config.get("cascade", {}),
                progress_callback=lambda p: asyncio.create_task(
                    self._notify_progress(session_id, "cascade", 20 + p * 0.4, f"Cascade step {p}")
                )
            )
            
            if not cascade_results.success:
                raise Exception(f"Cascade analysis failed: {cascade_results.error}")
            
            # Stage 3: TDA Analysis (60-95%)
            await self._notify_progress(session_id, "tda", 65, "Generating TDA matrices...")
            
            tda_results = await self.tda_service.run_complete_tda_workflow(
                cascade_results=cascade_results.data,
                config=config.get("tda", {}),
                progress_callback=lambda p: asyncio.create_task(
                    self._notify_progress(session_id, "tda", 65 + p * 0.3, f"TDA analysis: {p}%")
                )
            )
            
            if not tda_results.success:
                raise Exception(f"TDA analysis failed: {tda_results.error}")
            
            # Stage 4: Results Compilation (95-100%)
            await self._notify_progress(session_id, "finalizing", 95, "Compiling final results...")
            
            final_results = await self._compile_final_results(
                session_id, grid_data.data, fire_data.data, 
                cascade_results.data, tda_results.data
            )
            
            await self._notify_progress(session_id, "complete", 100, "Analysis complete!", 
                                      results=final_results)
            
            return final_results
            
        except Exception as e:
            logger.error(f"Analysis failed for session {session_id}: {e}")
            await self._notify_progress(session_id, "error", 0, f"Analysis failed: {e}")
            raise
    
    async def _compile_final_results(self, session_id: str, grid_data: Dict, fire_data: Dict,
                                   cascade_results: Dict, tda_results: Dict) -> Dict:
        """Compile all results into final comprehensive analysis"""
        
        # Calculate summary metrics
        total_buses = len(grid_data.get("buses", []))
        total_affected = sum(len(step.get("fire_affected", [])) for step in cascade_results.get("cascade_steps", []))
        cascade_amplification = cascade_results.get("cascade_amplification", 0)
        wasserstein_distance = tda_results.get("wasserstein_distance", 0)
        
        final_results = {
            "session_id": session_id,
            "analysis_timestamp": time.time(),
            "fire_information": {
                "name": fire_data.get("attr_IncidentName", "Unknown"),
                "state": fire_data.get("attr_POOState", "Unknown"), 
                "intensity": fire_data.get("fire_intensity", "Unknown"),
                "area_acres": fire_data.get("fire_acres", 0)
            },
            "grid_information": {
                "total_buses": total_buses,
                "total_edges": len(grid_data.get("edges", [])),
                "generator_buses": len([b for b in grid_data.get("buses", []) if b.get("total_gen", 0) > 0])
            },
            "cascade_analysis": cascade_results,
            "tda_analysis": tda_results,
            "summary_metrics": {
                "total_buses_affected": total_affected,
                "cascade_amplification": cascade_amplification,
                "topological_distance": wasserstein_distance,
                "final_grid_size": cascade_results.get("final_grid_size", total_buses),
                "resilience_score": self._calculate_resilience_score(
                    total_affected, total_buses, wasserstein_distance
                )
            },
            "downloadable_assets": await self._generate_downloadable_assets(
                session_id, cascade_results, tda_results
            )
        }
        
        # Store results for later retrieval
        await self.data_service.store_analysis_results(session_id, final_results)
        
        return final_results
    
    def _calculate_resilience_score(self, affected: int, total: int, topo_distance: float) -> float:
        """Calculate overall grid resilience score (0-100)"""
        if total == 0:
            return 0
        
        # Combine multiple factors into resilience score
        survival_rate = (total - affected) / total
        topo_impact = min(1.0, topo_distance / 0.1)  # Normalize topological change
        
        resilience_score = (survival_rate * 0.7 + (1 - topo_impact) * 0.3) * 100
        return max(0, min(100, resilience_score))
    
    async def _generate_downloadable_assets(self, session_id: str, cascade_results: Dict, 
                                          tda_results: Dict) -> Dict[str, str]:
        """Generate downloadable files and return their paths"""
        assets = {}
        
        try:
            # Generate cascade data CSV
            assets["cascade_data"] = await self.data_service.export_cascade_data(
                session_id, cascade_results
            )
            
            # Generate TDA matrices
            assets["before_matrix"] = tda_results.get("before_matrix_path")
            assets["after_matrix"] = tda_results.get("after_matrix_path")
            
            # Generate summary report
            assets["summary_report"] = await self.data_service.generate_summary_report(
                session_id, cascade_results, tda_results
            )
            
            # Generate visualizations
            assets["plots_package"] = await self.tda_service.export_visualizations(
                session_id, tda_results
            )
            
        except Exception as e:
            logger.warning(f"Failed to generate some downloadable assets: {e}")
        
        return assets