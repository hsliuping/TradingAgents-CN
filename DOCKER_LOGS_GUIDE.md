# 🐳 TradingAgents Docker Log Management Guide

## 📋 Overview

This guide explains how to manage and retrieve TradingAgents log files in a Docker environment.

## 🔧 Improvements

### 1. **Docker Compose Configuration Optimization**

Added log directory mapping in `docker-compose.yml`:

```yaml
volumes:
  - ./logs:/app/logs  # Map container logs to local logs directory
```

### 2. **Environment Variable Configuration**

Added detailed log configuration environment variables:

```yaml
environment:
  TRADINGAGENTS_LOG_LEVEL: "INFO"
  TRADINGAGENTS_LOG_DIR: "/app/logs"
  TRADINGAGENTS_LOG_FILE: "/app/logs/tradingagents.log"
  TRADINGAGENTS_LOG_MAX_SIZE: "100MB"
  TRADINGAGENTS_LOG_BACKUP_COUNT: "5"
```

### 3. **Docker Log Configuration**

Added Docker-level log rotation:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "3"
```

## 🚀 Usage

### **Method 1: Using Startup Script (Recommended)**

#### Linux/macOS:
```bash
# Give script execution permission
chmod +x start_docker.sh

# Start Docker services
./start_docker.sh
```

#### Windows PowerShell:
```powershell
# Start Docker services
.\start_docker.ps1
```

### **Method 2: Manual Startup**

```bash
# 1. Ensure the logs directory exists
python ensure_logs_dir.py

# 2. Start Docker containers
docker-compose up -d

# 3. Check container status
docker-compose ps
```

## 📄 Log File Locations

### **Local Log Files**
- **Location**: `./logs/` directory
- **Main log**: `logs/tradingagents.log`
- **Error log**: `logs/tradingagents_error.log` (if errors occur)
- **Rotated logs**: `logs/tradingagents.log.1`, `logs/tradingagents.log.2`, etc.

### **Docker Standard Logs**
- **View command**: `docker-compose logs web`
- **Real-time tracking**: `docker-compose logs -f web`

## 🔍 How to View Logs

### **1. Using Log Viewer Tool**
```bash
# Interactive log viewer tool
python view_logs.py
```

Features include:
- 📋 Display all log files
- 👀 View log file contents
- 📺 Real-time log tracking
- 🔍 Search log contents
- 🐳 View Docker logs

### **2. View Files Directly**

#### Linux/macOS:
```bash
# View latest logs
tail -f logs/tradingagents.log

# View last 100 lines
tail -100 logs/tradingagents.log

# Search for errors
grep -i error logs/tradingagents.log
```

#### Windows PowerShell:
```powershell
# Real-time log viewing
Get-Content logs\tradingagents.log -Wait

# View last 50 lines
Get-Content logs\tradingagents.log -Tail 50

# Search for errors
Select-String -Path logs\tradingagents.log -Pattern "error" -CaseSensitive:$false
```

### **3. Docker Log Commands**
```bash
# View container logs
docker logs TradingAgents-web

# Real-time container log tracking
docker logs -f TradingAgents-web

# View logs from the last hour
docker logs --since 1h TradingAgents-web

# View last 100 lines of logs
docker logs --tail 100 TradingAgents-web
```

## 📤 Retrieving Log Files

### **Files to Send to Developers**

When you need technical support, please send the following files:

1. **Main log file**: `logs/tradingagents.log`
2. **Error log file**: `logs/tradingagents_error.log` (if exists)
3. **Docker logs**: 
   ```bash
   docker logs TradingAgents-web > docker_logs.txt 2>&1
   ```

### **Quickly Package Logs**

#### Linux/macOS:
```bash
# Create a log archive
tar -czf tradingagents_logs_$(date +%Y%m%d_%H%M%S).tar.gz logs/ docker_logs.txt
```

#### Windows PowerShell:
```powershell
# Create a log archive
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Compress-Archive -Path logs\*,docker_logs.txt -DestinationPath "tradingagents_logs_$timestamp.zip"
```

## 🔧 Troubleshooting

### **Issue 1: logs directory is empty**

**Reason**: The application inside the container may be outputting logs to stdout instead of files

**Solution**:
1. Check Docker logs: `docker-compose logs web`
2. Ensure environment variables are configured correctly
3. Restart the container: `docker-compose restart web`

### **Issue 2: Permission problems**

**Linux/macOS**:
```bash
# Fix directory permissions
sudo chown -R $USER:$USER logs/
chmod 755 logs/
```

**Windows**: Usually no permission issues

### **Issue 3: Log files too large**

**Automatic rotation**: Configured for automatic rotation, main log file max 100MB
**Manual cleanup**:
```bash
# Backup and clear log
cp logs/tradingagents.log logs/tradingagents.log.backup
> logs/tradingagents.log
```

### **Issue 4: Container won't start**

**Check steps**:
1. Check Docker status: `docker info`
2. Check port usage: `netstat -tlnp | grep 8501`
3. View startup logs: `docker-compose logs web`
4. Check config files: Is the `.env` file present?

## 📊 Log Level Explanation

- **DEBUG**: Detailed debug info, including function calls, variable values, etc.
- **INFO**: General info, key steps of normal program operation
- **WARNING**: Warnings, program can continue but needs attention
- **ERROR**: Errors, program encountered an error but can recover
- **CRITICAL**: Severe errors, program may not continue

## 🎯 Best Practices

### **1. Check logs regularly**
```bash
# Check error logs daily
grep -i error logs/tradingagents.log | tail -20
```

### **2. Monitor log size**
```bash
# Check log file size
ls -lh logs/
```

### **3. Backup important logs**
```bash
# Regularly backup logs
cp logs/tradingagents.log backups/tradingagents_$(date +%Y%m%d).log
```

### **4. Real-time monitoring**
```bash
# Monitor logs in another terminal in real time
tail -f logs/tradingagents.log | grep -i "error\|warning"
```

## 📞 Technical Support

If you encounter problems:

1. **Collect logs**: Use the above methods to collect complete logs
2. **Describe the issue**: Describe the problem and steps to reproduce
3. **Environment info**: Provide OS, Docker version, etc.
4. **Send files**: Send log files to the developers

---

**With these improvements, you can now easily retrieve and manage TradingAgents log files!** 🎉
