import shutil, uvicorn, logging, sys, os, webbrowser, time
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from config import repo_path, output_path, todo, agent_logs
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

html_path = Path(__file__).parent / "index.html"

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("peaqock_api")

class UploadResponse(BaseModel):
    file_path: str

app = FastAPI(title="PeaQock Manus API", description="API for PeaQock_Manus Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Clean up output folder on startup
if output_path.exists():
    shutil.rmtree(output_path)
    logger.info("🗑️ Cleaned output folder on startup")


@app.get("/")
def open_browser():
    """Open the HTML test interface in the default browser after a short delay"""
    time.sleep(2)
    if html_path.exists():
        webbrowser.open(f'file://{html_path.absolute()}')
        logger.info(f" 📊 Opened HTML interface: http://127.0.0.1:8000/")
    else:
        logger.warning(f"HTML test file not found: {html_path}")
        
@app.post("/upload", response_model=UploadResponse)
def upload_excel(file: UploadFile = File(...), query: str = Form("")):
    """Upload Excel file for analysis and ask the agent"""
    if not file.filename.lower().endswith(('.xlsx', '.xls')): raise HTTPException(status_code=400, detail="Only Excel files allowed")
    repo_dir = Path(repo_path); repo_dir.mkdir(exist_ok=True)
    # Create scripts directory to avoid import errors
    scripts_dir = repo_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    
    if os.path.exists(output_path): shutil.rmtree(output_path)
    target_file = repo_dir / "data.xlsx"; target_file.unlink(missing_ok=True)
    with open(target_file, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    # Store the query in a variable as requested
    user_query = query
    logger.info(f"File uploaded: {target_file}, Query: {user_query}")
    try:
        # Import main function after creating necessary directories
        from main import main_function
        result = main_function(user_query)
        logger.info(f"Main function executed successfully")
    except Exception as e:
        logger.error(f"Error executing main function: {str(e)}")
    return UploadResponse(file_path=str(target_file))

@app.get("/download")
def download_output_file():
    """Auto-detect and download file from output folder"""
    if not output_path.exists(): raise HTTPException(404, "Output folder not found")
    files = [f for f in output_path.iterdir() if f.is_file()]
    if not files: raise HTTPException(404, "No files found")
    
    # Define media types for different file extensions
    media_types = {
        '.pdf': 'application/pdf',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        '.html': 'text/html',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg'
    }
    
    # Priority order for file types
    for ext in ['.pdf', '.xlsx', '.xls', '.html', '.png', '.jpg', '.jpeg']:
        for f in files:
            if f.suffix.lower() == ext:
                # Ensure the filename is preserved exactly as it is
                original_filename = f.name
                media_type = media_types.get(ext.lower(), 'application/octet-stream')
                logger.info(f"Serving file with original name: {original_filename}, media_type: {media_type}")
                return FileResponse(f, filename=original_filename, media_type=media_type)
    
    # If no priority files found, return the first one with its original name
    original_filename = files[0].name
    ext = Path(original_filename).suffix.lower()
    media_type = media_types.get(ext, 'application/octet-stream')
    logger.info(f"Serving first available file with original name: {original_filename}, media_type: {media_type}")
    return FileResponse(files[0], filename=original_filename, media_type=media_type)

@app.get("/list_output_files")
def list_output_files():
    """List all files in the output directory with their details"""
    if not output_path.exists():
        return []
    
    files = []
    try:
        for file_path in output_path.iterdir():
            if file_path.is_file():
                file_info = {
                    "name": file_path.name,
                    "size": file_path.stat().st_size
                }
                files.append(file_info)
        
        return files
    except Exception as e:
        logger.error(f"Error listing output files: {str(e)}")
        return []

@app.get("/download/{filename}")
def download_specific_file(filename: str):
    """Download a specific file from the output directory"""
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output folder not found")
    
    # Sanitize filename to prevent path traversal
    safe_filename = Path(filename).name
    file_path = output_path / safe_filename
    
    if not file_path.exists() or not file_path.is_file():
        logger.warning(f"File not found: {safe_filename}")
        raise HTTPException(status_code=404, detail=f"File '{safe_filename}' not found")
    
    # Define media types for different file extensions
    media_types = {
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
    
    ext = file_path.suffix.lower()
    media_type = media_types.get(ext, 'application/octet-stream')
    
    return FileResponse(file_path, filename=safe_filename, media_type=media_type)

# Global shutdown flag
shutdown_flag = False

def set_shutdown_flag():
    global shutdown_flag
    shutdown_flag = True

# SSE endpoint to stream live updates of todo.md
def todo_stream():
    """Stream todo.md content with shutdown support"""
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

# SSE endpoint to stream live updates of agent logs
# Global variable to track current session logs
current_session_logs = []

def agent_logs_stream(from_line: int = 0):
    """Stream agent_logs.txt content starting from a specific line"""
    global shutdown_flag, current_session_logs
    
    # Create agent logs file if it doesn't exist
    if not agent_logs.exists():
        agent_logs.parent.mkdir(parents=True, exist_ok=True)
        agent_logs.touch()
    
    # Send initial connection message only if starting from beginning
    if from_line == 0:
        yield f"data: Connected to agent logs stream\n\n"
        # Reset session logs for new connections starting from 0
        current_session_logs = []
    
    # Send any existing logs from the current session that the client hasn't seen
    if from_line < len(current_session_logs):
        for i in range(from_line, len(current_session_logs)):
            yield f"data: {current_session_logs[i]}\n\n"
    
    # Track the file size to detect new content
    last_size = 0
    if agent_logs.exists():
        last_size = agent_logs.stat().st_size
    
    for i in range(300):  # Allow longer streaming for agent logs
        if shutdown_flag:
            break
            
        try:
            if agent_logs.exists():
                current_size = agent_logs.stat().st_size
                
                # Only read new content if file has grown
                if current_size > last_size:
                    with open(agent_logs, 'r', encoding='utf-8') as f:
                        # Skip to the last read position
                        f.seek(last_size)
                        new_content = f.read()
                        
                        if new_content.strip():
                            # Split by lines and process each line
                            lines = new_content.strip().split('\n')
                            for line in lines:
                                clean_line = line.strip()
                                if clean_line:
                                    # Add to session logs
                                    current_session_logs.append(clean_line)
                                    # Send to client
                                    yield f"data: {clean_line}\n\n"
                            
                            last_size = current_size
                            
                elif current_size < last_size:
                    # File was truncated (cleared), reset everything for new session
                    last_size = 0
                    current_session_logs = []
                
        except Exception as e:
            error_msg = f"Error reading agent logs: {str(e)}"
            print(error_msg)  # Log to console
            yield f"data: {error_msg}\n\n"
        
        time.sleep(0.3)  # Check every 300ms for more responsive updates

    yield f"data: Agent logs stream ended\n\n"

@app.post("/clear_agent_logs_session")
async def clear_agent_logs_session():
    """Clear the current session logs (called when starting a new workflow)"""
    global current_session_logs
    current_session_logs = []
    return {"status": "success", "message": "Agent logs session cleared"}

@app.get("/stream_agent_logs")
async def stream_agent_logs(from_line: int = 0):
    """Stream agent logs file starting from a specific line"""
    return StreamingResponse(agent_logs_stream(from_line), media_type="text/event-stream")

@app.post("/test_agent_logs")
async def test_agent_logs():
    """Test endpoint to write some sample logs"""
    try:
        # Import here to avoid circular imports
        from agent_runner import log_agent_message, clear_agent_logs
        
        clear_agent_logs()
        log_agent_message("🧪 Testing agent logs system...")
        log_agent_message("⏱ This is a running message")
        log_agent_message("✅ This is a success message")
        log_agent_message("❌ This is an error message")
        log_agent_message("⚠️ This is a warning message")
        log_agent_message("📝 This is an info message")
        log_agent_message("🎉 Agent logs test completed!")
        
        return {"status": "success", "message": "Test logs written successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    print("API server starting at http://127.0.0.1:8000/")
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)
    
    