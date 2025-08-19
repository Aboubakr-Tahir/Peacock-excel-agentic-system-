import os, glob
from config import excel_path, context_path, profiler_notes_path, todo, cleaned_excel, filter_output_path, plot_output_path, repo_path, charts_path, images_path, workspace_path, queries_path, summary_path, web_images, report_path
from config import CleanerResponse, FilterResponse, PlotResponse, ReportResponse, SummaryResponse


def run_agents(query, manager, decision):
    orchestrator = manager.get_orchestrator_agent(todo=todo)
    
    # THE CLEANER AGENT
    if decision.agent_to_call == 'cleaner':
        print("\n--- Running Cleaner Agent (with Reviewer) ...")
        cleaner = manager.get_cleaner_agent(task=decision.task_to_perform, query=query, context_json=context_path, context_notes=profiler_notes_path, excel_path=excel_path, cleaned_path=cleaned_excel)
        if cleaned_excel.exists():
            try:
                os.remove(cleaned_excel)
                print("Removed existing cleaned file to verify agent creates a new one.")
            except Exception as e:
                print(f"Warning: Could not remove existing cleaned file: {e}")
        cleaning_response = cleaner.run()
        if isinstance(cleaning_response.content, CleanerResponse) and cleaning_response.content.status == "success":
            # Verify the cleaned file actually exists
            if os.path.isfile(cleaned_excel):
                print(f"cleaner agent finished successfully.")
                print(f"Summary : {cleaning_response.content.summary}")
                print(f"cleaned excel saved to : {cleaned_excel}")
                orchestrator.run(f"the task '{decision.task_to_perform}' has been completed successfully. Summary: {cleaning_response.content.summary}")
            else:
                print(f"!!! cleaner Agent reported success but cleaned file does not exist at: {cleaned_excel} !!!")
                print("!!! Halting workflow due to file verification failure. !!!")
                return False
        else:
            print("!!! cleaner Agent failed or returned an unexpected response. Halting workflow. !!!")
            print(f"Received: {cleaning_response.content}")
            return False

    # THE FILTER AGENT   
    elif decision.agent_to_call == 'filter':
        print("\n--- Running filter Agent ...")
        filter_agent = manager.get_filter_agent(context_notes=profiler_notes_path, task=decision.task_to_perform, cleaned_excel_path=cleaned_excel, output_path= filter_output_path)
        filter_response = filter_agent.run()
        if isinstance(filter_response.content, FilterResponse) and filter_response.content.status == "success":
            # Verify the filter output file exists
            patterns = ["*.csv", "*.xlsx", "*.xls", "*.txt"]
            if any(glob.glob(os.path.join(queries_path, pattern)) for pattern in patterns):
                print(f"filter Agent finished successfully.")
                print(f"Summary: {filter_response.content.summary}")
                print(f"filter file saved to: {queries_path}")
                orchestrator.run(f"The task '{decision.task_to_perform}' has been completed successfully. Summary: {filter_response.content.summary}")
            else:
                print(f"!!! filter Agent reported success but output file does not exist at: {queries_path} !!!")
                print("!!! Halting workflow due to file verification failure. !!!")
                return False
        else:
            print("!!! filter Agent failed or returned an unexpected response. Halting workflow. !!!")
            print(f"Received: {filter_response.content}")
            return False
            
    # THE PLOT AGENT
    elif decision.agent_to_call == 'plot':
        print("\n--- Running Plot Agent ...")
        plot_agent = manager.get_plot_agent(context_notes=profiler_notes_path, task=decision.task_to_perform, excel_path=cleaned_excel, output_path=plot_output_path)
        plot_response = plot_agent.run()
        if isinstance(plot_response.content, PlotResponse) and plot_response.content.status == "success":
            # Verify the plot file exists
            if glob.glob(os.path.join(plot_output_path, "*.html")):
                print(f"Plot Agent finished successfully.")
                print(f"Summary: {plot_response.content.summary}")
                print(f"Plot saved to: {plot_output_path}")
                orchestrator.run(f"The task '{decision.task_to_perform}' has been completed successfully. Summary: {plot_response.content.summary}")
            else:
                print(f"!!! Plot Agent reported success but plot file does not exist at: {plot_output_path} !!!")
                print("!!! Halting workflow due to file verification failure. !!!")
                return False
        else:
            print("!!! Plot Agent failed or returned an unexpected response. Halting workflow. !!!")
            print(f"Received: {plot_response.content}")
            return False
            
    # THE SUMMARY AGENT
    elif decision.agent_to_call == 'summary':
        print("\n--- Running Summary Agent ...")
        summary_agent = manager.get_summary_agent(repo_path=repo_path, excel_path=excel_path, profiler_notes_path=profiler_notes_path, workspace_path=workspace_path)
        summary_response = summary_agent.run()
        if isinstance(summary_response.content, SummaryResponse) and summary_response.content.status == "success":
            # Verify the summary file exists
            if os.path.isfile(summary_path):
                print(f"Summary Agent finished successfully.")
                orchestrator.run(f"The task '{decision.task_to_perform}' has been completed successfully.")
            else:
                print(f"!!! Summary Agent reported success but summary file does not exist at: {summary_path} !!!")
                print("!!! Halting workflow due to file verification failure. !!!")
                return False
        else:
            print("!!! Summary Agent failed or returned an unexpected response. Halting workflow. !!!")
            print(f"Received: {summary_response.content}")
            return False

    # THE REPORTER AGENT
    elif decision.agent_to_call == 'reporter':      
        # print("\n--- illustrating the Report ...")
        # manager.web_image_agent(summary_path=summary_path).run()
        print("\n--- The Report is being generated by the Report Agent ...")
        report_agent = manager.get_report_agent(repo_path=repo_path, images_path=images_path)
        report_response = report_agent.run()
        if isinstance(report_response.content, ReportResponse) and report_response.content.status == "success":
            # Verify the report file exists
            if os.path.isfile(report_path):
                print(f"Report Agent finished successfully.")
                print(f"Summary: {report_response.content.summary}")
                print(f"Report saved to: {report_path}")
                print(f"Content overview: {report_response.content.content_overview}")
                orchestrator.run(f"The task '{decision.task_to_perform}' has been completed successfully. Report generated at {report_path}")
            else:
                print(f"!!! Report Agent reported success but report file does not exist at: {report_path} !!!")
                print("!!! Halting workflow due to file verification failure. !!!")
                return False
        else:
            print("!!! Report Agent failed or returned an unexpected response. Halting workflow. !!!")
            print(f"Received: {report_response.content}")
            return False
    
    elif decision.agent_to_call == 'complete':
        print("All agents completed successfully. Workflow finished.")
        return True
    
    else:
        print(f"Unknown agent: {decision.agent_to_call}")
        return False
    
    return True
