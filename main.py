import sys, os, shutil
from dotenv import load_dotenv
from streamlit import json
from agents import AgentManager
from config import OrchestratorDecision, todo ,repo_path, excel_path, profiler_notes_path, workspace_path, output_path
from PreProcessing import run_preprocessing
from agent_runner import run_agents
from pathlib import Path
import time
import gc

load_dotenv()
key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = key
manager = AgentManager("gpt-4o")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# if __name__ == "__main__":
def main_function(query: str):

    print("Preprocessing ...")
    run_preprocessing(manager)
    
    print("========================================================================")
    print("Running Planner Agent: creating todo.md ...")
    planner = manager.get_planner_agent(query=query, todo=todo).run()
    print("Planner Agent finished\nOrchestrator is now running the plan ...")
    orchestrator = manager.get_orchestrator_agent(todo=todo)
    print("========================================================================\n")
    
    while True:
        decision_response = orchestrator.run("Read the todo.md file and decide the next step.")
        if not isinstance(decision_response.content, OrchestratorDecision):
            print(f"Orchestrator failed to make a valid decision. Halting.\nReceived: {decision_response.content}")
            break
        decision = decision_response.content
        print(f"Orchestrator Decision: Call agent '{decision.agent_to_call}' for task: '{decision.task_to_perform}'")
        print(f"Reasoning: {decision.reasoning}")
        
        # Check if run_agents returns False (indicating failure)
        agent_success = run_agents(query, manager, decision)
        if not agent_success:
            print("❌ Agent execution failed. Breaking workflow to prevent infinite loop.")
            
        if decision.agent_to_call == 'complete':
            print("\nAll tasks are complete. Workflow finished.")
            break
    delivery_agent = manager.get_delivery_agent(query=query, repo_path=repo_path, excel_path=excel_path, profiler_notes_path=profiler_notes_path, workspace_path=workspace_path).run()
    output = delivery_agent.content.chosen_path
    print("the path of the output is: ", output)
    
    # Force garbage collection to release any file handles
    gc.collect()
    time.sleep(1)  # Brief pause to ensure files are released
    
    try:
        final = "output"; os.makedirs(final, exist_ok=True)
        shutil.copy(output, final) if os.path.isfile(output) else shutil.copytree(output, os.path.join(final, os.path.basename(output)), dirs_exist_ok=True)
        if os.path.exists(repo_path): shutil.rmtree(repo_path)
    except FileNotFoundError as e:
        print(f"❌ PeaQock Manus failed, File not found: {e}")
    except Exception as e:
        print(f"❌ Error copying output: {e}")
