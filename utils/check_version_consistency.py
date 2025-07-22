#!/usr/bin/env python3
"""
Version consistency check tool
Ensure all version references in the project are consistent
"""

import os
import re
from pathlib import Path

# Import logging module
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('default')


def get_target_version():
    """Get target version number from VERSION file"""
    version_file = Path("VERSION")
    if version_file.exists():
        with open(version_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return None

def check_file_versions(file_path: Path, target_version: str):
    """Check version numbers in files"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Version number patterns
        version_patterns = [
            r'v?\d+\.\d+\.\d+(?:-\w+)?',  # Basic version number
            r'Version-v\d+\.\d+\.\d+',    # Badge version number
            r'Version.*?v?\d+\.\d+\.\d+',     # Chinese version description
        ]
        
        issues = []
        
        for pattern in version_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                found_version = match.group()
                
                # Skip some special cases
                if any(skip in found_version.lower() for skip in [
                    'python-3.', 'mongodb', 'redis', 'streamlit', 
                    'langchain', 'pandas', 'numpy'
                ]):
                    continue
                
                # Normalize version number for comparison
                normalized_found = found_version.lower().replace('version-', '').replace('Version', '').strip()
                normalized_target = target_version.lower()
                
                if normalized_found != normalized_target and not normalized_found.startswith('0.1.'):
                    # If not a historical version number, report inconsistency
                    if not any(hist in normalized_found for hist in ['0.1.1', '0.1.2', '0.1.3', '0.1.4', '0.1.5']):
                        issues.append({
                            'line': content[:match.start()].count('\n') + 1,
                            'found': found_version,
                            'expected': target_version,
                            'context': content[max(0, match.start()-20):match.end()+20]
                        })
        
        return issues
        
    except Exception as e:
        return [{'error': str(e)}]

def main():
    """Main check function"""
    logger.debug(f"🔍 Version consistency check")
    logger.info(f"=")
    
    # Get target version number
    target_version = get_target_version()
    if not target_version:
        logger.error(f"❌ Cannot read VERSION file")
        return
    
    logger.info(f"🎯 Target version: {target_version}")
    
    # Files to check
    files_to_check = [
        "README.md",
        "docs/PROJECT_INFO.md",
        "docs/releases/CHANGELOG.md",
        "docs/overview/quick-start.md",
        "docs/configuration/dashscope-config.md",
        "docs/data/data-sources.md",
    ]
    
    total_issues = 0
    
    for file_path in files_to_check:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"⚠️ File does not exist: {file_path}")
            continue
        
        logger.info(f"\n📄 Checking file: {file_path}")
        issues = check_file_versions(path, target_version)
        
        if not issues:
            logger.info(f"   ✅ Version numbers are consistent")
        else:
            for issue in issues:
                if 'error' in issue:
                    logger.error(f"   ❌ Check error: {issue['error']}")
                else:
                    logger.error(f"   ❌ Line {issue['line']}: Found '{issue['found']}', expected '{issue['expected']}'")
                    logger.info(f"      Context: ...{issue['context']}...")
                total_issues += len(issues)
    
    # Summary
    logger.info(f"\n📊 Check summary")
    logger.info(f"=")
    
    if total_issues == 0:
        logger.info(f"🎉 All version numbers are consistent!")
        logger.info(f"✅ Current version: {target_version}")
    else:
        logger.warning(f"⚠️ Found {total_issues} version number inconsistency issues")
        logger.info(f"Please manually fix the above issues")
    
    # Version number specification reminder
    logger.info(f"\n💡 Version number specification:")
    logger.info(f"   - Main version file: VERSION")
    logger.info(f"   - Current version: {target_version}")
    logger.info(f"   - Format requirement: v0.1.x")
    logger.info(f"   - Historical versions: Can be kept in CHANGELOG")

if __name__ == "__main__":
    main()
