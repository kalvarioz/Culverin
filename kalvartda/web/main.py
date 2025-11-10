from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio
from typing import Dict, Any
import uuid
from analysis.workflow import TDAWorkflow
from config.settings import TDAConfig

app = FastAPI(title="TDA Grid Analysis API")

# Store for background tasks
analysis_tasks: Dict[str, Dict[str, Any]] = {}

@app.post("/api/analysis/start")
async def start_analysis(
    background_tasks: BackgroundTasks,
    fire_data: UploadFile = File(...)
):
    """Start TDA analysis"""
    task_id = str(uuid.uuid4())
    
    # Save uploaded file
    fire_data_path = f"temp/{task_id}_fire_data.geojson"
    with open(fire_data_path, "wb") as f:
        content = await fire_data.read()
        f.write(content)
    
    # Start background analysis
    background_tasks.add_task(run_analysis_task, task_id, fire_data_path)
    
    analysis_tasks[task_id] = {
        "status": "running",
        "progress": 0,
        "result": None
    }
    
    return {"task_id": task_id, "status": "started"}

async def run_analysis_task(task_id: str, fire_data_path: str):
    """Background analysis task"""
    try:
        config = TDAConfig()
        workflow = TDAWorkflow(config)
        
        # Update progress
        analysis_tasks[task_id]["progress"] = 25
        
        result = await workflow.run_full_analysis(Path(fire_data_path))
        
        analysis_tasks[task_id].update({
            "status": "completed",
            "progress": 100,
            "result": result
        })
        
    except Exception as e:
        analysis_tasks[task_id].update({
            "status": "failed",
            "progress": 100,
            "error": str(e)
        })

@app.get("/api/analysis/{task_id}/status")
async def get_analysis_status(task_id: str):
    """Get analysis status"""
    if task_id not in analysis_tasks:
        return {"error": "Task not found"}
    
    return analysis_tasks[task_id]

# Mount static files for React frontend
app.mount("/", StaticFiles(directory="web/frontend/build", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)