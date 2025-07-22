#!/usr/bin/env python3
"""
TradingAgents-CN simplified startup script
The simplest solution to module import issues
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Main function"""
    print("🚀 TradingAgents-CN Web Application Launcher")
    print("=" * 50)
    
    # Get project root directory
    project_root = Path(__file__).parent
    web_dir = project_root / "web"
    app_file = web_dir / "app.py"
    
    # Check if the app file exists
    if not app_file.exists():
        print(f"❌ Cannot find application file: {app_file}")
        return
    
    # Check if running in a virtual environment
    in_venv = (
        hasattr(sys, 'real_prefix') or 
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )
    
    if not in_venv:
        print("⚠️ It is recommended to run in a virtual environment:")
        print("   Windows: .\\env\\Scripts\\activate")
        print("   Linux/macOS: source env/bin/activate")
        print()
    
    # Check if streamlit is installed
    try:
        import streamlit
        print("✅ Streamlit is installed")
    except ImportError:
        print("❌ Streamlit is not installed, installing now...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "streamlit", "plotly"], check=True)
            print("✅ Streamlit installed successfully")
        except subprocess.CalledProcessError:
            print("❌ Streamlit installation failed, please install manually: pip install streamlit plotly")
            return
    
    # Set environment variable, add project root to Python path
    env = os.environ.copy()
    current_path = env.get('PYTHONPATH', '')
    if current_path:
        env['PYTHONPATH'] = f"{project_root}{os.pathsep}{current_path}"
    else:
        env['PYTHONPATH'] = str(project_root)
    
    # Build startup command
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(app_file),
        "--server.port", "8501",
        "--server.address", "localhost",
        "--browser.gatherUsageStats", "false",
        "--server.fileWatcherType", "none",
        "--server.runOnSave", "false"
    ]
    
    print("🌐 Starting Web application...")
    print("📱 The browser will automatically open http://localhost:8501")
    print("⏹️  Press Ctrl+C to stop the application")
    print("=" * 50)
    
    try:
        # Start the application, passing the modified environment variables
        subprocess.run(cmd, cwd=project_root, env=env)
    except KeyboardInterrupt:
        print("\n⏹️ Web application stopped")
    except Exception as e:
        print(f"\n❌ Startup failed: {e}")
        print("\n💡 If you encounter module import issues, please try:")
        print("   1. Activate the virtual environment")
        print("   2. Run: pip install -e .")
        print("   3. Restart the web application")

if __name__ == "__main__":
    main()
