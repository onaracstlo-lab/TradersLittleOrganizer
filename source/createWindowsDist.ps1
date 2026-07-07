param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+$')]
    [string]$BundleNumber,

    [string]$SourceRoot = $PSScriptRoot,
    [string]$DistRoot = '',
    [string[]]$CustomScanner = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($DistRoot)) {
    $DistRoot = "C:\tloDist-V1.0Build$BundleNumber"
}

$TargetDir = Join-Path $DistRoot 'apps\Windows'
$ReportPath = Join-Path $DistRoot 'scan-reports\windows.json'
$ScanScript = Join-Path $SourceRoot 'scan_release_artifacts.py'
$IconRoot = Join-Path $SourceRoot 'icons'

function Get-PythonRunner {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return @($py.Source, '-3') }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return @($python.Source) }
    $python3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3) { return @($python3.Source) }
    throw 'Python 3 was not found in PATH.'
}

function Invoke-Python {
    param([string[]]$Runner, [string[]]$Arguments)
    if ($Runner.Count -gt 1) {
        & $Runner[0] $Runner[1..($Runner.Count - 1)] @Arguments
    }
    else {
        & $Runner[0] @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

function Find-SourceScript {
    param([string]$Name)
    $candidates = @(
        (Join-Path $SourceRoot $Name),
        (Join-Path (Join-Path $SourceRoot 'searchApps') $Name)
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    throw "Required source script not found: $Name"
}

function Build-OneFile {
    param(
        [string[]]$PythonRunner,
        [string]$ScriptPath,
        [string[]]$AdditionalArgs = @()
    )

    $BaseName = [IO.Path]::GetFileNameWithoutExtension($ScriptPath)
    $WorkRoot = Join-Path $DistRoot ".build-Windows-$BaseName"
    if (Test-Path -LiteralPath $WorkRoot) {
        Remove-Item -LiteralPath $WorkRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $WorkRoot -Force | Out-Null

    $Arguments = @(
        '-m', 'PyInstaller',
        '--noconfirm', '--clean', '--onefile', '--noupx',
        '--workpath', (Join-Path $WorkRoot 'work'),
        '--specpath', $WorkRoot,
        '--distpath', $TargetDir,
        '--paths', $SourceRoot
    ) + $AdditionalArgs + @($ScriptPath)

    Invoke-Python -Runner $PythonRunner -Arguments $Arguments

    $Expected = Join-Path $TargetDir "$BaseName.exe"
    if (-not (Test-Path -LiteralPath $Expected -PathType Leaf)) {
        throw "Expected executable was not created or was quarantined: $Expected"
    }

    Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
}

$PythonRunner = Get-PythonRunner
Invoke-Python -Runner $PythonRunner -Arguments @('-m', 'PyInstaller', '--version')

if (-not (Test-Path -LiteralPath $ScanScript -PathType Leaf)) {
    throw "Required scan utility not found: $ScanScript"
}

if (Test-Path -LiteralPath $TargetDir) {
    Remove-Item -LiteralPath $TargetDir -Recurse -Force
}
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $ReportPath) -Force | Out-Null

$InventoryIcon = Join-Path $IconRoot 'tlo-inventory-icon.ico'
$SearchIcon = Join-Path $IconRoot 'tlo-search-icon.ico'
$TagIcon = Join-Path $IconRoot 'tlo-tag-icon.ico'

foreach ($RequiredIcon in @($InventoryIcon, $SearchIcon, $TagIcon)) {
    if (-not (Test-Path -LiteralPath $RequiredIcon -PathType Leaf)) {
        throw "Required Windows icon file not found: $RequiredIcon"
    }
}

$ArtistArgs = @('--windowed')
$SearchArgs = @('--windowed', "--icon=$SearchIcon")
$GuiArgs = @('--windowed', '--collect-all', 'mutagen', '--collect-all', 'imageio_ffmpeg', '--collect-all', 'tkinterdnd2', "--icon=$InventoryIcon")
$TagArgs = @('--collect-all', 'mutagen', '--collect-all', 'imageio_ffmpeg', "--icon=$TagIcon")

Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'search-artist-db.py') -AdditionalArgs $ArtistArgs
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-gsi.py') -AdditionalArgs $SearchArgs
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-gi.py')
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-ggi.py') -AdditionalArgs $GuiArgs
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-tag.py') -AdditionalArgs $TagArgs

# Optional Authenticode signing. Set TLO_WINDOWS_CERT_SHA1 to the certificate
# thumbprint and ensure signtool.exe is in PATH. Signing occurs before scanning.
if (-not [string]::IsNullOrWhiteSpace($env:TLO_WINDOWS_CERT_SHA1)) {
    $SignTool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if (-not $SignTool) {
        throw 'TLO_WINDOWS_CERT_SHA1 is set, but signtool.exe was not found in PATH.'
    }
    Get-ChildItem -LiteralPath $TargetDir -Filter '*.exe' -File | ForEach-Object {
        & $SignTool.Source sign /sha1 $env:TLO_WINDOWS_CERT_SHA1 /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $_.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "Authenticode signing failed for $($_.FullName)."
        }
    }
}

$ScanArguments = @(
    $ScanScript,
    '--platform', 'windows',
    '--artifact-dir', $TargetDir,
    '--report', $ReportPath
)
foreach ($scanner in $CustomScanner) {
    $ScanArguments += @('--custom-scanner', $scanner)
}
Invoke-Python -Runner $PythonRunner -Arguments $ScanArguments

# Recheck after antivirus has had a chance to quarantine a newly written file.
Start-Sleep -Seconds 2
$ExpectedExecutables = @('search-artist-db.exe', 'tlo-gsi.exe', 'tlo-gi.exe', 'tlo-ggi.exe', 'tlo-tag.exe')
foreach ($name in $ExpectedExecutables) {
    $path = Join-Path $TargetDir $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Executable disappeared after scanning, probably due to quarantine: $path"
    }
}

Write-Host "Windows executables built and scanned clean: $TargetDir"
Write-Host "Scan receipt: $ReportPath"
