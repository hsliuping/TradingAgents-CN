#!/usr/bin/env python
"""
TradingAgents-CN Development Startup Script
Start Backend API and Worker for local development
"""

import os
import sys
import subprocess
import signal
import time
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def find_python_exe():
    """Find Python executable (venv/env/system)"""
    candidates = [
        project_root / "venv" / "Scripts" / "python.exe",
        project_root / "env" / "Scripts" / "python.exe",
        project_root / "vendors" / "python" / "python.exe",
        sys.executable
    ]
    
    for candidate in candidates:
        if candidate.exists() if isinstance(candidate, Path) else True:
            return str(candidate)
    
    return "python"


def main():
    parser = argparse.ArgumentParser(
        description="TradingAgents-CN Development Startup Script"
    )
    parser.add_argument(
        "--backend-only",
        action="store_true",
        help="Start Backend only"
    )
    parser.add_argument(
        "--worker-only",
        action="store_true",
        help="Start Worker only"
    )
    parser.add_argument(
        "--no-worker",
        action="store_true",
        help="Start Backend without Worker"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Backend port (default: 8000)"
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("TradingAgents-CN Development Mode")
    print("=" * 50)
    print()
    
    # Find Python
    python_exe = find_python_exe()
    print(f"[OK] Python: {python_exe}")
    
    # Set UTF-8 encoding
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONUNBUFFERED"] = "1"
    print("[OK] UTF-8 encoding enabled")
    print()
    
    # Check required files
    backend_main = project_root / "app" / "main.py"
    worker_main = project_root / "app" / "worker" / "__main__.py"
    
    if not args.backend_only and not args.worker_only:
        if not backend_main.exists():
            print(f"[ERROR] Backend not found: {backend_main}")
            sys.exit(1)
        if not args.no_worker and not worker_main.exists():
            print(f"[ERROR] Worker not found: {worker_main}")
            sys.exit(1)
    
    # Start processes
    processes = []
    
    try:
        if not args.worker_only:
            print("[1/2] Starting Backend API...")
            print(f"  Port: {args.port}")
            print(f"  URL: http://127.0.0.1:{args.port}")
            print(f"  Docs: http://127.0.0.1:{args.port}/docs")
            print()
            
            backend_process = subprocess.Popen(
                [python_exe, str(backend_main), "--port", str(args.port)],
                cwd=str(project_root),
                env=os.environ.copy()
            )
            processes.append(("Backend", backend_process))
            print(f"[OK] Backend started (PID: {backend_process.pid})")
            print()
            
            # Wait for backend to start
            time.sleep(2)
        
        if not args.backend_only and not args.no_worker:
            print("[2/2] Starting Worker...")
            print(f"  Log: logs/worker.log")
            print()
            
            worker_process = subprocess.Popen(
                [python_exe, str(worker_main)],
                cwd=str(project_root),
                env=os.environ.copy()
            )
            processes.append(("Worker", worker_process))
            print(f"[OK] Worker started (PID: {worker_process.pid})")
            print()
        
        print("=" * 50)
        print("Development server running!")
        print("=" * 50)
        print()
        print("Press Ctrl+C to stop all processes")
        print()
        
        # Wait for processes
        while True:
            time.sleep(1)
            
            # Check if any process exited
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"\n[ERROR] {name} exited with code {proc.returncode}")
                    raise KeyboardInterrupt
    
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")
    
    finally:
        # Stop all processes
        for name, proc in processes:
            if proc.poll() is None:
                print(f"Stopping {name} (PID: {proc.pid})...")
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"Force killing {name}...")
                    proc.kill()
        
        print()
        print("[OK] All processes stopped")
        print()


if __name__ == "__main__":
    main()

