import os
import sys
import subprocess

if __name__ == "__main__":
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
    os.chdir(backend_dir)
    print(f"Starting BIS Sahayak Backend from: {backend_dir}")
    print("API will be available at: http://127.0.0.1:8000")
    try:
        import uvicorn
        uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    except ImportError:
        print("uvicorn not installed. Running via subprocess...")
        subprocess.run(["uvicorn", "main:app", "--reload"])
