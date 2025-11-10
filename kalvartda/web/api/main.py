from fastapi import FastAPI, WebSocket, BackgroundTasks, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio
from typing import Dict, List, Optional
from services.wildfire_service import WildfireService
from services.cascade_orchestrator import CascadeOrchestrator
from services.tda_service import TDAService
from services.map_service import MapService

app = FastAPI(title="Wildfire Grid Resilience API")

# Services
wildfire_service = WildfireService()
cascade_orchestrator = CascadeOrchestrator() 
tda_service = TDAService()
map_service = MapService()

# Active analysis sessions
active_sessions: Dict[str, Dict] = {}

@app.websocket("/ws/session/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Main WebSocket for real-time application state"""
    await websocket.accept()
    
    if session_id not in active_sessions:
        active_sessions[session_id] = {
            "selected_fire": None,
            "filters": {},
            "cascade_results": None,
            "tda_results": None,
            "progress": {"status": "ready", "percent": 0}
        }
    
    session = active_sessions[session_id]
    
    try:
        while True:
            message = await websocket.receive_json()
            await handle_websocket_message(websocket, session_id, message)
    except:
        # Client disconnected
        pass

async def handle_websocket_message(websocket: WebSocket, session_id: str, message: Dict):
    """Handle real-time messages from client"""
    action = message.get("action")
    session = active_sessions[session_id]
    
    if action == "select_fire":
        fire_id = message.get("fire_id")
        session["selected_fire"] = await wildfire_service.get_fire_data(fire_id)
        await websocket.send_json({
            "type": "fire_selected",
            "data": session["selected_fire"]
        })
    
    elif action == "update_filters":
        session["filters"] = message.get("filters", {})
        filtered_fires = await wildfire_service.get_filtered_fires(session["filters"])
        await websocket.send_json({
            "type": "fires_filtered", 
            "data": filtered_fires
        })
    
    elif action == "start_cascade":
        config = message.get("config", {})
        await start_cascade_analysis(websocket, session_id, config)
    
    elif action == "start_tda":
        if session["cascade_results"]:
            await start_tda_analysis(websocket, session_id)

@app.get("/api/map/initial-data")
async def get_initial_map_data():
    """Load initial map data (buses, states, base fire data)"""
    return {
        "buses": await map_service.get_bus_data(),
        "states": await map_service.get_state_boundaries(),
        "fire_summary": await wildfire_service.get_fire_summary()
    }

@app.get("/api/fires/search")
async def search_fires(
    state: Optional[str] = None,
    intensity: Optional[str] = None,
    fuel_type: Optional[str] = None,
    landowner: Optional[str] = None
):
    """Search and filter fire data"""
    filters = {k: v for k, v in {
        "state": state,
        "intensity": intensity, 
        "fuel_type": fuel_type,
        "landowner": landowner
    }.items() if v is not None}
    
    return await wildfire_service.get_filtered_fires(filters)

@app.post("/api/cascade/start/{session_id}")
async def start_cascade_api(
    session_id: str,
    config: Dict,
    background_tasks: BackgroundTasks
):
    """Start cascade analysis"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    if not session["selected_fire"]:
        raise HTTPException(status_code=400, detail="No fire selected")
    
    background_tasks.add_task(
        run_cascade_background,
        session_id,
        session["selected_fire"],
        config
    )
    
    return {"status": "started", "session_id": session_id}

async def start_cascade_analysis(websocket: WebSocket, session_id: str, config: Dict):
    """Start cascade analysis with real-time updates"""
    session = active_sessions[session_id]
    
    # Progress callback
    def progress_callback(progress):
        try:
            asyncio.create_task(websocket.send_json({
                "type": "cascade_progress",
                "data": progress
            }))
        except:
            pass  # WebSocket might be closed
    
    cascade_orchestrator.subscribe_to_progress(progress_callback)
    
    try:
        result = await cascade_orchestrator.run_cascade_analysis(
            session["selected_fire"],
            config
        )
        
        session["cascade_results"] = result
        
        await websocket.send_json({
            "type": "cascade_complete",
            "data": result
        })
        
    except Exception as e:
        await websocket.send_json({
            "type": "cascade_error",
            "error": str(e)
        })

async def start_tda_analysis(websocket: WebSocket, session_id: str):
    """Start TDA analysis using cascade results"""
    session = active_sessions[session_id]
    cascade_results = session["cascade_results"]
    
    def tda_progress_callback(progress):
        try:
            asyncio.create_task(websocket.send_json({
                "type": "tda_progress", 
                "data": progress
            }))
        except:
            pass
    
    try:
        tda_result = await tda_service.run_tda_analysis(
            cascade_results,
            progress_callback
        )
        
        session["tda_results"] = tda_result
        
        await websocket.send_json({
            "type": "tda_complete",
            "data": tda_result
        })
        
    except Exception as e:
        await websocket.send_json({
            "type": "tda_error",
            "error": str(e)
        })

@app.get("/api/download/results/{session_id}")
async def download_results(session_id: str):
    """Download complete analysis results"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    # Generate results file
    results_path = await generate_results_file(
        session["cascade_results"],
        session["tda_results"]
    )
    
    return FileResponse(
        results_path,
        filename=f"wildfire_analysis_{session_id}.zip"
    )

# Mount static files for React frontend
app.mount("/", StaticFiles(directory="frontend/build", html=True), name="static")