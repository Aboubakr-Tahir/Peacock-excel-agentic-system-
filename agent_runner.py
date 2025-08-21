import os, glob
from config import excel_path, context_path, profiler_notes_path, todo, cleaned_excel, filter_output_path, plot_output_path, repo_path, charts_path, images_path, workspace_path, queries_path, summary_path, web_images, report_path, agent_logs
from config import CleanerResponse, FilterResponse, PlotResponse, ReportResponse, SummaryResponse
import time

def log_agent_message(message):
    """Write a message to both console and agent logs file"""
    print(message)
    try:
        # Ensure the directory exists
        agent_logs.parent.mkdir(parents=True, exist_ok=True)
        
        with open(agent_logs, 'a', encoding='utf-8', buffering=1) as f:  # Line buffering
            timestamp = time.strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}\n"
            f.write(log_entry)
            f.flush()  # Force write to disk
            os.fsync(f.fileno())  # Force OS to write to disk
            
        # Small delay to ensure file system updates
        time.sleep(0.1)
    except Exception as e:
        print(f"Warning: Could not write to agent logs: {e}")

def clear_agent_logs():
    """Clear the agent logs file at the start of a new workflow"""
    try:
        # Ensure the directory exists
        agent_logs.parent.mkdir(parents=True, exist_ok=True)
        
        with open(agent_logs, 'w', encoding='utf-8') as f:
            f.write("")  # Clear the file
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print(f"Warning: Could not clear agent logs: {e}")


def run_agents(query, manager, decision):
    # Clear logs at the start of a new workflow
    clear_agent_logs()
    
    # Add initial log message to test the system
    log_agent_message("🚀 Starting agent workflow...")
    log_agent_message(f"🎯 Agent to call: {decision.agent_to_call}")
    
    orchestrator = manager.get_orchestrator_agent(todo=todo)
    
    # THE CLEANER AGENT
    if decision.agent_to_call == 'cleaner':
        log_agent_message("\n⏱ Running Cleaner Agent ...")
        cleaner = manager.get_cleaner_agent(task=decision.task_to_perform, query=query, context_json=context_path, context_notes=profiler_notes_path, excel_path=excel_path, cleaned_path=cleaned_excel)
        if cleaned_excel.exists():
            try:
                os.remove(cleaned_excel)
                log_agent_message("Removed existing cleaned file to verify agent creates a new one.")
            except Exception as e:
                log_agent_message(f"❌ Warning: Could not remove existing cleaned file: {e}")
        cleaning_response = cleaner.run()
        if isinstance(cleaning_response.content, CleanerResponse) and cleaning_response.content.status == "success":
            # Verify the cleaned file actually exists
            if os.path.isfile(cleaned_excel):
                log_agent_message(f"✅ cleaner agent finished successfully.")
                log_agent_message(f"Summary : {cleaning_response.content.summary}")
                orchestrator.run(f"✅ the task '{decision.task_to_perform}' has been completed successfully. Summary: {cleaning_response.content.summary}")
            else:
                log_agent_message(f"❌ cleaner Agent reported success but cleaned file does not exist at: {cleaned_excel} !!!")
                log_agent_message("❌ Halting workflow due to file verification failure. !!!")
                return False
        else:
            log_agent_message("❌ cleaner Agent failed or returned an unexpected response. Halting workflow. !!!")
            log_agent_message(f"Received: {cleaning_response.content}")
            return False

    # THE FILTER AGENT   
    elif decision.agent_to_call == 'filter':
        log_agent_message("\n⏱ Running filter Agent ...")
        filter_agent = manager.get_filter_agent(context_notes=profiler_notes_path, task=decision.task_to_perform, cleaned_excel_path=cleaned_excel, output_path=filter_output_path)
        filter_response = filter_agent.run()
        if isinstance(filter_response.content, FilterResponse) and filter_response.content.status == "success":
            # Verify the filter output file exists
            patterns = ["*.csv", "*.xlsx", "*.xls", "*.txt"]
            if any(glob.glob(os.path.join(queries_path, pattern)) for pattern in patterns):
                log_agent_message(f"✅ filter Agent finished successfully.")
                log_agent_message(f"Summary: {filter_response.content.summary}")
                orchestrator.run(f"✅ The task '{decision.task_to_perform}' has been completed successfully. Summary: {filter_response.content.summary}")
            else:
                log_agent_message(f"❌ filter Agent reported success but output file does not exist at: {queries_path} !!!")
                log_agent_message("❌ Halting workflow due to file verification failure. !!!")
                return False
        else:
            log_agent_message("❌ filter Agent failed or returned an unexpected response. Halting workflow. !!!")
            log_agent_message(f"Received: {filter_response.content}")
            return False
            
    # THE PLOT AGENT
    elif decision.agent_to_call == 'plot':
        log_agent_message("\n⏱ Running Plot Agent ...")
        plot_agent = manager.get_plot_agent(context_notes=profiler_notes_path, task=decision.task_to_perform, excel_path=cleaned_excel, output_path=plot_output_path)
        plot_response = plot_agent.run()
        if isinstance(plot_response.content, PlotResponse) and plot_response.content.status == "success":
            # Verify the plot file exists
            if glob.glob(os.path.join(plot_output_path, "*.html")):
                log_agent_message(f"✅ Plot Agent finished successfully.")
                log_agent_message(f"Summary: {plot_response.content.summary}")
                orchestrator.run(f"✅ The task '{decision.task_to_perform}' has been completed successfully. Summary: {plot_response.content.summary}")
            else:
                log_agent_message(f"❌ Plot Agent reported success but plot file does not exist at: {plot_output_path} !!!")
                log_agent_message("❌ Halting workflow due to file verification failure. !!!")
                return False
        else:
            log_agent_message("❌ Plot Agent failed or returned an unexpected response. Halting workflow. !!!")
            log_agent_message(f"Received: {plot_response.content}")
            return False
            
    # THE SUMMARY AGENT
    elif decision.agent_to_call == 'summary':
        log_agent_message("\n⏱ Running Summary Agent ...")
        summary_agent = manager.get_summary_agent(repo_path=repo_path, excel_path=excel_path, profiler_notes_path=profiler_notes_path, workspace_path=workspace_path)
        summary_response = summary_agent.run()
        if isinstance(summary_response.content, SummaryResponse) and summary_response.content.status == "success":
            # Verify the summary file exists
            if os.path.isfile(summary_path):
                log_agent_message(f"✅ Summary Agent finished successfully.")
                orchestrator.run(f"✅ The task '{decision.task_to_perform}' has been completed successfully.")
            else:
                log_agent_message(f"❌ Summary Agent reported success but summary file does not exist at: {summary_path} !!!")
                log_agent_message("❌ Halting workflow due to file verification failure. !!!")
                return False
        else:
            log_agent_message("❌ Summary Agent failed or returned an unexpected response. Halting workflow. !!!")
            log_agent_message(f"Received: {summary_response.content}")
            return False

    # THE REPORTER AGENT
    elif decision.agent_to_call == 'reporter':      
        # log_agent_message("\n--- illustrating the Report ...")
        # manager.web_image_agent(summary_path=summary_path).run()
        log_agent_message("\n⏱ The Report is being generated by the Report Agent ...")
        report_agent = manager.get_report_agent(repo_path=repo_path, images_path=images_path)
        report_response = report_agent.run()
        if isinstance(report_response.content, ReportResponse) and report_response.content.status == "success":
            # Verify the report file exists
            if os.path.isfile(report_path):
                log_agent_message(f"✅ Report Agent finished successfully.")
                log_agent_message(f"Summary: {report_response.content.summary}")
                log_agent_message(f"Content overview: {report_response.content.content_overview}")
                orchestrator.run(f"✅ The task '{decision.task_to_perform}' has been completed successfully. Report generated at {report_path}")
            else:
                log_agent_message(f"❌ Report Agent reported success but report file does not exist at: {report_path} !!!")
                log_agent_message("❌ Halting workflow due to file verification failure. !!!")
                return False
        else:
            log_agent_message("❌ Report Agent failed or returned an unexpected response. Halting workflow. !!!")
            log_agent_message(f"Received: {report_response.content}")
            return False
    
    elif decision.agent_to_call == 'complete':
        log_agent_message("✅ All agents completed successfully. Workflow finished.")
        return True
    
    else:
        log_agent_message(f"❌ Unknown agent: {decision.agent_to_call}")
        return False
    
    return True
