import sys, os, shutil, time, gc, logging, uvicorn, glob
from pathlib import Path
from dotenv import load_dotenv
from agents.agents import AgentManager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import dashboard, upload, download, streaming
from core.Structured_Output import OrchestratorDecision, CleanerResponse, FilterResponse, PlotResponse, ReportResponse, SummaryResponse
from core.Yielding import log_agent_message, clear_agent_logs

from core.paths import (
    excel_path, context_path, profiler_notes_path, review_notes_path, cleaned_excel,
    repo_path, media_json_path, workspace_path, summary_path, todo, output_path,
    filter_output_path, plot_output_path, images_path, queries_path, report_path)

load_dotenv()
key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = key
manager = AgentManager("gpt-4o")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_preprocessing(manager):
    log_agent_message("Data extraction started")
    extractor = manager.get_data_extractor_agent()
    extractor.run()
    log_agent_message("✅ All Data extracted successfully")

    log_agent_message("Scouting the excel file...")
    scout = manager.get_scout_agent()
    scout_response = scout.run(f"Run the initial data scout on '{excel_path}' and save the report to '{context_path}'.")
    log_agent_message(f"✅ Scouting is finished.")

    log_agent_message("Understanding excel file...")
    profiler = manager.get_profiler_agent()
    profiler_response = profiler.run(f"Analyze the data in '{excel_path}' to understand its business context and save your findings to '{profiler_notes_path}'.")
    log_agent_message(f"✅ Understanding is finished.")

    log_agent_message("Analysing excel file...")
    analyst = manager.get_analyst_agent()
    analyst_response = analyst.run(f"Read the scout report from 'context.json' and the profiler notes from 'context_notes.txt'. Then, perform a deeper analysis on the file at {excel_path} and update the report at {context_path} with all findings.")
    log_agent_message("✅ Analysing has been completed.")

    log_agent_message("Reviewing the preprocessing analysis...")
    reviewer = manager.get_preprocessing_reviewer_agent()
    reviewer_response = reviewer.run(f"Review the JSON report at 'context.json' for logical errors and save your findings to '{review_notes_path}'.")
    log_agent_message("✅ Review Complete")

    log_agent_message("Correcting analysis...")
    if review_notes_path.exists() and review_notes_path.stat().st_size > 0:
        correction_response = analyst.run(f"A review of your previous work has been completed. The notes are in 'review_notes.txt'. Please read the notes and correct the JSON report at 'context.json' accordingly.")
        log_agent_message("✅ Full Inspection and Correction Completed")
    else:
        log_agent_message("❌ No review notes found or review notes were empty. The report is considered final.")

    workspace = manager.get_workspace_agent(context_note_path=profiler_notes_path, context_path=context_path, repo_path=repo_path, media_json_path=media_json_path)
    workspace.run()

    summary_exist = False
    while not summary_exist:
        summary_agent = manager.get_summary_agent(repo_path=repo_path, excel_path=excel_path, profiler_notes_path=profiler_notes_path, workspace_path=workspace_path)
        summary_response = summary_agent.run()
        if os.path.isfile(summary_path):
            summary_exist = True
            log_agent_message("✅ The Preprocessing is Done\n")
        log_agent_message("Creating summary...\n")
        
def run_agents(query, manager, decision):
    clear_agent_logs()
    log_agent_message(f"🎯 Agent to call: {decision.agent_to_call}")
    
    orchestrator = manager.get_orchestrator_agent(todo=todo)
    
    if decision.agent_to_call == 'cleaner':
        log_agent_message("\n⏱ Cleaning ...")
        cleaner = manager.get_cleaner_agent(task=decision.task_to_perform, query=query, context_json=context_path, context_notes=profiler_notes_path, excel_path=excel_path, cleaned_path=cleaned_excel)
        if cleaned_excel.exists():
            try:
                os.remove(cleaned_excel)
            except Exception as e:
                log_agent_message(f"❌ Warning: Could not remove existing cleaned file: {e}")
        cleaning_response = cleaner.run()
        
        if isinstance(cleaning_response.content, CleanerResponse) and cleaning_response.content.status == "success":
            if os.path.isfile(cleaned_excel):
                log_agent_message(f"✅ cleaning finished successfully.")
                log_agent_message(f"Summary : {cleaning_response.content.summary}")
                orchestrator.run(f"✅ the task '{decision.task_to_perform}' has been completed successfully. Summary: {cleaning_response.content.summary}")
            else:
                log_agent_message(f"❌ cleaning reported success but cleaned file does not exist at: {cleaned_excel} !!!")
                log_agent_message("❌ Halting workflow due to file verification failure. !!!")
                return False
        else:
            log_agent_message("❌ cleaning failed or returned an unexpected response. Halting workflow. !!!")
            log_agent_message(f"Received: {cleaning_response.content}")
            return False
    elif decision.agent_to_call == 'filter':
        log_agent_message("\n⏱ filtering the excel file ...")
        filter_agent = manager.get_filter_agent(context_notes=profiler_notes_path, task=decision.task_to_perform, cleaned_excel_path=cleaned_excel, output_path=filter_output_path)
        filter_response = filter_agent.run()
        
        if isinstance(filter_response.content, FilterResponse) and filter_response.content.status == "success":
            patterns = ["*.csv", "*.xlsx", "*.xls", "*.txt"]
            if any(glob.glob(os.path.join(queries_path, pattern)) for pattern in patterns):
                log_agent_message(f"✅ filtering has been finished successfully.")
                log_agent_message(f"Summary: {filter_response.content.summary}")
                orchestrator.run(f"✅ The task '{decision.task_to_perform}' has been completed successfully. Summary: {filter_response.content.summary}")
            else:
                log_agent_message(f"❌ filtering task reported success but output file does not exist at: {queries_path} !!!")
                log_agent_message("❌ Halting workflow due to file verification failure. !!!")
                return False
        else:
            log_agent_message("❌ filtering failed or returned an unexpected response. Halting workflow. !!!")
            log_agent_message(f"Received: {filter_response.content}")
            return False
    elif decision.agent_to_call == 'plot':
        log_agent_message("\n⏱ Ploting the user request ...")
        plot_agent = manager.get_plot_agent(context_notes=profiler_notes_path, task=decision.task_to_perform, excel_path=cleaned_excel, output_path=plot_output_path)
        plot_response = plot_agent.run()
        
        if isinstance(plot_response.content, PlotResponse) and plot_response.content.status == "success":
            if glob.glob(os.path.join(plot_output_path, "*.html")):
                log_agent_message(f"✅ Plotting finished successfully.")
                log_agent_message(f"Summary: {plot_response.content.summary}")
                orchestrator.run(f"✅ The task '{decision.task_to_perform}' has been completed successfully. Summary: {plot_response.content.summary}")
                log_agent_message("📊 you can access your plots at: http://localhost:8001")
            else:
                log_agent_message(f"❌ Plotting reported success but plot file does not exist at: {plot_output_path} !!!")
                log_agent_message("❌ Halting workflow due to file verification failure. !!!")
                return False
        else:
            log_agent_message("❌ Plotting failed or returned an unexpected response. Halting workflow. !!!")
            log_agent_message(f"Received: {plot_response.content}")
            return False
    elif decision.agent_to_call == 'summary':
        log_agent_message("\n⏱ Summarizing please wait ...")
        summary_agent = manager.get_summary_agent(repo_path=repo_path, excel_path=excel_path, profiler_notes_path=profiler_notes_path, workspace_path=workspace_path)
        summary_response = summary_agent.run()
        
        if isinstance(summary_response.content, SummaryResponse) and summary_response.content.status == "success":
            if os.path.isfile(summary_path):
                log_agent_message(f"✅ Summarizing finished successfully.")
                orchestrator.run(f"✅ The task '{decision.task_to_perform}' has been completed successfully.")
            else:
                log_agent_message(f"❌ Summarising reported success but summary file does not exist at: {summary_path} !!!")
                log_agent_message("❌ Halting workflow due to file verification failure. !!!")
                return False
        else:
            log_agent_message("❌ Summarising failed or returned an unexpected response. Halting workflow. !!!")
            log_agent_message(f"Received: {summary_response.content}")
            return False

    # THE REPORTER AGENT
    elif decision.agent_to_call == 'reporter':      
        log_agent_message("\n⏱ The Report is being generated please wait ...")
        report_agent = manager.get_report_agent(repo_path=repo_path, images_path=images_path)
        report_response = report_agent.run()
        
        if isinstance(report_response.content, ReportResponse) and report_response.content.status == "success":
            if os.path.isfile(report_path):
                log_agent_message(f"✅ Report finished successfully.")
                log_agent_message(f"Summary: {report_response.content.summary}")
                log_agent_message(f"Content overview: {report_response.content.content_overview}")
                orchestrator.run(f"✅ The task '{decision.task_to_perform}' has been completed successfully. Report generated at {report_path}")
            else:
                log_agent_message(f"❌ Report reported success but report file does not exist at: {report_path} !!!")
                log_agent_message("❌ Halting workflow due to file verification failure. !!!")
                return False
        else:
            log_agent_message("❌ Report failed or returned an unexpected response. Halting workflow. !!!")
            log_agent_message(f"Received: {report_response.content}")
            return False
    
    elif decision.agent_to_call == 'complete':
        log_agent_message("✅ All agents completed successfully. Workflow finished.")
        return True
    
    else:
        log_agent_message(f"❌ Unknown agent: {decision.agent_to_call}")
        return False
    
    return True

def main_function(query: str):
    final_message = ""
    
    log_agent_message("⏱ Preprocessing ...")
    run_preprocessing(manager)

    log_agent_message("⏱ Planning steps ...")
    planner = manager.get_planner_agent(query=query, todo=todo).run()
    log_agent_message("✅The plan has been created succefully ,  You can follow the steps of my plan in the Task Progress section\n⏱ Running first step ...")
    orchestrator = manager.get_orchestrator_agent(todo=todo)
    
    while True:
        decision_response = orchestrator.run("Read the todo.md file and decide the next step.")
        
        if not isinstance(decision_response.content, OrchestratorDecision):
            log_agent_message(f"❌ failed to make a valid decision. Halting.\nReceived: {decision_response.content}")
            break
            
        decision = decision_response.content
        
        if decision.agent_to_call == 'complete':
            log_agent_message("✅ All tasks are complete. Workflow finished.")
            break
        else:
            agent_success = run_agents(query, manager, decision)
            if not agent_success:
                log_agent_message("❌ Agent execution failed.")

    log_agent_message("⏱ The output is being generated...")
    delivery_agent = manager.get_delivery_agent(query=query, repo_path=repo_path, excel_path=excel_path, profiler_notes_path=profiler_notes_path, workspace_path=workspace_path).run()
    output = delivery_agent.content.chosen_path
    clickable_link = getattr(delivery_agent.content, 'clickable_link', '')

    gc.collect()
    time.sleep(1)

    log_agent_message("⏱ one more second...")
    try:
        final = "output"; os.makedirs(final, exist_ok=True)
        shutil.copy(output, final) if os.path.isfile(output) else shutil.copytree(output, os.path.join(final, os.path.basename(output)), dirs_exist_ok=True)
        
        output_dir_path = Path(final)
        html_files = list(output_dir_path.glob('*.html'))
        
        if os.path.exists(repo_path): shutil.rmtree(repo_path)
    except FileNotFoundError as e:
        log_agent_message(f"❌ PeaQock Manus failed, File not found: {e}")
        final_message = f"❌ Error: File not found - {e}"
    except Exception as e:
        log_agent_message(f"❌ Error copying output: {e}")
        final_message = f"❌ Error copying output: {e}"
    
    return final_message if final_message else "✅ Task completed successfully!"

# Import routers
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("peaqock_api")

app = FastAPI(title="PeaQock Manus API", description="API for PeaQock_Manus Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Include routers
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(upload.router, tags=["upload"])
app.include_router(download.router, tags=["download"])  
app.include_router(streaming.router, tags=["streaming"])

if output_path.exists():
    try:
        shutil.rmtree(output_path)
        logger.info("Cleaned output folder on startup")
    except PermissionError:
        logger.warning("Could not clean output folder - in use by another process")
    except Exception as e:
        logger.warning(f"Could not clean output folder: {e}")

if __name__ == "__main__":
    print("API server starting at http://127.0.0.1:8000/")
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)
    