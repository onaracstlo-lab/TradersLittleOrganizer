# Creates the Windows MSI from the already-signed Windows COMPLETE tree.
# Run after signing/verification of EXEs, before publishing/signing release metadata.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SignedWindowsTree,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [Parameter(Mandatory)][string]$DataSourceDirectory,
    [Parameter(Mandatory)][ValidateRange(1, 65535)][int]$BuildNumber,
    [string]$VersionPrefix = '1.7',
    [string]$SignToolPath = $env:TLO_SIGNTOOL_PATH,
    [string]$MainExe
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'MSI build requires a Windows runner.' }
# Updater integration is tested by CI.
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = (Resolve-Path -LiteralPath $SignedWindowsTree).Path
if (-not $SignToolPath -or -not (Test-Path -LiteralPath $SignToolPath -PathType Leaf)) { throw 'An existing trusted signtool.exe path is required.' }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'python must be on PATH.' }
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { throw '.NET SDK must be on PATH.' }
if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Missing staged Windows tree: $source" }

# These are the same binaries as the ZIP release, and must already be signed.
$executables = @(Get-ChildItem -LiteralPath $source -Recurse -File -Filter '*.exe')
if ($executables.Count -eq 0) { throw 'Signed Windows tree has no executables.' }
foreach ($exe in $executables) {
    & $SignToolPath verify /pa /all /v $exe.FullName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Unsigned or invalid Windows executable: $($exe.FullName)" }
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$output = (Resolve-Path -LiteralPath $OutputDirectory).Path
$working = Join-Path $env:RUNNER_TEMP ('tlo-msi-work-' + $BuildNumber)
$stage = Join-Path $working 'payload'
$wxs = Join-Path $working 'TLO.Generated.wxs'
if (Test-Path -LiteralPath $working) { Remove-Item -LiteralPath $working -Recurse -Force }
New-Item -ItemType Directory -Path $working -Force | Out-Null
$version = "$VersionPrefix.$BuildNumber"
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid MSI version: $version" }
$filename = "TLO_V${VersionPrefix}Build${BuildNumber}_Windows_x64.msi"
$msi = Join-Path $output $filename

$generatorArgs = @((Join-Path $root 'msi\generate_wix.py'), '--source-stage', $source,
    '--prepared-stage', $stage, '--worker', (Join-Path $root 'msi\TLO-MSI-Update-Worker.ps1'),
    '--wxs', $wxs, '--version', $version,
    '--data-source', $DataSourceDirectory, '--document-source', $root)
if ($MainExe) { $generatorArgs += @('--main-exe', $MainExe) }
& python @generatorArgs
if ($LASTEXITCODE -ne 0) { throw 'WiX source generation failed.' }

Push-Location $root
try {
    & dotnet tool restore
    if ($LASTEXITCODE -ne 0) { throw 'Pinned WiX 6.0.2 tool restore failed.' }
    & dotnet tool run wix -- build -arch x64 -o $msi $wxs
    if ($LASTEXITCODE -ne 0) { throw 'WiX MSI build failed.' }
    & dotnet tool run wix -- msi validate $msi
    if ($LASTEXITCODE -ne 0) { throw 'MSI ICE validation failed.' }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $msi -PathType Leaf)) { throw 'WiX did not produce MSI.' }
# Reuse EXACTLY the Azure Artifact Signing metadata/DLIB used by the EXE pipeline.
$MetadataFile = $env:TLO_ARTIFACT_SIGNING_METADATA
$DlibFile = $env:TLO_ARTIFACT_SIGNING_DLIB
if (-not $MetadataFile -or -not $DlibFile -or
    -not (Test-Path -LiteralPath $MetadataFile -PathType Leaf) -or
    -not (Test-Path -LiteralPath $DlibFile -PathType Leaf)) {
    throw 'MSI signing requires the approved Artifact Signing metadata and DLIB.'
}
& $SignToolPath sign /v /fd SHA256 /tr http://timestamp.acs.microsoft.com /td SHA256 /dlib $DlibFile /dmdf $MetadataFile $msi
if ($LASTEXITCODE -ne 0) { throw 'MSI Azure Artifact Signing failed.' }
& $SignToolPath verify /pa /all /v $msi | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'MSI Authenticode verification failed.' }
$sig = Get-AuthenticodeSignature -LiteralPath $msi
if ($sig.Status -ne 'Valid') { throw "MSI signature status: $($sig.Status)" }

$hash = (Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash.ToLowerInvariant()
$shaFile = "$msi.sha256"
Set-Content -LiteralPath $shaFile -Value "$hash  $filename" -Encoding ascii
$releaseFragment = [ordered]@{
    format = 1; install_kind = 'msi'; platform = 'windows-x64';
    version = $version; asset = $filename; sha256 = $hash;
    bytes = (Get-Item -LiteralPath $msi).Length;
    # This is an UNSIGNED FRAGMENT, not an authenticated update manifest.
    # Fold it into the existing SIGNED update manifest before signing it.
    release_metadata_signing = "Protect-TLORelease.ps1"
}
$metadataPath = Join-Path $output "$filename.release-fragment.json"
$releaseFragment | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $metadataPath -Encoding utf8
Write-Host "Signed and verified MSI: $msi"
Write-Host "SHA256: $hash"
Write-Host "Unsigned manifest fragment (must be added to signed release metadata): $metadataPath"
