from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import shutil,uvicorn, logging, sys, os, webbrowser, time
from pathlib import Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import repo_path, output_path

html_path = Path(__file__).parent / "test_api.html"

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("peaqock_api")

class UploadResponse(BaseModel):
    file_path: str

app = FastAPI(title="PeaQock Manus API", description="API for PeaQock_Manus Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


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
    
    # Priority order for file types
    for ext in ['.pdf', '.xlsx', '.xls', '.html', '.png', '.jpg', '.jpeg']:
        for f in files:
            if f.suffix.lower() == ext:
                # Ensure the filename is preserved exactly as it is
                original_filename = f.name
                logger.info(f"Serving file with original name: {original_filename}")
                return FileResponse(f, filename=original_filename, media_type='application/octet-stream')
    
    # If no priority files found, return the first one with its original name
    original_filename = files[0].name
    logger.info(f"Serving first available file with original name: {original_filename}")
    return FileResponse(files[0], filename=original_filename, media_type='application/octet-stream')


if __name__ == "__main__":
    open_browser()
    uvicorn.run(app, host="127.0.0.1", port=8000)