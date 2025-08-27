from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import logging
from core.paths import output_path

logger = logging.getLogger("peaqock_api")
router = APIRouter()

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

@router.get("/download")
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

@router.get("/list_output_files")
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

@router.get("/download/{filename}")
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
