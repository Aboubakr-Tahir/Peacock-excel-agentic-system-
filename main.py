import sys, os
from dotenv import load_dotenv
from agents import AgentManager
from config import OrchestratorDecision, todo
from PreProcessing import run_preprocessing
from agent_runner import run_agents

load_dotenv()
key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = key
manager = AgentManager("gpt-4o")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":    
    query = input("Hello I am PeaQock Manus IA Agent how can i help you today?\n===> ")
    print("Preprocessing ...\n")
    run_preprocessing(manager)
    
    print("\n\n========================================================================")
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
        
        run_agents(query, manager, decision)
        if decision.agent_to_call == 'complete':
            print("\nAll tasks are complete. Workflow finished.")
            break
