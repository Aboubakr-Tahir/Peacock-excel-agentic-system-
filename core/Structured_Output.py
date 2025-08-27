from pydantic import BaseModel, Field

class OrchestratorDecision(BaseModel):
    """The decision made by the orchestrator on which agent to run next."""
    agent_to_call: str = Field(..., description="The name of the agent to call next from the available list: 'cleaner', 'filter', 'plot', 'summary', 'reporter'. If no task is left, return 'complete'.")
    task_to_perform: str = Field(..., description="The specific high-level task for the chosen agent to execute.")
    reasoning: str = Field(..., description="A brief justification for choosing this agent for this task.")

class CleanerResponse(BaseModel):
    """The structured output from the Cleaner Agent after processing the data."""
    status: str = Field(..., description="The status of the cleaning operation used by Python tools to clean the excel with a python script, either 'success' or 'failure'.")
    summary: str = Field(..., description="A human-readable summary of all the cleaning actions that were performed using pythontools.")

class FilterResponse(BaseModel):
    status: str = Field(..., description="The status of the filtering/querying operation used by Python tools to query the excel with a python script, either 'success' or 'failure'.")
    summary: str = Field(..., description="A human-readable summary of all the filtering/querying actions that were performed using python tools.")
    result: str = Field(..., description="Key numbers, counts, or findings from the filtering operation")
    output_path: str = Field(..., description="absolute path where you outputted the filtered file")

class PlotResponse(BaseModel):
    status: str = Field(..., description="The status of the plotting operation ('success' or 'failure').")
    summary: str = Field(..., description="A human-readable summary of the visualization created.")
    plot_html: str = Field(..., description="The absolute path where the interactive HTML plot file was saved.")
    plot_image: str = Field(..., description="The absolute path where the static image (PNG) plot file was saved.")
    insight: str = Field(..., description="Business insights derived from the visualization.")

class WebImageWords(BaseModel):
    chosen_words: str = Field(..., description="The two most important words about the excel file like that: (keyword1: detailed explanation in the context, keyword2: detailed explanation in the context)")

class ReportResponse(BaseModel):
    """The structured output from the Report Agent after generating a report."""
    status: str = Field(..., description="The status of the report generation operation, either 'success' or 'failure'.")
    summary: str = Field(..., description="A human-readable summary of the report generation process and what was included.")
    report_path: str = Field(..., description="The absolute path where the PDF report was saved.")
    content_overview: str = Field(..., description="Brief overview of what content was included in the report (charts, analysis, etc.).")

class SummaryResponse(BaseModel):
    """The structured output from the Summary Agent after generating a summary."""
    status: str = Field(..., description="The status of the summary generation operation, either 'success' or 'failure'.")
    summary_path: str = Field(..., description="The absolute path where the summary file was saved.")
    
class DeliveryResponse(BaseModel):
    """The structured output from the Delivery Agent after selecting the correct file."""
    status: str = Field(..., description="The status of the correct file selecting, either 'success' or 'failure'.")
    chosen_path: str = Field(..., description="The absolute path to the chosen file.")
    clickable_link: str = Field(default="", description="If applicable, a clickable link to access the content (for plots, this would be the server URL).")
