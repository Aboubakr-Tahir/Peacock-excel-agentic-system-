import time, os
from core.paths import agent_logs

def log_agent_message(message):
    """Write a message to both console and agent logs file"""
    print(message)
    try:
        agent_logs.parent.mkdir(parents=True, exist_ok=True)
        
        with open(agent_logs, 'a', encoding='utf-8', buffering=1) as f:
            timestamp = time.strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}\n"
            f.write(log_entry)
            f.flush()
            os.fsync(f.fileno())
            
        time.sleep(0.1)
    except Exception as e:
        print(f"Warning: Could not write to agent logs: {e}")

def clear_agent_logs():
    """Clear the agent logs file at the start of a new workflow"""
    try:
        agent_logs.parent.mkdir(parents=True, exist_ok=True)
        
        with open(agent_logs, 'w', encoding='utf-8') as f:
            f.write("")
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print(f"Warning: Could not clear agent logs: {e}")