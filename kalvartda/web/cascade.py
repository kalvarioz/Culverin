from fastapi import FastAPI, WebSocket, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
import asyncio
import json
from typing import Dict, Any
import uuid
from services.cascade_orchestrator import CascadeOrchestrator, CascadeConfig
from services.data_service import DataService

app = FastAPI()

# Global orchestrators for different analyses
orchestrators: Dict[str, CascadeOrchestrator] = {}

@app.post("/api/cascade/start")
async def start_cascade_analysis(
    config: Dict[str, Any],
    fire_data_id: str,
    background_tasks: BackgroundTasks
):
    """Start cascade analysis"""
    analysis_id = str(uuid.uuid4())
    
    # Create orchestrator
    orchestrator = CascadeOrchestrator()
    orchestrators[analysis_id] = orchestrator
    
    # Start background task
    background_tasks.add_task(
        run_cascade_background,
        analysis_id,
        config,
        fire_data_id
    )
    
    return {"analysis_id": analysis_id, "status": "started"}

async def run_cascade_background(
    analysis_id: str,
    config: Dict[str, Any],
    fire_data_id: str
):
    """Background task for cascade analysis"""
    try:
        orchestrator = orchestrators[analysis_id]
        data_service = DataService()
        
        # Load required data
        fire_data = await data_service.get_data("wildfire", fire_data_id)
        buses_data = await data_service.get_data("buses")
        graph_data = await data_service.get_data("graph")
        
        # Configure analysis
        cascade_config = CascadeConfig(**config)
        
        # Run analysis
        result = await orchestrator.run_cascade_analysis(
            fire_data.data,
            buses_data.data,
            graph_data.data,
            cascade_config
        )
        
        # Store result
        orchestrator.result = result
        
    except Exception as e:
        orchestrator.progress.status = "failed"
        orchestrator.progress.errors.append(str(e))

@app.websocket("/ws/cascade/{analysis_id}/progress")
async def cascade_progress_websocket(websocket: WebSocket, analysis_id: str):
    """WebSocket for real-time progress updates"""
    await websocket.accept()
    
    if analysis_id not in orchestrators:
        await websocket.close(code=4004, reason="Analysis not found")
        return
    
    orchestrator = orchestrators[analysis_id]
    
    def progress_callback(progress):
        try:
            asyncio.create_task(
                websocket.send_text(json.dumps(asdict(progress)))
            )
        except:
            pass  # Connection might be closed
    
    orchestrator.subscribe_to_progress(progress_callback)
    
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except:
        pass  # Client disconnected

@app.get("/api/cascade/{analysis_id}/status")
async def get_cascade_status(analysis_id: str):
    """Get cascade analysis status"""
    if analysis_id not in orchestrators:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    orchestrator = orchestrators[analysis_id]
    status = orchestrator.get_progress()
    
    # Add result if completed
    if hasattr(orchestrator, 'result'):
        status['result'] = orchestrator.result
    
    return status

@app.get("/api/cascade/{analysis_id}/result")
async def get_cascade_result(analysis_id: str):
    """Get cascade analysis result"""
    if analysis_id not in orchestrators:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    orchestrator = orchestrators[analysis_id]
    
    if not hasattr(orchestrator, 'result'):
        raise HTTPException(status_code=404, detail="Result not available")
    
    return orchestrator.result

@app.get("/api/cascade/{analysis_id}/matrix/{matrix_type}")
async def download_matrix(analysis_id: str, matrix_type: str):
    """Download before/after matrix files"""
    if analysis_id not in orchestrators:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    orchestrator = orchestrators[analysis_id]
    
    if not hasattr(orchestrator, 'result'):
        raise HTTPException(status_code=404, detail="Result not available")
    
    if matrix_type == "before":
        file_path = orchestrator.result.before_matrix
    elif matrix_type == "after":
        file_path = orchestrator.result.after_matrix
    else:
        raise HTTPException(status_code=400, detail="Invalid matrix type")
    
    if not file_path:
        raise HTTPException(status_code=404, detail="Matrix not generated")
    
    return FileResponse(file_path, filename=f"{matrix_type}_cascade_matrix.csv")