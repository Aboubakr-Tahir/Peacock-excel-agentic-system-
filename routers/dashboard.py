from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pathlib import Path
import logging

logger = logging.getLogger("peaqock_api")
router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def get_dashboard():
    """Serve the main dashboard HTML"""
    html_file = Path(__file__).parent.parent / "static" / "index.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard HTML file not found")
    
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content)
