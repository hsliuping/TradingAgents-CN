#!/usr/bin/env python3
"""
Batch update data source references
Update all "Tongdaxin" references to "Tushare" or general description
"""

import os
import re
from pathlib import Path

# Import logging module
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('default')


def update_file_content(file_path: Path, replacements: list):
    """Update file content"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        for old_text, new_text in replacements:
            content = content.replace(old_text, new_text)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"✅ Updated: {file_path}")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"❌ Update failed {file_path}: {e}")
        return False

def main():
    """Main function"""
    logger.info(f"🔧 Batch update data source references")
    logger.info(f"=")
    
    # Project root directory
    project_root = Path(__file__).parent.parent
    
    # File patterns to update
    file_patterns = [
        "**/*.py",
        "**/*.md",
        "**/*.txt"
    ]
    
    # Directories to exclude
    exclude_dirs = {
        ".git", "__pycache__", "env", "venv", ".vscode", 
        "node_modules", ".pytest_cache", "dist", "build"
    }
    
    # Replacement rules
    replacements = [
        # Data source identifier
        ("Data source: Tushare data interface", "Data source: Tushare data interface"),
        ("Data source: Tushare data interface (real-time data)", "Data source: Tushare data interface"),
        ("Data source: Tushare data interface\n", "Data source: Tushare data interface\n"),
        
        # User interface prompts
        ("Use Chinese stock data source for fundamental analysis", "Use Chinese stock data source for fundamental analysis"),
        ("Use Chinese stock data source", "Use Chinese stock data source"),
        ("Tushare data interface + Fundamental analysis model", "Tushare data interface + Fundamental analysis model"),
        
        # Error prompts
        ("Due to data interface limitations", "Due to data interface limitations"),
        ("Data interface requires network connection", "Data interface requires network connection"),
        ("Data server", "Data server"),
        
        # Technical documentation
        ("Tushare + FinnHub API", "Tushare + FinnHub API"),
        ("Tushare data interface", "Tushare data interface"),
        
        # CLI prompts
        ("Will use Chinese stock data source", "Will use Chinese stock data source"),
        ("china_stock", "china_stock"),
        
        # Comments and explanations
        ("# Chinese stock data", "# Chinese stock data"),
        ("Data source search function", "Data source search function"),
        
        # Variable names and identifiers (keep code functionality, only update display text)
        ("'china_stock'", "'china_stock'"),
        ('"china_stock"', '"china_stock"'),
    ]
    
    # Collect all files to update
    files_to_update = []
    
    for pattern in file_patterns:
        for file_path in project_root.glob(pattern):
            # Check if in excluded directories
            if any(exclude_dir in file_path.parts for exclude_dir in exclude_dirs):
                continue
            
            # Skip binary files and special files
            if file_path.suffix in {'.pyc', '.pyo', '.so', '.dll', '.exe'}:
                continue
                
            files_to_update.append(file_path)
    
    logger.info(f"📁 Found {len(files_to_update)} files to check")
    
    # Update files
    updated_count = 0
    
    for file_path in files_to_update:
        if update_file_content(file_path, replacements):
            updated_count += 1
    
    logger.info(f"\n�� Update complete:")
    logger.info(f"   Checked files: {len(files_to_update)}")
    logger.info(f"   Updated files: {updated_count}")
    
    if updated_count > 0:
        logger.info(f"\n🎉 Successfully updated {updated_count} data source references!")
        logger.info(f"\n📋 Main updates:")
        logger.info(f"   ✅ 'Tushare data interface' → 'Tushare data interface'")
        logger.info(f"   ✅ 'Tongdaxin data source' → 'Chinese stock data source'")
        logger.error(f"   ✅ Error prompts and user interface text")
        logger.info(f"   ✅ Technical documentation and comments")
    else:
        logger.info(f"\n✅ All data source references are up-to-date")

if __name__ == "__main__":
    main()
