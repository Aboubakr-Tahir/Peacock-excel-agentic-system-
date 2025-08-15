from agno.tools import tool, Toolkit
import pandas as pd
import json
import os
import shutil
import zipfile
import requests
from typing import Dict
from dotenv import load_dotenv
from config import repo_path, web_images, excel_path

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

@tool(show_result=True)
def read_file_utf8(file_name: str) -> str:
    try:
        with open(repo_path / file_name, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {file_name}: {e}"

@tool(show_result=True)
def save_file_utf8(file_name: str, contents: str) -> str:
    try:
        with open(repo_path / file_name, 'w', encoding='utf-8') as f:
            f.write(contents)
        return f"Successfully saved to {file_name}"
    except Exception as e:
        return f"Error saving file {file_name}: {e}"

@tool(show_result=True)
def initial_data_scout(file_path: str, output_path: str) -> str:
    try:
        excel_file = pd.ExcelFile(file_path, engine='openpyxl')
        report = {"file_path": file_path, "sheets": {}}
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            sheet_issues = []
            for col in df.columns:
                if df[col].isnull().sum() > 0:
                    sheet_issues.append({"column": col, "issue_type": "Missing Data", "details": f"Column '{col}' contains {df[col].isnull().sum()} null values."})
            if sheet_issues:
                report["sheets"][sheet_name] = sheet_issues
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        
        return f"Initial inspection complete. Report saved to {output_path}"
    except Exception as e:
        return f"Error during initial data scout: {e}"

@tool(show_result=True)
def google_images_search(query: str, num_images: int = 2):
    if not SERPAPI_KEY:
        return "Error: SERPAPI_KEY environment variable is not set. Please set it in your .env file or environment."
    os.makedirs(web_images, exist_ok=True)
    search_url = "https://serpapi.com/search.json"
    params = {"q": query, "tbm": "isch", "ijn": "0", "api_key": SERPAPI_KEY}
    try:
        response = requests.get(search_url, params=params)
        data = response.json()
        if "images_results" not in data:
            return f"API Error: {data.get('error', 'No images found')}" if "error" in data else f"No images found for {query}"
        
        results = []
        for i, img in enumerate(data["images_results"][:num_images]):
            img_url = img.get("original") or img.get("thumbnail")
            if not img_url:
                continue
            try:
                img_response = requests.get(img_url, timeout=10)
                if img_response.status_code == 200:
                    # Create a short, safe filename to avoid Windows path length limits
                    safe_query = "".join(c for c in query.split(':')[0] if c.isalnum() or c in " _-").strip()[:50]
                    img_path = os.path.join(web_images, f"{safe_query}_{i+1}.jpg")
                    with open(img_path, "wb") as f:
                        f.write(img_response.content)
                    results.append(img_path)
            except Exception:
                continue
        return f"Downloaded {len(results)} images for '{query}' in {web_images}/"
    except Exception as e:
        return f"Error searching for images: {e}"

def _extract_charts(excel_file: str = None) -> Dict:
    """Extract charts using Spire.XLS"""
    try:
        from spire.xls import Workbook
        excel_file = excel_file or str(excel_path)
        output_dir = repo_path / "charts"
        os.makedirs(output_dir, exist_ok=True)
        
        workbook = Workbook()
        workbook.LoadFromFile(excel_file)
        chart_files = []
        chart_counter = 0
        
        for sheet in workbook.Worksheets:
            for i, chart in enumerate(sheet.Charts):
                chart_counter += 1
                chart_filename = f"chart{chart_counter}.png"
                image_path = os.path.join(output_dir, chart_filename)
                chart.SaveToImage(image_path)
                chart_files.append({
                    "filename": chart_filename, "path": image_path, "sheet": sheet.Name,
                    "chart_index": i + 1, "global_chart_number": chart_counter
                })
        
        return {"success": True, "total_charts": len(chart_files), "charts": chart_files, "output_directory": str(output_dir), "method": "spire_xls_extraction"}
    except ImportError:
        return {"success": False, "error": "Spire.XLS not installed. Please install with: pip install Spire.XLS", "charts": []}
    except Exception as e:
        return {"success": False, "error": str(e), "charts": []}

def _extract_images(excel_filepath: str = None) -> Dict:
    """Extract embedded images from Excel file"""
    excel_filepath = excel_filepath or str(excel_path)
    output_dir = repo_path / "images"
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = output_dir / "temp_excel_extract"
    os.makedirs(temp_dir, exist_ok=True)
    extracted_images = []
    
    try:
        with zipfile.ZipFile(excel_filepath, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        media_path = temp_dir / 'xl' / 'media'
        if media_path.exists():
            for i, filename in enumerate(os.listdir(media_path)):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    source_path = media_path / filename
                    file_extension = os.path.splitext(filename)[1]
                    new_filename = f"image{i+1}{file_extension}"
                    output_path = output_dir / new_filename
                    shutil.copy(source_path, output_path)
                    extracted_images.append({"filename": new_filename, "path": str(output_path), "original_name": filename})
        
        return {"success": True, "total_images": len(extracted_images), "images": extracted_images, "output_directory": str(output_dir)}
    except Exception as e:
        return {"success": False, "error": str(e), "images": []}
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

def _analyze_image(image_path: str) -> Dict:
    """Analyze image content using OpenAI Vision API"""
    try:
        import base64
        if not os.path.exists(image_path):
            return {"error": f"Image file not found: {image_path}"}
        
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"error": "OpenAI API key not found"}
        
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        payload = {
            "model": "gpt-4o",
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": "Analyze this image and describe what you see. If this is a chart or graph, focus on: chart type, data values, trends, axes labels, legend, patterns, insights, and key takeaways. If it's a regular image, describe the content, objects, text, and visual elements. Provide a comprehensive analysis. Keep response detailed but under 300 words."
                }, {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"}
                }]
            }],
            "max_tokens": 400
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return {
                "image_path": image_path, "analysis_success": True,
                "description": result['choices'][0]['message']['content'],
                "file_size": os.path.getsize(image_path), "message": "Image analyzed successfully with vision AI"
            }
        else:
            return {"error": f"API call failed: {response.status_code}", "analysis_success": False}
    except Exception as e:
        return {"error": f"Failed to analyze image: {str(e)}", "analysis_success": False}

def _save_to_media_json(data_type: str, data: Dict):
    """Save analysis results to media.json"""
    media_json_path = repo_path / "media.json"
    try:
        media_data = json.load(open(media_json_path, 'r', encoding='utf-8')) if media_json_path.exists() else {}
    except:
        media_data = {}
    
    # Handle different key names for total count
    total_key = f'total_{data_type}_extracted' if f'total_{data_type}_extracted' in data else f'total_{data_type}'
    
    # Handle different key names for analyses
    analyses_key = f'{data_type}_analyses'
    if analyses_key not in data:
        # Try singular form (e.g., 'image_analyses' instead of 'images_analyses')
        singular_type = data_type[:-1] if data_type.endswith('s') else data_type
        analyses_key = f'{singular_type}_analyses'
    
    media_data[data_type] = {
        'extraction_date': str(pd.Timestamp.now()),
        'total_extracted': data.get(total_key, 0),
        'extraction_method': data.get('method', 'unknown'),
        'output_directory': data.get('output_directory', ''),
        'analyses': data.get(analyses_key, [])
    }
    
    with open(media_json_path, 'w', encoding='utf-8') as f:
        json.dump(media_data, f, indent=4, ensure_ascii=False)

class ExcelParserTool(Toolkit):
    """Streamlined Excel parsing tool with chart/image extraction and AI analysis"""
    def __init__(self):
        super().__init__(name="excel_parser", tools=[self.excel_parser, self.extract_and_analyze_charts, self.extract_and_analyze_images])

    def excel_parser(self, file_path: str = None) -> Dict:
        """Parse Excel file structure and data"""
        file_path = file_path or str(excel_path)
        results = {"file_path": file_path, "sheets": {}, "success": False, "errors": []}
        
        if not os.path.exists(file_path):
            results["errors"].append(f"File not found: {file_path}")
            return results
        
        try:
            excel_file = pd.ExcelFile(file_path)
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                results["sheets"][sheet_name] = {
                    "shape": df.shape, "columns": list(df.columns),
                    "dtypes": df.dtypes.to_dict(), "sample_data": df.head(3).to_dict()
                }
            results["success"] = True
        except Exception as e:
            results["errors"].append(str(e))
        return results

    def extract_and_analyze_charts(self, file_path: str = None) -> Dict:
        """Extract charts and analyze with AI"""
        extraction_result = _extract_charts(file_path)
        if not extraction_result["success"] or extraction_result["total_charts"] == 0:
            _save_to_media_json("charts", extraction_result)
            return extraction_result
        
        chart_analyses = []
        for chart_info in extraction_result["charts"]:
            analysis = _analyze_image(chart_info["path"])
            chart_analyses.append({
                "chart_file": chart_info["filename"], "path": chart_info["path"], "sheet": chart_info["sheet"],
                "chart_index": chart_info["chart_index"], "analysis": analysis.get("description", f"Analysis failed: {analysis.get('error', 'Unknown error')}"),
                "file_size": f"{os.path.getsize(chart_info['path'])} bytes", "extraction_method": "spire_xls",
                "analysis_failed": not analysis.get("analysis_success", False)
            })
        
        result = {
            "success": True, "method": "spire_xls_with_vision_analysis", "charts_found": len(chart_analyses),
            "total_charts_extracted": extraction_result["total_charts"], "chart_analyses": chart_analyses,
            "output_directory": extraction_result["output_directory"],
            "message": f"Successfully extracted {extraction_result['total_charts']} charts and analyzed {len([c for c in chart_analyses if not c.get('analysis_failed')])} with vision AI"
        }
        _save_to_media_json("charts", result)
        return result

    def extract_and_analyze_images(self, file_path: str = None) -> Dict:
        """Extract embedded images and analyze with AI"""
        extraction_result = _extract_images(file_path)
        if not extraction_result["success"] or extraction_result["total_images"] == 0:
            _save_to_media_json("images", extraction_result)
            return extraction_result
        
        image_analyses = []
        for image_info in extraction_result["images"]:
            analysis = _analyze_image(image_info["path"])
            image_analyses.append({
                "image_file": image_info["filename"], "path": image_info["path"], "original_name": image_info["original_name"],
                "analysis": analysis.get("description", f"Analysis failed: {analysis.get('error', 'Unknown error')}"),
                "file_size": f"{os.path.getsize(image_info['path'])} bytes", "extraction_method": "zip_extraction",
                "analysis_failed": not analysis.get("analysis_success", False)
            })
        
        result = {
            "success": True, "method": "zip_extraction_with_vision_analysis", "images_found": len(image_analyses),
            "total_images_extracted": extraction_result["total_images"], "image_analyses": image_analyses,
            "output_directory": extraction_result["output_directory"],
            "message": f"Successfully extracted {extraction_result['total_images']} images and analyzed {len([c for c in image_analyses if not c.get('analysis_failed')])} with vision AI"
        }
        _save_to_media_json("images", result)
        return result

# Tool functions for agent use
@tool(show_result=True)
def excel_structure_parser(file_path: str = None) -> Dict:
    return ExcelParserTool().excel_parser(file_path)

@tool(show_result=True)
def extract_and_analyze_charts_tool(file_path: str = None) -> Dict:
    return ExcelParserTool().extract_and_analyze_charts(file_path)

@tool(show_result=True)
def extract_and_analyze_images_tool(file_path: str = None) -> Dict:
    return ExcelParserTool().extract_and_analyze_images(file_path)

@tool(show_result=True)
def analyze_extracted_image_content_tool(image_path: str) -> Dict:
    return _analyze_image(image_path)

def excel_parser():
    return ExcelParserTool()

#LATEX tools
from agno.tools import Toolkit, tool
import subprocess
import re
from pathlib import Path
from config import repo_path, tectonic_path

@tool("latex_runner")
def compile_latex(tex_file_path: str):
    try:
        # Use repo_path if relative path provided
        if not Path(tex_file_path).is_absolute():
            tex_file_path = str(repo_path / tex_file_path)
        
        # Get the directory where the .tex file is located
        tex_file = Path(tex_file_path)
        output_dir = str(tex_file.parent)
        
        # Compile with output directory set to same folder as .tex file
        subprocess.run([str(tectonic_path), "--outdir", output_dir, tex_file_path], check=True)
        print("✅ PDF generated successfully.")
    except subprocess.CalledProcessError as e:
        print("❌ Error during LaTeX compilation:", e)

@tool("latex_escape")
def escape_latex(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    accents_mapping = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'á': 'a', 'â': 'a', 'ä': 'a',
        'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
        'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
        'ò': 'o', 'ó': 'o', 'ô': 'o', 'ö': 'o',
        'ç': 'c', 'ñ': 'n',
        'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
        'À': 'A', 'Á': 'A', 'Â': 'A', 'Ä': 'A',
        'Ù': 'U', 'Ú': 'U', 'Û': 'U', 'Ü': 'U',
        'Ì': 'I', 'Í': 'I', 'Î': 'I', 'Ï': 'I',
        'Ò': 'O', 'Ó': 'O', 'Ô': 'O', 'Ö': 'O',
        'Ç': 'C', 'Ñ': 'N',
        'N°': 'Num'
    }
    
    # Replace accented characters first
    for accent, replacement in accents_mapping.items():
        text = text.replace(accent, replacement)
    
    # Then handle LaTeX special characters
    latex_mapping = {
        '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
        '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}',
        '^': r'\^{}', '\\': r'\textbackslash{}', '€': r'\euro{}'
    }
    pattern = re.compile('|'.join(re.escape(k) for k in latex_mapping))
    return pattern.sub(lambda m: latex_mapping[m.group()], text)

@tool(name="write_latex_file_utf8")
def proper_write_latex(latex_code: str, file_name: str = "latex.tex") -> str:
    try:
        # Use repo_path if relative path provided
        if not Path(file_name).is_absolute():
            path = repo_path / file_name
        else:
            path = Path(file_name)
            
        with open(path, "w", encoding="utf-8") as f:
            f.write(latex_code)
        return f"LaTeX code successfully written to {path.resolve()}"
    except Exception as e:
        return f"Error writing LaTeX file: {e}"

@tool(name="list_available_visualizations")
def list_available_visualizations() -> str:
    """List all available plots, charts, and images for inclusion in reports"""
    try:
        from config import repo_path, charts_path, images_path, plot_output_path, web_images
        
        available_files = {
            "plots": [],
            "charts": [],
            "images": [],
            "web_images": []
        }
        
        # Check plots directory
        plots_dir = repo_path / "plots"
        if plots_dir.exists():
            for file in plots_dir.glob("*"):
                if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.html', '.svg']:
                    available_files["plots"].append({
                        "filename": file.name,
                        "path": str(file),
                        "relative_path": f"plots/{file.name}",
                        "type": file.suffix[1:].upper()
                    })
        
        # Check charts directory
        charts_dir = repo_path / "charts"
        if charts_dir.exists():
            for file in charts_dir.glob("*"):
                if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.svg']:
                    available_files["charts"].append({
                        "filename": file.name,
                        "path": str(file),
                        "relative_path": f"charts/{file.name}",
                        "type": file.suffix[1:].upper()
                    })
        
        # Check images directory
        images_dir = repo_path / "images"
        if images_dir.exists():
            for file in images_dir.glob("*"):
                if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.svg']:
                    available_files["images"].append({
                        "filename": file.name,
                        "path": str(file),
                        "relative_path": f"images/{file.name}",
                        "type": file.suffix[1:].upper()
                    })
        
        # Check web_images directory
        web_images_dir = repo_path / "web_images"
        if web_images_dir.exists():
            for file in web_images_dir.glob("*"):
                if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.svg']:
                    available_files["web_images"].append({
                        "filename": file.name,
                        "path": str(file),
                        "relative_path": f"web_images/{file.name}",
                        "type": file.suffix[1:].upper()
                    })
        
        result = "AVAILABLE VISUALIZATIONS FOR REPORT:\n\n"
        
        for category, files in available_files.items():
            result += f"{category.upper()} ({len(files)} files):\n"
            if files:
                for file_info in files:
                    result += f"  - {file_info['filename']} ({file_info['type']}) -> Use: {file_info['relative_path']}\n"
            else:
                result += "  - No files found\n"
            result += "\n"
        
        result += "LaTeX USAGE EXAMPLES:\n"
        
        # Generate dynamic examples based on actual files found
        example_count = 0
        
        # First show plot examples if any exist
        if available_files["plots"]:
            for plot_file in available_files["plots"][:2]:  # Show max 2 plot examples
                if plot_file["type"] in ["PNG", "JPG", "JPEG", "SVG"]:  # Only image formats for LaTeX
                    result += f"\\includegraphics[width=0.8\\textwidth]{{{plot_file['relative_path']}}}\n"
                    example_count += 1
        
        # Then show chart examples if any exist
        if available_files["charts"] and example_count < 3:
            for chart_file in available_files["charts"][:2]:  # Show max 2 chart examples
                if chart_file["type"] in ["PNG", "JPG", "JPEG", "SVG"]:
                    result += f"\\includegraphics[width=0.7\\textwidth]{{{chart_file['relative_path']}}}\n"
                    example_count += 1
        
        # Finally show image examples if any exist
        if available_files["images"] and example_count < 4:
            for image_file in available_files["images"][:2]:  # Show max 2 image examples
                if image_file["type"] in ["PNG", "JPG", "JPEG", "SVG"]:
                    result += f"\\includegraphics[width=0.6\\textwidth]{{{image_file['relative_path']}}}\n"
                    example_count += 1
        
        # Finally show web_images examples if any exist
        if available_files["web_images"] and example_count < 6:
            for web_image_file in available_files["web_images"][:2]:  # Show max 2 web_image examples
                if web_image_file["type"] in ["PNG", "JPG", "JPEG", "SVG"]:
                    result += f"\\includegraphics[width=0.5\\textwidth]{{{web_image_file['relative_path']}}}\n"
                    example_count += 1
        
        # If no files found, show generic examples
        if example_count == 0:
            result += "\\includegraphics[width=0.8\\textwidth]{plots/your_plot.png}\n"
            result += "\\includegraphics[width=0.6\\textwidth]{images/your_image.png}\n"
            result += "\\includegraphics[width=0.5\\textwidth]{web_images/your_web_image.png}\n"
        
        result += "\n"
        
        total_files = sum(len(files) for files in available_files.values())
        result += f"TOTAL AVAILABLE FILES: {total_files}\n\n"
        
        # Add usage notes
        result += "USAGE NOTES:\n"
        result += "- Use relative paths as shown above for LaTeX \\includegraphics commands\n"
        result += "- Plots: Use width=0.8\\textwidth for main visualizations\n"
        result += "- Charts: Use width=0.7\\textwidth for extracted charts\n"
        result += "- Images: Use width=0.6\\textwidth for extracted images\n"
        result += "- Web Images: Use width=0.5\\textwidth for downloaded web images\n"
        result += "- Always include proper figure captions with \\caption{Your Caption}"
        
        return result
        
    except Exception as e:
        return f"Error listing visualizations: {e}"

