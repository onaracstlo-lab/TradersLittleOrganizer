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
    # Pin WixUI to the exact WiX tool version. The MSI data-folder chooser
    # must be present in the release; no silent fallback to a UI-less MSI.
    & dotnet tool run wix -- extension add WixToolset.UI.wixext/6.0.2
    if ($LASTEXITCODE -ne 0) { throw 'Pinned WiX UI extension installation failed.' }
    & dotnet tool run wix -- build -arch x64 -ext WixToolset.UI.wixext -loc (Join-Path $root 'msi\TLO.en-us.wxl') -o $msi $wxs
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

# Exercise the signed package on an isolated GitHub-hosted Windows runner;
# never install/uninstall a product on a developer's machine.
if ($env:GITHUB_ACTIONS -eq 'true' -and $env:RUNNER_ENVIRONMENT -eq 'github-hosted') {
    $installerKey = 'HKCU:\Software\TradersLittleOrganizer\Installer'
    $settingsKey = 'HKCU:\Software\TradersLittleOrganizer\UserSettings'
    if ((Test-Path -LiteralPath $installerKey) -or (Test-Path -LiteralPath $settingsKey)) {
        throw 'Native MSI database smoke test requires a clean disposable runner.'
    }
    $smokeTestDataHome = Join-Path $working 'native test data'
    $dbDir = Join-Path $smokeTestDataHome 'TLO_DBs'
    New-Item -ItemType Directory -Path $dbDir -Force | Out-Null
    $databases = @('artists.sqlite', 'venues.txt', 'cities.sqlite', 'venues.sqlite')
    foreach ($db in $databases) {
        # Existing unversioned and user-modified files must be replaced by MSI.
        $path = Join-Path $dbDir $db
        Set-Content -LiteralPath $path -Value 'old user-modified master'
        (Get-Item -LiteralPath $path).LastWriteTime = (Get-Date).AddDays(1)
    }
    $sentinels = @('bootlist.csv', 'tlo-preferences.ini', 'TLO_DBs\unmanaged.txt', 'logs\preserve.txt', 'setlists\preserve.txt')
    foreach ($relative in $sentinels) {
        $path = Join-Path $smokeTestDataHome $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
        Set-Content -LiteralPath $path -Value 'preserve user data'
    }
    $engine = Join-Path ([Environment]::GetFolderPath('System')) 'msiexec.exe'
    $log = Join-Path $working 'native-msi-install.log'
    $uninstallLog = Join-Path $working 'native-msi-uninstall.log'
    $homeArg = 'TLODATAFOLDER="' + $smokeTestDataHome + '"'
    $msiArg = '"' + $msi + '"'
    $previousUserHome = [Environment]::GetEnvironmentVariable('TLOHome', 'User')
    $attempted = $false
    try {
        $attempted = $true
        $result = Start-Process -FilePath $engine -ArgumentList @('/i', $msiArg, $homeArg, '/qn', '/norestart', '/L*V', ('"' + $log + '"')) -Wait -PassThru
        if ($result.ExitCode -ne 0) {
            Get-Content -LiteralPath $log -Tail 80 | Write-Host
            throw "Native MSI installation failed: $($result.ExitCode)"
        }
        foreach ($db in $databases) {
            $expected = (Get-FileHash -LiteralPath (Join-Path $DataSourceDirectory $db) -Algorithm SHA256).Hash
            $actual = (Get-FileHash -LiteralPath (Join-Path $dbDir $db) -Algorithm SHA256).Hash
            if ($actual -ne $expected) { throw "Native MSI did not install current database directly: $db" }
        }
        $program = (Get-ItemProperty -LiteralPath $installerKey).InstallPath
        $auxExe = Join-Path $program 'searchAuxDBs.exe'
        if (-not (Test-Path -LiteralPath $auxExe -PathType Leaf)) {
            throw 'Native MSI did not install searchAuxDBs.exe.'
        }
        if (Test-Path -LiteralPath (Join-Path $program 'search-artist-db.exe')) {
            throw 'Native MSI unexpectedly installed the obsolete artist search executable.'
        }
        $menuFolder = Join-Path ([Environment]::GetFolderPath('Programs')) 'Traders Little Organizer'
        $auxShortcut = Join-Path $menuFolder 'TLO Auxiliary Database Search.lnk'
        if (-not (Test-Path -LiteralPath $auxShortcut -PathType Leaf)) {
            throw 'Native MSI auxiliary database Start Menu shortcut is missing.'
        }
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($auxShortcut)
        if ([IO.Path]::GetFullPath($shortcut.TargetPath) -ne [IO.Path]::GetFullPath($auxExe)) {
            throw 'Native MSI auxiliary database shortcut points to the wrong executable.'
        }
        $configured = (Get-ItemProperty -LiteralPath $settingsKey).DataHome
        $userVariable = [Environment]::GetEnvironmentVariable('TLOHome', 'User')
        if ($configured.TrimEnd('\') -ne $smokeTestDataHome -or $userVariable.TrimEnd('\') -ne $smokeTestDataHome) {
            throw 'MSI did not persist the selected TLOHome.'
        }
        if (Test-Path -LiteralPath (Join-Path $program 'TLO_DBs')) {
            throw 'MSI unexpectedly installed a second database directory under the applications.'
        }
        foreach ($relative in $sentinels) {
            if ((Get-Content -LiteralPath (Join-Path $smokeTestDataHome $relative) -Raw).Trim() -ne 'preserve user data') {
                throw "MSI modified unmanaged user data: $relative"
            }
        }
        Write-Host 'Native MSI direct-install gate passed: all four database masters installed before application launch.'
    } finally {
        if ($attempted -and (Test-Path -LiteralPath $installerKey)) {
            $removed = Start-Process -FilePath $engine -ArgumentList @('/x', $msiArg, '/qn', '/norestart', '/L*V', ('"' + $uninstallLog + '"')) -Wait -PassThru
            if ($removed.ExitCode -ne 0) { throw "Native MSI uninstall failed: $($removed.ExitCode)" }
        }
        # The runner is disposable but persistent configuration must not point
        # to our temporary fixture for subsequent pipeline steps.
        if (Test-Path -LiteralPath $settingsKey) { Remove-Item -LiteralPath $settingsKey -Recurse -Force }
        [Environment]::SetEnvironmentVariable('TLOHome', $previousUserHome, 'User')
    }
    foreach ($relative in $sentinels) {
        if ((Get-Content -LiteralPath (Join-Path $smokeTestDataHome $relative) -Raw).Trim() -ne 'preserve user data') {
            throw "MSI uninstall modified unmanaged user data: $relative"
        }
    }
    foreach ($db in $databases) {
        if (Test-Path -LiteralPath (Join-Path $dbDir $db)) {
            throw "MSI uninstall did not remove owned database: $db"
        }
    }
    if ((Test-Path -LiteralPath $auxExe) -or (Test-Path -LiteralPath $auxShortcut)) {
        throw 'Native MSI uninstall retained the auxiliary database executable or shortcut.'
    }
    Write-Host 'Native MSI uninstall gate passed: unmanaged user data preserved.'
}

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
