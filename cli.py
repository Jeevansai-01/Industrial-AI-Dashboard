import argparse
import subprocess
import os
import signal
import sys


PID_FILE = "simulator.pid" # File to store the simulator's PID 

def is_running(pid):
    """Return True if a process with this PID exists."""
    try:
        
        os.kill(pid, 0)   
        return True
    except OSError:
        return False

def read_pid():
    """Read PID from file if it exists, else return None."""
    if not os.path.exists(PID_FILE):  
        return None
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:  # Open the PID file.
            return int(f.read().strip())   
    except Exception:
        return None

def write_pid(pid):
    """Write PID to file."""
    with open(PID_FILE, "w", encoding="utf-8") as f:  
        f.write(str(pid))   

def remove_pid():
    """Delete the PID file if it exists."""
    if os.path.exists(PID_FILE):  
        os.remove(PID_FILE)  

def start_simulator():
    """Start data_simulator.py in the background and save its PID."""
    existing = read_pid()  
    if existing and is_running(existing):  
        print(f"Simulator already running with PID {existing}")  
        return

    # Build the command to run the simulator with the same Python interpreter being used now.
    cmd = [sys.executable, "data_simulator.py"]  # Portable way to run Python script. 

    # Use subprocess to start it detached from this CLI so it continues running.
    if os.name == "nt":
        # On Windows, CREATE_NEW_PROCESS_GROUP makes a new group; DETACHED_PROCESS hides console.
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        proc = subprocess.Popen(
            cmd,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,  
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )   
    else:
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
            close_fds=True,
        )   

    write_pid(proc.pid)   
    print(f"Simulator started with PID {proc.pid}")  

def stop_simulator():
    """Stop the running simulator process using the stored PID."""
    pid = read_pid()   
    if not pid:
        print("No PID file found; simulator not running?")  
        return

    if not is_running(pid):
        print("Simulator not running; cleaning up PID file.")  
        remove_pid()
        return

    try:
        if os.name == "nt":
            
            os.kill(pid, signal.SIGTERM)  # Request termination. 
        else:
            
            os.killpg(pid, signal.SIGTERM)  # Terminate the process group. 
        print(f"Sent stop signal to PID {pid}")  # Feedback.
    except Exception as e:
        print(f"Failed to stop simulator: {e}")  # Error feedback.
    finally:
        remove_pid()  # Remove PID file regardless to avoid stale state. 

def status_simulator():
    """Print whether the simulator is running."""
    pid = read_pid()  # Check for saved PID. 
    if pid and is_running(pid):
        print(f"Simulator is running (PID {pid})")  # Positive status.
    else:
        print("Simulator is not running")  # Negative status.

def main():
    
    parser = argparse.ArgumentParser(description="Control the data simulator")   
    # Add subcommands: start, stop, status.
    subparsers = parser.add_subparsers(dest="command", required=True)  # Group of subcommands. 

    subparsers.add_parser("start", help="Start the simulator")  # 'start' command. 
    subparsers.add_parser("stop", help="Stop the simulator")    # 'stop' command. 
    subparsers.add_parser("status", help="Show simulator status")  # 'status' command. 

    args = parser.parse_args()   

    
    if args.command == "start":
        start_simulator()  # Launch background process.
    elif args.command == "stop":
        stop_simulator()   # Terminate if running.
    elif args.command == "status":
        status_simulator() # Print status.

if __name__ == "__main__":
    main()  # Entry point when running: python cli.py <command>
