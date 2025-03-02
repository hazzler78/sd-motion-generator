import subprocess
import os
import sys
import time
import webbrowser
from pathlib import Path
import shutil

def check_npm():
    """Check if npm is available and return its path"""
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    npm_path = shutil.which(npm_cmd)
    
    if not npm_path:
        print("Error: npm not found. Please install Node.js from https://nodejs.org/")
        sys.exit(1)
    
    return npm_path

def start_backend():
    """Start the FastAPI backend server"""
    print("Starting backend server...")
    backend_path = Path("backend")
    if sys.platform == "win32":
        python_path = backend_path / "venv" / "Scripts" / "python.exe"
    else:
        python_path = backend_path / "venv" / "bin" / "python"
    
    if not python_path.exists():
        print("Virtual environment not found. Please set up the backend first.")
        sys.exit(1)

    backend_process = subprocess.Popen(
        [str(python_path), "-m", "uvicorn", "politik.main:app", "--reload"],
        cwd=str(backend_path)
    )
    return backend_process

def start_frontend():
    """Start the Next.js frontend server"""
    print("Starting frontend server...")
    frontend_path = Path("sd-motion-generator")
    npm_path = check_npm()
    
    if not (frontend_path / "node_modules").exists():
        print("Node modules not found. Installing dependencies...")
        try:
            subprocess.run([npm_path, "install"], cwd=str(frontend_path), check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error installing dependencies: {e}")
            sys.exit(1)

    try:
        frontend_process = subprocess.Popen(
            [npm_path, "run", "dev"],
            cwd=str(frontend_path),
            env=dict(os.environ)  # Pass current environment variables
        )
        return frontend_process
    except subprocess.CalledProcessError as e:
        print(f"Error starting frontend: {e}")
        sys.exit(1)

def main():
    try:
        # Start backend
        backend_process = start_backend()
        print("Backend server started at http://localhost:8000")
        
        # Wait a bit for backend to initialize
        time.sleep(2)
        
        # Start frontend
        frontend_process = start_frontend()
        print("Frontend server started at http://localhost:3000")
        
        # Open browser after a short delay
        time.sleep(3)
        webbrowser.open("http://localhost:3000")
        
        print("\nPress Ctrl+C to stop both servers...")
        
        # Wait for processes to complete or user interrupt
        backend_process.wait()
        frontend_process.wait()
        
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        backend_process.terminate()
        frontend_process.terminate()
        backend_process.wait()
        frontend_process.wait()
        print("Servers stopped.")
    except subprocess.CalledProcessError as e:
        print(f"Error starting servers: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 