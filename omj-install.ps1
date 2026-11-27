param(
    [string]$InstallDir = ""
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue

$Branch = 'myself'
$RepoZipMirrors = @(
    [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('aHR0cHM6Ly9naXRlZS5jb20vaWFsbjhpL29tai9yZXBvc2l0b3J5L2FyY2hpdmUvbXlzZWxmLnppcA==')),
    [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('aHR0cHM6Ly9naXRodWIuY29tL2lsYW44aS9vbWovYXJjaGl2ZS9yZWZzL2hlYWRzL215c2VsZi56aXA='))
)
$RepoZip = $RepoZipMirrors[0]
$Repo = $RepoZip.Substring(0, $RepoZip.IndexOf('/repository/')) + '.git'
$PyVersion = '3.10.11'
$Port = 22267
$PypiMirrors = @(
    'https://mirrors.aliyun.com/pypi/simple',
    'https://mirrors.cloud.tencent.com/pypi/simple',
    'https://pypi.tuna.tsinghua.edu.cn/simple',
    'https://pypi.org/simple'
)
$PyMirrors = @(
    "https://www.nuget.org/api/v2/package/python/$PyVersion"
)
$PipMirrors = @(
    'https://mirrors.aliyun.com/pypi/get-pip.py',
    'https://bootstrap.pypa.io/get-pip.py'
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

# PowerShell 5.1 在 ErrorActionPreference=Stop 时会把原生命令的 stderr
# 当成终止错误（NativeCommandError）。这里绕过 PowerShell 的原生命令调用，
# 直接用 Process 执行并返回退出码，避免误导性的红色报错。
function Invoke-Exe($file, $arguments, [switch]$Quiet) {
    $argLine = ($arguments | ForEach-Object {
        $a = [string]$_
        if ($a -match '\s') { '"' + ($a -replace '"', '\"') + '"' } else { $a }
    }) -join ' '

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $file
    $psi.Arguments = $argLine
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::Default
    $psi.StandardErrorEncoding = [System.Text.Encoding]::Default

    $proc = [System.Diagnostics.Process]::Start($psi)
    $outTask = $proc.StandardOutput.ReadToEndAsync()
    $errTask = $proc.StandardError.ReadToEndAsync()
    $proc.WaitForExit()
    $out = $outTask.Result
    $err = $errTask.Result

    if (-not $Quiet) {
        if ($out) { Write-Host $out.TrimEnd() }
        if ($proc.ExitCode -ne 0 -and $err) { Write-Host $err.TrimEnd() -ForegroundColor DarkGray }
    }
    return $proc.ExitCode
}

function Test-Zip($path) {
    try {
        $zip = [System.IO.Compression.ZipFile]::OpenRead($path)
        try {
            return ($zip.Entries.Count -gt 0)
        } finally {
            $zip.Dispose()
        }
    } catch {
        return $false
    }
}

function Download-File($urls, $dest, $what, [switch]$Zip) {
    $curl = Get-Exe 'curl.exe'
    foreach ($url in $urls) {
        Info "正在下载$what..."
        $ok = $false

        # Gitee 会对 PowerShell 的 Invoke-WebRequest 返回拦截页，优先用 curl.exe。
        if ($curl) {
            $code = Invoke-Exe $curl @('-sS', '-L', '--fail', '--retry', '3', '-o', $dest, $url) -Quiet
            if ($code -eq 0 -and (Test-Path $dest) -and ((Get-Item $dest).Length -gt 0)) {
                $ok = $true
            }
        }

        if (-not $ok) {
            try {
                Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $dest -TimeoutSec 600
                if ((Test-Path $dest) -and ((Get-Item $dest).Length -gt 0)) {
                    $ok = $true
                }
            } catch {
                $ok = $false
            }
        }

        if ($ok -and (-not $Zip -or (Test-Zip $dest))) {
            return
        }

        Warn '下载内容无效，尝试下一个下载源...'
        Remove-Item $dest -Force -ErrorAction SilentlyContinue
    }
    Fail "无法下载$what，请检查网络或代理后重试。"
}

# 安装目录中不保留真实仓库地址。
function Hide-RepoAddress($root) {
    if ([string]::IsNullOrEmpty($Repo)) { return }
    $fake = 'https://localhost/omj.git'
    foreach ($rel in @('deploy/template', 'deploy/config.py', 'config/deploy.yaml')) {
        $file = Join-Path $root $rel
        if (-not (Test-Path $file)) { continue }
        $text = [System.IO.File]::ReadAllText($file)
        if ($text.Contains($Repo)) {
            $text = $text.Replace($Repo, $fake)
            [System.IO.File]::WriteAllText($file, $text, (New-Object System.Text.UTF8Encoding($false)))
        }
    }
}

Info '开始安装 OMJ...'

if ($InstallDir) {
    $installDir = [System.IO.Path]::GetFullPath($InstallDir)
} else {
    $installDir = $PSScriptRoot
}
$isDevRepo = ($installDir -eq $PSScriptRoot) -and (Test-Path (Join-Path $PSScriptRoot '.git'))
$downloadDir = Join-Path $installDir '.download'
$origTemp = $env:TEMP
$origTmp = $env:TMP

$hasRepoFiles = Test-Path (Join-Path $installDir 'server.py')

if (-not $hasRepoFiles -and $installDir -ne $PSScriptRoot) {
    if ((Test-Path $installDir) -and (Get-ChildItem $installDir -Force | Select-Object -First 1)) {
        Fail "安装目录非空：$installDir。请移走其中的文件后重试。"
    }
}

New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
$env:TEMP = Join-Path $downloadDir 'tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $downloadDir 'pip-cache'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

if ($hasRepoFiles) {
    Info "检测到已解压的 OMJ：$installDir"
} else {
    $tmpZip = Join-Path $downloadDir 'omj-release.zip'
    $tmpDir = Join-Path $downloadDir ("omj-unzip-" + [Guid]::NewGuid().ToString('N'))
    Download-File $RepoZipMirrors $tmpZip 'OMJ 安装包' -Zip
    try {
        [System.IO.Compression.ZipFile]::ExtractToDirectory($tmpZip, $tmpDir)
    } catch {
        Fail '安装包解压失败，请检查网络后重试。'
    }
    $source = Get-ChildItem -Path $tmpDir -Directory | Select-Object -First 1
    if (-not $source) {
        Fail '压缩包内容异常，未找到安装目录。'
    }
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    Get-ChildItem -Path $source.FullName -Force | Copy-Item -Destination $installDir -Recurse -Force
    Remove-Item $tmpZip, $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

# 仅在非开发仓库目录中清理真实仓库地址。
if (-not $isDevRepo) {
    $gitDir = Join-Path $installDir '.git'
    if (Test-Path $gitDir) {
        Remove-Item $gitDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    Hide-RepoAddress $installDir
}

$toolkit = Join-Path $installDir 'toolkit'
$py = Join-Path $toolkit 'python.exe'

$runtimeMarker = Join-Path $toolkit '.omj_runtime'
$runtimeOk = (Test-Path $py) -and (Test-Path $runtimeMarker) -and ((Get-Content $runtimeMarker -Raw -ErrorAction SilentlyContinue).Trim() -eq "nuget-$PyVersion")

if (-not $runtimeOk) {
    Info "正在下载 Python $PyVersion 运行环境..."
    $tmpPy = Join-Path $env:TEMP "python-$PyVersion.nupkg"
    Download-File $PyMirrors $tmpPy 'Python 运行时' -Zip
    $extractDir = Join-Path $env:TEMP ("python-extract-" + [Guid]::NewGuid().ToString('N'))
    try {
        [System.IO.Compression.ZipFile]::ExtractToDirectory($tmpPy, $extractDir)
    } catch {
        Fail 'Python 运行时解压失败，请检查网络后重试。'
    }
    $tools = Join-Path $extractDir 'tools'
    if (-not (Test-Path $tools)) {
        Fail 'Python 安装包内容异常。'
    }
    if (Test-Path $toolkit) {
        Remove-Item $toolkit -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Force -Path $toolkit | Out-Null
    Get-ChildItem -Path $tools -Force | Copy-Item -Destination $toolkit -Recurse -Force
    Remove-Item $tmpPy, $extractDir -Recurse -Force -ErrorAction SilentlyContinue
    [System.IO.File]::WriteAllText($runtimeMarker, "nuget-$PyVersion", (New-Object System.Text.UTF8Encoding($false)))
}

$pth = Join-Path $toolkit 'python310._pth'
if (Test-Path $pth) {
    Remove-Item $pth -Force -ErrorAction SilentlyContinue
}

Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
$env:PYTHONPATH = $installDir

$pipCode = Invoke-Exe $py @('-c', 'import pip') -Quiet
if ($pipCode -ne 0) {
    Info '正在安装 pip...'
    $getPip = Join-Path $toolkit 'get-pip.py'
    Download-File $PipMirrors $getPip 'pip 安装脚本'
    $code = Invoke-Exe $py @($getPip, '--no-warn-script-location')
    if ($code -ne 0) {
        Fail 'pip 安装失败。'
    }
    Remove-Item $getPip -Force -ErrorAction SilentlyContinue
}

Info '正在升级 pip...'
foreach ($mirror in $PypiMirrors) {
    $code = Invoke-Exe $py @('-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location', '--upgrade', 'pip', 'wheel', '-i', $mirror)
    if ($code -eq 0) {
        break
    }
    Warn 'pip 升级失败，尝试下一个源...'
}

$futureWheel = Join-Path $PSScriptRoot 'vendor\future-0.18.3-py3-none-any.whl'
if (Test-Path $futureWheel) {
    Info '正在预装 future...'
    $code = Invoke-Exe $py @('-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location', '--no-deps', '--no-index', $futureWheel)
    if ($code -ne 0) {
        Warn 'future 预装失败，将继续尝试在线安装。'
    }
}

$requirements = Join-Path $installDir 'requirements.txt'
Info '正在安装依赖（首次安装需要几分钟）...'
$usedMirror = ''
foreach ($mirror in $PypiMirrors) {
    Info "使用源：$mirror"
    $code = Invoke-Exe $py @('-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location', '--retries', '5', '--timeout', '60', '--prefer-binary', '-r', $requirements, '-i', $mirror)
    if ($code -eq 0) {
        $usedMirror = $mirror
        break
    }
    Warn '该源安装失败，尝试下一个...'
}
if (-not $usedMirror) {
    Fail '依赖安装失败，请查看上方日志。'
}

Info '正在校准 setuptools（保留 pkg_resources）...'
$code = Invoke-Exe $py @('-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location', '--retries', '5', '--timeout', '60', 'setuptools==80.9.0', '-i', $usedMirror)
if ($code -ne 0) {
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

$pythonPath = $py.Replace('\', '/')

$deployYaml = @"
Deploy:
  Git:
    Repository: https://localhost/omj.git
    Branch: $Branch
    GitExecutable: git
    AutoUpdate: false
    KeepLocalChanges: false
  Python:
    PythonExecutable: $pythonPath
    PypiMirror: $usedMirror
    InstallDependencies: false
  Adb:
    AdbExecutable: $adbPath
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
    $code = Invoke-Exe $py @('-m', 'deploy.installer')
    if ($code -ne 0) {
        Fail '运行环境初始化失败，请查看上方日志。'
    }
} finally {
    Pop-Location
}

$startBat = @"
@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
set "PADDLE_PDX_CACHE_HOME=%~dp0models"
set "HF_HOME=%~dp0models\huggingface"
set "MODELSCOPE_CACHE=%~dp0models\modelscope"
"toolkit\python.exe" server.py
pause
"@
[System.IO.File]::WriteAllText((Join-Path $installDir 'start-omj.bat'), $startBat, $utf8NoBom)

$env:TEMP = $origTemp
$env:TMP = $origTmp
Remove-Item Env:PIP_CACHE_DIR -ErrorAction SilentlyContinue
Remove-Item $downloadDir -Recurse -Force -ErrorAction SilentlyContinue

$modelsDir = Join-Path $installDir 'models'
$env:PADDLE_PDX_CACHE_HOME = $modelsDir
$env:HF_HOME = Join-Path $modelsDir 'huggingface'
$env:MODELSCOPE_CACHE = Join-Path $modelsDir 'modelscope'

Info '启动 OMJ 服务...'
Start-Process -FilePath $py -ArgumentList 'server.py' -WorkingDirectory $installDir
Start-Sleep -Seconds 6
Start-Process "http://127.0.0.1:$Port"

Info '安装完成。'
Info "安装目录：$installDir"
Info '已内置 Python 3.10，无需系统安装 Python。以后双击 start-omj.bat 启动。'
