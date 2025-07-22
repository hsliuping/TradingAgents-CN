# 🧹 Web application cache cleaning guide

## 📋 Why clean cache?

### 🎯 Main reasons
The main reason for Web launcher to clean Python cache files (`__pycache__`):

1. **Avoid Streamlit file monitoring errors**
   - Streamlit has auto-reload functionality
   - `__pycache__` file changes may trigger false reloads
   - In some cases, cache files are locked, causing monitoring errors

2. **Ensure code synchronization**
   - Force recompilation of all Python files
   - Avoid old cache hiding code modification effects
   - Ensure running the latest code

3. **Development environment optimization**
   - Avoid cache inconsistencies when frequently modifying code
   - Reduce confusion during debugging
   - Clean up disk space

## 🚀 Launch options

### Default launch (recommended)
```bash
python web/run_web.py
```
- ✅ Only clean project code cache
- ✅ Keep virtual environment cache
- ✅ Balance performance and stability

### Skip cache cleaning
```bash
python web/run_web.py --no-clean
```
- ⚡ Faster launch
- ⚠️ May encounter Streamlit monitoring issues
- 💡 Suitable for stable environments

### Force clean all cache
```bash
python web/run_web.py --force-clean
```
- 🧹 Clean all cache (including virtual environment)
- 🐌 Slower launch
- 🔧 Suitable for resolving cache issues

### Environment variable control
```bash
# Windows
set SKIP_CACHE_CLEAN=true
python web/run_web.py

# Linux/Mac
export SKIP_CACHE_CLEAN=true
python web/run_web.py
```

## 🤔 When do you need to clean?

### ✅ Suggested cleaning situations
- 🔄 **Development phase**: Frequent code modification
- 🐛 **Debugging issues**: Code modification does not take effect
- ⚠️ **Streamlit errors**: File monitoring anomalies
- 🆕 **Version updates**: First launch after updating code

### ❌ Can skip cleaning situations
- 🏃 **Quick launch**: Just view the interface
- 🔒 **Stable environment**: Code rarely modified
- ⚡ **Performance priority**: Launch speed is important
- 🎯 **Production environment**: Code is fixed

## 📊 Performance comparison

| Launch method | Launch time | Stability | Applicable scenarios |
|---------|---------|--------|----------|
| Default launch | Medium | High | Daily development |
| Skip cleaning | Fast | Medium | Quick view |
| Force cleaning | Slow | Highest | Problem troubleshooting |

## 🔧 Troubleshooting

### Common issues

#### 1. Streamlit file monitoring error
```
FileWatcherError: Cannot watch file changes
```
**Solution**: Use force cleaning
```bash
python web/run_web.py --force-clean
```

#### 2. Code modification does not take effect
**Symptoms**: Modified Python files but Web application did not update
**Solution**: Clean project cache
```bash
python web/run_web.py  # Default will clean project cache
```

#### 3. Launch too slow
**Symptoms**: Takes a long time to launch every time
**Solution**: Skip cleaning or use environment variable
```bash
python web/run_web.py --no-clean
# Or
set SKIP_CACHE_CLEAN=true
```

#### 4. Module import error
```
ModuleNotFoundError: No module named 'xxx'
```
**Solution**: Force clean all cache
```bash
python web/run_web.py --force-clean
```

## 💡 Best practices

### Development phase
- Use default launch (clean project cache)
- Use force cleaning when encountering issues
- Set IDE to automatically clean cache

### Demonstration/Production
- Use `--no-clean` for quick launch
- Set `SKIP_CACHE_CLEAN=true` environment variable
- Periodically manually clean cache

### Debugging issues
1. First try default launch
2. If the problem persists, use force cleaning
3. Check if the virtual environment is damaged
4. Reinstall dependency packages

## 🎯 Summary

Cache cleaning is to ensure stable operation of the Web application, especially in the development environment. Now you can choose different launch methods based on your needs:

- **Daily use**: `python web/run_web.py`
- **Quick launch**: `python web/run_web.py --no-clean`
- **Problem troubleshooting**: `python web/run_web.py --force-clean`

Choose the launch method that best suits your current needs!
