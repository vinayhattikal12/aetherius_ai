import os
import sys
import subprocess
import time
import platform
import shutil

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data", "postgres")
DESKTOP_DIR = os.path.join(ROOT_DIR, "apps", "desktop")


def check_and_start_postgres():
    print("[1/4] Configuring PostgreSQL Database Cluster...")
    os.makedirs(os.path.join(ROOT_DIR, "data"), exist_ok=True)
    
    if not os.path.exists(DATA_DIR):
        print("  -> Initializing fresh PostgreSQL data cluster in data/postgres...")
        subprocess.run(["initdb", "-D", DATA_DIR, "-U", "postgres", "-A", "trust"], check=True)

    print("  -> Starting PostgreSQL on port 54329...")
    log_file = os.path.join(DATA_DIR, "server.log")
    subprocess.run(["pg_ctl", "-D", DATA_DIR, "-l", log_file, "-o", "-p 54329", "start"], check=False)
    time.sleep(2)

    # Ensure database exists
    try:
        subprocess.run(["createdb", "-h", "localhost", "-p", "54329", "-U", "postgres", "aetherius"], stderr=subprocess.DEVNULL)
    except Exception:
        pass


def run_database_migrations():
    print("[2/4] Running Alembic schema migrations...")
    python_bin = os.path.join(ROOT_DIR, ".venv", "Scripts", "python") if platform.system() == "Windows" else os.path.join(ROOT_DIR, ".venv", "bin", "python")
    if not os.path.exists(python_bin):
        python_bin = sys.executable
    
    try:
        subprocess.run([python_bin, "-m", "alembic", "upgrade", "head"], cwd=ROOT_DIR, check=False)
    except Exception as e:
        print(f"  Migration notice: {e}")


def start_backend():
    print("[3/4] Starting Aetherius FastAPI Core on http://127.0.0.1:8000...")
    python_bin = os.path.join(ROOT_DIR, ".venv", "Scripts", "python") if platform.system() == "Windows" else os.path.join(ROOT_DIR, ".venv", "bin", "python")
    if not os.path.exists(python_bin):
        python_bin = sys.executable

    cmd = [python_bin, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
    return subprocess.Popen(cmd, cwd=ROOT_DIR)


def start_desktop():
    print("[4/4] Starting Aetherius Desktop App (Vite + Electron)...")
    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
    return subprocess.Popen([npm_cmd, "start"], cwd=DESKTOP_DIR)


if __name__ == "__main__":
    print("=======================================================")
    print("          AETHERIUS AI OPERATING ENVIRONMENT           ")
    print("      Phase 1: Foundation + Hardware + PostgreSQL      ")
    print("=======================================================\n")
    
    check_and_start_postgres()
    run_database_migrations()
    
    backend_proc = start_backend()
    time.sleep(2)
    
    desktop_proc = start_desktop()
    
    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        print("\nStopping Aetherius...")
        backend_proc.terminate()
        desktop_proc.terminate()
        subprocess.run(["pg_ctl", "-D", DATA_DIR, "stop"], check=False)
        print("Shutdown complete.")
