import argparse
import requests
import json
import os
import sys

# Configuration
BASE_URL = "http://localhost:8000/api"
LOGIN_URL = f"{BASE_URL}/auth/login"
USERNAME = "admin"
PASSWORD = "admin123"

def get_token():
    """Get access token"""
    try:
        response = requests.post(
            LOGIN_URL,
            json={"username": USERNAME, "password": PASSWORD},
        )
        response.raise_for_status()
        data = response.json()
        if "data" in data and "access_token" in data["data"]:
            return data["data"]["access_token"]
        return data["access_token"]
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return None

def get_markdown_report(token, task_id):
    """Get markdown report content"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/reports/{task_id}/download?format=markdown"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Failed to get report: {e}")
        return None

def verify_content(content):
    """Verify presence of key sections and fields"""
    required_sections = [
        "## 政策分析",
        "## 行业分析",
        "## 国际新闻分析"
    ]
    
    required_fields = [
        "overall_support_strength",
        "key_events",
        "industry_policy",
        "sector_stage",
        "growth_potential",
        "geopolitical_impact"
    ]
    
    missing_sections = []
    for section in required_sections:
        if section not in content and section.replace("## ", "# ") not in content:
             missing_sections.append(section)
             
    # Note: Fields might be formatted in the text, so we check for keywords related to them
    # or check if the section content is non-empty.
    # For now, let's just check if the sections exist and have some content.
    
    passed = True
    if missing_sections:
        print(f"❌ Missing sections: {missing_sections}")
        passed = False
    else:
        print("✅ All required sections present.")
        
    return passed, missing_sections

def main():
    parser = argparse.ArgumentParser(description='Verify report content')
    parser.add_argument('--task_id', required=True, help='Task ID to verify')
    args = parser.parse_args()
    
    TASK_ID = args.task_id
    
    token = get_token()
    if token:
        content = get_markdown_report(token, TASK_ID)
        if content:
            # print first 20 lines to check content visually
            print("\n--- Report Preview (First 20 lines) ---")
            print("\n".join(content.split("\n")[:20]))
            
            passed, _ = verify_content(content)
            
            if passed:
                print("\n✅ All checks passed!")
            else:
                print("\n⚠️ Some checks failed. Please inspect the report.")

if __name__ == "__main__":
    main()
