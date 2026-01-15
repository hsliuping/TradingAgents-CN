#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Import MongoDB configuration from JSON export file
"""

import sys
import json
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import OperationFailure, ConnectionFailure
from bson import ObjectId


def convert_objectid(data):
    """Convert _id strings to ObjectId recursively"""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key == '_id' and isinstance(value, str):
                try:
                    result[key] = ObjectId(value)
                except Exception:
                    result[key] = value
            else:
                result[key] = convert_objectid(value)
        return result
    elif isinstance(data, list):
        return [convert_objectid(item) for item in data]
    else:
        return data


def import_mongodb_config(
    json_file,
    host='127.0.0.1',
    port=27017,
    username='admin',
    password='tradingagents123',
    database='tradingagents'
):
    """Import MongoDB configuration from JSON file"""
    
    # Check if JSON file exists
    json_path = Path(json_file)
    if not json_path.exists():
        print(f"ERROR: JSON file not found: {json_file}")
        return False
    
    print(f"Reading configuration from: {json_file}")
    
    try:
        # Read JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            export_data = json.load(f)
        
        print(f"  Loaded JSON file successfully")
        
        # Validate JSON structure
        if 'data' not in export_data:
            print("ERROR: Invalid JSON structure, missing 'data' key")
            return False
        
        collections_data = export_data['data']
        print(f"  Found {len(collections_data)} collections to import")
        
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON file: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Failed to read JSON file: {e}")
        return False
    
    try:
        # Connect to MongoDB with authentication
        print(f"Connecting to MongoDB at {host}:{port}...")
        client = MongoClient(
            host,
            port,
            username=username,
            password=password,
            authSource='admin',
            serverSelectionTimeoutMS=10000
        )
        
        # Test connection
        client.admin.command('ping')
        print("  Connected to MongoDB successfully")
        
        # Switch to target database
        db = client[database]
        print(f"  Using database: {database}")
        
        # Import each collection
        total_imported = 0
        total_errors = 0
        
        for collection_name, documents in collections_data.items():
            if not documents:
                print(f"  Skipping empty collection: {collection_name}")
                continue
            
            print(f"  Importing collection: {collection_name} ({len(documents)} documents)")
            
            try:
                collection = db[collection_name]
                
                # Convert _id strings to ObjectId
                converted_docs = [convert_objectid(doc) for doc in documents]
                
                # Drop existing collection to avoid duplicates
                collection.drop()
                print(f"    Dropped existing collection: {collection_name}")
                
                # Insert documents
                if converted_docs:
                    result = collection.insert_many(converted_docs, ordered=False)
                    inserted_count = len(result.inserted_ids)
                    total_imported += inserted_count
                    print(f"    Inserted {inserted_count} documents")
                
            except Exception as e:
                print(f"    ERROR importing {collection_name}: {e}")
                total_errors += 1
        
        print(f"\nImport completed:")
        print(f"  Total documents imported: {total_imported}")
        print(f"  Collections with errors: {total_errors}")
        
        return total_errors == 0
        
    except ConnectionFailure as e:
        print(f"ERROR: Failed to connect to MongoDB: {e}")
        return False
    except OperationFailure as e:
        print(f"ERROR: MongoDB operation failed: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return False
    finally:
        try:
            client.close()
        except:
            pass


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_mongodb_config.py <json_file> [host] [port] [username] [password] [database]")
        print("Example: python import_mongodb_config.py config.json 127.0.0.1 27017 admin tradingagents123 tradingagents")
        sys.exit(1)
    
    json_file = sys.argv[1]
    host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 27017
    username = sys.argv[4] if len(sys.argv) > 4 else 'admin'
    password = sys.argv[5] if len(sys.argv) > 5 else 'tradingagents123'
    database = sys.argv[6] if len(sys.argv) > 6 else 'tradingagents'
    
    success = import_mongodb_config(json_file, host, port, username, password, database)
    sys.exit(0 if success else 1)

