param(
    [string]$InstallDir = ""
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = 'https://gitee.com/ialn8i/omj.git'
$RepoZip = 'https://gitee.com/ialn8i/omj/repository/archive/myself.zip'
$Branch = 'myself'
$PyVersion = '3.10.11'
$Port = 22267
$PypiMirrors = @(
    'https://mirrors.aliyun.com/pypi/simple',
    'https://pypi.tuna.tsinghua.edu.cn/simple',
    'https://pypi.org/simple'
)
$PyMirrors = @(
    "https://mirrors.huaweicloud.com/python/$PyVersion/python-$PyVersion-embed-amd64.zip",
    "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip"
)
$PipMirrors = @(
    'https://bootstrap.pypa.io/get-pip.py',
    'https://mirrors.aliyun.com/pypi/get-pip.py'
)

function Info($message) {
    Write-Host "[OMJ] $message" -ForegroundColor Cyan
}

function Warn($message) {
    Write-Host "[OMJ] $message" -ForegroundColor Yellow
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

function Download-File($urls, $dest, $what) {
    foreach ($url in $urls) {
        try {
            Info "下载$what：$url"
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $dest -TimeoutSec 300
            if ((Test-Path $dest) -and ((Get-Item $dest).Length -gt 0)) {
                return
            }
        } catch {
            Warn "下载失败：$($_.Exception.Message)"
        }
    }
    Fail "无法下载$what，请检查网络或代理后重试。"
}

Info '开始安装 OMJ...'

if ($InstallDir) {
    $installDir = [System.IO.Path]::GetFullPath($InstallDir)
} elseif (Test-Path (Join-Path $PSScriptRoot '.git')) {
    $installDir = $PSScriptRoot
} else {
    $installDir = Join-Path $env:USERPROFILE 'OMJ'
}

$git = Get-Exe 'git'
$hasGitRepo = Test-Path (Join-Path $installDir '.git')
$hasRepoFiles = Test-Path (Join-Path $installDir 'server.py')

if ($hasGitRepo) {
    if ($git) {
        Info '检测到已安装的 OMJ，正在更新...'
        Push-Location $installDir
        try {
            & $git pull --ff-only
            if ($LASTEXITCODE -ne 0) {
                Warn '自动更新失败，将继续使用当前版本。'
            }
        } finally {
            Pop-Location
        }
    }
} elseif ($hasRepoFiles) {
    Info "检测到已解压的 OMJ：$installDir"
} elseif ($git) {
    Info "正在克隆 $Repo ..."
    & $git clone --depth 1 --branch $Branch $Repo $installDir
    if ($LASTEXITCODE -ne 0) {
        Fail '克隆仓库失败，请检查网络后重试。'
    }
} else {
    Info '未找到 Git，改用 Gitee 压缩包下载...'
    if ((Test-Path $installDir) -and (Get-ChildItem $installDir -Force | Select-Object -First 1)) {
        Fail "安装目录非空：$installDir。请移走其中的文件后重试。"
    }
    $tmpZip = Join-Path $env:TEMP 'omj-release.zip'
    $tmpDir = Join-Path $env:TEMP ("omj-unzip-" + [Guid]::NewGuid().ToString('N'))
    Download-File @($RepoZip) $tmpZip 'OMJ 压缩包'
    Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force
    $source = Get-ChildItem -Path $tmpDir -Directory | Select-Object -First 1
    if (-not $source) {
        Fail '压缩包内容异常，未找到仓库目录。'
    }
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    Get-ChildItem -Path $source.FullName -Force | Copy-Item -Destination $installDir -Recurse -Force
    Remove-Item $tmpZip, $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

$toolkit = Join-Path $installDir 'toolkit'
$py = Join-Path $toolkit 'python.exe'

if (-not (Test-Path $py)) {
    Info "正在下载 Python $PyVersion 运行环境..."
    $tmpPy = Join-Path $env:TEMP "python-$PyVersion-embed-amd64.zip"
    Download-File $PyMirrors $tmpPy 'Python 运行时'
    New-Item -ItemType Directory -Force -Path $toolkit | Out-Null
    Expand-Archive -Path $tmpPy -DestinationPath $toolkit -Force
    Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue

    $pth = Join-Path $toolkit 'python310._pth'
    $pthContent = "python310.zip`r`n.`r`n..`r`nLib\site-packages`r`nimport site`r`n"
    [System.IO.File]::WriteAllText($pth, $pthContent, (New-Object System.Text.UTF8Encoding($false)))
}

& $py -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    Info '正在安装 pip...'
    $getPip = Join-Path $toolkit 'get-pip.py'
    Download-File $PipMirrors $getPip 'pip 安装脚本'
    & $py $getPip --no-warn-script-location
    if ($LASTEXITCODE -ne 0) {
        Fail 'pip 安装失败。'
    }
    Remove-Item $getPip -Force -ErrorAction SilentlyContinue
}

$requirements = Join-Path $installDir 'requirements.txt'
Info '正在安装依赖（首次安装需要几分钟）...'
$usedMirror = ''
foreach ($mirror in $PypiMirrors) {
    Info "使用源：$mirror"
    & $py -m pip install --disable-pip-version-check --no-warn-script-location --retries 5 --timeout 60 -r $requirements -i $mirror
    if ($LASTEXITCODE -eq 0) {
        $usedMirror = $mirror
        break
    }
    Warn '该源安装失败，尝试下一个...'
}
if (-not $usedMirror) {
    Fail '依赖安装失败，请查看上方日志。'
}

Info '正在校准 setuptools（保留 pkg_resources）...'
& $py -m pip install --disable-pip-version-check --no-warn-script-location --retries 5 --timeout 60 'setuptools==80.9.0' -i $usedMirror
if ($LASTEXITCODE -ne 0) {
    Fail '安装兼容版 setuptools 失败，adbutils 将无法导入。'
}

$adbInToolkit = Join-Path $toolkit 'Lib\site-packages\adbutils\binaries\adb.exe'
$systemAdb = Get-Exe 'adb'
if (Test-Path $adbInToolkit) {
    $adbPath = $adbInToolkit.Replace('\', '/')
    $adbOk = 'true'
} elseif ($systemAdb) {
    $adbPath = $systemAdb.Replace('\', '/')
    $adbOk = 'true'
} else {
    $adbPath = 'adb'
    $adbOk = 'false'
    Warn '未找到 ADB，将跳过设备连接和 uiautomator2 初始化。'
}

$gitPath = if ($git) { $git.Replace('\', '/') } else { 'git' }
$pythonPath = $py.Replace('\', '/')

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
    PypiMirror: "$usedMirror"
    InstallDependencies: false
  Adb:
    AdbExecutable: "$adbPath"
    ReplaceAdb: $adbOk
    AutoConnect: $adbOk
    InstallUiautomator2: $adbOk
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
    & $py -m deploy.installer
    if ($LASTEXITCODE -ne 0) {
        Fail '运行环境初始化失败，请查看上方日志。'
    }
} finally {
    Pop-Location
}

$startBat = @"
@echo off
cd /d "%~dp0"
"toolkit\python.exe" server.py
pause
"@
[System.IO.File]::WriteAllText((Join-Path $installDir 'start-omj.bat'), $startBat, $utf8NoBom)

Info '启动 OMJ 服务...'
Start-Process -FilePath $py -ArgumentList 'server.py' -WorkingDirectory $installDir
Start-Sleep -Seconds 6
Start-Process "http://127.0.0.1:$Port"

Info '安装完成。'
Info "安装目录：$installDir"
Info '已内置 Python 3.10，无需系统安装 Python。以后双击 start-omj.bat 启动。'
