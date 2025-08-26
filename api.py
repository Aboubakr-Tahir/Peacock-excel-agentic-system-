import shutil, logging, sys, os, time, uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from pydantic import BaseModel
from pathlib import Path
from config import repo_path, output_path, todo, agent_logs

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("peaqock_api")

class UploadResponse(BaseModel):
    file_path: str

app = FastAPI(title="PeaQock Manus API", description="API for PeaQock_Manus Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

if output_path.exists():
    try:
        shutil.rmtree(output_path)
        logger.info("Cleaned output folder on startup")
    except PermissionError:
        logger.warning("Could not clean output folder - in use by another process")
    except Exception as e:
        logger.warning(f"Could not clean output folder: {e}")

MEDIA_TYPES = {
    '.pdf': 'application/pdf',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.csv': 'text/csv',
    '.txt': 'text/plain',
    '.html': 'text/html',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword'
}

shutdown_flag = False
current_session_logs = []

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    """Serve the main dashboard HTML"""
    html_file = Path(__file__).parent / "index.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard HTML file not found")
    
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content)

@app.post("/upload", response_model=UploadResponse)
def upload_excel(file: UploadFile = File(...), query: str = Form("")):
    """Upload Excel file for analysis and processing"""
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files allowed")
    
    repo_dir = Path(repo_path)
    repo_dir.mkdir(exist_ok=True)
    (repo_dir / "scripts").mkdir(exist_ok=True)
    
    if output_path.exists():
        shutil.rmtree(output_path)
    
    target_file = repo_dir / "data.xlsx"
    target_file.unlink(missing_ok=True)
    
    with open(target_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    logger.info(f"File uploaded: {target_file}, Query: {query}")
    
    try:
        from main import main_function
        result = main_function(query)
        logger.info("Main function executed successfully")
        
        response_data = {"file_path": str(target_file)}
        
        if result and result.strip():
            response_data["message"] = result
            response_data["has_custom_message"] = True
        else:
            response_data["message"] = "Query processed successfully. Results available for download."
            response_data["has_custom_message"] = False
            
        return response_data
    except Exception as e:
        logger.error(f"Error executing main function: {str(e)}")
        return {
            "file_path": str(target_file), 
            "message": f"Error processing query: {str(e)}", 
            "has_custom_message": True
        }

@app.get("/download")
def download_output_file():
    """Auto-detect and download the highest priority file from output folder"""
    if not output_path.exists():
        raise HTTPException(404, "Output folder not found")
    
    files = [f for f in output_path.iterdir() if f.is_file()]
    if not files:
        raise HTTPException(404, "No files found")
    
    for ext in ['.pdf', '.xlsx', '.xls', '.html', '.png', '.jpg', '.jpeg']:
        for f in files:
            if f.suffix.lower() == ext:
                media_type = MEDIA_TYPES.get(ext.lower(), 'application/octet-stream')
                return FileResponse(f, filename=f.name, media_type=media_type)
    
    file = files[0]
    ext = file.suffix.lower()
    media_type = MEDIA_TYPES.get(ext, 'application/octet-stream')
    return FileResponse(file, filename=file.name, media_type=media_type)

@app.get("/list_output_files")
def list_output_files():
    """List all files in the output directory"""
    if not output_path.exists():
        return []
    
    try:
        return [
            {"name": file_path.name, "size": file_path.stat().st_size}
            for file_path in output_path.iterdir()
            if file_path.is_file()
        ]
    except Exception as e:
        logger.error(f"Error listing output files: {str(e)}")
        return []

@app.get("/download/{filename}")
def download_specific_file(filename: str):
    """Download a specific file from the output directory"""
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output folder not found")
    
    safe_filename = Path(filename).name
    file_path = output_path / safe_filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{safe_filename}' not found")
    
    ext = file_path.suffix.lower()
    media_type = MEDIA_TYPES.get(ext, 'application/octet-stream')
    return FileResponse(file_path, filename=safe_filename, media_type=media_type)

def set_shutdown_flag():
    global shutdown_flag
    shutdown_flag = True

def todo_stream():
    """Stream todo.md content"""
    global shutdown_flag
    last_content = None
    
    for i in range(50):
        if shutdown_flag:
            break
        
        content = todo.read_text(encoding="utf-8") if todo.exists() else "Creating task list..."
        content = content or "[Todo list is being prepared...]"
        
        if content != last_content or i % 20 == 0:
            yield f"data: {content.replace(chr(10), '\\n')}\n\n"
            last_content = content
        
        time.sleep(0.2)

@app.get("/stream_todo")
async def stream_todo_md():
    """Stream todo.md file"""
    return StreamingResponse(todo_stream(), media_type="text/event-stream")

def agent_logs_stream(from_line: int = 0):
    """Stream agent_logs.txt content starting from a specific line"""
    global shutdown_flag, current_session_logs
    
    if not agent_logs.exists():
        agent_logs.parent.mkdir(parents=True, exist_ok=True)
        agent_logs.touch()
    
    if from_line == 0:
        yield f"data: Connected to agent logs stream\n\n"
        current_session_logs = []
    
    if from_line < len(current_session_logs):
        for i in range(from_line, len(current_session_logs)):
            yield f"data: {current_session_logs[i]}\n\n"
    
    last_size = agent_logs.stat().st_size if agent_logs.exists() else 0
    
    for i in range(300):
        if shutdown_flag:
            break
            
        try:
            if agent_logs.exists():
                current_size = agent_logs.stat().st_size
                
                if current_size > last_size:
                    with open(agent_logs, 'r', encoding='utf-8') as f:
                        f.seek(last_size)
                        new_content = f.read()
                        
                        if new_content.strip():
                            lines = new_content.strip().split('\n')
                            for line in lines:
                                clean_line = line.strip()
                                if clean_line:
                                    current_session_logs.append(clean_line)
                                    yield f"data: {clean_line}\n\n"
                            
                            last_size = current_size
                            
                elif current_size < last_size:
                    last_size = 0
                    current_session_logs = []
                
        except Exception as e:
            error_msg = f"Error reading agent logs: {str(e)}"
            yield f"data: {error_msg}\n\n"
        
        time.sleep(0.3)
    
    yield f"data: Agent logs stream ended\n\n"

@app.post("/clear_agent_logs_session")
async def clear_agent_logs_session():
    """Clear the current session logs"""
    global current_session_logs
    current_session_logs = []
    return {"status": "success", "message": "Agent logs session cleared"}

@app.get("/stream_agent_logs")
async def stream_agent_logs(from_line: int = 0):
    """Stream agent logs file starting from a specific line"""
    return StreamingResponse(agent_logs_stream(from_line), media_type="text/event-stream")
    
if __name__ == "__main__":
    print("API server starting at http://127.0.0.1:8000/")
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)