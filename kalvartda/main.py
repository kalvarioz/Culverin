from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.staticfiles import StaticFiles
import asyncio
import uuid
from typing import Dict, Optional
from services.data_service import DataService
from services.tda_service import TDAService  
from services.cascade_service import CascadeService
from services.orchestrator import AnalysisOrchestrator
from models.analysis_models import AnalysisRequest, AnalysisSession

app = FastAPI(title="Wildfire Grid Resilience Platform")

# Global service instances
data_service = DataService()
tda_service = TDAService()
cascade_service = CascadeService()
orchestrator = AnalysisOrchestrator(data_service, cascade_service, tda_service)

# Active analysis sessions
sessions: Dict[str, AnalysisSession] = {}

@app.websocket("/ws/analysis/{session_id}")
async def analysis_websocket(websocket: WebSocket, session_id: str):
    """Main WebSocket for coordinating complete analysis workflow"""
    await websocket.accept()
    
    if session_id not in sessions:
        sessions[session_id] = AnalysisSession(session_id)
    
    session = sessions[session_id]
    
    # Register session for progress updates
    orchestrator.register_session(session_id, websocket)
    
    try:
        while True:
            message = await websocket.receive_json()
            await handle_analysis_message(session, message)
    except:
        orchestrator.unregister_session(session_id)

async def handle_analysis_message(session: AnalysisSession, message: Dict):
    """Route messages to appropriate service"""
    action = message.get("action")
    
    if action == "start_full_analysis":
        # Start complete workflow: Data → Cascade → TDA
        await orchestrator.run_complete_analysis(
            session.id, 
            message.get("config", {})
        )
    elif action == "start_cascade_only":
        # Just cascade analysis
        await orchestrator.run_cascade_analysis(
            session.id,
            message.get("fire_data"),
            message.get("config", {})
        )
    elif action == "start_tda_only":
        # TDA analysis from existing cascade results
        await orchestrator.run_tda_analysis(
            session.id,
            message.get("cascade_results"),
            message.get("config", {})
        )

@app.get("/api/system/health")
async def system_health():
    """Check health of all components"""
    health = {}
    
    # Check data service
    health["data_service"] = await data_service.health_check()
    
    # Check TDA engine
    health["tda_engine"] = await tda_service.health_check()
    
    # Check cascade engine  
    health["cascade_engine"] = await cascade_service.health_check()
    
    # Check overall system
    health["overall"] = all(h["status"] == "healthy" for h in health.values())
    
    return health

# Mount React frontend
app.mount("/", StaticFiles(directory="frontend/build", html=True), name="static")