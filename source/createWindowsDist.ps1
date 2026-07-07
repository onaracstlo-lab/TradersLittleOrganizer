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


function Assert-WindowsIcoIsDibBased {
    param(
        [Parameter(Mandatory = $true)][string]$IconPath,
        [Parameter(Mandatory = $true)][string]$DisplayName,
        [int]$MinimumIconImages = 5
    )

    $VerifierRoot = Join-Path $DistRoot '.build-icon-verification'
    New-Item -ItemType Directory -Path $VerifierRoot -Force | Out-Null
    $VerifierPath = Join-Path $VerifierRoot ('verify_source_ico_{0}.py' -f [guid]::NewGuid().ToString('N'))
    $Verifier = @"
import struct
import sys
from pathlib import Path

path = Path(sys.argv[1])
minimum = int(sys.argv[2])
name = sys.argv[3]
data = path.read_bytes()
if len(data) < 6:
    raise SystemExit(f"{name} is not a valid ICO file: too short")
reserved, icon_type, count = struct.unpack_from('<HHH', data, 0)
if reserved != 0 or icon_type != 1 or count < minimum:
    raise SystemExit(f"{name} is not a usable Windows ICO file: reserved={reserved}, type={icon_type}, count={count}, expected at least {minimum}")
for index in range(count):
    entry_offset = 6 + index * 16
    if entry_offset + 16 > len(data):
        raise SystemExit(f"{name} has a truncated ICO directory")
    width, height, colors, res, planes, bit_count, size, image_offset = struct.unpack_from('<BBBBHHII', data, entry_offset)
    blob = data[image_offset:image_offset + size]
    if len(blob) != size:
        raise SystemExit(f"{name} has truncated image data at entry {index}")
    if blob.startswith(bytes([137, 80, 78, 71, 13, 10, 26, 10])):
        raise SystemExit(f"{name} entry {index} is PNG-compressed inside the ICO; use DIB/BMP-based ICO entries for PyInstaller/Explorer compatibility")
print(f"Verified DIB/BMP-based Windows ICO for {name}: {count} images")
"@

    Set-Content -LiteralPath $VerifierPath -Value $Verifier -Encoding UTF8
    try {
        Invoke-Python -Runner $PythonRunner -Arguments @($VerifierPath, $IconPath, [string]$MinimumIconImages, $DisplayName)
    }
    finally {
        Remove-Item -LiteralPath $VerifierPath -Force -ErrorAction SilentlyContinue
    }
}

function Assert-WindowsExeMatchesSourceIcon {
    param(
        [Parameter(Mandatory = $true)][string]$ExePath,
        [Parameter(Mandatory = $true)][string]$IconPath,
        [Parameter(Mandatory = $true)][string]$DisplayName,
        [int]$MinimumIconImages = 5
    )

    if (-not (Test-Path -LiteralPath $ExePath -PathType Leaf)) {
        throw "Cannot verify Windows icon for ${DisplayName}; executable not found: $ExePath"
    }
    if (-not (Test-Path -LiteralPath $IconPath -PathType Leaf)) {
        throw "Cannot verify Windows icon for ${DisplayName}; icon not found: $IconPath"
    }

    $VerifierRoot = Join-Path $DistRoot '.build-icon-verification'
    New-Item -ItemType Directory -Path $VerifierRoot -Force | Out-Null
    $VerifierPath = Join-Path $VerifierRoot ('verify_windows_icon_match_{0}.py' -f [guid]::NewGuid().ToString('N'))
    $Verifier = @"
import hashlib
import struct
import sys
from pathlib import Path
import pefile

exe = Path(sys.argv[1])
ico = Path(sys.argv[2])
minimum = int(sys.argv[3])
name = sys.argv[4]

def ico_digests(path):
    data = path.read_bytes()
    if len(data) < 6:
        raise SystemExit(f"{name}: invalid ICO file {path}: too short")
    reserved, icon_type, count = struct.unpack_from('<HHH', data, 0)
    if reserved != 0 or icon_type != 1 or count < minimum:
        raise SystemExit(f"{name}: invalid ICO header in {path}: reserved={reserved}, type={icon_type}, count={count}")
    digests = []
    png_entries = 0
    for index in range(count):
        entry_offset = 6 + index * 16
        width, height, colors, res, planes, bit_count, size, image_offset = struct.unpack_from('<BBBBHHII', data, entry_offset)
        blob = data[image_offset:image_offset + size]
        if len(blob) != size:
            raise SystemExit(f"{name}: truncated ICO image entry {index} in {path}")
        if blob.startswith(bytes([137, 80, 78, 71, 13, 10, 26, 10])):
            png_entries += 1
        digests.append(hashlib.sha256(blob).hexdigest())
    if png_entries:
        raise SystemExit(f"{name}: {path} has {png_entries} PNG-compressed ICO entries; use DIB/BMP-based ICO entries")
    return set(digests), count

def exe_icon_digests(path):
    pe = pefile.PE(str(path), fast_load=False)
    digests = set()
    groups = 0
    try:
        for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if getattr(entry, 'id', None) == pefile.RESOURCE_TYPE['RT_ICON']:
                for icon_entry in entry.directory.entries:
                    for lang_entry in icon_entry.directory.entries:
                        data_entry = lang_entry.data.struct
                        blob = pe.get_data(data_entry.OffsetToData, data_entry.Size)
                        digests.add(hashlib.sha256(blob).hexdigest())
            elif getattr(entry, 'id', None) == pefile.RESOURCE_TYPE['RT_GROUP_ICON']:
                for group_entry in entry.directory.entries:
                    for lang_entry in group_entry.directory.entries:
                        groups += 1
    except AttributeError:
        pass
    return digests, groups

source_digests, source_count = ico_digests(ico)
exe_digests, group_count = exe_icon_digests(exe)
missing = source_digests - exe_digests
if group_count < 1 or len(exe_digests) < minimum or missing:
    raise SystemExit(
        f"{name} does not contain the packaged custom Windows icon from {ico}. "
        f"source_images={source_count}, exe_icon_images={len(exe_digests)}, group_icons={group_count}, missing_source_images={len(missing)}"
    )
print(f"Verified packaged custom Windows icon for {name}: source_images={source_count}, exe_icon_images={len(exe_digests)}, group_icons={group_count}")
"@

    Set-Content -LiteralPath $VerifierPath -Value $Verifier -Encoding UTF8
    try {
        Invoke-Python -Runner $PythonRunner -Arguments @($VerifierPath, $ExePath, $IconPath, [string]$MinimumIconImages, $DisplayName)
    }
    finally {
        Remove-Item -LiteralPath $VerifierPath -Force -ErrorAction SilentlyContinue
    }
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

Assert-WindowsIcoIsDibBased -IconPath $InventoryIcon -DisplayName 'TLO Inventory icon'
Assert-WindowsIcoIsDibBased -IconPath $SearchIcon -DisplayName 'TLO Search icon'
Assert-WindowsIcoIsDibBased -IconPath $TagIcon -DisplayName 'TLO Tagger icon'

$ArtistArgs = @('--windowed')
$SearchArgs = @('--windowed', "--icon=$SearchIcon")
$GuiArgs = @('--windowed', '--collect-all', 'mutagen', '--collect-all', 'imageio_ffmpeg', '--collect-all', 'tkinterdnd2', "--icon=$InventoryIcon")
$TagArgs = @('--collect-all', 'mutagen', '--collect-all', 'imageio_ffmpeg', "--icon=$TagIcon")

Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'search-artist-db.py') -AdditionalArgs $ArtistArgs
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-gsi.py') -AdditionalArgs $SearchArgs
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-gi.py')
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-ggi.py') -AdditionalArgs $GuiArgs
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-tag.py') -AdditionalArgs $TagArgs

Assert-WindowsExeMatchesSourceIcon -ExePath (Join-Path $TargetDir 'tlo-gsi.exe') -IconPath $SearchIcon -DisplayName 'TLO Search GUI'
Assert-WindowsExeMatchesSourceIcon -ExePath (Join-Path $TargetDir 'tlo-ggi.exe') -IconPath $InventoryIcon -DisplayName 'TLO Inventory GUI'
Assert-WindowsExeMatchesSourceIcon -ExePath (Join-Path $TargetDir 'tlo-tag.exe') -IconPath $TagIcon -DisplayName 'TLO Tagger'

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
