$ErrorActionPreference = 'Stop'

$Repo = 'https://gitee.com/ialn8i/omj.git'
$Branch = 'myself'
$Port = 22267
$PypiMirror = 'https://pypi.tuna.tsinghua.edu.cn/simple'

function Info($message) {
    Write-Host "[OMJ] $message" -ForegroundColor Cyan
}

function Fail($message) {
    Write-Host "[错误] $message" -ForegroundColor Red
    exit 1
}

function Get-Exe($name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

Info '开始安装 OMJ...'

$git = Get-Exe 'git'
$python = Get-Exe 'python'
if (-not $python) {
    Fail '未找到 Python。请安装 Python 3.10-3.12，并勾选 Add Python to PATH：https://mirrors.huaweicloud.com/python/'
}

& $python -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) {
    Fail '需要 Python 3.10-3.12（推荐 3.10）。当前版本不满足要求。'
}

$insideRepo = Test-Path (Join-Path $PSScriptRoot '.git')
if ($insideRepo) {
    $installDir = $PSScriptRoot
} else {
    $installDir = Join-Path $env:USERPROFILE 'OMJ'
}

if (-not (Test-Path (Join-Path $installDir '.git'))) {
    if (-not $git) {
        Fail '未找到 Git。请先安装 Git for Windows：https://git-scm.com/download/win'
    }
    if ((Test-Path $installDir) -and (Get-ChildItem $installDir -Force | Select-Object -First 1)) {
        Fail "安装目录非空：$installDir。请移走其中的文件后重试。"
    }
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    Info "正在克隆 $Repo ..."
    & $git clone --branch $Branch $Repo $installDir
    if ($LASTEXITCODE -ne 0) {
        Fail '克隆仓库失败，请检查网络后重试。'
    }
} else {
    Info '检测到已安装的 OMJ，正在更新...'
    Push-Location $installDir
    try {
        if ($git) {
            & $git pull --ff-only
            if ($LASTEXITCODE -ne 0) {
                Info '自动更新失败，将继续使用当前版本。'
            }
        }
    } finally {
        Pop-Location
    }
}

$venv = Join-Path $installDir '.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Info '正在创建 Python 虚拟环境...'
    & $python -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        Fail '创建虚拟环境失败。'
    }
}

Info '正在安装依赖（首次安装可能需要几分钟）...'
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $installDir 'requirements.txt') -i $PypiMirror
if ($LASTEXITCODE -ne 0) {
    Info '镜像源安装失败，改用官方源重试...'
    & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $installDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) {
        Fail '依赖安装失败，请查看上方日志。'
    }
}

$adb = Get-Exe 'adb'
$gitPath = if ($git) { $git.Replace('\', '/') } else { 'git' }
$pythonPath = $venvPython.Replace('\', '/')
$adbPath = if ($adb) { $adb.Replace('\', '/') } else { '' }
$autoAdb = if ($adbPath) { 'true' } else { 'false' }

$deployYaml = @"
Deploy:
  Git:
    Repository: "$Repo"
    Branch: "$Branch"
    GitExecutable: "$gitPath"
    AutoUpdate: false
    KeepLocalChanges: false
  Python:
    PythonExecutable: "$pythonPath"
    PypiMirror: "$PypiMirror"
    InstallDependencies: false
  Adb:
    AdbExecutable: "$(if ($adbPath) { $adbPath } else { 'adb' })"
    ReplaceAdb: false
    AutoConnect: $autoAdb
    InstallUiautomator2: $autoAdb
  Webui:
    Language: zh-CN
    WebuiPort: $Port
"@

$configDir = Join-Path $installDir 'config'
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $configDir 'deploy.yaml'), $deployYaml, $utf8NoBom)

Push-Location $installDir
try {
    Info '正在初始化运行环境...'
    & $venvPython -m deploy.installer
    if ($LASTEXITCODE -ne 0) {
        Fail '运行环境初始化失败，请查看上方日志。'
    }
} finally {
    Pop-Location
}

$startBat = @"
@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" server.py
pause
"@
[System.IO.File]::WriteAllText((Join-Path $installDir 'start-omj.bat'), $startBat, $utf8NoBom)

Info '启动 OMJ 服务...'
Start-Process -FilePath $venvPython -ArgumentList 'server.py' -WorkingDirectory $installDir
Start-Sleep -Seconds 6
Start-Process "http://127.0.0.1:$Port"

Info '安装完成。'
Info "安装目录：$installDir"
Info '以后可双击 start-omj.bat 启动，或运行其中的 python server.py。'
