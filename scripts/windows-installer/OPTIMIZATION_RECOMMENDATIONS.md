# Windows 安装包优化建议

## 🔍 问题分析

### 当前问题
1. **安装慢**：解压 477MB ZIP 需要 2-5 分钟
2. **体积大**：安装包 452MB，便携版 ZIP 477MB
3. **NSIS 限制**：直接打包 1.2GB 文件会导致内存错误

### 根本原因
便携版目录包含了很多不必要的文件：
- `vendors/` - 2.5GB（嵌入式运行时）
- `venv/` - 723MB（虚拟环境，不应该打包）
- `data/` - 235MB（数据库数据，应该在安装时创建）

---

## 💡 优化方案

### 方案 1: 优化便携版内容（推荐）⭐

**目标**：减小便携版 ZIP 体积，从而加快安装速度

**步骤**：

1. **排除 venv 目录**
   - 不打包虚拟环境
   - 使用嵌入式 Python 的 site-packages

2. **优化 vendors 目录**
   - 只保留必要的运行时文件
   - 移除调试符号和文档

3. **排除数据目录**
   - 不打包 `data/` 目录
   - 安装时创建空目录

4. **排除日志和临时文件**
   - 不打包 `logs/`, `temp/`, `__pycache__/`

**预期效果**：
- 便携版 ZIP: 477MB → ~200MB（减少 58%）
- 安装时间: 2-5分钟 → 30秒-1分钟（减少 80%）
- 安装包大小: 452MB → ~180MB（减少 60%）

---

### 方案 2: 分离运行时和应用（中等复杂度）

**目标**：将大文件（vendors）与应用代码分离

**步骤**：

1. **创建两个 ZIP 包**
   - `runtime.zip` - vendors 目录（2.5GB，很少更新）
   - `app.zip` - 应用代码（~50MB，经常更新）

2. **安装时智能下载**
   - 检查是否已有 runtime.zip
   - 只下载缺失的部分

3. **增量更新**
   - 更新时只需下载 app.zip

**预期效果**：
- 首次安装: 下载 2.5GB
- 更新安装: 只下载 50MB
- 节省 98% 的更新流量

---

### 方案 3: 使用 7-Zip 自解压（简单）

**目标**：使用更高效的压缩算法

**步骤**：

1. **使用 7-Zip LZMA2 压缩**
   ```powershell
   7z a -t7z -m0=lzma2 -mx=9 -mfb=64 -md=32m -ms=on portable.7z portable\
   ```

2. **创建自解压程序**
   ```powershell
   copy /b 7zSD.sfx + config.txt + portable.7z installer.exe
   ```

3. **配置解压参数**
   - 显示进度条
   - 自动运行配置脚本

**预期效果**：
- 压缩率: 提升 20-30%
- 解压速度: 提升 10-20%
- 安装包大小: 452MB → ~320MB

---

## 🚀 立即可行的优化

### 优化 1: 清理便携版打包脚本

修改 `scripts/deployment/build_portable_package.ps1`：

```powershell
# 排除不必要的目录
$ExcludeDirs = @(
    "venv",
    "env",
    "__pycache__",
    "*.pyc",
    ".git",
    ".vscode",
    "data/mongodb/*",  # 保留目录结构，但不复制数据
    "data/redis/*",
    "logs/*",
    "temp/*"
)

# 优化 vendors 目录
$VendorsOptimize = @{
    "python" = @("*.pdb", "Doc", "tcl", "test")  # 移除调试符号和文档
    "mongodb" = @("*.pdb")
    "redis" = @("*.pdb")
}
```

### 优化 2: 使用更好的压缩参数

修改 NSIS 脚本：

```nsis
SetCompressor /SOLID /FINAL lzma
SetCompressorDictSize 64
SetDatablockOptimize on
```

### 优化 3: 显示详细进度

修改 NSIS 脚本，添加进度提示：

```nsis
DetailPrint "Extracting files... (this may take 2-5 minutes)"
DetailPrint "Progress: extracting portable package..."
DetailPrint "Please wait, do not close this window"
```

---

## 📊 优化效果对比

| 优化方案 | 安装包大小 | 安装时间 | 实施难度 | 推荐度 |
|---------|-----------|---------|---------|--------|
| **当前方案** | 452 MB | 2-5 分钟 | - | - |
| 优化便携版内容 | ~180 MB | 30秒-1分钟 | ⭐ 简单 | ⭐⭐⭐⭐⭐ |
| 分离运行时 | 50 MB (更新) | 10-30秒 (更新) | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐ |
| 使用 7-Zip | ~320 MB | 1-3 分钟 | ⭐⭐ 简单 | ⭐⭐⭐ |

---

## ✅ 推荐实施步骤

### 第一阶段：立即优化（1-2小时）

1. **清理 venv 目录**
   - 修改 `build_portable_package.ps1`
   - 排除 `venv/` 目录
   - 测试便携版是否正常运行

2. **优化 vendors 目录**
   - 移除 `.pdb` 调试符号
   - 移除文档和测试文件
   - 减少 20-30% 体积

3. **排除数据目录**
   - 不打包 `data/mongodb/*` 和 `data/redis/*`
   - 安装时创建空目录

**预期效果**：
- 便携版 ZIP: 477MB → ~200MB
- 安装时间: 2-5分钟 → 30秒-1分钟
- 用户体验显著提升

### 第二阶段：进一步优化（1-2天）

1. **实施运行时分离**
   - 创建 `runtime.zip` 和 `app.zip`
   - 实现智能下载逻辑
   - 支持增量更新

2. **优化安装流程**
   - 添加详细进度提示
   - 支持断点续传
   - 添加安装后验证

---

## 🎯 结论

**直接打包方式不适合当前项目**，因为：
1. NSIS 无法处理 1.2GB+ 的文件集合
2. 即使排除大文件，vendors (2.5GB) 仍然太大

**推荐方案**：
1. **短期**：优化便携版内容，减小 ZIP 体积（方案 1）
2. **长期**：分离运行时和应用，支持增量更新（方案 2）

**立即行动**：
- 修改 `build_portable_package.ps1` 排除 venv
- 优化 vendors 目录
- 测试优化后的安装包

---

**最后更新**: 2026-01-06  
**推荐方案**: 优化便携版内容（方案 1）

