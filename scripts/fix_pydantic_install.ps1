# 修复 Python 扩展包缺失问题
# 重新安装 pydantic、cryptography 等包，确保使用预编译的二进制包

param(
    [string]$InstallDir = "C:\TradingAgentsCN111f"
)

$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "修复 Python 扩展包缺失问题" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "安装目录: $InstallDir" -ForegroundColor Yellow
Write-Host ""

# 检查安装目录
if (-not (Test-Path $InstallDir)) {
    Write-Host "❌ 安装目录不存在: $InstallDir" -ForegroundColor Red
    exit 1
}

# 检查 Python 可执行文件
$pythonExe = Join-Path $InstallDir "vendors\python\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "❌ Python 可执行文件不存在: $pythonExe" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 找到 Python: $pythonExe" -ForegroundColor Green
Write-Host ""

# 检查当前 pydantic 版本
Write-Host "[1/4] 检查当前 pydantic 版本..." -ForegroundColor Yellow
$pydanticVersion = & $pythonExe -m pip show pydantic 2>&1 | Select-String "Version:"
if ($pydanticVersion) {
    Write-Host "  当前版本: $pydanticVersion" -ForegroundColor Gray
} else {
    Write-Host "  ⚠️ pydantic 未安装" -ForegroundColor Yellow
}
Write-Host ""

# 卸载有问题的包
Write-Host "[2/5] 卸载现有的扩展包..." -ForegroundColor Yellow
& $pythonExe -m pip uninstall -y pydantic pydantic_core cryptography PyJWT bcrypt 2>&1 | Out-Null
Write-Host "  ✅ 卸载完成" -ForegroundColor Green
Write-Host ""

# 重新安装 cryptography（使用预编译的二进制包）
Write-Host "[3/5] 重新安装 cryptography（使用预编译包）..." -ForegroundColor Yellow
Write-Host "  使用镜像: 阿里云" -ForegroundColor Gray
Write-Host "  选项: --only-binary :all: (强制使用预编译包)" -ForegroundColor Gray
Write-Host ""

$installArgs = @(
    "-m", "pip", "install",
    "cryptography==41.0.7",  # 固定版本，避免 46.x 的 PyO3 兼容性问题
    "zstandard",
    "--only-binary", ":all:",
    "-i", "https://mirrors.aliyun.com/pypi/simple/",
    "--trusted-host", "mirrors.aliyun.com",
    "--no-warn-script-location",
    "--force-reinstall"
)

Write-Host "  执行命令: python.exe $($installArgs -join ' ')" -ForegroundColor DarkGray
Write-Host ""

& $pythonExe @installArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ⚠️ 阿里云镜像失败，尝试清华镜像..." -ForegroundColor Yellow

    $installArgs[5] = "https://pypi.tuna.tsinghua.edu.cn/simple"
    $installArgs[7] = "pypi.tuna.tsinghua.edu.cn"

    & $pythonExe @installArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  ❌ cryptography 安装失败" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "  ✅ cryptography 安装完成" -ForegroundColor Green
Write-Host ""

# 重新安装 pydantic（使用预编译的二进制包）
Write-Host "[4/5] 重新安装 pydantic 和相关包（使用预编译包）..." -ForegroundColor Yellow
Write-Host "  使用镜像: 阿里云" -ForegroundColor Gray
Write-Host ""

$installArgs2 = @(
    "-m", "pip", "install",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "PyJWT>=2.0.0",
    "bcrypt>=4.0.0",
    "--only-binary", ":all:",
    "-i", "https://mirrors.aliyun.com/pypi/simple/",
    "--trusted-host", "mirrors.aliyun.com",
    "--no-warn-script-location"
)

Write-Host "  执行命令: python.exe $($installArgs2 -join ' ')" -ForegroundColor DarkGray
Write-Host ""

& $pythonExe @installArgs2

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ⚠️ 阿里云镜像失败，尝试清华镜像..." -ForegroundColor Yellow

    $installArgs2[9] = "https://pypi.tuna.tsinghua.edu.cn/simple"
    $installArgs2[11] = "pypi.tuna.tsinghua.edu.cn"

    & $pythonExe @installArgs2

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  ❌ pydantic 安装失败" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "  ✅ pydantic 安装完成" -ForegroundColor Green
Write-Host ""

# 验证安装
Write-Host "[5/5] 验证安装..." -ForegroundColor Yellow

# 检查 pydantic_core 扩展文件
$pydanticCoreDir = Join-Path $InstallDir "vendors\python\Lib\site-packages\pydantic_core"
$pydFiles = Get-ChildItem $pydanticCoreDir -Filter "*.pyd" -ErrorAction SilentlyContinue
if ($pydFiles) {
    Write-Host "  ✅ pydantic_core 扩展文件存在" -ForegroundColor Green
    foreach ($file in $pydFiles) {
        $fileSize = [math]::Round($file.Length / 1MB, 2)
        Write-Host "     $($file.Name) ($fileSize MB)" -ForegroundColor Gray
    }
} else {
    Write-Host "  ❌ pydantic_core 扩展文件缺失" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 检查 cryptography 扩展文件
$cryptoDir = Join-Path $InstallDir "vendors\python\Lib\site-packages\cryptography\hazmat\bindings"
$cryptoPydFiles = Get-ChildItem $cryptoDir -Filter "*.pyd" -Recurse -ErrorAction SilentlyContinue
if ($cryptoPydFiles) {
    Write-Host "  ✅ cryptography 扩展文件存在" -ForegroundColor Green
    Write-Host "     找到 $($cryptoPydFiles.Count) 个扩展文件" -ForegroundColor Gray
} else {
    Write-Host "  ❌ cryptography 扩展文件缺失" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 测试导入
Write-Host "  测试导入 cryptography..." -ForegroundColor Gray
$testImport1 = & $pythonExe -c "import cryptography; print(f'cryptography {cryptography.__version__}')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ $testImport1" -ForegroundColor Green
} else {
    Write-Host "  ❌ 导入失败: $testImport1" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "  测试导入 pydantic..." -ForegroundColor Gray
$testImport2 = & $pythonExe -c "import pydantic; print(f'pydantic {pydantic.__version__}')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ $testImport2" -ForegroundColor Green
} else {
    Write-Host "  ❌ 导入失败: $testImport2" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "  测试导入 PyJWT..." -ForegroundColor Gray
$testImport3 = & $pythonExe -c "import jwt; print(f'PyJWT {jwt.__version__}')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ $testImport3" -ForegroundColor Green
} else {
    Write-Host "  ❌ 导入失败: $testImport3" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ 修复完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步:" -ForegroundColor Yellow
Write-Host "  cd $InstallDir" -ForegroundColor Gray
Write-Host "  .\start_all.ps1" -ForegroundColor Gray
Write-Host ""

