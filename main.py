import sys, os, shutil, time, gc
from pathlib import Path
from dotenv import load_dotenv
from agents import AgentManager
from config import OrchestratorDecision, todo ,repo_path, excel_path, profiler_notes_path, workspace_path, output_path
from PreProcessing import run_preprocessing
from agent_runner import log_agent_message, run_agents
from plot_config import (start_plot_server_for_output, create_plot_viewer_html, get_plot_server_url,  get_success_message, get_fallback_message)

load_dotenv()
key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = key
manager = AgentManager("gpt-4o")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main_function(query: str):
    final_message = ""
    
    log_agent_message("⏱ Preprocessing ...")
    run_preprocessing(manager)

    log_agent_message("⏱ Running Planner Agent: creating todo.md ...")
    planner = manager.get_planner_agent(query=query, todo=todo).run()
    log_agent_message("✅ Planner Agent finished You can follow the steps of my plan in the Task Progress section\n⏱ Orchestrator is now running the plan ...")
    orchestrator = manager.get_orchestrator_agent(todo=todo)
    
    while True:
        log_agent_message("⏱ Orchestrator is deciding the next step ...")
        decision_response = orchestrator.run("Read the todo.md file and decide the next step.")
        if not isinstance(decision_response.content, OrchestratorDecision):
            log_agent_message(f"❌ Orchestrator failed to make a valid decision. Halting.\nReceived: {decision_response.content}")
            break
        decision = decision_response.content
        if decision.agent_to_call == 'complete':
            log_agent_message("✅ All tasks are complete. Workflow finished.")
            break
        else:
            log_agent_message(f"Orchestrator Decision: Call agent '{decision.agent_to_call}' for task: '{decision.task_to_perform}'")
            log_agent_message(f"Reasoning: {decision.reasoning}")
            agent_success = run_agents(query, manager, decision)
            if not agent_success:
                log_agent_message("❌ Agent execution failed.")

    log_agent_message("⏱ The output is being generated...")
    delivery_agent = manager.get_delivery_agent(query=query, repo_path=repo_path, excel_path=excel_path, profiler_notes_path=profiler_notes_path, workspace_path=workspace_path).run()
    output = delivery_agent.content.chosen_path
    clickable_link = getattr(delivery_agent.content, 'clickable_link', '')

    gc.collect() # Force garbage collection to release any file handles
    time.sleep(1)  # Brief pause to ensure files are released

    log_agent_message("⏱ one more second...")
    try:
        final = "output"; os.makedirs(final, exist_ok=True)
        shutil.copy(output, final) if os.path.isfile(output) else shutil.copytree(output, os.path.join(final, os.path.basename(output)), dirs_exist_ok=True)
        
        # Check if plots were generated and start server if needed
        output_dir_path = Path(final)
        html_files = list(output_dir_path.glob('*.html'))
        
        if html_files:
            # Start the plot server silently in background
            try:
                server_started = start_plot_server_for_output(final, auto_open=False)
                if server_started and clickable_link:
                    # Use the delivery agent's provided link
                    final_message = get_success_message(clickable_link)
                    log_agent_message(final_message)
                elif server_started:
                    # Default server link
                    final_message = get_success_message()
                    log_agent_message(final_message)
                else:
                    # Fallback to direct file access
                    viewer_path = create_plot_viewer_html(output_dir_path)
                    abs_viewer_path = viewer_path.resolve()
                    final_message = get_fallback_message(f"file:///{abs_viewer_path}")
                    log_agent_message(final_message)
            except Exception as e:
                # Fallback to direct file access
                viewer_path = create_plot_viewer_html(output_dir_path)
                abs_viewer_path = viewer_path.resolve()
                final_message = get_fallback_message(f"file:///{abs_viewer_path}")
                log_agent_message(final_message)
        else:
            final_message = "✅ Task completed successfully! You can download the results from the downloads section."
        
        if os.path.exists(repo_path): shutil.rmtree(repo_path)
    except FileNotFoundError as e:
        log_agent_message(f"❌ PeaQock Manus failed, File not found: {e}")
        final_message = f"❌ Error: File not found - {e}"
    except Exception as e:
        log_agent_message(f"❌ Error copying output: {e}")
        final_message = f"❌ Error copying output: {e}"
    
    return final_message if final_message else "✅ Task completed successfully!"
