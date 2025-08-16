from agno.agent import Agent
from tools import read_file_utf8, save_file_utf8, initial_data_scout, google_images_search, excel_structure_parser, extract_and_analyze_charts_tool, extract_and_analyze_images_tool, analyze_extracted_image_content_tool, compile_latex, escape_latex, proper_write_latex, list_available_visualizations
from agno.tools.python import PythonTools
from agno.models.openai import OpenAIChat
from config import OrchestratorDecision, CleanerResponse, FilterResponse, PlotResponse, WebImageWords, ReportResponse, SummaryResponse, DeliveryResponse
from config import repo_path, scripts_path, profiler_notes_path, excel_path, summary_path, cleaned_excel, plot_output_path, queries_path, report_path, output_path
from pathlib import Path

class AgentManager:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.repo_path = repo_path
        self.scripts_path = scripts_path
        self.context_note_path = profiler_notes_path
        self.excel_path = excel_path
        self.scripts_path.mkdir(exist_ok=True)
        self.toolset = [PythonTools(base_dir=self.scripts_path), read_file_utf8, save_file_utf8, google_images_search, excel_structure_parser, extract_and_analyze_charts_tool, extract_and_analyze_images_tool, analyze_extracted_image_content_tool, compile_latex, escape_latex, proper_write_latex]

    def get_scout_agent(self) -> Agent:
        return Agent( name="scout_agent", model=OpenAIChat(self.model_name , temperature=0.0), tools=[initial_data_scout], instructions=["You are a script-running assistant.", "Your only job is to call the initial_data_scout tool with the file paths you are given."])

    def get_profiler_agent(self) -> Agent:
        return Agent( 
            name="profiler_agent",
            model=OpenAIChat(self.model_name , temperature=0.0),
            tools=self.toolset,
            instructions=[
                "You are a Business Intelligence Analyst. Your goal is to understand and document the business context of a dataset from an Excel file.",
                "1. *Load the data*: Write and run a Python script to load the Excel file into a pandas DataFrame.",
                "2. *Analyze Columns*: Examine the column names and sample data to infer the business purpose of each column.",
                "3. *Document Findings*: Write a clear summary of your findings into a string.",
                "4. *Save the Output*: Use the save_file_utf8 tool to save your summary to the specified file path." ,
                f"stock the python scripts you create in {self.scripts_path}"
            ]
        )

    def get_analyst_agent(self) -> Agent:
        return Agent(  name="analyst_agent", model=OpenAIChat(self.model_name, temperature=0.0), tools=self.toolset, instructions=[
            """You are an expert-level senior data analyst. Your goal is to produce a comprehensive data quality report by performing both a systematic check and an exploratory analysis.
            *Part 1: Systematic Quality Check*
            Write and execute a Python script to perform a thorough analysis of the Excel file. Your script MUST check for the following common issues:
            1.  *Missing Data*: Count nulls in all columns.
            2.  *Outliers: Use the IQR method for numeric columns. **Crucially, your script should only store a small, representative sample (e.g., the first 20 found) of the outlier values for the report.* Do not store all of them.
            3.  *Low Variability*: Identify columns with only one unique value.
            4.  *Duplicate Rows*: Check for complete duplicate entries.
            5.  *Data Type Consistency*: Verify appropriate data types.
            6.  *High Cardinality*: Flag columns with a very high number of unique values (like IDs).
            *Part 2: Exploratory & Logical Analysis*
            After the systematic check, your goal is to find issues that require logical reasoning or business context.
            1.  *Read Business Context*: Re-examine the context_notes.txt.
            2.  *Look for Anomalies*: Think like a detective. Are there patterns that don't make sense? For example:
                - Do quantities or costs have illogical negative values?
                - Are there strange patterns in dates (e.g., all transactions on one day)?
                - Are there relationships that seem odd (e.g., a 'Unit Price' of 0 for a non-free item)?
            3.  This part is about your intelligence as an analyst, not just a checklist. Document any such logical inconsistencies or unusual findings.

            *Final Report Generation:*
            - Combine all findings from both Part 1 and Part 2 into a single, comprehensive JSON report.
            - Use save_file_utf8 to overwrite context.json with the final report."""])

    def get_preprocessing_reviewer_agent(self) -> Agent:
        return Agent(
            name="reviewer_agent",
            model=OpenAIChat(self.model_name, temperature=0.0),
            tools=[read_file_utf8, save_file_utf8],
            instructions=[
                "You are a meticulous Quality Assurance analyst. Your job is to review a JSON data quality report and find logical flaws in the analysis itself.",
                "1. *Read the report*: Use read_file_utf8 to read the specified JSON report file.",
                "2. *Scrutinize each issue*: Look for illogical conclusions. (e.g., flagging a 'Description' column for being an 'Incorrect Data Type' because it contains text is a logical flaw).",
                "3. *Write your findings*: Document any flaws you find. If there are no flaws, state that the report is logically consistent.",
                "4. *Save the review*: Use save_file_utf8 to save your findings to the specified review file path."
            ]
        )
        
    def get_planner_agent(self, query: str , todo : Path ):
        return Agent(
            name="planner_agent",
            model=OpenAIChat(self.model_name, temperature=0.2),
            tools=[save_file_utf8],
            instructions = [
                "You are the PeaQockManus Planner, a master workflow architect. Your job is to convert user requests into a high-level, strategic plan.",
                "You have a team of specialized sub-agents available: a Cleaner, a Filterer, a Plotter, a Reporter, a Summarizer and an Analyst.",
                "Your plan must consist of high-level, delegable tasks for these agents. You must trust that the sub-agents will be given the necessary context to do their jobs.",
                
                "## Guiding Principles:",
                "1.  *Delegate, Don't Micromanage:* Your tasks should describe what to achieve, not how to achieve it.",
                "2.  *Think in Phases:* Structure the plan logically (e.g., cleaning and summarization always come first, reporting comes last).",
                "3.  *Be Specific and Actionable:* The user's original goal must be converted into a concrete task. Vague tasks like 'Analyze the data' or 'Extract insights' are forbidden.",

                "## Example of a GOOD, HIGH-LEVEL plan (✅ THIS IS CORRECT):",
                "markdown",
                "### Phase 1: Data Preparation",
                "- [ ] Clean and preprocess the dataset according to the user's instructions from the interaction phase.",
                "### Phase 2: Analysis",
                "- [ ] Summarize the excel file",
                "- [ ] Fulfill the user's primary analysis request: 'Filter the data to find the top 10 products by sales in the North region.'",
                "### Phase 3: Reporting",
                "- [ ] Generate a PDF report summarizing the key findings from the analysis.",
                "",

                "## Critical Rules:",
                "- If the user's request involves cleaning, the first task MUST be a cleaning task.",
                "- If the user's request involves a report, the last task MUST be a reporting task.",
                "- The second task MUST be a direct, specific action that addresses the user's original goal (e.g., 'Plot a bar chart of sales per category', 'Filter the data for entries after 2023') and this can be the end of the tasks if there are no other specifications or tasks to do.",
                "- never ever add a task talking about gathering insights or context ."
                "- If the user did not ask for a report, DO NOT add a report generation task.",

                f"## Current Request:",
                f"- The user's original, high-level goal was: '{query}'",
                
                "Based on this, create a strategic, high-level plan in Markdown and save it to 'repo/todo.md' using the save_file_utf8 tool.",
                "Your final output MUST be ONLY the call to the save_file_utf8 tool."
                f"here is the path of the todo file {todo}"
            ]
        )    
        
    def get_orchestrator_agent(self , todo : Path ) -> Agent:
        return Agent(
            name="orchestrator_agent",
            model=OpenAIChat(self.model_name, temperature=0.0),
            tools=[read_file_utf8 , save_file_utf8],
            response_model=OrchestratorDecision,
            instructions=[
                 f"You are the PeaQockManus Orchestrator — your job is to read and execute tasks from {todo} using the appropriate subagent.",
                    "You do NOT plan. You only execute what's already written in todo.md.",
                    "Begin each session by reading repo/todo.md and identifying the next unchecked task ('- [ ]').",
                    f"here is the path of the todo.md {todo}"
                    "You do NOT clean, visualize, or create files, you only delegate. You are the conductor.",
                    
                    "Your process:",
                    "- [1] Read todo.md",
                    "- [2] Find the next task to do (the first one marked '- [ ]')",
                    "- [3] Assign task to the correct agent: 'cleaner', 'filter', 'plot', 'summary', or 'reporter'",
                    "- [4] Wait for and verify the output",
                    "- [5] When you receive confirmation that a task is complete, IMMEDIATELY update todo.md using save_file_utf8",
                    "- [6] If a task failed, analyze why, revise instructions, and retry",

                    "Subagents:",
                        "'cleaner' handles: cleaning",
                        "'summerizer' handles: summaries",
                        "'plot' handles: plots requested by the user", 
                        "'filter' handles: quering on the excel file, aggregating, doing analytical operations on the excel (top 10 products, etc.)", 
                        "'reporter' handles: creating a pdf report",
                        
                    "Task completion:",
                        "- When a sub-agent reports 'The task X has been completed successfully', you MUST immediately mark that task as complete in todo.md",
                        "- Use save_file_utf8 to update todo.md by replacing '- [ ] X' with '- [x] X'",
                        "- After marking a task complete, move on to the next unchecked task",    
                    
                    "Handling failures:",
                    "- Don't mark failed tasks as done",
                    "- Retry with better context or reassign if needed",
                    "- Modify the plan if something is missing or impossible",
                    
                    "To update todo.md, always use this exact process:",
                    "1. Read current content with read_file_utf8",
                    "2. Replace the specific task string with its completed version",
                    "3. Save updated content with save_file_utf8",

                    f"use write_file_utf8 to update the todo file {todo}.",
                    "Completion = all tasks checked ('- [x]') and expected files exist.",
                    "Do not print or return anything unless all tasks are done. Then say: 'All tasks completed successfully.'" , 
                         "Example of correct updating:",
                            "python",
                            "# Original content",
                            "\"\"\"",
                            "### Phase 1: Data Preparation",
                            "- [ ] Clean and preprocess the dataset.",
                            "",
                            "### Phase 2: Analysis",
                            "- [ ] Plot a chart.",
                            "\"\"\"",
                            "",
                            "# Updated content (after cleaning task completion)",
                            "\"\"\"",
                            "### Phase 1: Data Preparation",
                            "- [x] Clean and preprocess the dataset.",
                            "",
                            "### Phase 2: Analysis",
                            "- [ ] Plot a chart.",
                            "\"\"\"",
                            "### Phase 1: Data Preparation",
                            "- [x] Clean and preprocess the dataset.",
                            "",
                            "### Phase 2: Analysis",
                            "- [x] Plot a chart.",
                            "\"\"\"",
                            "",
                            "of course this is just an example DO NOT replace the original todo.md content with the content with this example , i repeat this is JUST an example on how to file the todo.md" ,    

                            "Completion = all tasks checked ('- [x]') and expected files exist.",
                            "Do not print or return anything unless all tasks are done. Then say: 'All tasks completed successfully.'"
                    
            ]
        )    

    def get_cleaner_agent(self , task : str , query : str , context_json : Path , context_notes : Path , excel_path : Path , cleaned_path : Path ) : 
        return Agent(
            name="cleaner agent" , 
            model=OpenAIChat(self.model_name , temperature=0.0) , 
            tools=[self.toolset[0] , self.toolset[1]] , 
            structured_outputs=True , 
            response_model=CleanerResponse , 
            instructions=[
                "You are a specialized Data Cleaning agent that MUST follow this EXACT two-step process:",
                
                "## STEP 1 (MANDATORY): Write and Execute a Python Script",
                f"FIRST you must write and execute a Python script that cleans the file '{excel_path}' based on the user's instructions.",
                "focus only on the sheets that contain relevant data for the task, don't clean all the excel file sheets",
                f"The script MUST save the cleaned data to '{cleaned_path}'.",
                "You MUST use the save_to_file_and_run tool from PythonTools to execute this script BEFORE doing anything else.",
                "Until you have successfully executed this script, DO NOT proceed to Step 2.",
                
                "## STEP 2 (After script execution): Provide Structured Response",
                "ONLY after the Python script has successfully executed, return a CleanerResponse with:",
                "- status: the status of the cleaning process you followed ('success' or 'failure')",
                "- summary: A detailed explanation of what cleaning actions your script performed",
                
                "## Your Task and Context:",
                f"Task: {task}",
                f"User's Instructions: {query}",
                f"Data Quality Report: Read file at '{context_json}'",
                f"Business Context: Read file at '{context_notes}'",
                f"Input File: '{excel_path}'",
                f"Output File: '{cleaned_path}'",
                
                "## Critical Rules:",
                "1. NEVER claim you've cleaned the data without first executing a Python script",
                "2. The Python script MUST contain pandas code that actually processes the data",
                "3. You MUST include a print statement at the end of your script confirming completion",
                "4. If your script fails, fix it and try again until it succeeds",
                "5. In your structured response summary, detail each cleaning action performed and its business impact",
                "INSTRUCTIONS:",
                "1. If the column contains text (strings), replace missing values with the most frequent value (mode).",
                "2. If the column contains numbers, replace missing values with the average (mean) of the column.",
                "3. Never drop low_variability columns they might contain important informations , unless the user had specified it or you have no other option and it must be dropped."
            ]
        )
                
    def get_filter_agent(self, task: str, cleaned_excel_path: Path, output_path: Path , context_notes : Path):
        return Agent(
            name="filter_agent", 
            model=OpenAIChat(self.model_name, temperature=0.0), 
            tools=[self.toolset[0], self.toolset[1]],
            structured_outputs=True,
            response_model=FilterResponse,  
            instructions=[
                "You are a specialized Data Filtering agent that MUST follow this EXACT two-step process:",

                "## STEP 1 (MANDATORY): Write and Execute a Python Script",
                f"First you cant just assume something in the excel file , so you always must build context using context notes : {context_notes} and using the excel file : {cleaned_excel_path} inspecting it using pandas" ,
                "so you ALWAYS inspect first and build understanding on the excel then ", 
                f"Second you must write and execute a Python script that filters/queries the file '{cleaned_excel_path}' based on the task description.",
                "You MUST use the save_to_file_and_run tool from PythonTools to execute this script BEFORE doing anything else.",
                f"The script should save filtered data in this repo : {output_path}",
                f"the scripts should be stocked here {self.scripts_path}",

                "## STEP 2 (After script execution): Provide Structured Response",
                "ONLY after the Python script has successfully executed, return a FilterResponse with:",
                "- status: 'success'",
                "- summary: A detailed explanation of the filtering and its business implications",
                "- results: Key numbers, counts, or findings from the filtering operation",

                f"## Your Task: {task}",
                f"## Input File: '{cleaned_excel_path}'",
                f"## Output Path: '{output_path}'",
                f"## context notes to understand more the excel : '{context_notes}' " , 
                
                "## Critical Rules:",
                "1. If your script fails, fix it and try again until it succeeds",
                "2. to avoid failing ALWAYS inspect the excel file first using pandas"
            ]
        )
        
    def get_plot_agent(self, task: str, context_notes : Path ,  excel_path: Path, output_path: Path) -> Agent:
        return Agent(
            name="plot_agent",
            model=OpenAIChat(self.model_name, temperature=0.0),
            tools=[self.toolset[0], self.toolset[1]],
            structured_outputs=True,
            response_model=PlotResponse,
            instructions=[
                "You are a specialized Data Visualization agent that MUST follow this EXACT two-step process:",
                
                "## STEP 1 (MANDATORY): Write and Execute a Python Script",
                f"First you must inspect the data in '{excel_path}' using pandas to understand its structure, and also {context_notes} to understand the context of the excel, NEVER USE THIS JSON FILE FOR PLOTING IT JUST HELP YOU UNDERSTAND THE CONTEXT OF THE EXCEL FILE, ALWAYS USE THE EXCEL FILE FOR PLOTING",
                f"Then you must write and execute a Python script that creates a Plotly visualization based on the task description.",
                "You MUST use the save_to_file_and_run tool from PythonTools to execute this script BEFORE doing anything else.",
                f"All scripts must be saved here: {self.scripts_path}",

                "For creating plots:",
                "1. Always use Plotly (import plotly.express as px or import plotly.graph_objects as go)",
                "2. Make plots interactive with hover data, tooltips, and proper labels",
                "3. Use appropriate color schemes and layouts",
                "4. Save the plot as an HTML file to maintain interactivity",
                f"5. ALSO export a static image of the same plot (PNG) to the {output_path} folder",
                "6. Your script MUST end with BOTH:",
                f"- fig.write_html('{output_path}/plot_name.html')",
                f"- fig.write_image('{output_path}/plot_name.png')",

                "## STEP 2 (After script execution): Provide Structured Response",
                "ONLY after the Python script has successfully executed, return a PlotResponse with:",
                "- status: 'success'",
                "- summary: A detailed explanation of the visualization",
                "- plot_html: The full path to the saved HTML plot file",
                "- plot_image: The full path to the saved PNG image file",
                "- insight: Key business insights derived from the visualization",

                f"## Your Task: {task}",
                f"## Input File: '{excel_path}'",
                f"## Output Path: '{output_path}'",
                f"## Context notes: '{context_notes}'",

                "## Important Notes:",
                "- Always include appropriate titles, labels, and legends",
                "- Use interactive features like hover data and tooltips",
                "- Choose appropriate colors and chart types for the data",
                "- Focus on making the visualization informative and easy to understand",
                "- If your script fails, fix it and try again until it succeeds",
                "- To avoid failing ALWAYS inspect the Excel file first using pandas"
            ]
        )
        
    def web_image_agent(self, summary_path: Path) :
        return Agent(
            name="ImageFetcher",
            model=OpenAIChat(self.model_name, temperature=0.3),
            tools=[self.toolset[0], self.toolset[1], google_images_search],
            response_model=WebImageWords,
            instructions = [
                "You are a Keyword-Image Specialist Agent.",
                f"Read the summary file at {summary_path} to extract exactly TWO keywords that represent the core meaning of the dataset.",
                "CRUCIAL RULES:",
                "1. Keywords must capture the MAIN THEME and BUSINESS VALUE.",
                "2. Do NOT select raw column names or minor details.",
                "3. For each keyword, create a visual description for image search.",
                "   - Keyword1: symbolic image of the domain (e.g., 'a football ball picture in a stadium').",
                "   - Keyword2: symbolic/conceptual image of the business purpose, **the word itself must appear prominently in the image**, and do NOT depict dashboards, charts, or spreadsheets.",
                "     Instead, use conceptual or thematic imagery (e.g., medical symbols, abstract representations, or objects associated with the domain).",
                "4. Output format must be:",
                "   (Keyword1: visual description, Keyword2: visual description)",
                "   Example: (Football: a football ball picture in a stadium, Sports Analytics: the words 'Sports Analytics' floating above a shadow football player or in a conceptual sports scene)",
                "5. Use google_images_search('Keyword1: visual description, Keyword2: visual description', 2) to fetch 2 images closely matching the prompts."
            ]
        )
    
    def get_data_extractor_agent(self):
        return Agent(
            name="Data_Extractor_Agent",
            model=OpenAIChat(self.model_name, temperature=0.0),
            tools=self.toolset,
            #debug_mode=True,
            instructions=[
                f"You are an Excel analysis agent. Your Excel file is at: {self.excel_path}",
                "Your job is to extract images and charts from the Excel file and save them to folders INSIDE the repo directory.",
                "WORKFLOW - Follow these steps in order:",
                f"1. Call save_to_file_and_run() to create a simple Python script that creates an empty JSON file",
                f"2. Call excel_structure_parser() to analyze the Excel structure (this will use the default excel path)",
                f"3. Call extract_and_analyze_charts_tool() to extract charts (saves to repo/charts/ and results to media.json)",
                f"4. Call extract_and_analyze_images_tool() to extract images (saves to repo/images/ and results to media.json)",
                f"IMPORTANT: All files will be automatically saved inside the repo directory: {self.repo_path}",
                f"- Images will be saved to: {self.repo_path}/images/",
                f"- Charts will be saved to: {self.repo_path}/charts/",
                f"- Analysis results will be saved to: {self.repo_path}/media.json",
                "5. When finished, respond with a brief summary of what was extracted"
            ]
        )

    def get_workspace_agent(self, context_note_path: Path, context_path: Path, repo_path: Path, media_json_path: Path):
        return Agent(
            name="Workspace_Agent",
            model=OpenAIChat(self.model_name, temperature=0.0),
            tools=self.toolset,
            #debug_mode=True,
            instructions=[
                "you are a generale context agent your work is to use save_file_utf8 to create a workspace.json file"
                "this file is used to store all relevant context information for the current workspace"
                "WORKFLOW:"
                "1. use save_file_utf8 to initiate the workspace.json file"
                f"2. use read_file_utf8 to read the context_notes file located at {context_note_path} it contain all the columns analysis, then use save_file_utf8 to save the relevant information to workspace.json",
                f"3. use read_file_utf8 to read the context file located at {context_path} it contain all the anomalies and problems found by the profiler agent, then use save_file_utf8 to append the relevant information to workspace.json",
                f"4. use read_file_utf8 to read the media file located at {media_json_path} it contain all the media information, then use save_file_utf8 to append the relevant information to workspace.json",
                f"5. make sure that the json file is well structured and save it in the {repo_path} folder as workspace.json"
            ]
        )

    def get_report_agent(self, repo_path: Path, charts_path: Path, images_path: Path, workspace_path: Path, context_note_path: Path, queries_path: Path, web_images: Path):
        report_toolset = [read_file_utf8, save_file_utf8, google_images_search, excel_structure_parser, extract_and_analyze_charts_tool, extract_and_analyze_images_tool, analyze_extracted_image_content_tool, compile_latex, escape_latex, proper_write_latex, list_available_visualizations]
        return Agent(
            name="Report_Agent",
            model=OpenAIChat(self.model_name, temperature=0.0),
            tools=report_toolset,
            response_model=ReportResponse,
            #debug_mode=True,
            instructions = [
                "You are an autonomous Excel report-generating agent that creates professional PDF reports.",
                "Your job is to create a professional PDF report based exactly on the user's request, no more, no less.",
                f"You will find all necessary data in the {repo_path} folder, which contains:",
                "- Excel files (original and cleaned)",
                "- A summary of findings (summary.txt)",
                "- Analysis results (context.json, context_notes.txt)",  
                "- Charts and plots (in charts/ and plots/ folders)",
                "- Query results (in queries/ folder)",
                "- Images and visualizations (in images/ folder)",
                "- Important images to always add (in web_images/ folder)",
                "- Workspace data (workspace.json)",
                "Before generating, determine: does the user want a FULL report or only specific information?",
                "RULES:",
                "- If the user wants a FULL report: write a detailed report of at least 1000 words, covering all available data, charts, and images.",
                "- If the user asks for SPECIFIC information: only include that information. Keep it concise and exclude unrelated data.",
                "WORKFLOW:",
                "1. First, read the workspace.json and context_notes.txt files to understand the data context",
                "2. Use list_available_visualizations tool to see all available plots, charts, and images",
                f"3. PRIORITY: Include existing plots from {repo_path}/plots folder in the report",
                f"4. Include any extracted images from {images_path} folder and {web_images} folder",
                "5. Create a comprehensive LaTeX report using proper_write_latex tool with filename 'report.tex'",
                "6. ALWAYS include available plots using \\includegraphics commands in LaTeX",
                "7. ALWAYS start with a summary that contain the same text in the {summary_path} file",
                "8. Use escape_latex tool to properly escape any text from JSON files before inserting into LaTeX",
                f"9. Compile the report using compile_latex('report.tex') to generate PDF in {repo_path}",
                "",
                "IMPORTANT - PLOT INCLUSION:",
                f"- Always use list_available_visualizations() tool first to get exact filenames",
                "- Include PNG files using \\includegraphics in LaTeX",
                "- Use the EXACT filenames returned by the tool (e.g., product_quantity.png, not product_quantities.png)",
                "- Do NOT rely solely on chart extraction tools - use existing plots",
                "- If chart extraction fails, still proceed with available plots and data",
                "",
                "REPORT STRUCTURE:",
                "- Title: 'Product Quantity Analysis Report'",
                "- Executive Summary",
                "- Data Overview and Context", 
                "- Detailed Analysis with Charts/Plots (ALWAYS include existing plots)",
                "- Key Findings and Insights",
                "- Conclusions and Recommendations",
                "",
                "RESPONSE FORMAT:",
                "You must return a structured response with:",
                "- status: 'success' if report generated successfully, 'failure' if any errors occurred",
                "- summary: Brief description of what was included in the report",
                f"- report_path: Full path to the generated PDF file (should be {repo_path}/report.pdf)",
                "- content_overview: List what visualizations and analysis were included",
                "",
                "ERROR HANDLING:",
                "- If chart extraction tools fail, continue with existing plots from plots/ folder",
                "- If any files are missing, continue with available data and note in summary",
                "- If LaTeX compilation fails, return status='failure' with error details",
                "- Always provide meaningful feedback about what succeeded or failed"
            ]
        )
    
    def get_summary_agent(self, repo_path: Path, excel_path: Path, profiler_notes_path: Path, workspace_path: Path):
        return Agent(
            name="Summary_Agent",
            model=OpenAIChat(self.model_name, temperature=0.4),
            tools=self.toolset,
            response_model=SummaryResponse,
            #debug_mode=True,
            instructions = [
                "You are an autonomous Summarization Specialist agent that creates a deep and narrative-style summary from the analyses done earlier.",
                "Your job is to read all the content you will find in the {repo_path} to understand the exact content of the Excel file.",
                f"Start by reading the {excel_path} file and then focus more on those two files: {profiler_notes_path} and {workspace_path}.",
                "Write the output as ONE long, flowing paragraph, like an executive summary. Do NOT use bullet points, headers, or markdown formatting.",
                "The paragraph must describe: the most relevant sheet (name, rows, columns, and main purpose), the important columns and what they represent, any anomalies or trends, the presence of images/charts and what they illustrate, and finally why the file is important and how it can be valuable if improved with more consistent data.",
                "Save this narrative summary in a txt file named 'summary.txt' inside {repo_path}.",
                "never stop improving, and never use the files name so instead of saying 'the food_sale excel' just say 'the excel file'",
                "RESPONSE FORMAT:",
                "- status: 'success' if summary.txt file was generated successfully, 'failure' if any errors occurred",
                f"- summary_path: Full path to the generated summary file (should be {summary_path})",
            ]
        )

    def get_delivery_agent(self, query: str, repo_path: Path, excel_path: Path, profiler_notes_path: Path, workspace_path: Path):
        return Agent(
            name="delivery_Agent",
            model=OpenAIChat(self.model_name, temperature=0.0),
            response_model=DeliveryResponse,
            #debug_mode=True,
            instructions = [
                "You are a delivery agent that deliver the correct output to the user from a repo folder",
                f"you will find all the files and folder in the {repo_path}",
                f"1.your work is the read the user {query} and know wich file to deliver to the user",
                f"2.if the user {query} is about:",
                f"cleaning -> select {cleaned_excel}",
                f"summaries -> select {summary_path}",
                f"creating a pdf report -> select {report_path}",
                f"whenever the user asks for report and add something focus just on the report and selecty {report_path}",
                f"plots requested by the user -> select {plot_output_path}", 
                f"quering on the excel file, aggregating, doing analytical operations on the excel -> select {queries_path}",              
                "3.put the path of the selected file or folder in chosen_path"
            ]
        )