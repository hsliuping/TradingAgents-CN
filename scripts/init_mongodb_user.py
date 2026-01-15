#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MongoDB User Initialization Script
Creates admin user for TradingAgents-CN portable installation
"""

import sys
import time
from pymongo import MongoClient
from pymongo.errors import OperationFailure, ConnectionFailure

def init_mongodb_user(host='127.0.0.1', port=27017, username='admin', password='tradingagents123', max_retries=10):
    """Initialize MongoDB admin user with retry logic"""

    # Retry connection with exponential backoff
    for attempt in range(max_retries):
        try:
            # Connect to MongoDB without authentication
            print(f"Connecting to MongoDB at {host}:{port}... (attempt {attempt + 1}/{max_retries})")
            client = MongoClient(host, port, serverSelectionTimeoutMS=3000)

            # Test connection
            client.admin.command('ping')
            print("Connected to MongoDB successfully")

            # Switch to admin database
            admin_db = client.admin

            # Check if user already exists
            try:
                users = admin_db.command('usersInfo', username)
                if users['users']:
                    print(f"User '{username}' already exists, skipping creation")
                    return True
            except Exception as e:
                print(f"Checking existing users: {e}")

            # Create admin user
            print(f"Creating admin user '{username}'...")
            admin_db.command(
                'createUser',
                username,
                pwd=password,
                roles=[
                    {'role': 'userAdminAnyDatabase', 'db': 'admin'},
                    {'role': 'readWriteAnyDatabase', 'db': 'admin'},
                    {'role': 'dbAdminAnyDatabase', 'db': 'admin'},
                    {'role': 'root', 'db': 'admin'}
                ]
            )

            print(f"Admin user '{username}' created successfully")

            # Verify user creation
            client_auth = MongoClient(
                host,
                port,
                username=username,
                password=password,
                authSource='admin',
                serverSelectionTimeoutMS=5000
            )
            client_auth.admin.command('ping')
            print("User authentication verified successfully")

            return True

        except ConnectionFailure as e:
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10 seconds
                print(f"Connection failed, retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                print(f"ERROR: Failed to connect to MongoDB after {max_retries} attempts: {e}")
                return False
        except OperationFailure as e:
            print(f"ERROR: Failed to create user: {e}")
            return False
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 10)
                print(f"Unexpected error, retrying in {wait_time} seconds: {e}")
                time.sleep(wait_time)
                continue
            else:
                print(f"ERROR: Unexpected error after {max_retries} attempts: {e}")
                return False
        finally:
            try:
                client.close()
            except:
                pass

    return False

if __name__ == '__main__':
    # Parse command line arguments
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 27017
    username = sys.argv[3] if len(sys.argv) > 3 else 'admin'
    password = sys.argv[4] if len(sys.argv) > 4 else 'tradingagents123'
    
    success = init_mongodb_user(host, port, username, password)
    sys.exit(0 if success else 1)

