from fastapi import FastAPI, WebSocket, BackgroundTasks
from typing import Dict, Any
import asyncio
import json
from services.initialization_service import InitializationService
from config.core_config import AppConfig

app = FastAPI()
config = AppConfig.load_from_env()

# Global initialization service
init_service = InitializationService(config)
initialization_task = None

@app.websocket("/ws/initialization")
async def initialization_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time initialization progress"""
    await websocket.accept()
    
    def progress_callback(status):
        try:
            asyncio.create_task(websocket.send_text(json.dumps({
                "progress": status.progress,
                "current_task": status.current_task,
                "complete": status.complete,
                "errors": status.errors
            })))
        except:
            pass  # Connection might be closed
    
    init_service.subscribe_to_progress(progress_callback)
    
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except:
        pass  # Client disconnected

@app.post("/api/initialize")
async def start_initialization(background_tasks: BackgroundTasks):
    """Start system initialization"""
    global initialization_task
    
    if initialization_task and not initialization_task.done():
        return {"status": "already_running"}
    
    initialization_task = asyncio.create_task(init_service.initialize_system())
    return {"status": "started"}

@app.get("/api/initialization/status")
async def get_initialization_status():
    """Get current initialization status"""
    return {
        "complete": init_service.status.complete,
        "progress": init_service.status.progress,
        "current_task": init_service.status.current_task,
        "errors": init_service.status.errors,
        "data_status": init_service.status.data_status
    }