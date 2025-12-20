import asyncio
import sys
import os
import requests
import time
import json

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.services.user_service import user_service
from app.core.database import get_mongo_db

async def ensure_admin_exists():
    print("Ensuring admin user exists...")
    try:
        # We need to initialize the DB connection if not already done by the app import
        # user_service creates its own connection if I recall correctly or uses the global one
        # Let's just try calling the method.
        user = await user_service.create_admin_user()
        if user:
            print(f"Admin user ensured: {user.username}")
        else:
            print("Admin user might already exist or creation failed.")
    except Exception as e:
        print(f"Error ensuring admin: {e}")

def test_index_analysis():
    base_url = "http://127.0.0.1:8000"
    
    # 1. Login
    print("\n1. Logging in...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    try:
        response = requests.post(f"{base_url}/api/auth/login", json=login_data)
        response.raise_for_status()
        token_data = response.json()["data"]
        token = token_data["access_token"]
        print("Login successful.")
    except Exception as e:
        print(f"Login failed: {e}")
        try:
            print(f"Response: {response.text}")
        except:
            pass
        return

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # 2. Submit Analysis
    print("\n2. Submitting Index Analysis Task...")
    # Using h30590.CSI (CSI Robot Index)
    payload = {
        "symbol": "h30590.CSI",
        "parameters": {
            "analysis_type": "index",
            "research_depth": "标准", 
            "include_sentiment": True,
            "include_risk": True,
            "quick_analysis_model": "deepseek-chat",
            "deep_analysis_model": "deepseek-chat"
        }
    }
    
    try:
        response = requests.post(f"{base_url}/api/analysis/single", json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        task_id = result["data"]["task_id"]
        print(f"Task submitted. Task ID: {task_id}")
    except Exception as e:
        print(f"Submission failed: {e}")
        try:
            print(f"Response: {response.text}")
        except:
            pass
        return

    # 3. Poll for Status
    print("\n3. Polling for results...")
    max_retries = 100 # Increase wait time
    for i in range(max_retries):
        try:
            status_resp = requests.get(f"{base_url}/api/analysis/tasks/{task_id}/status", headers=headers)
            status_resp.raise_for_status()
            status_data = status_resp.json()["data"]
            status = status_data["status"]
            progress = status_data.get("progress", 0)
            
            print(f"Status: {status}, Progress: {progress}%")
            
            if status == "completed":
                print("Analysis completed!")
                break
            elif status == "failed":
                print(f"Analysis failed. Reason: {status_data.get('error') or status_data.get('message')}")
                return
            
            time.sleep(3)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(3)

    # 4. Get Result
    print("\n4. Retrieving Result...")
    try:
        result_resp = requests.get(f"{base_url}/api/analysis/tasks/{task_id}/result", headers=headers)
        result_resp.raise_for_status()
        result_data = result_resp.json()["data"]
        
        print("\n" + "="*50)
        print("ANALYSIS RESULT")
        print("="*50)
        print(f"Symbol: {result_data.get('stock_symbol')}")
        print(f"Date: {result_data.get('analysis_date')}")
        print(f"Summary: {result_data.get('summary')}")
        print(f"Recommendation: {result_data.get('recommendation')}")
        print("-" * 30)
        
        # Display report sections if available
        reports = result_data.get("reports", {})
        if reports:
            print("\nAvailable Reports:")
            for key, content in reports.items():
                print(f"\n--- Report: {key} ---")
                print(content[:500] + "..." if len(content) > 500 else content)
                
    except Exception as e:
        print(f"Failed to retrieve result: {e}")
        try:
            print(f"Response: {result_resp.text}")
        except:
            pass

if __name__ == "__main__":
    # Ensure admin exists first
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ensure_admin_exists())
    except Exception as e:
        print(f"Warning: Could not run async admin creation: {e}")
    
    # Run test
    test_index_analysis()
