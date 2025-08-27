from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import time, logging
from core.paths import todo, agent_logs

logger = logging.getLogger("peaqock_api")
router = APIRouter()

shutdown_flag = False
current_session_logs = []

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

@router.get("/stream_todo")
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

@router.post("/clear_agent_logs_session")
async def clear_agent_logs_session():
    """Clear the current session logs"""
    global current_session_logs
    current_session_logs = []
    return {"status": "success", "message": "Agent logs session cleared"}

@router.get("/stream_agent_logs")
async def stream_agent_logs(from_line: int = 0):
    """Stream agent logs file starting from a specific line"""
    return StreamingResponse(agent_logs_stream(from_line), media_type="text/event-stream")
