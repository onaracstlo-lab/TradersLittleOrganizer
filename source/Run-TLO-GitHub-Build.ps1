# TLO GitHub Build Process version: v075
[CmdletBinding()]
param(
    # Deprecated. Retained only for callers that explicitly pass -Build. Normal use is -bnumber.
    [ValidatePattern('^\d{1,5}[A-Za-z]?$')]
    [string]$Build = '',

    [string]$VNumber = '',

    [ValidatePattern('^\d{1,5}[A-Za-z]?$')]
    [string]$BNumber = '',

    [Parameter(Position = 0)]
    [string]$Bundle = '',

    # Repositories are fixed for the TLO Option A process. These older parameters are
    # retained only to fail clearly if an unexpected repository is supplied.
    [string]$Repo = '',
    [string]$BuildRepo = '',
    [string]$ReleaseRepo = '',

    # Default is build-only. Use -release to publish to the fixed public release repo.
    [switch]$Release,
    [switch]$FromBuilt,
    [switch]$PublishRelease,
    [switch]$KeepGitHubRun,
    [switch]$AllowPrivateBuildRepo,
    [switch]$AllowPrivateReleaseRepo,

    [string]$WorkflowFile = "$PSScriptRoot\support\05-GitHub-Build-Release.yml",
    [string]$BuilderFile = "$PSScriptRoot\support\06-Assemble-TLO-Release.py",
    [string]$WorkRoot = "C:\TLO-GitHub-Build",
    [string]$ReleaseRoot = "C:\TLO-Releases",
    [string]$ArtistDbRoot = "/mnt/c/dev/ArtistDB-Master",
    [switch]$KeepSnapshot,
    [switch]$SkipDefenderScan
)

$ProcessVersion = 'v075'
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Require-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required command not found: $Name"
    }
    return $command
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string[]]$ArgumentList = @(),
        [switch]$AllowFailure
    )
    & $Command @ArgumentList
    if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
        throw "$Command failed with exit code $LASTEXITCODE."
    }
}

function Invoke-QuietNative {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string[]]$ArgumentList = @(),
        [switch]$CaptureErrorOutput
    )

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        if ($CaptureErrorOutput) {
            # Preserve native stderr for callers that need diagnostics while still
            # preventing a nonzero native exit code from being mistaken for a
            # PowerShell terminating error. On success this remains stdout-only.
            $output = & $Command @ArgumentList 2>&1
        }
        else {
            $output = & $Command @ArgumentList 2>$null
        }
        $exitCode = $LASTEXITCODE
        return [pscustomobject]@{
            ExitCode = $exitCode
            Output = @($output)
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Find-PythonRunner {
    $candidates = @(
        @{ Command = 'python3'; Prefix = @() },
        @{ Command = 'python'; Prefix = @() },
        @{ Command = 'py'; Prefix = @('-3') }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) {
            continue
        }

        $versionText = & $candidate.Command @($candidate.Prefix) --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            continue
        }

        $joinedVersion = ($versionText | Out-String).Trim()
        if ($joinedVersion -match 'Python\s+3\.') {
            $candidate['VersionText'] = $joinedVersion
            return $candidate
        }
    }

    return $null
}

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)]$Runner,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $Runner.Command @($Runner.Prefix) @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Text
    )
    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $Parent = [System.IO.Path]::GetDirectoryName($FullPath)
    if (-not [string]::IsNullOrWhiteSpace($Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }
    $encoding = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($FullPath, $Text, $encoding)
}

function Resolve-DefaultDownloadDirectory {
    $UserProfile = [Environment]::GetFolderPath('UserProfile')
    if ([string]::IsNullOrWhiteSpace($UserProfile)) {
        $UserProfile = $env:USERPROFILE
    }
    if ([string]::IsNullOrWhiteSpace($UserProfile)) {
        throw 'Unable to determine the current user profile directory for the default Downloads folder.'
    }
    return (Join-Path $UserProfile 'Downloads')
}

function Test-FullyQualifiedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    try {
        return [System.IO.Path]::IsPathFullyQualified($Path)
    }
    catch {
        $Root = [System.IO.Path]::GetPathRoot($Path)
        return (-not [string]::IsNullOrWhiteSpace($Root))
    }
}

function Resolve-BundleDirectory {
    param([string]$BundleDirectoryArgument)

    $Candidate = $BundleDirectoryArgument
    if ([string]::IsNullOrWhiteSpace($Candidate)) {
        $Candidate = Resolve-DefaultDownloadDirectory
    }
    if (-not (Test-FullyQualifiedPath -Path $Candidate)) {
        throw "--bundle must be a complete path to the directory containing music_inventory_flat_bundle_v$BuildToken.zip: $Candidate"
    }
    if (-not (Test-Path -LiteralPath $Candidate -PathType Container)) {
        throw "Bundle directory not found: $Candidate"
    }
    return [System.IO.Path]::GetFullPath($Candidate)
}

function Add-UniqueCandidatePath {
    param(
        [AllowEmptyCollection()][System.Collections.Generic.List[string]]$Candidates,
        [string]$Candidate
    )

    if ($null -eq $Candidates) {
        return
    }
    if ([string]::IsNullOrWhiteSpace($Candidate)) {
        return
    }
    foreach ($Existing in $Candidates) {
        if ([string]::Equals($Existing, $Candidate, [System.StringComparison]::OrdinalIgnoreCase)) {
            return
        }
    }
    $Candidates.Add($Candidate) | Out-Null
}

function Get-PortablePathCandidates {
    param([AllowEmptyString()][string]$Path)

    $Candidates = [System.Collections.Generic.List[string]]::new()
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return @($Candidates)
    }
    Add-UniqueCandidatePath -Candidates $Candidates -Candidate $Path

    if ($Path -match '^/mnt/([A-Za-z])/(.+)$') {
        $DriveLetter = $Matches[1].ToUpperInvariant()
        $Rest = $Matches[2].Replace('/', '\')
        Add-UniqueCandidatePath -Candidates $Candidates -Candidate (('{0}:\{1}' -f $DriveLetter, $Rest))
    }

    if ($Path -match '^/([A-Za-z])/(.+)$') {
        $DriveLetter = $Matches[1].ToUpperInvariant()
        $Rest = $Matches[2].Replace('/', '\')
        Add-UniqueCandidatePath -Candidates $Candidates -Candidate (('{0}:\{1}' -f $DriveLetter, $Rest))
    }

    return @($Candidates)
}

function Resolve-ArtistDbMasterDirectory {
    param([AllowEmptyString()][string]$RequestedPath)

    $Candidates = [System.Collections.Generic.List[string]]::new()
    foreach ($Candidate in (Get-PortablePathCandidates -Path $RequestedPath)) {
        Add-UniqueCandidatePath -Candidates $Candidates -Candidate $Candidate
    }
    foreach ($Candidate in (Get-PortablePathCandidates -Path '/mnt/c/dev/ArtistDB-Master')) {
        Add-UniqueCandidatePath -Candidates $Candidates -Candidate $Candidate
    }
    Add-UniqueCandidatePath -Candidates $Candidates -Candidate 'C:\dev\ArtistDB-Master'

    foreach ($Candidate in $Candidates) {
        try {
            $Full = [System.IO.Path]::GetFullPath($Candidate)
            if (Test-Path -LiteralPath $Full -PathType Container) {
                return $Full
            }
        }
        catch {
            if (Test-Path -LiteralPath $Candidate -PathType Container) {
                return $Candidate
            }
        }
    }

    throw "ArtistDB master directory not found. Checked: $($Candidates -join ', ')"
}

function Copy-RequiredArtistDbFilesIntoSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDirectory,
        [Parameter(Mandatory = $true)][string]$SnapshotRoot
    )

    $TargetDirectory = Join-Path $SnapshotRoot 'TLO_DBs'
    New-Item -ItemType Directory -Path $TargetDirectory -Force | Out-Null

    foreach ($ReadmeFile in @(Get-ChildItem -LiteralPath $TargetDirectory -File -Filter 'README*' -ErrorAction SilentlyContinue)) {
        Remove-Item -LiteralPath $ReadmeFile.FullName -Force -ErrorAction Stop
    }

    foreach ($Name in @('artists.sqlite', 'venues.txt')) {
        $SourcePath = Join-Path $SourceDirectory $Name
        Assert-File $SourcePath
        Copy-Item -LiteralPath $SourcePath -Destination (Join-Path $TargetDirectory $Name) -Force
        Assert-File (Join-Path $TargetDirectory $Name)
    }

    Write-Host "Copied ArtistDB master files into source snapshot TLO_DBs: $SourceDirectory"
}

function Set-PythonLiteralVersionStamp {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Version
    )

    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $Text = [System.IO.File]::ReadAllText($FullPath, [System.Text.Encoding]::UTF8)
    $VersionLine = "__version__ = `"$Version`""

    if ($Text -match '(?m)^__version__\s*=') {
        $Text = [regex]::Replace($Text, '(?m)^__version__\s*=\s*.*$', $VersionLine, 1)
    }
    elseif ($Text -match '(?m)^PROCESS_VERSION\s*=\s*.*$') {
        $Text = [regex]::Replace($Text, '(?m)^(PROCESS_VERSION\s*=\s*.*)$', "`$1`n$VersionLine", 1)
    }
    else {
        $Text = "$VersionLine`n$Text"
    }

    Write-Utf8NoBom -Path $FullPath -Text $Text
}

function Assert-File {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file not found: $Path"
    }
}

function Assert-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Required directory not found: $Path"
    }
}


function Invoke-GitHubRepositoryCleanup {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$BuildLabel
    )

    if ([string]::IsNullOrWhiteSpace($Repository)) {
        return
    }

    $CleanupRoot = Join-Path $env:TEMP ("TLO-github-repo-cleanup-{0}-{1}" -f $BuildLabel, [guid]::NewGuid().ToString('N'))
    try {
        Write-Host "Cleaning GitHub repository contents: $Repository"
        $ViewResult = Invoke-QuietNative -Command 'gh' -ArgumentList @('repo', 'view', $Repository)
        if ($ViewResult.ExitCode -ne 0) {
            Write-Warning "Could not verify GitHub repository $Repository before cleanup. Repository cleanup skipped."
            return
        }

        New-Item -ItemType Directory -Path $CleanupRoot -Force | Out-Null
        Invoke-Checked -Command 'git' -ArgumentList @('-C', $CleanupRoot, 'init')
        Invoke-Checked -Command 'git' -ArgumentList @('-C', $CleanupRoot, 'branch', '-M', 'main')
        Invoke-Checked -Command 'git' -ArgumentList @('-C', $CleanupRoot, 'config', 'core.autocrlf', 'false')
        Invoke-Checked -Command 'git' -ArgumentList @('-C', $CleanupRoot, 'config', 'user.name', 'TLO Build Cleanup')
        Invoke-Checked -Command 'git' -ArgumentList @('-C', $CleanupRoot, 'config', 'user.email', 'tlo-build-cleanup@example.invalid')
        Invoke-Checked -Command 'git' -ArgumentList @('-C', $CleanupRoot, 'commit', '--allow-empty', '-m', "Clean repository after TLO build $BuildLabel")
        Invoke-Checked -Command 'git' -ArgumentList @('-C', $CleanupRoot, 'remote', 'add', 'origin', "https://github.com/$Repository.git")
        Invoke-Checked -Command 'git' -ArgumentList @('-C', $CleanupRoot, 'push', '--force', 'origin', 'main')
        Write-Host "GitHub repository contents cleaned: $Repository"
    }
    catch {
        Write-Warning "GitHub repository cleanup did not complete: $($_.Exception.Message)"
    }
    finally {
        Remove-Item -LiteralPath $CleanupRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}


function Test-GitHubRepositoryVisibility {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$Purpose,
        [switch]$AllowPrivate
    )

    $Visibility = (& gh repo view $Repository --json visibility --jq .visibility).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Visibility)) {
        throw "Could not determine visibility for $Purpose repository: $Repository"
    }

    if ($Visibility.ToUpperInvariant() -ne 'PUBLIC' -and -not $AllowPrivate) {
        throw "$Purpose repository must be public for the no-cost Option A workflow: $Repository is $Visibility. Use a public repository or rerun with the explicit AllowPrivate switch if you intentionally want a private repository."
    }

    Write-Host "$Purpose repository visibility: $Repository = $Visibility"
}

function Invoke-GitHubActionsRunCleanup {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$RunId
    )

    if ([string]::IsNullOrWhiteSpace($Repository) -or [string]::IsNullOrWhiteSpace($RunId)) {
        return
    }

    try {
        Write-Host "Cleaning GitHub Actions artifacts/logs for run ${RunId}: $Repository"

        $ArtifactIds = @(& gh api "repos/$Repository/actions/runs/$RunId/artifacts" --jq '.artifacts[].id' 2>$null)
        if ($LASTEXITCODE -eq 0) {
            foreach ($ArtifactId in @($ArtifactIds | Where-Object { $_ -match '^\d+$' })) {
                $DeleteArtifact = Invoke-QuietNative -Command 'gh' -ArgumentList @('api', '-X', 'DELETE', "repos/$Repository/actions/artifacts/$ArtifactId")
                if ($DeleteArtifact.ExitCode -ne 0) {
                    Write-Warning "Could not delete GitHub Actions artifact $ArtifactId for run ${RunId}."
                }
            }
        }
        else {
            Write-Warning "Could not list GitHub Actions artifacts for run ${RunId}."
        }

        $DeleteRun = Invoke-QuietNative -Command 'gh' -ArgumentList @('api', '-X', 'DELETE', "repos/$Repository/actions/runs/$RunId")
        if ($DeleteRun.ExitCode -eq 0) {
            Write-Host "GitHub Actions run deleted: $RunId"
        }
        else {
            Write-Warning "Could not delete GitHub Actions run $RunId. The repository contents are still cleaned separately."
        }
    }
    catch {
        Write-Warning "GitHub Actions run cleanup did not complete: $($_.Exception.Message)"
    }
}

function Test-TloReleaseRepoPreservedRootItem {
    param([Parameter(Mandatory = $true)][System.IO.FileSystemInfo]$Item)

    if ($Item.PSIsContainer) {
        return $false
    }

    $Name = $Item.Name
    return ($Name -match '^(?i:README)(\..*)?$' -or
            $Name -match '^(?i:LICENSE)(\..*)?$')
}

function Test-TloSourcePublishSkipRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][int]$NumericBuild
    )

    $Normalized = $RelativePath.Replace('\', '/')
    $Name = [System.IO.Path]::GetFileName($Normalized)

    if ([string]::IsNullOrWhiteSpace($Name)) {
        return $false
    }

    if ($Name -match '^(?i:old-change-logs\.zip)$') { return $true }
    if ($Name -match '^(?i:changes?_v?\d+[a-z]?\.txt)$') { return $true }
    if ($Name -match '^(?i:change[-_ ]?log.*)$') { return $true }
    if ($Name -match '^(?i:changelog.*)$') { return $true }

    if ($Name -match '^TLO_Inventory_Requirements_Working_v(\d{1,5})([A-Za-z]?)\.docx$') {
        return ([int]$Matches[1] -ne $NumericBuild)
    }

    if ($Name -match '^TLO_Inventory_User_Manual_v(\d{1,5})([A-Za-z]?)\.(rtf|docx)$') {
        return ([int]$Matches[1] -ne $NumericBuild)
    }

    return $false
}

function Copy-TloSourceBundleForRepositoryPublication {
    param(
        [Parameter(Mandatory = $true)][string]$SourceBundleZip,
        [Parameter(Mandatory = $true)][string]$DestinationDirectory,
        [Parameter(Mandatory = $true)][int]$NumericBuild
    )

    Assert-File $SourceBundleZip
    Remove-Item -LiteralPath $DestinationDirectory -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $DestinationDirectory -Force | Out-Null

    $ExtractRoot = Join-Path $env:TEMP ('TLO-source-publish-{0}' -f [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $ExtractRoot -Force | Out-Null
        Expand-Archive -LiteralPath $SourceBundleZip -DestinationPath $ExtractRoot -Force
        $ExtractRootFull = [System.IO.Path]::GetFullPath($ExtractRoot)

        foreach ($Item in @(Get-ChildItem -LiteralPath $ExtractRootFull -Recurse -Force -File)) {
            $Relative = $Item.FullName.Substring($ExtractRootFull.Length).TrimStart([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
            if (Test-TloSourcePublishSkipRelativePath -RelativePath $Relative -NumericBuild $NumericBuild) {
                continue
            }
            $Destination = Join-Path $DestinationDirectory $Relative
            $DestinationParent = Split-Path -Parent $Destination
            New-Item -ItemType Directory -Path $DestinationParent -Force | Out-Null
            Copy-Item -LiteralPath $Item.FullName -Destination $Destination -Force
        }
    }
    finally {
        Remove-Item -LiteralPath $ExtractRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    $RequiredPublishedSourceFiles = @(
        'tlo-gi.py',
        'tlo-research.py',
        'tlo_research_lib.py',
        'tlo-ggi.py',
        'tlo-gsi.py',
        'tlo-tag.py',
        'tlo-deleteDupes.py',
        'search-artist-db.py',
        ("TLO_Inventory_User_Manual_v{0}.rtf" -f $NumericBuild),
        ("TLO_Inventory_Requirements_Working_v{0}.docx" -f $NumericBuild),
        'Run-TLO-GitHub-Build.ps1',
        ("TLO_GitHub_Build_Process_Requirements_{0}.docx" -f $ProcessVersion),
        'TLO-FAQ.txt'
    )
    foreach ($RelativePath in $RequiredPublishedSourceFiles) {
        Assert-File (Join-Path $DestinationDirectory $RelativePath)
    }

    $UnexpectedChangeLogs = @(
        Get-ChildItem -LiteralPath $DestinationDirectory -Recurse -File -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^(?i:old-change-logs\.zip|changes?_v?\d+[a-z]?\.txt|change[-_ ]?log.*|changelog.*)$' }
    )
    if ($UnexpectedChangeLogs.Count -gt 0) {
        throw "Source publication contains change logs: $($UnexpectedChangeLogs.FullName -join ', ')"
    }

    $UnexpectedRequirementsDocs = @(
        Get-ChildItem -LiteralPath $DestinationDirectory -Filter 'TLO_Inventory_Requirements_Working_v*.docx' -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne ("TLO_Inventory_Requirements_Working_v{0}.docx" -f $NumericBuild) }
    )
    if ($UnexpectedRequirementsDocs.Count -gt 0) {
        throw "Source publication contains non-current requirements document(s): $($UnexpectedRequirementsDocs.FullName -join ', ')"
    }

    $UnexpectedManuals = @(
        Get-ChildItem -LiteralPath $DestinationDirectory -Filter 'TLO_Inventory_User_Manual_v*.*' -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne ("TLO_Inventory_User_Manual_v{0}.rtf" -f $NumericBuild) }
    )
    if ($UnexpectedManuals.Count -gt 0) {
        throw "Source publication contains non-current user manual(s): $($UnexpectedManuals.FullName -join ', ')"
    }
}

function Remove-TloDirectoryWithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$Attempts = 6,
        [int]$DelayMilliseconds = 750
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return
    }

    $LastError = $null
    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            $LastError = $_
            if ($Attempt -lt $Attempts) {
                Start-Sleep -Milliseconds $DelayMilliseconds
            }
        }
    }

    throw "Unable to remove release-publication working directory after $Attempts attempt(s): $Path. Last error: $($LastError.Exception.Message)"
}

function New-TloReleaseRepositoryWorkingCopy {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$BuildLabel,
        [Parameter(Mandatory = $true)][string]$PublicationWorkRoot,
        [int]$Attempts = 3
    )

    if ([string]::IsNullOrWhiteSpace($PublicationWorkRoot)) {
        throw 'Publication work root must not be empty.'
    }

    $PublicationParent = Join-Path ([System.IO.Path]::GetFullPath($PublicationWorkRoot)) '_release-publication'
    New-Item -ItemType Directory -Path $PublicationParent -Force | Out-Null

    $LastError = $null
    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        $AttemptRoot = Join-Path $PublicationParent ("TLO-public-release-repo-{0}-attempt{1}-{2}" -f $BuildLabel, $Attempt, [guid]::NewGuid().ToString('N'))
        try {
            Write-Host "Preparing public release repository working copy (attempt $Attempt/$Attempts): $AttemptRoot"
            New-Item -ItemType Directory -Path $AttemptRoot -Force | Out-Null
            # This helper returns a path. Native command stdout is success-stream output in
            # PowerShell, so suppress it here; otherwise callers receive an array containing
            # Git status text plus the path instead of one directory string.
            $null = Invoke-Checked -Command 'git' -ArgumentList @('-C', $AttemptRoot, 'init')
            $null = Invoke-Checked -Command 'git' -ArgumentList @('-C', $AttemptRoot, 'config', 'core.autocrlf', 'false')
            $null = Invoke-Checked -Command 'git' -ArgumentList @('-C', $AttemptRoot, 'config', 'core.longpaths', 'true')
            $null = Invoke-Checked -Command 'git' -ArgumentList @('-C', $AttemptRoot, 'remote', 'add', 'origin', "https://github.com/$Repository.git")

            # Release publication needs only the current main-branch baseline, not the full
            # repository history. Keep the fetch shallow and strongly prefer loose objects
            # so endpoint security cannot lock a permanent .pack file during clone finalization.
            $null = Invoke-Checked -Command 'git' -ArgumentList @(
                '-C', $AttemptRoot,
                '-c', 'fetch.unpackLimit=100000',
                '-c', 'transfer.unpackLimit=100000',
                'fetch', '--depth', '1', '--no-tags', 'origin', 'main'
            )
            $null = Invoke-Checked -Command 'git' -ArgumentList @('-C', $AttemptRoot, 'checkout', '-B', 'main', 'FETCH_HEAD')
            return [string]$AttemptRoot
        }
        catch {
            $LastError = $_
            Write-Warning "Public release repository working-copy attempt $Attempt failed: $($_.Exception.Message)"
            try {
                Remove-TloDirectoryWithRetry -Path $AttemptRoot
            }
            catch {
                Write-Warning "Could not fully remove failed publication attempt directory yet: $($_.Exception.Message)"
            }
            if ($Attempt -lt $Attempts) {
                Start-Sleep -Seconds 2
            }
        }
    }

    throw "Unable to prepare the public release repository after $Attempts attempt(s). Last error: $($LastError.Exception.Message)"
}

function Invoke-TloReleaseRepositoryPublication {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$BuildLabel,
        [Parameter(Mandatory = $true)][int]$NumericBuild,
        [Parameter(Mandatory = $true)][string]$SourceBundleZip,
        [Parameter(Mandatory = $true)][string]$PublicationWorkRoot
    )

    Assert-File $SourceBundleZip
    Invoke-Checked -Command 'gh' -ArgumentList @('repo', 'view', $Repository)

    $PublishRoot = $null
    try {
        $WorkingCopyResult = @(
            New-TloReleaseRepositoryWorkingCopy `
                -Repository $Repository `
                -BuildLabel $BuildLabel `
                -PublicationWorkRoot $PublicationWorkRoot
        )
        if ($WorkingCopyResult.Count -ne 1) {
            $Preview = (($WorkingCopyResult | ForEach-Object { [string]$_ }) -join ' | ')
            throw "Public release repository helper returned $($WorkingCopyResult.Count) success-stream values instead of exactly one path. Output: $Preview"
        }
        $PublishRoot = [string]$WorkingCopyResult[0]
        if (-not (Test-FullyQualifiedPath -Path $PublishRoot)) {
            throw "Public release repository helper returned a non-absolute path: $PublishRoot"
        }
        if (-not (Test-Path -LiteralPath $PublishRoot -PathType Container)) {
            throw "Public release repository working directory was not created: $PublishRoot"
        }

        foreach ($Item in @(Get-ChildItem -LiteralPath $PublishRoot -Force -ErrorAction SilentlyContinue)) {
            if ($Item.Name -eq '.git') { continue }
            if (Test-TloReleaseRepoPreservedRootItem -Item $Item) { continue }
            Remove-Item -LiteralPath $Item.FullName -Recurse -Force -ErrorAction Stop
        }

        $SourceDestination = Join-Path $PublishRoot 'source'
        Copy-TloSourceBundleForRepositoryPublication -SourceBundleZip $SourceBundleZip -DestinationDirectory $SourceDestination -NumericBuild $NumericBuild

        $ForbiddenLargeZipFiles = @(
            Get-ChildItem -LiteralPath $PublishRoot -Recurse -File -Force -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '^TLO_V1\.[0-9]+Build\d+.*\.zip$' }
        )
        if ($ForbiddenLargeZipFiles.Count -gt 0) {
            throw "Release repository publication must not commit distribution ZIPs; use GitHub Release assets instead: $($ForbiddenLargeZipFiles.FullName -join ', ')"
        }

        $ForbiddenChangeLogs = @(
            Get-ChildItem -LiteralPath $PublishRoot -Recurse -File -Force -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '^(?i:old-change-logs\.zip|changes?_v?\d+[a-z]?\.txt|change[-_ ]?log.*|changelog.*)$' }
        )
        if ($ForbiddenChangeLogs.Count -gt 0) {
            throw "Release repository publication contains change logs: $($ForbiddenChangeLogs.FullName -join ', ')"
        }

        Invoke-Checked -Command 'git' -ArgumentList @('-C', $PublishRoot, 'add', '-A')
        $Status = @(& git -C $PublishRoot status --porcelain)
        if ($LASTEXITCODE -ne 0) {
            throw 'git status failed while preparing the public release repository.'
        }
        if ($Status.Count -eq 0) {
            Write-Host "Public release repository source baseline already matches build $BuildLabel. No commit was needed."
            return
        }

        Invoke-Checked -Command 'git' -ArgumentList @('-C', $PublishRoot, 'commit', '-m', "Publish TLO source baseline $BuildLabel")
        Invoke-Checked -Command 'git' -ArgumentList @('-C', $PublishRoot, 'push', 'origin', 'HEAD:main')
        Write-Host "Published public repository source baseline: $Repository build $BuildLabel"
    }
    finally {
        if (-not [string]::IsNullOrWhiteSpace($PublishRoot)) {
            try {
                Remove-TloDirectoryWithRetry -Path $PublishRoot
            }
            catch {
                Write-Warning "Public release repository working-copy cleanup did not complete: $($_.Exception.Message)"
            }
        }

        $PublicationParent = Join-Path ([System.IO.Path]::GetFullPath($PublicationWorkRoot)) '_release-publication'
        if (Test-Path -LiteralPath $PublicationParent -PathType Container) {
            $RemainingPublicationItems = @(Get-ChildItem -LiteralPath $PublicationParent -Force -ErrorAction SilentlyContinue)
            if ($RemainingPublicationItems.Count -eq 0) {
                Remove-Item -LiteralPath $PublicationParent -Force -ErrorAction SilentlyContinue
            }
        }
    }
}


function Invoke-TloGitHubReleaseAssetPublication {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$VersionNumber,
        [Parameter(Mandatory = $true)][string]$BuildLabel,
        [Parameter(Mandatory = $true)][int]$NumericBuild,
        [Parameter(Mandatory = $true)][string[]]$AssetPaths
    )

    foreach ($AssetPath in $AssetPaths) {
        Assert-File $AssetPath
    }

    $VersionDisplay = "v$VersionNumber"
    $VersionAssetPrefix = "V$VersionNumber"
    $TagName = "${VersionDisplay}-build$BuildLabel"
    $Title = "TLO $VersionDisplay Build $BuildLabel"
    $Notes = @"
Traders Little Organizer(TM) - TLO $VersionDisplay Build $BuildLabel

Recommended downloads:
- Windows self-contained complete distribution (six PyInstaller onefile apps; tlo-deleteDupes.cmd launches an official CPython embeddable runtime): TLO_${VersionAssetPrefix}Build${NumericBuild}_complete_Windows.zip
- Windows onedir complete distribution (five root PyInstaller executables + shared _internal; tlo-deleteDupes.cmd + official CPython embeddable runtime): TLO_${VersionAssetPrefix}Build${NumericBuild}_complete_Windows_onedir.zip
- Linux complete distribution: TLO_${VersionAssetPrefix}Build${NumericBuild}_complete_Linux.zip
- macOS complete distribution: TLO_${VersionAssetPrefix}Build${NumericBuild}_complete_macOS.zip
- Windows self-contained application-only update (six PyInstaller onefile apps; tlo-deleteDupes.cmd + official CPython embeddable runtime): TLO_${VersionAssetPrefix}Build${NumericBuild}_update_Windows.zip
- Windows onedir application-only update (six PyInstaller executables + shared _internal; tlo-deleteDupes.cmd + official CPython embeddable runtime): TLO_${VersionAssetPrefix}Build${NumericBuild}_update_Windows_onedir.zip
- Linux executable-only update: TLO_${VersionAssetPrefix}Build${NumericBuild}_update_Linux.zip
- macOS executable-only update: TLO_${VersionAssetPrefix}Build${NumericBuild}_update_macOS.zip

Use an update ZIP for an existing TLOHome when only application files are needed.
Use the matching complete platform ZIP for a new installation or when release notes say required support files changed.

The repository contents contain the matching source baseline and current documentation.
"@

    $ExistingRelease = Invoke-QuietNative -Command 'gh' -ArgumentList @('release', 'view', $TagName, '--repo', $Repository)
    if ($ExistingRelease.ExitCode -eq 0) {
        Write-Host "Updating existing GitHub Release: $Repository $TagName"
        $ExistingAssets = @(& gh release view $TagName --repo $Repository --json assets --jq '.assets[].name' 2>$null)
        if ($LASTEXITCODE -eq 0) {
            foreach ($AssetName in @($ExistingAssets | Where-Object { $_ })) {
                Invoke-Checked -Command 'gh' -ArgumentList @('release', 'delete-asset', $TagName, $AssetName, '--repo', $Repository, '--yes')
            }
        }
        Invoke-Checked -Command 'gh' -ArgumentList @('release', 'edit', $TagName, '--repo', $Repository, '--title', $Title, '--notes', $Notes)
    }
    else {
        Write-Host "Creating GitHub Release: $Repository $TagName"
        Invoke-Checked -Command 'gh' -ArgumentList @('release', 'create', $TagName, '--repo', $Repository, '--title', $Title, '--notes', $Notes, '--target', 'main')
    }

    $UploadArgs = @('release', 'upload', $TagName) + @($AssetPaths) + @('--repo', $Repository, '--clobber')
    Invoke-Checked -Command 'gh' -ArgumentList $UploadArgs
    Write-Host "Published platform GitHub Release assets: $Repository $TagName"
}


function Remove-LocalItemExceptPreserved {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string]$PreserveFullPath = ''
    )

    $FullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $FullPath)) {
        return
    }

    if ((-not [string]::IsNullOrWhiteSpace($PreserveFullPath)) -and
        [string]::Equals($FullPath, $PreserveFullPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        return
    }

    $Item = Get-Item -LiteralPath $FullPath -Force
    if (-not $Item.PSIsContainer) {
        Remove-Item -LiteralPath $FullPath -Force -ErrorAction Stop
        return
    }

    foreach ($Child in @(Get-ChildItem -LiteralPath $FullPath -Force -ErrorAction SilentlyContinue)) {
        Remove-LocalItemExceptPreserved -Path $Child.FullName -PreserveFullPath $PreserveFullPath
    }

    $RemainingChildren = @(Get-ChildItem -LiteralPath $FullPath -Force -ErrorAction SilentlyContinue)
    if ($RemainingChildren.Count -eq 0) {
        Remove-Item -LiteralPath $FullPath -Force -Recurse -ErrorAction Stop
    }
}

function Normalize-TloVersionNumber {
    param([Parameter(Mandatory = $true)][string]$RawVersion)

    $Text = $RawVersion.Trim()
    if ($Text.StartsWith('v', [System.StringComparison]::OrdinalIgnoreCase)) {
        $Text = $Text.Substring(1)
    }
    if ($Text -notmatch '^\d+(?:\.\d+){1,2}$') {
        throw "Version must be in numeric dotted form, for example -vnumber 1.3 or -vnumber v1.3."
    }
    return $Text
}

function Invoke-LocalBuildRootCleanup {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [string]$PreserveFile = ''
    )

    if ([string]::IsNullOrWhiteSpace($Root)) {
        return
    }

    $RootFull = [System.IO.Path]::GetFullPath($Root)
    if (-not (Test-Path -LiteralPath $RootFull -PathType Container)) {
        return
    }

    $DriveRoot = [System.IO.Path]::GetPathRoot($RootFull)
    if ([string]::Equals($RootFull, $DriveRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Warning "Refusing to clean drive root as local build root: $RootFull"
        return
    }

    $PreserveFullPath = ''
    if (-not [string]::IsNullOrWhiteSpace($PreserveFile)) {
        try {
            $CandidatePreserve = [System.IO.Path]::GetFullPath($PreserveFile)
            if (Test-Path -LiteralPath $CandidatePreserve -PathType Leaf) {
                $PreserveFullPath = $CandidatePreserve
            }
        }
        catch {
            $PreserveFullPath = ''
        }
    }

    Write-Host "Cleaning local TLO-GitHub-Build content: $RootFull"
    if (-not [string]::IsNullOrWhiteSpace($PreserveFullPath)) {
        Write-Host "Preserving original source bundle ZIP during local cleanup: $PreserveFullPath"
    }

    foreach ($Child in @(Get-ChildItem -LiteralPath $RootFull -Force -ErrorAction SilentlyContinue)) {
        Remove-LocalItemExceptPreserved -Path $Child.FullName -PreserveFullPath $PreserveFullPath
    }

    Write-Host "Local TLO-GitHub-Build content cleaned: $RootFull"
}

$RepositoryContainsBuildSnapshot = $false
$ResolvedBundleZipForCleanup = ''
$GitHubActionsRunIdForCleanup = ''
$GitHubActionsRunFailed = $false
$GitHubActionsRunStateUncertain = $false
$PreserveRepositorySnapshot = $false
$PreserveGitHubRunForRecovery = $false

try {
$BuildToken = if (-not [string]::IsNullOrWhiteSpace($BNumber)) { $BNumber } else { $Build }
if ([string]::IsNullOrWhiteSpace($BuildToken)) {
    throw "Build number is required. Use -bnumber 359, optionally with a one-letter suffix such as 359a."
}
if ([string]::IsNullOrWhiteSpace($VNumber)) {
    throw "Version number is required. Use -vnumber 1.3 or -vnumber v1.3."
}
$BuildNumberText = ([regex]::Match($BuildToken, '^\d{1,5}')).Value
if ([string]::IsNullOrWhiteSpace($BuildNumberText)) {
    throw "Build must be 1 to 5 digits with an optional single letter suffix, for example 359 or 359a."
}
$BuildNumber = [int]$BuildNumberText
$VersionNumber = Normalize-TloVersionNumber -RawVersion $VNumber
$VersionDisplay = "v$VersionNumber"
$VersionAssetPrefix = "V$VersionNumber"

Require-Command git | Out-Null
Require-Command gh | Out-Null
$PythonRunner = Find-PythonRunner

$FixedBuildRepo = 'onaracstlo-lab/tlo-build-disposable'
$FixedReleaseRepo = 'onaracstlo-lab/TradersLittleOrganizer'

foreach ($SuppliedRepo in @($Repo, $BuildRepo)) {
    if ((-not [string]::IsNullOrWhiteSpace($SuppliedRepo)) -and
        (-not [string]::Equals($SuppliedRepo, $FixedBuildRepo, [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "The disposable build repository is fixed as $FixedBuildRepo. Do not pass another build repository. Supplied: $SuppliedRepo"
    }
}
$Repo = $FixedBuildRepo

if ((-not [string]::IsNullOrWhiteSpace($ReleaseRepo)) -and
    (-not [string]::Equals($ReleaseRepo, $FixedReleaseRepo, [System.StringComparison]::OrdinalIgnoreCase))) {
    throw "The public release repository is fixed as $FixedReleaseRepo. Do not pass another release repository. Supplied: $ReleaseRepo"
}
$ReleaseRepo = $FixedReleaseRepo

if ($Release -or $FromBuilt) {
    $PublishRelease = $true
}

$BundleDirectory = Resolve-BundleDirectory -BundleDirectoryArgument $Bundle
$BundleZip = Join-Path $BundleDirectory "music_inventory_flat_bundle_v$BuildToken.zip"
$BundleZip = [System.IO.Path]::GetFullPath($BundleZip)
$ResolvedBundleZipForCleanup = $BundleZip
Write-Host "Using source bundle: $BundleZip"
$WorkflowFile = [System.IO.Path]::GetFullPath($WorkflowFile)
$BuilderFile = [System.IO.Path]::GetFullPath($BuilderFile)
$SnapshotRoot = Join-Path $WorkRoot $BuildToken
$ReleaseOutput = Join-Path $ReleaseRoot $BuildToken
$VerifyRoot = Join-Path $env:TEMP "TLO-build-$BuildToken-verification"
$CompleteZipWindows = Join-Path $ReleaseOutput "TLO_${VersionAssetPrefix}Build${BuildNumber}_complete_Windows.zip"
$CompleteZipWindowsOneDir = Join-Path $ReleaseOutput "TLO_${VersionAssetPrefix}Build${BuildNumber}_complete_Windows_onedir.zip"
$CompleteZipLinux = Join-Path $ReleaseOutput "TLO_${VersionAssetPrefix}Build${BuildNumber}_complete_Linux.zip"
$CompleteZipMacOS = Join-Path $ReleaseOutput "TLO_${VersionAssetPrefix}Build${BuildNumber}_complete_macOS.zip"
$UpdateZipWindows = Join-Path $ReleaseOutput "TLO_${VersionAssetPrefix}Build${BuildNumber}_update_Windows.zip"
$UpdateZipWindowsOneDir = Join-Path $ReleaseOutput "TLO_${VersionAssetPrefix}Build${BuildNumber}_update_Windows_onedir.zip"
$UpdateZipLinux = Join-Path $ReleaseOutput "TLO_${VersionAssetPrefix}Build${BuildNumber}_update_Linux.zip"
$UpdateZipMacOS = Join-Path $ReleaseOutput "TLO_${VersionAssetPrefix}Build${BuildNumber}_update_macOS.zip"
$CompleteZipPaths = @($CompleteZipWindows, $CompleteZipWindowsOneDir, $CompleteZipLinux, $CompleteZipMacOS)
$ReleaseAssetPaths = @(
    $CompleteZipWindows, $CompleteZipWindowsOneDir, $CompleteZipLinux, $CompleteZipMacOS,
    $UpdateZipWindows, $UpdateZipWindowsOneDir, $UpdateZipLinux, $UpdateZipMacOS
)
$ArtifactName = "tlo-distribution-$BuildNumber"
$ManualName = "TLO_Inventory_User_Manual_v$BuildNumber.rtf"

Assert-File $BundleZip
Assert-File $WorkflowFile
Assert-File $BuilderFile

Invoke-Checked -Command 'gh' -ArgumentList @('auth', 'status')
if (-not $FromBuilt) {
    Invoke-Checked -Command 'gh' -ArgumentList @('repo', 'view', $Repo)
    Test-GitHubRepositoryVisibility -Repository $Repo -Purpose 'Disposable build' -AllowPrivate:$AllowPrivateBuildRepo
}
if ($PublishRelease) {
    Invoke-Checked -Command 'gh' -ArgumentList @('repo', 'view', $ReleaseRepo)
    Test-GitHubRepositoryVisibility -Repository $ReleaseRepo -Purpose 'Public release' -AllowPrivate:$AllowPrivateReleaseRepo
}

if ($FromBuilt) {
    foreach ($AssetPath in $ReleaseAssetPaths) {
        Assert-File $AssetPath
    }
    Write-Host "Using existing built output for build ${BuildToken}:"
    foreach ($AssetPath in $ReleaseAssetPaths) {
        Write-Host " - $AssetPath"
    }
    Invoke-TloReleaseRepositoryPublication `
        -Repository $ReleaseRepo `
        -BuildLabel $BuildToken `
        -NumericBuild $BuildNumber `
        -SourceBundleZip $BundleZip `
        -PublicationWorkRoot $WorkRoot

    Invoke-TloGitHubReleaseAssetPublication `
        -Repository $ReleaseRepo `
        -VersionNumber $VersionNumber `
        -BuildLabel $BuildToken `
        -NumericBuild $BuildNumber `
        -AssetPaths $ReleaseAssetPaths

    Write-Host ''
    Write-Host "Git-build process version: $ProcessVersion"
    Write-Host 'TLO public repository/source and eight release assets completed from existing built output.'
    foreach ($AssetPath in $ReleaseAssetPaths) {
        $AssetHash = Get-FileHash -LiteralPath $AssetPath -Algorithm SHA256
        Write-Host "Asset: $AssetPath"
        Write-Host "SHA-256: $($AssetHash.Hash)"
    }
    return
}
Remove-Item -LiteralPath $SnapshotRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $ReleaseOutput -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $VerifyRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $SnapshotRoot -Force | Out-Null
New-Item -ItemType Directory -Path $ReleaseOutput -Force | Out-Null

Expand-Archive -LiteralPath $BundleZip -DestinationPath $SnapshotRoot -Force
$SnapshotRoot = [System.IO.Path]::GetFullPath($SnapshotRoot)
Write-Host "Prepared source snapshot: $SnapshotRoot"

# The bundle must be flat: the application sources and RTF manual are expected
# directly at the extracted root, not under a versioned wrapper directory.
$RequiredBundleFiles = @(
    'tlo-gi.py',
    'tlo-research.py',
    'tlo_research_lib.py',
    'tlo-ggi.py',
    'tlo-gsi.py',
    'tlo-tag.py',
    'tlo-deleteDupes.py',
    'search-artist-db.py',
    'createWindowsDist.ps1',
    'createLinuxDist.sh',
    'createMacOSDist.sh',
    'scan_release_artifacts.py',
    'test_tlo_requirements.py',
    'Run-TLO-GitHub-Build.ps1',
    ("TLO_GitHub_Build_Process_Requirements_{0}.docx" -f $ProcessVersion),
    $ManualName,
    'icons/tlo-inventory-icon.png',
    'icons/tlo-search-icon.png',
    'icons/tlo-tag-icon.png',
    'icons/tlo-inventory-icon.ico',
    'icons/tlo-search-icon.ico',
    'icons/tlo-tag-icon.ico',
    'icons/tlo-inventory-icon.icns',
    'icons/tlo-search-icon.icns',
    'icons/tlo-tag-icon.icns',
    'TLO-FAQ.txt'
)
foreach ($relativePath in $RequiredBundleFiles) {
    Assert-File (Join-Path $SnapshotRoot $relativePath)
}

$ArtistDbMasterResolved = Resolve-ArtistDbMasterDirectory -RequestedPath $ArtistDbRoot
Copy-RequiredArtistDbFilesIntoSnapshot -SourceDirectory $ArtistDbMasterResolved -SnapshotRoot $SnapshotRoot

$DocxManuals = @(Get-ChildItem -LiteralPath $SnapshotRoot -Filter 'TLO_Inventory_User_Manual_v*.docx' -File -ErrorAction SilentlyContinue)
if ($DocxManuals.Count -gt 0) {
    throw "The bundle contains DOCX user manual(s). The release bundle must contain only the RTF user manual: $($DocxManuals.Name -join ', ')"
}
$WrongRtfManuals = @(
    Get-ChildItem -LiteralPath $SnapshotRoot -Filter 'TLO_Inventory_User_Manual_v*.rtf' -File |
        Where-Object Name -ne $ManualName
)
if ($WrongRtfManuals.Count -gt 0) {
    throw "The bundle contains RTF manual(s) for another build: $($WrongRtfManuals.Name -join ', ')"
}

$WorkflowDestinationDir = Join-Path $SnapshotRoot '.github\workflows'
$WorkflowDestination = Join-Path $WorkflowDestinationDir 'build-release.yml'
$BuilderDestination = Join-Path $SnapshotRoot 'build_tlo_release.py'
New-Item -ItemType Directory -Path $WorkflowDestinationDir -Force | Out-Null
Copy-Item -LiteralPath $WorkflowFile -Destination $WorkflowDestination -Force
Copy-Item -LiteralPath $BuilderFile -Destination $BuilderDestination -Force

$WorkflowText = Get-Content -LiteralPath $WorkflowDestination -Raw
foreach ($RequiredDefenderRetryToken in @(
    '0x80070652',
    'another installation is already in progress',
    '$MaxAttempts = 5',
    'Get-MpComputerStatus',
    'AntivirusSignatureAge'
)) {
    if ($WorkflowText -notmatch [regex]::Escape($RequiredDefenderRetryToken)) {
        throw "GitHub workflow is missing Defender signature-update retry protection token: $RequiredDefenderRetryToken"
    }
}

if (-not (Select-String -LiteralPath $BuilderDestination -Pattern '\.rtf' -Quiet)) {
    throw 'The supplied build_tlo_release.py does not support RTF documentation.'
}

# The support assembler is injected into the temporary TLO source snapshot as
# build_tlo_release.py. The TLO release tests require every root-level Python
# file to carry the current TLO source version stamp, not the Git-build-process
# version. Patch only the injected copy so the process scripts keep their own
# internal version while the uploaded snapshot remains test-clean.
Set-PythonLiteralVersionStamp -Path $BuilderDestination -Version "$VersionDisplay Build $BuildNumber"

@(
    'pyinstaller',
    'mutagen',
    'imageio-ffmpeg',
    'tkinterdnd2',
    'pefile',
    'pytest',
    'python-docx'
) | Set-Content -LiteralPath (Join-Path $SnapshotRoot 'requirements-build.txt') -Encoding utf8

# Ensure the native PyInstaller scripts collect the packages required by the
# release runners and the Windows drag/drop GUI. Do not rely on one exact
# source-script text block: source bundles can evolve. Patch by locating the
# specific functions/commands we need, then validate the result.
function Replace-FunctionBeforeNextFunction {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$FunctionName,
        [Parameter(Mandatory = $true)][string]$NextFunctionName,
        [Parameter(Mandatory = $true)][string]$ReplacementText
    )

    $Text = Get-Content -LiteralPath $Path -Raw
    $Pattern = "(?s)function\s+$([regex]::Escape($FunctionName))\s*\{.*?\r?\nfunction\s+$([regex]::Escape($NextFunctionName))\s*\{"
    if (-not [regex]::IsMatch($Text, $Pattern)) {
        throw "Could not locate function $FunctionName before $NextFunctionName in $Path."
    }

    $Replacement = $ReplacementText.TrimEnd() + "`n`nfunction $NextFunctionName {"
    $Text = [regex]::Replace(
        $Text,
        $Pattern,
        [System.Text.RegularExpressions.MatchEvaluator]{ param($Match) $Replacement },
        1
    )
    Write-Utf8NoBom -Path $Path -Text $Text
}

function Replace-RegexOnce {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Replacement,
        [string]$Description = 'requested update'
    )

    $Text = Get-Content -LiteralPath $Path -Raw
    if (-not [regex]::IsMatch($Text, $Pattern)) {
        throw "Could not locate text for ${Description} in $Path."
    }
    $Text = [regex]::Replace($Text, $Pattern, $Replacement, 1)
    Write-Utf8NoBom -Path $Path -Text $Text
}

function Ensure-WindowsBuildScript {
    param([Parameter(Mandatory = $true)][string]$Path)

    # Generate one complete Windows build script instead of incrementally
    # rewriting the source-bundle script. This guarantees a single top-level
    # param block and keeps the Windows hybrid and shared onedir layouts in lockstep.
    $WindowsBuildScript = @'
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
    $DistRoot = "C:\tloDist-Build$BundleNumber"
}

$TargetDir = Join-Path $DistRoot 'apps\Windows'
$OneDirTargetDir = Join-Path $DistRoot 'apps\Windows-onedir'
$ReportPath = Join-Path $DistRoot 'scan-reports\windows.json'
$OneDirReportPath = Join-Path $DistRoot 'scan-reports\windows-onedir.json'
$ScanScript = Join-Path $SourceRoot 'scan_release_artifacts.py'
$IconRoot = Join-Path $SourceRoot 'icons'

function Get-PythonRunner {
    foreach ($envVarName in @('pythonLocation', 'Python_ROOT_DIR', 'Python3_ROOT_DIR')) {
        $root = [Environment]::GetEnvironmentVariable($envVarName)
        if (-not [string]::IsNullOrWhiteSpace($root)) {
            $candidate = Join-Path $root 'python.exe'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                return @($candidate)
            }
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return @($python.Source) }
    $python3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3) { return @($python3.Source) }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return @($py.Source, '-3') }

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
    $WorkRoot = Join-Path $DistRoot ".build-Windows-onefile-$BaseName"
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
        throw "Expected onefile executable was not created or was quarantined: $Expected"
    }

    Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
}

function Build-EmbeddedDeleteDupes {
    param(
        [string[]]$PythonRunner,
        [string]$ScriptPath,
        [string[]]$TargetRoots,
        [string]$RuntimeDirectoryName = 'tlo-deleteDupes_runtime'
    )

    # Use Python.org's official signed embeddable CPython runtime rather than a
    # custom-compiled tlo-deleteDupes.exe. This keeps the Windows utility fully
    # self-contained while avoiding the PyInstaller/Nuitka executable signatures
    # that have triggered security products on local verification systems.
    $EmbeddedPythonVersion = '3.13.14'
    $EmbeddedPythonUrl = 'https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip'
    $EmbeddedPythonSha256 = '90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907'

    $WorkRoot = Join-Path $DistRoot '.build-Windows-embedded-tlo-deleteDupes'
    $RuntimeStaging = Join-Path $WorkRoot 'runtime'
    $EmbeddedZip = Join-Path $WorkRoot "python-$EmbeddedPythonVersion-embed-amd64.zip"
    if (Test-Path -LiteralPath $WorkRoot) {
        Remove-Item -LiteralPath $WorkRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $RuntimeStaging -Force | Out-Null

    Write-Host "Downloading official CPython $EmbeddedPythonVersion embeddable runtime for tlo-deleteDupes."
    Invoke-WebRequest -Uri $EmbeddedPythonUrl -OutFile $EmbeddedZip -UseBasicParsing
    $DownloadedHash = (Get-FileHash -LiteralPath $EmbeddedZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($DownloadedHash -ne $EmbeddedPythonSha256) {
        throw "Embedded CPython download checksum mismatch. Expected $EmbeddedPythonSha256 but found $DownloadedHash."
    }
    Expand-Archive -LiteralPath $EmbeddedZip -DestinationPath $RuntimeStaging -Force

    $EmbeddedPythonExe = Join-Path $RuntimeStaging 'python.exe'
    if (-not (Test-Path -LiteralPath $EmbeddedPythonExe -PathType Leaf)) {
        throw "Official embeddable Python runtime did not contain python.exe: $EmbeddedPythonExe"
    }

    # The embeddable package intentionally isolates imports with python313._pth.
    # Enable the runtime root and a private site-packages directory while keeping
    # the standard-library ZIP that ships with CPython.
    $PthPath = Join-Path $RuntimeStaging 'python313._pth'
    @(
        'python313.zip',
        '.',
        'Lib\site-packages',
        'import site'
    ) | Set-Content -LiteralPath $PthPath -Encoding ascii

    $SitePackages = Join-Path $RuntimeStaging 'Lib\site-packages'
    New-Item -ItemType Directory -Path $SitePackages -Force | Out-Null

    # Copy the already-installed imageio_ffmpeg package (including its bundled
    # ffmpeg executable/data) into the private runtime. Avoid a second dependency
    # resolution pass so the runtime uses the exact package tested by this job.
    $CopyImageIoCode = 'import pathlib, shutil, sys, imageio_ffmpeg; src=pathlib.Path(imageio_ffmpeg.__file__).resolve().parent; dst=pathlib.Path(sys.argv[1]).resolve()/"imageio_ffmpeg"; dst.exists() and shutil.rmtree(dst); shutil.copytree(src,dst)'
    Invoke-Python -Runner $PythonRunner -Arguments @('-c', $CopyImageIoCode, $SitePackages)

    # tlo-deleteDupes has a deliberately small local-module closure. Copy those
    # source modules into the private runtime so no external Python installation
    # or TLO source tree is required at execution time.
    $RuntimeModules = @(
        $ScriptPath,
        (Find-SourceScript 'console_output_lib.py'),
        (Find-SourceScript 'tlo_path_inputs.py'),
        (Find-SourceScript 'tlo_text_utils.py'),
        (Find-SourceScript 'tlo_constants.py')
    )
    foreach ($ModulePath in $RuntimeModules) {
        Copy-Item -LiteralPath $ModulePath -Destination (Join-Path $RuntimeStaging ([IO.Path]::GetFileName($ModulePath))) -Force
    }

    # Smoke-test the exact private runtime before it is copied to either Windows
    # distribution layout. This verifies imports and the bundled ffmpeg path.
    & $EmbeddedPythonExe (Join-Path $RuntimeStaging 'tlo-deleteDupes.py') --help | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Embedded tlo-deleteDupes runtime failed its --help smoke test with exit code $LASTEXITCODE."
    }
    & $EmbeddedPythonExe -c "import imageio_ffmpeg, os; p=imageio_ffmpeg.get_ffmpeg_exe(); assert p and os.path.isfile(p), p"
    if ($LASTEXITCODE -ne 0) {
        throw "Embedded tlo-deleteDupes runtime could not locate its bundled ffmpeg executable."
    }

    foreach ($TargetRoot in $TargetRoots) {
        $TargetRuntime = Join-Path $TargetRoot $RuntimeDirectoryName
        $Launcher = Join-Path $TargetRoot 'tlo-deleteDupes.cmd'
        if (Test-Path -LiteralPath $TargetRuntime) {
            Remove-Item -LiteralPath $TargetRuntime -Recurse -Force
        }
        if (Test-Path -LiteralPath $Launcher) {
            Remove-Item -LiteralPath $Launcher -Force
        }
        Copy-Item -LiteralPath $RuntimeStaging -Destination $TargetRuntime -Recurse
        @(
            '@echo off',
            '"%~dp0tlo-deleteDupes_runtime\python.exe" "%~dp0tlo-deleteDupes_runtime\tlo-deleteDupes.py" %*',
            'exit /b %errorlevel%'
        ) | Set-Content -LiteralPath $Launcher -Encoding ascii

        $InstalledPython = Join-Path $TargetRuntime 'python.exe'
        $InstalledScript = Join-Path $TargetRuntime 'tlo-deleteDupes.py'
        if (-not (Test-Path -LiteralPath $InstalledPython -PathType Leaf) -or -not (Test-Path -LiteralPath $InstalledScript -PathType Leaf)) {
            throw "Embedded tlo-deleteDupes runtime was not installed under: $TargetRuntime"
        }
        if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) {
            throw "tlo-deleteDupes launcher was not installed: $Launcher"
        }
    }

    Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
}

function Build-SharedOneDir {
    param([string[]]$PythonRunner)

    $WorkRoot = Join-Path $DistRoot '.build-Windows-onedir-shared'
    $SpecDistRoot = Join-Path $WorkRoot 'dist'
    $SpecPath = Join-Path $WorkRoot 'tlo-windows-onedir-shared.spec'
    $BuiltRoot = Join-Path $SpecDistRoot 'TLO-Windows-onedir'

    if (Test-Path -LiteralPath $WorkRoot) {
        Remove-Item -LiteralPath $WorkRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $WorkRoot -Force | Out-Null

    # Build the six PyInstaller applications in one COLLECT operation. Building
    # independent onedir trees and merging their _internal folders is not
    # safe because generated files such as base_library.zip may legitimately
    # differ between analyses.
    $SpecText = @"
# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

source_root = Path(os.environ["TLO_PYI_SOURCE_ROOT"]).resolve()
icon_root = source_root / "icons"


def find_script(name):
    for candidate in (source_root / name, source_root / "searchApps" / name):
        if candidate.is_file():
            return str(candidate)
    raise SystemExit(f"Required source script not found: {name}")


def collect_packages(*package_names):
    datas = []
    binaries = []
    hiddenimports = []
    for package_name in package_names:
        package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_hiddenimports
    return datas, binaries, hiddenimports


gui_datas, gui_binaries, gui_hiddenimports = collect_packages(
    "mutagen", "imageio_ffmpeg", "tkinterdnd2"
)
tag_datas, tag_binaries, tag_hiddenimports = collect_packages(
    "mutagen", "imageio_ffmpeg"
)

common_analysis = dict(
    pathex=[str(source_root)],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

artist_a = Analysis(
    [find_script("search-artist-db.py")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    **common_analysis,
)
search_a = Analysis(
    [find_script("tlo-gsi.py")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    **common_analysis,
)
cli_a = Analysis(
    [find_script("tlo-gi.py")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    **common_analysis,
)
research_a = Analysis(
    [find_script("tlo-research.py")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    **common_analysis,
)
gui_a = Analysis(
    [find_script("tlo-ggi.py")],
    binaries=gui_binaries,
    datas=gui_datas,
    hiddenimports=gui_hiddenimports,
    **common_analysis,
)
tag_a = Analysis(
    [find_script("tlo-tag.py")],
    binaries=tag_binaries,
    datas=tag_datas,
    hiddenimports=tag_hiddenimports,
    **common_analysis,
)

artist_pyz = PYZ(artist_a.pure)
search_pyz = PYZ(search_a.pure)
cli_pyz = PYZ(cli_a.pure)
research_pyz = PYZ(research_a.pure)
gui_pyz = PYZ(gui_a.pure)
tag_pyz = PYZ(tag_a.pure)

artist_exe = EXE(
    artist_pyz,
    artist_a.scripts,
    [],
    exclude_binaries=True,
    name="search-artist-db",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
search_exe = EXE(
    search_pyz,
    search_a.scripts,
    [],
    exclude_binaries=True,
    name="tlo-gsi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_root / "tlo-search-icon.ico"),
)
cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    [],
    exclude_binaries=True,
    name="tlo-gi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
research_exe = EXE(
    research_pyz,
    research_a.scripts,
    [],
    exclude_binaries=True,
    name="tlo-research",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
gui_exe = EXE(
    gui_pyz,
    gui_a.scripts,
    [],
    exclude_binaries=True,
    name="tlo-ggi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_root / "tlo-inventory-icon.ico"),
)
tag_exe = EXE(
    tag_pyz,
    tag_a.scripts,
    [],
    exclude_binaries=True,
    name="tlo-tag",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_root / "tlo-tag-icon.ico"),
)

# One shared COLLECT creates root-level executables and exactly one _internal
# directory. Do not replace this with separate onedir builds plus file copying.
shared = COLLECT(
    artist_exe,
    artist_a.binaries,
    artist_a.datas,
    search_exe,
    search_a.binaries,
    search_a.datas,
    cli_exe,
    cli_a.binaries,
    cli_a.datas,
    research_exe,
    research_a.binaries,
    research_a.datas,
    gui_exe,
    gui_a.binaries,
    gui_a.datas,
    tag_exe,
    tag_a.binaries,
    tag_a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TLO-Windows-onedir",
    contents_directory="_internal",
)
"@

    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($SpecPath, $SpecText, $Utf8NoBom)

    $PreviousSourceRoot = [Environment]::GetEnvironmentVariable('TLO_PYI_SOURCE_ROOT')
    [Environment]::SetEnvironmentVariable('TLO_PYI_SOURCE_ROOT', $SourceRoot)
    try {
        $Arguments = @(
            '-m', 'PyInstaller',
            '--noconfirm', '--clean',
            '--workpath', (Join-Path $WorkRoot 'work'),
            '--distpath', $SpecDistRoot,
            $SpecPath
        )
        Invoke-Python -Runner $PythonRunner -Arguments $Arguments
    }
    finally {
        [Environment]::SetEnvironmentVariable('TLO_PYI_SOURCE_ROOT', $PreviousSourceRoot)
    }

    if (-not (Test-Path -LiteralPath $BuiltRoot -PathType Container)) {
        throw "Expected shared onedir output was not created: $BuiltRoot"
    }

    if (Test-Path -LiteralPath $OneDirTargetDir) {
        Remove-Item -LiteralPath $OneDirTargetDir -Recurse -Force
    }
    Move-Item -LiteralPath $BuiltRoot -Destination $OneDirTargetDir

    # At this point only the six PyInstaller applications exist.
    # tlo-deleteDupes is added afterward by Build-EmbeddedDeleteDupes.
    $ApplicationNames = @('search-artist-db', 'tlo-gsi', 'tlo-gi', 'tlo-research', 'tlo-ggi', 'tlo-tag')
    foreach ($AppName in $ApplicationNames) {
        $Expected = Join-Path $OneDirTargetDir "$AppName.exe"
        if (-not (Test-Path -LiteralPath $Expected -PathType Leaf)) {
            throw "Shared-layout onedir executable was not created or was quarantined: $Expected"
        }
    }

    $SharedInternal = Join-Path $OneDirTargetDir '_internal'
    if (-not (Test-Path -LiteralPath $SharedInternal -PathType Container)) {
        throw "Shared Windows onedir _internal folder was not created: $SharedInternal"
    }
    if (-not (Get-ChildItem -LiteralPath $SharedInternal -File -Recurse | Select-Object -First 1)) {
        throw "Shared Windows onedir _internal folder is empty: $SharedInternal"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $SharedInternal 'base_library.zip') -PathType Leaf)) {
        throw "Shared Windows onedir base_library.zip was not created."
    }

    $UnexpectedDirectories = @(Get-ChildItem -LiteralPath $OneDirTargetDir -Directory -Force | Where-Object {
        $_.Name -ne '_internal'
    })
    if ($UnexpectedDirectories.Count -gt 0) {
        $Names = ($UnexpectedDirectories | ForEach-Object Name) -join ', '
        throw "Windows onedir output contains unexpected per-application directories: $Names"
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

function Invoke-WindowsArtifactScan {
    param(
        [Parameter(Mandatory = $true)][string]$ArtifactDir,
        [Parameter(Mandatory = $true)][string]$ReceiptPath
    )

    $ScanArguments = @(
        $ScanScript,
        '--platform', 'windows',
        '--artifact-dir', $ArtifactDir,
        '--report', $ReceiptPath
    )
    foreach ($scanner in $CustomScanner) {
        $ScanArguments += @('--custom-scanner', $scanner)
    }
    Invoke-Python -Runner $PythonRunner -Arguments $ScanArguments
}

$PythonRunner = Get-PythonRunner
Invoke-Python -Runner $PythonRunner -Arguments @('-m', 'PyInstaller', '--version')

if (-not (Test-Path -LiteralPath $ScanScript -PathType Leaf)) {
    throw "Required scan utility not found: $ScanScript"
}

foreach ($BuildTarget in @($TargetDir, $OneDirTargetDir)) {
    if (Test-Path -LiteralPath $BuildTarget) {
        Remove-Item -LiteralPath $BuildTarget -Recurse -Force
    }
    New-Item -ItemType Directory -Path $BuildTarget -Force | Out-Null
}
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
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-research.py')
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-ggi.py') -AdditionalArgs $GuiArgs
Build-OneFile -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-tag.py') -AdditionalArgs $TagArgs

Build-SharedOneDir -PythonRunner $PythonRunner
Build-EmbeddedDeleteDupes -PythonRunner $PythonRunner -ScriptPath (Find-SourceScript 'tlo-deleteDupes.py') -TargetRoots @($TargetDir, $OneDirTargetDir) -RuntimeDirectoryName 'tlo-deleteDupes_runtime'

Assert-WindowsExeMatchesSourceIcon -ExePath (Join-Path $TargetDir 'tlo-gsi.exe') -IconPath $SearchIcon -DisplayName 'TLO Search GUI onefile'
Assert-WindowsExeMatchesSourceIcon -ExePath (Join-Path $TargetDir 'tlo-ggi.exe') -IconPath $InventoryIcon -DisplayName 'TLO Inventory GUI onefile'
Assert-WindowsExeMatchesSourceIcon -ExePath (Join-Path $TargetDir 'tlo-tag.exe') -IconPath $TagIcon -DisplayName 'TLO Tagger onefile'
Assert-WindowsExeMatchesSourceIcon -ExePath (Join-Path $OneDirTargetDir 'tlo-gsi.exe') -IconPath $SearchIcon -DisplayName 'TLO Search GUI onedir'
Assert-WindowsExeMatchesSourceIcon -ExePath (Join-Path $OneDirTargetDir 'tlo-ggi.exe') -IconPath $InventoryIcon -DisplayName 'TLO Inventory GUI onedir'
Assert-WindowsExeMatchesSourceIcon -ExePath (Join-Path $OneDirTargetDir 'tlo-tag.exe') -IconPath $TagIcon -DisplayName 'TLO Tagger onedir'

# Optional Authenticode signing. Set TLO_WINDOWS_CERT_SHA1 to the certificate
# thumbprint and ensure signtool.exe is in PATH. Signing occurs before scanning.
if (-not [string]::IsNullOrWhiteSpace($env:TLO_WINDOWS_CERT_SHA1)) {
    $SignTool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if (-not $SignTool) {
        throw 'TLO_WINDOWS_CERT_SHA1 is set, but signtool.exe was not found in PATH.'
    }
    Get-ChildItem -LiteralPath @($TargetDir, $OneDirTargetDir) -Filter '*.exe' -File -Recurse | ForEach-Object {
        & $SignTool.Source sign /sha1 $env:TLO_WINDOWS_CERT_SHA1 /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $_.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "Authenticode signing failed for $($_.FullName)."
        }
    }
}

Invoke-WindowsArtifactScan -ArtifactDir $TargetDir -ReceiptPath $ReportPath
Invoke-WindowsArtifactScan -ArtifactDir $OneDirTargetDir -ReceiptPath $OneDirReportPath

# Recheck after antivirus has had a chance to quarantine newly written files.
Start-Sleep -Seconds 2
$ExpectedWindowsExecutables = @('search-artist-db.exe', 'tlo-gsi.exe', 'tlo-gi.exe', 'tlo-research.exe', 'tlo-ggi.exe', 'tlo-tag.exe')
foreach ($name in $ExpectedWindowsExecutables) {
    $path = Join-Path $TargetDir $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Windows executable disappeared after scanning, probably due to quarantine: $path"
    }
}
$DeleteDupesPrivateRuntime = Join-Path $TargetDir 'tlo-deleteDupes_runtime'
if (-not (Test-Path -LiteralPath $DeleteDupesPrivateRuntime -PathType Container) -or -not (Get-ChildItem -LiteralPath $DeleteDupesPrivateRuntime -File -Recurse | Select-Object -First 1)) {
    throw "Windows tlo-deleteDupes private runtime disappeared after scanning or is empty: $DeleteDupesPrivateRuntime"
}
$DeleteDupesLauncher = Join-Path $TargetDir 'tlo-deleteDupes.cmd'
$DeleteDupesRuntimeExe = Join-Path $DeleteDupesPrivateRuntime 'python.exe'
$DeleteDupesRuntimeScript = Join-Path $DeleteDupesPrivateRuntime 'tlo-deleteDupes.py'
if (-not (Test-Path -LiteralPath $DeleteDupesLauncher -PathType Leaf) -or -not (Test-Path -LiteralPath $DeleteDupesRuntimeExe -PathType Leaf) -or -not (Test-Path -LiteralPath $DeleteDupesRuntimeScript -PathType Leaf)) {
    throw "Windows embedded-Python tlo-deleteDupes launcher/runtime disappeared after scanning."
}
$ExpectedOneDirExecutables = @('search-artist-db.exe', 'tlo-gsi.exe', 'tlo-gi.exe', 'tlo-research.exe', 'tlo-ggi.exe', 'tlo-tag.exe')
foreach ($name in $ExpectedOneDirExecutables) {
    $path = Join-Path $OneDirTargetDir $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Onedir executable disappeared after scanning, probably due to quarantine: $path"
    }
}
$SharedInternal = Join-Path $OneDirTargetDir '_internal'
if (-not (Test-Path -LiteralPath $SharedInternal -PathType Container) -or -not (Get-ChildItem -LiteralPath $SharedInternal -File -Recurse | Select-Object -First 1)) {
    throw "Shared onedir _internal folder disappeared after scanning or is empty: $SharedInternal"
}
$OneDirDeleteRuntime = Join-Path $OneDirTargetDir 'tlo-deleteDupes_runtime'
$OneDirDeleteLauncher = Join-Path $OneDirTargetDir 'tlo-deleteDupes.cmd'
if (-not (Test-Path -LiteralPath (Join-Path $OneDirDeleteRuntime 'python.exe') -PathType Leaf) -or -not (Test-Path -LiteralPath (Join-Path $OneDirDeleteRuntime 'tlo-deleteDupes.py') -PathType Leaf) -or -not (Test-Path -LiteralPath $OneDirDeleteLauncher -PathType Leaf)) {
    throw "Windows onedir embedded-Python tlo-deleteDupes launcher/runtime disappeared after scanning."
}

Write-Host "Windows self-contained hybrid applications built and scanned clean: $TargetDir"
Write-Host "Windows onedir applications built and scanned clean: $OneDirTargetDir"
Write-Host "Onefile scan receipt: $ReportPath"
Write-Host "Onedir scan receipt: $OneDirReportPath"
'@

    Write-Utf8NoBom -Path $Path -Text ($WindowsBuildScript.TrimStart() + "`n")

    $Text = Get-Content -LiteralPath $Path -Raw
    foreach ($Pattern in @(
        '^param\(',
        'function\s+Build-OneFile',
        'function\s+Build-EmbeddedDeleteDupes',
        'function\s+Build-SharedOneDir',
        'shared\s*=\s*COLLECT\(',
        'contents_directory="_internal"',
        'collect_all',
        '--onefile',
        'python-3\.13\.14-embed-amd64\.zip',
        '90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907',
        'tlo-deleteDupes\.cmd',
        'tlo-deleteDupes_runtime',
        'Windows-onedir',
        'windows-onedir\.json',
        'Assert-WindowsIcoIsDibBased',
        'Assert-WindowsExeMatchesSourceIcon',
        'tlo-inventory-icon\.ico',
        'tlo-search-icon\.ico',
        'tlo-tag-icon\.ico',
        'Invoke-WindowsArtifactScan'
    )) {
        if (-not ($Text -match $Pattern)) {
            throw "Generated Windows build script is incomplete in $Path. Missing pattern: $Pattern"
        }
    }

    if ([regex]::Matches($Text, '(?m)^param\(').Count -ne 1) {
        throw "Generated Windows build script must contain exactly one top-level param block: $Path"
    }
    if ($Text -match 'Convert-PngIconToWindowsIco' -or $Text -match '(?:\bPIL\b|\bPillow\b)') {
        throw "Windows build script must use packaged .ico files, not build-time PNG-to-ICO conversion: $Path"
    }
    if ($Text -match 'function\s+Merge-OneDirApplications' -or $Text -match 'Conflicting runtime file while creating shared onedir') {
        throw "Windows build script must use one shared PyInstaller COLLECT, not merge independent onedir trees: $Path"
    }
}


function Ensure-ShellGuiCollectAll {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$PlatformName
    )

    $Text = Get-Content -LiteralPath $Path -Raw
    if ($Text -match 'tlo-ggi\.py[\s\S]*?tkinterdnd2') {
        return
    }

    $Pattern = '(?m)^([ \t]*--collect-all[ \t]+imageio_ffmpeg)([ \t]*)$'
    if (-not [regex]::IsMatch($Text, $Pattern)) {
        throw "Could not find the $PlatformName GUI imageio_ffmpeg collect-all line in $Path."
    }
    $Replacement = "`$1 \`n    --collect-all tkinterdnd2"
    $Text = [regex]::Replace($Text, $Pattern, $Replacement, 1)
    Write-Utf8NoBom -Path $Path -Text $Text
}

function Ensure-MacIconSupport {
    param([Parameter(Mandatory = $true)][string]$Path)

    $Text = Get-Content -LiteralPath $Path -Raw

    if ($Text -match 'tlo-inventory-icon\.icns' -and
        $Text -match 'tlo-search-icon\.icns' -and
        $Text -match 'build_windowed_with_optional_icon') {
        return
    }

    if ($Text -notmatch 'find_optional_icon') {
        $IconFunctions = @'
find_optional_icon() {
    local name="$1"
    local candidate
    for candidate in \
        "${SOURCE_ROOT}/icons/${name}" \
        "${SOURCE_ROOT}/UtilityData-Apps/iconInfo/${name}"
    do
        if [[ -f "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

build_windowed_with_optional_icon() {
    local script_path="$1"
    local icon_path="$2"
    shift 2

    if [[ -n "$icon_path" ]]; then
        build_one "$script_path" yes --icon "$icon_path" "$@"
    else
        build_one "$script_path" yes "$@"
    fi
}

'@
        $Pattern = '(?s)(find_script\(\)\s*\{.*?\r?\n\}\r?\n\r?\n)(rm -rf -- "\$TARGET_DIR")'
        if (-not [regex]::IsMatch($Text, $Pattern)) {
            throw "Could not locate insertion point for macOS icon helpers in $Path."
        }
        $Text = [regex]::Replace(
            $Text,
            $Pattern,
            [System.Text.RegularExpressions.MatchEvaluator]{ param($Match) $Match.Groups[1].Value + $IconFunctions + $Match.Groups[2].Value },
            1
        )
        Write-Utf8NoBom -Path $Path -Text $Text
        $Text = Get-Content -LiteralPath $Path -Raw
    }

    if ($Text -notmatch 'build_windowed_with_optional_icon .*tlo-gsi\.py' -or
        $Text -notmatch 'build_windowed_with_optional_icon .*tlo-ggi\.py') {
        $IconBuildCalls = @'
INVENTORY_ICON=""
SEARCH_ICON=""
if icon_candidate="$(find_optional_icon tlo-inventory-icon.icns)"; then
    INVENTORY_ICON="$icon_candidate"
fi
if icon_candidate="$(find_optional_icon tlo-search-icon.icns)"; then
    SEARCH_ICON="$icon_candidate"
fi

build_one "$(find_script search-artist-db.py)" yes
build_windowed_with_optional_icon "$(find_script tlo-gsi.py)" "$SEARCH_ICON"
build_one "$(find_script tlo-gi.py)" no
build_one "$(find_script tlo-research.py)" no
build_windowed_with_optional_icon "$(find_script tlo-ggi.py)" "$INVENTORY_ICON" \
    --collect-all mutagen \
    --collect-all imageio_ffmpeg
'@
        $Pattern = '(?s)build_one "\$\(find_script search-artist-db\.py\)" yes\r?\n' +
                   'build_one "\$\(find_script tlo-gsi\.py\)" yes\r?\n' +
                   'build_one "\$\(find_script tlo-gi\.py\)" no\r?\n' +
                   '(?:build_one "\$\(find_script tlo-research\.py\)" no\r?\n)?' +
                   'build_one "\$\(find_script tlo-ggi\.py\)" yes \\\r?\n\s*--collect-all mutagen \\\r?\n\s*--collect-all imageio_ffmpeg'
        if (-not [regex]::IsMatch($Text, $Pattern)) {
            throw "Could not locate macOS GUI build calls for icon update in $Path."
        }
        $Text = [regex]::Replace(
            $Text,
            $Pattern,
            [System.Text.RegularExpressions.MatchEvaluator]{ param($Match) $IconBuildCalls.TrimEnd() },
            1
        )
        Write-Utf8NoBom -Path $Path -Text $Text
        $Text = Get-Content -LiteralPath $Path -Raw
    }

    foreach ($Pattern in @('tlo-inventory-icon\.icns', 'tlo-search-icon\.icns', 'tlo-tag-icon\.icns', '--icon')) {
        if (-not ($Text -match $Pattern)) {
            throw "macOS icon support is incomplete in $Path. Missing pattern: $Pattern"
        }
    }
}

function Ensure-MacSigningGuard {
    param([Parameter(Mandatory = $true)][string]$Path)

    $Text = Get-Content -LiteralPath $Path -Raw
    if ($Text -match 'if \[\[ \$\{#COMMON_SIGNING_ARGS\[@\]\} -gt 0 \]\]') {
        return
    }

    $Old = '    args+=("${COMMON_SIGNING_ARGS[@]}")'
    if (-not $Text.Contains($Old)) {
        Write-Warning "The macOS signing argument expansion was not found in $Path. Leaving macOS signing block unchanged."
        return
    }
    $New = @'
    if [[ ${#COMMON_SIGNING_ARGS[@]} -gt 0 ]]; then
        args+=("${COMMON_SIGNING_ARGS[@]}")
    fi
'@
    $New = $New.TrimEnd()
    $Text = $Text.Replace($Old, $New)
    Write-Utf8NoBom -Path $Path -Text $Text
}

Ensure-WindowsBuildScript -Path (Join-Path $SnapshotRoot 'createWindowsDist.ps1')
Ensure-ShellGuiCollectAll -Path (Join-Path $SnapshotRoot 'createLinuxDist.sh') -PlatformName 'Linux'
Ensure-ShellGuiCollectAll -Path (Join-Path $SnapshotRoot 'createMacOSDist.sh') -PlatformName 'macOS'
Ensure-MacIconSupport -Path (Join-Path $SnapshotRoot 'createMacOSDist.sh')
Ensure-MacSigningGuard -Path (Join-Path $SnapshotRoot 'createMacOSDist.sh')

$BuildScriptsWithRequiredCollections = @(
    (Join-Path $SnapshotRoot 'createWindowsDist.ps1'),
    (Join-Path $SnapshotRoot 'createLinuxDist.sh'),
    (Join-Path $SnapshotRoot 'createMacOSDist.sh')
)
foreach ($BuildScript in $BuildScriptsWithRequiredCollections) {
    foreach ($Pattern in @('mutagen', 'imageio_ffmpeg', 'tkinterdnd2')) {
        if (-not (Select-String -LiteralPath $BuildScript -Pattern $Pattern -Quiet)) {
            throw "The source bundle build script does not collect or reference ${Pattern}: $BuildScript"
        }
    }
}

$WindowsBuildScript = Join-Path $SnapshotRoot 'createWindowsDist.ps1'
foreach ($Pattern in @('Assert-WindowsIcoIsDibBased', 'Assert-WindowsExeMatchesSourceIcon', 'Required Windows icon file not found', 'tlo-inventory-icon\.ico', 'tlo-search-icon\.ico', 'tlo-tag-icon\.ico', '--icon')) {
    if (-not (Select-String -LiteralPath $WindowsBuildScript -Pattern $Pattern -Quiet)) {
        throw "The Windows build script does not apply the required packaged-ICO icon support. Missing pattern: $Pattern"
    }
}
if (Select-String -LiteralPath $WindowsBuildScript -Pattern 'Convert-PngIconToWindowsIco|(?:\bPIL\b|\bPillow\b)' -Quiet) {
    throw "The Windows build script must use packaged .ico files, not build-time PNG-to-ICO conversion."
}

$MacBuildScript = Join-Path $SnapshotRoot 'createMacOSDist.sh'
foreach ($Pattern in @('tlo-inventory-icon\.icns', 'tlo-search-icon\.icns', 'tlo-tag-icon\.icns', '--icon')) {
    if (-not (Select-String -LiteralPath $MacBuildScript -Pattern $Pattern -Quiet)) {
        throw "The macOS build script does not apply the required inventory/search icon support. Missing pattern: $Pattern"
    }
}

$GitAttributesText = @'
*.py text eol=lf
*.sh text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.ps1 text eol=crlf
*.rtf binary
*.docx binary
*.zip binary
*.exe binary
*.sqlite binary
*.db binary
*.ico binary
*.icns binary
*.png binary
'@
$GitAttributesText | Set-Content -LiteralPath (Join-Path $SnapshotRoot '.gitattributes') -Encoding ascii

$GitIgnoreText = @'
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
build/
dist/
*.spec
downloaded/
release/
ci-artifact/
_staging_*/
tloDist-*/
TLO_V*Build*.zip
TLO_DBs/*
!TLO_DBs/artists.sqlite
!TLO_DBs/venues.txt
'@
$GitIgnoreText | Set-Content -LiteralPath (Join-Path $SnapshotRoot '.gitignore') -Encoding ascii

if ($PythonRunner) {
    Write-Host "Using local Python for optional source compilation check: $($PythonRunner.VersionText)"
    Invoke-Python -Runner $PythonRunner -Arguments @('-m', 'compileall', '-q', $SnapshotRoot)
}
else {
    Write-Warning 'No usable local Python 3 command was found. Skipping optional local compile check; GitHub Actions will run the required Python validation and tests.'
}

# Validate the exact release-control files after preparation.
$RequiredPreparedFiles = @(
    '.github\workflows\build-release.yml',
    'requirements-build.txt',
    'build_tlo_release.py',
    'scan_release_artifacts.py',
    'createWindowsDist.ps1',
    'createLinuxDist.sh',
    'createMacOSDist.sh',
    $ManualName,
    'TLO_DBs\artists.sqlite',
    'TLO_DBs\venues.txt'
)
foreach ($relativePath in $RequiredPreparedFiles) {
    Assert-File (Join-Path $SnapshotRoot $relativePath)
}

Remove-Item -LiteralPath (Join-Path $SnapshotRoot '.git') -Recurse -Force -ErrorAction SilentlyContinue
Invoke-Checked -Command 'git' -ArgumentList @('-C', $SnapshotRoot, 'init')
Invoke-Checked -Command 'git' -ArgumentList @('-C', $SnapshotRoot, 'branch', '-M', 'main')
Invoke-Checked -Command 'git' -ArgumentList @('-C', $SnapshotRoot, 'config', 'core.autocrlf', 'false')

# In a fresh temporary repository, --renormalize alone does not stage new files.
# Stage the full extracted snapshot first, then fail clearly if nothing is staged.
Invoke-Checked -Command 'git' -ArgumentList @('-C', $SnapshotRoot, 'add', '-A')
$StagedFiles = @(& git -C $SnapshotRoot diff --cached --name-only)
if ($LASTEXITCODE -ne 0) {
    throw 'git diff --cached failed while checking the staged snapshot.'
}
if ($StagedFiles.Count -eq 0) {
    throw 'No files were staged for the temporary Git snapshot. Check .gitignore and bundle extraction.'
}
Write-Host "Staged $($StagedFiles.Count) file(s) for the temporary Git snapshot."
Invoke-Checked -Command 'git' -ArgumentList @('-C', $SnapshotRoot, 'commit', '-m', "TLO Build $BuildToken tested release snapshot")
$RemoteResult = Invoke-QuietNative -Command 'git' -ArgumentList @('-C', $SnapshotRoot, 'remote')
if ($RemoteResult.ExitCode -ne 0) {
    throw 'git remote failed while checking the temporary repository remotes.'
}
$RemoteNames = @($RemoteResult.Output | ForEach-Object { ($_ | Out-String).Trim() } | Where-Object { $_ })
if ($RemoteNames -contains 'origin') {
    Invoke-Checked -Command 'git' -ArgumentList @('-C', $SnapshotRoot, 'remote', 'remove', 'origin')
}
Invoke-Checked -Command 'git' -ArgumentList @('-C', $SnapshotRoot, 'remote', 'add', 'origin', "https://github.com/$Repo.git")
Invoke-Checked -Command 'git' -ArgumentList @('-C', $SnapshotRoot, 'push', '--force', '--set-upstream', 'origin', 'main')
$RepositoryContainsBuildSnapshot = $true

# A brand-new disposable repository can briefly report that the workflow is not
# on the default branch immediately after the first push. Make main the default
# branch explicitly, then wait until GitHub Actions has indexed the workflow.
$DefaultBranch = (& gh api "repos/$Repo" --jq '.default_branch').Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($DefaultBranch)) {
    throw 'Could not read the GitHub repository default branch.'
}
if ($DefaultBranch -ne 'main') {
    Write-Host "Changing GitHub default branch from '$DefaultBranch' to 'main'."
    Invoke-Checked -Command 'gh' -ArgumentList @('api', '-X', 'PATCH', "repos/$Repo", '-f', 'default_branch=main')
}

$WorkflowName = 'build-release.yml'
$WorkflowPath = '.github/workflows/build-release.yml'
$WorkflowReady = $false
for ($Attempt = 1; $Attempt -le 24; $Attempt++) {
    $ContentCheck = Invoke-QuietNative -Command 'gh' -ArgumentList @('api', "repos/$Repo/contents/$WorkflowPath`?ref=main", '--jq', '.path')
    $ContentIsPresent = ($ContentCheck.ExitCode -eq 0)

    $WorkflowCheck = Invoke-QuietNative -Command 'gh' -ArgumentList @('workflow', 'view', $WorkflowName, '--repo', $Repo)
    $WorkflowIsIndexed = ($WorkflowCheck.ExitCode -eq 0)

    if ($ContentIsPresent -and $WorkflowIsIndexed) {
        $WorkflowReady = $true
        break
    }

    if ($Attempt -eq 1) {
        Write-Host "Waiting for GitHub to index $WorkflowPath on branch main."
    }
    Start-Sleep -Seconds 5
}

if (-not $WorkflowReady) {
    Write-Host 'Workflow files currently visible on branch main:'
    $VisibleWorkflowFiles = Invoke-QuietNative -Command 'gh' -ArgumentList @('api', "repos/$Repo/contents/.github/workflows`?ref=main", '--jq', '.[].name')
    if ($VisibleWorkflowFiles.ExitCode -eq 0) {
        $VisibleWorkflowFiles.Output | ForEach-Object { Write-Host $_ }
    }
    else {
        Write-Host '(GitHub did not return a workflow-file listing.)'
    }
    throw "GitHub did not expose workflow $WorkflowName on the repository default branch after waiting. Open the repository Actions tab once, verify Actions are enabled, then rerun Step 03."
}


function Wait-TloGitHubActionsRun {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$RunId,
        [int]$PollSeconds = 10,
        [int]$ProgressHeartbeatSeconds = 30,
        [int]$TimeoutMinutes = 240,
        [int]$MaxConsecutiveApiErrors = 12
    )

    $Deadline = [DateTime]::UtcNow.AddMinutes($TimeoutMinutes)
    $MonitorStarted = [DateTime]::UtcNow
    $ConsecutiveApiErrors = 0
    $LastStatus = ''
    $LastProgressSignature = ''
    $LastProgressDisplay = [DateTime]::MinValue

    while ([DateTime]::UtcNow -lt $Deadline) {
        # Fetch raw JSON and parse it in PowerShell. Do not pass a compound --jq
        # expression through Windows PowerShell's native-command argument marshalling;
        # that can split the expression and make gh report "accepts 1 arg(s), received 4".
        $StatusResult = Invoke-QuietNative -Command 'gh' -ArgumentList @(
            'api',
            "repos/$Repository/actions/runs/$RunId"
        ) -CaptureErrorOutput

        if ($StatusResult.ExitCode -ne 0) {
            $ConsecutiveApiErrors++
            $ErrorText = (($StatusResult.Output | ForEach-Object { [string]$_ }) -join "`n").Trim()
            if ([string]::IsNullOrWhiteSpace($ErrorText)) {
                $ErrorText = '(gh returned no diagnostic text)'
            }
            if ($ErrorText.Length -gt 2000) {
                $ErrorText = $ErrorText.Substring(0, 2000) + ' ... [truncated]'
            }

            $Delay = [Math]::Min(60, $PollSeconds * $ConsecutiveApiErrors)
            Write-Warning "GitHub API status check for run $RunId failed ($ConsecutiveApiErrors/$MaxConsecutiveApiErrors; gh exit code $($StatusResult.ExitCode))."
            Write-Warning "GitHub CLI/API diagnostic: $ErrorText"

            if ($ConsecutiveApiErrors -ge $MaxConsecutiveApiErrors) {
                throw "Could not determine GitHub Actions run $RunId status after $ConsecutiveApiErrors consecutive GitHub API errors. The run may still be active. Last gh diagnostic: $ErrorText"
            }

            Write-Warning "Retrying in $Delay seconds; the run is not being classified as failed."
            Start-Sleep -Seconds $Delay
            continue
        }

        $JsonText = (($StatusResult.Output | ForEach-Object { [string]$_ }) -join "`n").Trim()
        if ([string]::IsNullOrWhiteSpace($JsonText)) {
            $ConsecutiveApiErrors++
            $Delay = [Math]::Min(60, $PollSeconds * $ConsecutiveApiErrors)
            Write-Warning "GitHub API returned an empty run-status response for run $RunId ($ConsecutiveApiErrors/$MaxConsecutiveApiErrors)."
            if ($ConsecutiveApiErrors -ge $MaxConsecutiveApiErrors) {
                throw "Could not determine GitHub Actions run $RunId status after $ConsecutiveApiErrors consecutive empty API responses. The run may still be active."
            }
            Write-Warning "Retrying in $Delay seconds; the run is not being classified as failed."
            Start-Sleep -Seconds $Delay
            continue
        }

        try {
            $RunState = $JsonText | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            $ConsecutiveApiErrors++
            $Delay = [Math]::Min(60, $PollSeconds * $ConsecutiveApiErrors)
            $ParseDiagnostic = $_.Exception.Message
            $ResponsePreview = $JsonText
            if ($ResponsePreview.Length -gt 1000) {
                $ResponsePreview = $ResponsePreview.Substring(0, 1000) + ' ... [truncated]'
            }
            Write-Warning "GitHub API run-status response for run $RunId could not be parsed as JSON ($ConsecutiveApiErrors/$MaxConsecutiveApiErrors): $ParseDiagnostic"
            Write-Warning "GitHub API response: $ResponsePreview"
            if ($ConsecutiveApiErrors -ge $MaxConsecutiveApiErrors) {
                throw "Could not determine GitHub Actions run $RunId status after $ConsecutiveApiErrors consecutive malformed API responses. The run may still be active. Last parse diagnostic: $ParseDiagnostic"
            }
            Write-Warning "Retrying in $Delay seconds; the run is not being classified as failed."
            Start-Sleep -Seconds $Delay
            continue
        }

        $ConsecutiveApiErrors = 0
        $Status = [string]$RunState.status
        $Conclusion = [string]$RunState.conclusion
        $Url = [string]$RunState.html_url

        if ([string]::IsNullOrWhiteSpace($Status)) {
            Write-Warning "GitHub returned a run-status object without a status value for run $RunId. Retrying in $PollSeconds seconds."
            Start-Sleep -Seconds $PollSeconds
            continue
        }

        if ($Status -ne $LastStatus) {
            if ([string]::IsNullOrWhiteSpace($Url)) {
                Write-Host "GitHub Actions run $RunId status: $Status"
            }
            else {
                Write-Host "GitHub Actions run $RunId status: $Status ($Url)"
            }
            $LastStatus = $Status
        }

        # Best-effort job/step progress is display-only. Failure to retrieve job details
        # never changes the authoritative run status or failure classification above.
        $ProgressNow = [DateTime]::UtcNow
        $ProgressSignature = "run=$Status|conclusion=$Conclusion"
        $JobDisplayLines = @()
        $CompletedJobs = 0
        $RunningJobs = 0
        $QueuedJobs = 0
        $TotalJobs = 0
        $HaveJobDetails = $false

        $JobsResult = Invoke-QuietNative -Command 'gh' -ArgumentList @(
            'api',
            "repos/$Repository/actions/runs/$RunId/jobs?per_page=100"
        ) -CaptureErrorOutput

        if ($JobsResult.ExitCode -eq 0) {
            $JobsJsonText = (($JobsResult.Output | ForEach-Object { [string]$_ }) -join "`n").Trim()
            if (-not [string]::IsNullOrWhiteSpace($JobsJsonText)) {
                try {
                    $JobsState = $JobsJsonText | ConvertFrom-Json -ErrorAction Stop
                    $Jobs = @()
                    if ($null -ne $JobsState.jobs) {
                        $Jobs = @($JobsState.jobs)
                    }
                    if ($Jobs.Count -gt 0) {
                        $HaveJobDetails = $true
                        $TotalJobs = $Jobs.Count
                        foreach ($Job in $Jobs) {
                            $JobName = [string]$Job.name
                            $JobStatus = [string]$Job.status
                            $JobConclusion = [string]$Job.conclusion
                            $ActiveStepName = ''

                            if ([string]::Equals($JobStatus, 'completed', [System.StringComparison]::OrdinalIgnoreCase)) {
                                $CompletedJobs++
                            }
                            elseif ([string]::Equals($JobStatus, 'in_progress', [System.StringComparison]::OrdinalIgnoreCase)) {
                                $RunningJobs++
                            }
                            else {
                                $QueuedJobs++
                            }

                            if ([string]::Equals($JobStatus, 'in_progress', [System.StringComparison]::OrdinalIgnoreCase) -and $null -ne $Job.steps) {
                                $ActiveStep = $Job.steps |
                                    Where-Object { [string]::Equals([string]$_.status, 'in_progress', [System.StringComparison]::OrdinalIgnoreCase) } |
                                    Select-Object -First 1
                                if ($null -ne $ActiveStep) {
                                    $ActiveStepName = [string]$ActiveStep.name
                                }
                            }

                            if ([string]::Equals($JobStatus, 'completed', [System.StringComparison]::OrdinalIgnoreCase)) {
                                $DisplayState = if ([string]::IsNullOrWhiteSpace($JobConclusion)) { 'completed' } else { "completed/$JobConclusion" }
                            }
                            elseif (-not [string]::IsNullOrWhiteSpace($ActiveStepName)) {
                                $DisplayState = "$JobStatus - $ActiveStepName"
                            }
                            else {
                                $DisplayState = $JobStatus
                            }

                            $JobDisplayLines += "  $JobName : $DisplayState"
                            $ProgressSignature += "|$JobName=$JobStatus/$JobConclusion/$ActiveStepName"
                        }
                    }
                }
                catch {
                    # Progress detail is intentionally best-effort. The run-level status above
                    # remains authoritative and will continue to be polled normally.
                }
            }
        }

        $SignatureChanged = -not [string]::Equals($ProgressSignature, $LastProgressSignature, [System.StringComparison]::Ordinal)
        $HeartbeatDue = (($ProgressNow - $LastProgressDisplay).TotalSeconds -ge $ProgressHeartbeatSeconds)
        if ($SignatureChanged -or $HeartbeatDue) {
            $Elapsed = $ProgressNow - $MonitorStarted
            $ElapsedText = ('{0:00}:{1:00}:{2:00}' -f [int]$Elapsed.TotalHours, $Elapsed.Minutes, $Elapsed.Seconds)
            if ($HaveJobDetails) {
                Write-Host "GitHub Actions progress [$ElapsedText]: run=$Status; jobs $CompletedJobs/$TotalJobs complete, $RunningJobs running, $QueuedJobs queued."
                if ($SignatureChanged) {
                    $JobDisplayLines | ForEach-Object { Write-Host $_ }
                }
            }
            else {
                Write-Host "GitHub Actions progress [$ElapsedText]: run=$Status; job details temporarily unavailable."
            }
            $LastProgressSignature = $ProgressSignature
            $LastProgressDisplay = $ProgressNow
        }

        if ([string]::Equals($Status, 'completed', [System.StringComparison]::OrdinalIgnoreCase)) {
            return [pscustomobject]@{
                Status = $Status
                Conclusion = $Conclusion
                Url = $Url
                Success = [string]::Equals($Conclusion, 'success', [System.StringComparison]::OrdinalIgnoreCase)
            }
        }

        Start-Sleep -Seconds $PollSeconds
    }

    throw "Timed out after $TimeoutMinutes minutes while waiting for GitHub Actions run $RunId. The run is not being classified as failed because its terminal conclusion was not confirmed."
}

function Show-TloGitHubFailedLogBestEffort {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$RunId
    )

    for ($Attempt = 1; $Attempt -le 5; $Attempt++) {
        & gh run view $RunId --repo $Repository --log-failed
        if ($LASTEXITCODE -eq 0) {
            return
        }
        if ($Attempt -lt 5) {
            $Delay = 5 * $Attempt
            Write-Warning "Could not retrieve failed-step logs for run $RunId (attempt $Attempt/5). Retrying in $Delay seconds."
            Start-Sleep -Seconds $Delay
        }
    }
    Write-Warning "GitHub Actions run $RunId has a confirmed non-success conclusion, but failed-step logs could not be retrieved after retries. Open the preserved run in GitHub for diagnosis."
}

function Download-TloGitHubArtifactWithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$RunId,
        [Parameter(Mandatory = $true)][string]$ArtifactName,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $LastOutput = @()
    for ($Attempt = 1; $Attempt -le 6; $Attempt++) {
        $LastOutput = @(& gh run download $RunId --repo $Repository --name $ArtifactName --dir $Destination 2>&1)
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Success = $true; Output = @($LastOutput) }
        }
        if ($Attempt -lt 6) {
            $Delay = [Math]::Min(60, 10 * $Attempt)
            Write-Warning "Artifact download for run $RunId failed (attempt $Attempt/6). Retrying in $Delay seconds."
            Start-Sleep -Seconds $Delay
        }
    }
    return [pscustomobject]@{ Success = $false; Output = @($LastOutput) }
}

$WorkflowRunOutput = @(& gh workflow run $WorkflowName --repo $Repo --ref main -f "version_number=$VersionNumber" -f "build_number=$BuildNumber" 2>&1)
if ($LASTEXITCODE -ne 0) {
    $WorkflowRunOutput | ForEach-Object { Write-Host $_ }
    throw "gh workflow run failed with exit code $LASTEXITCODE."
}
$WorkflowRunOutput | ForEach-Object { Write-Host $_ }
$WorkflowRunText = ($WorkflowRunOutput | Out-String)
$RunId = $null
if ($WorkflowRunText -match '/actions/runs/(\d+)') {
    $RunId = $Matches[1]
}

if ([string]::IsNullOrWhiteSpace($RunId)) {
    Write-Host 'GitHub CLI did not return a run URL. Waiting for the newest workflow_dispatch run to appear.'
    for ($Attempt = 1; $Attempt -le 24; $Attempt++) {
        $RunListResult = Invoke-QuietNative -Command 'gh' -ArgumentList @('run', 'list', '--repo', $Repo, '--workflow', $WorkflowName, '--branch', 'main', '--event', 'workflow_dispatch', '--limit', '1', '--json', 'databaseId', '--jq', '.[0].databaseId')
        if ($RunListResult.ExitCode -eq 0) {
            $RunIdCandidateText = ($RunListResult.Output | Out-String).Trim()
            if ($RunIdCandidateText -match '^\d+$') {
                $RunId = $RunIdCandidateText
                break
            }
        }
        Start-Sleep -Seconds 5
    }
}

if ([string]::IsNullOrWhiteSpace($RunId)) {
    throw 'Could not identify the newly started GitHub Actions run.'
}
Write-Host "GitHub Actions run: $RunId"
$GitHubActionsRunIdForCleanup = $RunId

try {
    $RunResult = Wait-TloGitHubActionsRun -Repository $Repo -RunId $RunId
}
catch {
    $GitHubActionsRunStateUncertain = $true
    $PreserveRepositorySnapshot = $true
    Write-Host ''
    Write-Warning $_.Exception.Message
    Write-Host "GitHub Actions run $RunId was not classified as failed because a terminal conclusion could not be confirmed."
    Write-Host "Preserving the GitHub run, disposable repository snapshot, and local build workspace so the in-progress or temporarily unreachable run is not disrupted."
    throw "Could not confirm the terminal state of GitHub Actions run $RunId. Nothing was cleaned that could interfere with the run. Rerun Step 03 or use Step 04 after GitHub API access is healthy."
}

if (-not $RunResult.Success) {
    $GitHubActionsRunFailed = $true
    Write-Host ''
    Write-Host "GitHub Actions run $RunId completed with conclusion '$($RunResult.Conclusion)'. Failed-step log follows:"
    Show-TloGitHubFailedLogBestEffort -Repository $Repo -RunId $RunId
    Write-Host ''
    Write-Host "Preserving failed GitHub Actions run $RunId and its artifacts/logs for diagnosis."
    throw "GitHub Actions run $RunId completed with conclusion '$($RunResult.Conclusion)'. The failed run was preserved; see the diagnostics above."
}

Write-Host "GitHub Actions run $RunId completed successfully."
Write-Host "Downloading GitHub Actions artifact: $ArtifactName"
$DownloadResult = Download-TloGitHubArtifactWithRetry -Repository $Repo -RunId $RunId -ArtifactName $ArtifactName -Destination $ReleaseOutput
$DownloadOutput = @($DownloadResult.Output)
if (-not $DownloadResult.Success) {
    $DownloadOutput | ForEach-Object { Write-Host $_ }
    $PreserveRepositorySnapshot = $true
    $PreserveGitHubRunForRecovery = $true
    Write-Host "Available artifacts for run ${RunId}:"
    $ArtifactListOutput = @(& gh api "repos/$Repo/actions/runs/$RunId/artifacts" --jq '.artifacts[].name' 2>&1)
    if ($LASTEXITCODE -eq 0 -and $ArtifactListOutput.Count -gt 0) {
        $ArtifactListOutput | ForEach-Object { Write-Host " - $_" }
    } else {
        $ArtifactListOutput | ForEach-Object { Write-Host $_ }
        Write-Host '(Unable to list run artifacts.)'
    }
    throw "GitHub Actions run $RunId succeeded, but artifact '$ArtifactName' could not be downloaded after retries. The repository snapshot and local workspace were preserved for recovery."
}
foreach ($AssetPath in $ReleaseAssetPaths) {
    Assert-File $AssetPath
}

function Get-TloSha256OrThrow {
    param([Parameter(Mandatory = $true)][string]$FilePath)

    try {
        $HashResult = Get-FileHash -LiteralPath $FilePath -Algorithm SHA256 -ErrorAction Stop
    }
    catch {
        $Detail = $_.Exception.Message
        throw "Could not read/hash '$FilePath'. Windows security software may have blocked or quarantined the file. No checksum verification was bypassed. Detail: $Detail"
    }
    if ($null -eq $HashResult -or
        -not ($HashResult.PSObject.Properties.Name -contains 'Hash') -or
        [string]::IsNullOrWhiteSpace([string]$HashResult.Hash)) {
        throw "Could not read/hash '$FilePath': Get-FileHash returned no usable hash. Windows security software may have blocked or quarantined the file. No checksum verification was bypassed."
    }
    return ([string]$HashResult.Hash).ToUpperInvariant()
}


function Expand-TloVerificationZipOrThrow {
    param(
        [Parameter(Mandatory = $true)][string]$ZipPath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    Remove-Item -LiteralPath $DestinationPath -Recurse -Force -ErrorAction SilentlyContinue
    try {
        try { Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue } catch {}
        [System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $DestinationPath)
    }
    catch {
        $Detail = $_.Exception.Message
        Remove-Item -LiteralPath $DestinationPath -Recurse -Force -ErrorAction SilentlyContinue
        throw "Could not extract '$ZipPath' for local verification. Windows security software may have blocked or quarantined a packaged file. Detail: $Detail"
    }
}


function Get-TloZipEntryIndex {
    param(
        [Parameter(Mandatory = $true)][System.IO.Compression.ZipArchive]$Archive,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )

    $Index = @{}
    foreach ($Entry in $Archive.Entries) {
        $Name = ([string]$Entry.FullName).Replace('\', '/').TrimStart('/')
        if ([string]::IsNullOrWhiteSpace($Name) -or $Name.EndsWith('/')) { continue }
        $Key = $Name.ToLowerInvariant()
        if ($Index.ContainsKey($Key)) {
            throw "ZIP contains duplicate file entries that differ only by case or repeat the same path: $Name in $ZipPath"
        }
        $Index[$Key] = $Entry
    }
    return $Index
}

function Test-TloZipEntryFile {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Index,
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )

    $Normalized = $RelativePath.Replace('\', '/').TrimStart('/')
    if (-not $Index.ContainsKey($Normalized.ToLowerInvariant())) {
        throw "ZIP $ZipPath is missing required file: $RelativePath"
    }
}

function Test-TloZipEntryDirectory {
    param(
        [Parameter(Mandatory = $true)][System.IO.Compression.ZipArchive]$Archive,
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )

    $Normalized = $RelativePath.Replace('\', '/').Trim('/').ToLowerInvariant()
    $Prefix = $Normalized + '/'
    $Found = $false
    foreach ($Entry in $Archive.Entries) {
        $Name = ([string]$Entry.FullName).Replace('\', '/').TrimStart('/').ToLowerInvariant()
        if ($Name -eq $Prefix -or $Name.StartsWith($Prefix)) {
            $Found = $true
            break
        }
    }
    if (-not $Found) {
        throw "ZIP $ZipPath is missing required directory: $RelativePath"
    }
}

function Get-TloZipSha256OrThrow {
    param(
        [Parameter(Mandatory = $true)][System.IO.Compression.ZipArchiveEntry]$Entry,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )

    $Stream = $null
    $Sha = $null
    try {
        $Stream = $Entry.Open()
        $Sha = [System.Security.Cryptography.SHA256]::Create()
        $Bytes = $Sha.ComputeHash($Stream)
        return (($Bytes | ForEach-Object { $_.ToString('x2') }) -join '').ToUpperInvariant()
    }
    catch {
        $Detail = $_.Exception.Message
        throw "Could not read/hash ZIP member '$($Entry.FullName)' inside '$ZipPath'. No extracted executable was created and no checksum verification was bypassed. Detail: $Detail"
    }
    finally {
        if ($null -ne $Sha) { $Sha.Dispose() }
        if ($null -ne $Stream) { $Stream.Dispose() }
    }
}

function Test-TloZipChecksumsInPlace {
    param(
        [Parameter(Mandatory = $true)][System.IO.Compression.ZipArchive]$Archive,
        [Parameter(Mandatory = $true)][hashtable]$Index,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )

    Test-TloZipEntryFile -Index $Index -RelativePath 'checksums.txt' -ZipPath $ZipPath
    $ChecksumEntry = $Index['checksums.txt']
    $Reader = $null
    $Stream = $null
    try {
        $Stream = $ChecksumEntry.Open()
        $Reader = New-Object -TypeName System.IO.StreamReader -ArgumentList $Stream
        $ChecksumText = $Reader.ReadToEnd()
    }
    finally {
        if ($null -ne $Reader) { $Reader.Dispose() }
        elseif ($null -ne $Stream) { $Stream.Dispose() }
    }

    foreach ($Line in ($ChecksumText -split "`r?`n")) {
        if ([string]::IsNullOrWhiteSpace($Line)) { continue }
        if ($Line -notmatch '^([0-9a-fA-F]{64})  (.+)$') {
            throw "Malformed checksums.txt line in ${ZipPath}: $Line"
        }
        $ExpectedHash = $Matches[1].ToUpperInvariant()
        $RelativePath = $Matches[2].Replace('\', '/').TrimStart('/')
        $Key = $RelativePath.ToLowerInvariant()
        if (-not $Index.ContainsKey($Key)) {
            throw "Checksum manifest in $ZipPath references missing file: $RelativePath"
        }
        $ActualHash = Get-TloZipSha256OrThrow -Entry $Index[$Key] -ZipPath $ZipPath
        if ($ActualHash -ne $ExpectedHash) {
            throw "Checksum mismatch in ${ZipPath}: $RelativePath"
        }
    }
}

function Test-TloWindowsZipInPlace {
    param(
        [Parameter(Mandatory = $true)][string]$ZipPath,
        [Parameter(Mandatory = $true)][string]$PlatformKey,
        [Parameter(Mandatory = $true)][string]$ScanReceipt,
        [Parameter(Mandatory = $true)][string[]]$RequiredAppFiles,
        [Parameter(Mandatory = $true)][bool]$IsComplete
    )

    try { Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue } catch {}
    $Archive = $null
    try {
        $Archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        $Index = Get-TloZipEntryIndex -Archive $Archive -ZipPath $ZipPath

        if ($IsComplete) {
            $ExpectedRootDirectories = @('apps', 'debug', 'dups', 'logs', 'readyForXfer', 'setlists', 'staged', 'TLO_DBs', 'scan-reports')
            foreach ($Directory in $ExpectedRootDirectories) {
                Test-TloZipEntryDirectory -Archive $Archive -RelativePath $Directory -ZipPath $ZipPath
            }
            $ExpectedFiles = @(
                $ManualName,
                'TLO-FAQ.txt',
                'TLO_DBs\artists.sqlite',
                'TLO_DBs\venues.txt',
                ("scan-reports\{0}" -f $ScanReceipt),
                'scan-reports\final-package-scan.json',
                'README_FIRST.txt',
                'toBeInventoried.txt',
                'manifest.json',
                'checksums.txt'
            ) + $RequiredAppFiles
        }
        else {
            Test-TloZipEntryDirectory -Archive $Archive -RelativePath 'apps\Windows' -ZipPath $ZipPath
            $ExpectedFiles = @(
                ("scan-reports\{0}" -f $ScanReceipt),
                'UPDATE_MANIFEST.json',
                'README_UPDATE.txt',
                'checksums.txt'
            ) + $RequiredAppFiles
        }
        foreach ($RelativePath in $ExpectedFiles) {
            Test-TloZipEntryFile -Index $Index -RelativePath $RelativePath -ZipPath $ZipPath
        }

        $PlatformNames = @{}
        foreach ($Entry in $Archive.Entries) {
            $Name = ([string]$Entry.FullName).Replace('\', '/').TrimStart('/')
            $Parts = @($Name -split '/')
            if ($Parts.Count -ge 2 -and $Parts[0].ToLowerInvariant() -eq 'apps' -and -not [string]::IsNullOrWhiteSpace($Parts[1])) {
                $PlatformNames[$Parts[1].ToLowerInvariant()] = $Parts[1]
            }
        }
        $UnexpectedPlatforms = @($PlatformNames.Values | Where-Object { $_ -ine 'Windows' })
        if ($UnexpectedPlatforms.Count -gt 0) {
            throw "ZIP $ZipPath contains other platform app folders: $($UnexpectedPlatforms -join ', ')"
        }

        Test-TloZipEntryDirectory -Archive $Archive -RelativePath 'apps\Windows\tlo-deleteDupes_runtime' -ZipPath $ZipPath
        Test-TloZipEntryFile -Index $Index -RelativePath 'apps\Windows\tlo-deleteDupes_runtime\python.exe' -ZipPath $ZipPath
        Test-TloZipEntryFile -Index $Index -RelativePath 'apps\Windows\tlo-deleteDupes_runtime\tlo-deleteDupes.py' -ZipPath $ZipPath

        if ($PlatformKey -eq 'windows-onedir') {
            Test-TloZipEntryDirectory -Archive $Archive -RelativePath 'apps\Windows\_internal' -ZipPath $ZipPath
            $UnexpectedApplicationDirectories = @{}
            foreach ($Entry in $Archive.Entries) {
                $Name = ([string]$Entry.FullName).Replace('\', '/').TrimStart('/')
                $Parts = @($Name -split '/')
                if ($Parts.Count -ge 4 -and $Parts[0] -ieq 'apps' -and $Parts[1] -ieq 'Windows' -and -not [string]::IsNullOrWhiteSpace($Parts[2])) {
                    if ($Parts[2] -inotmatch '^(_internal|tlo-deleteDupes_runtime)$') {
                        $UnexpectedApplicationDirectories[$Parts[2].ToLowerInvariant()] = $Parts[2]
                    }
                }
            }
            if ($UnexpectedApplicationDirectories.Count -gt 0) {
                throw "Windows onedir ZIP contains unexpected application subdirectories: $($UnexpectedApplicationDirectories.Values -join ', ')"
            }
        }

        if ($IsComplete) {
            $AllowedDatabaseRelativePaths = @('tlo_dbs/artists.sqlite', 'tlo_dbs/venues.txt')
            $UnexpectedDatabaseEntries = @()
            $UnexpectedRequirementsDocuments = @()
            $UnexpectedRtfManuals = @()
            foreach ($Entry in $Archive.Entries) {
                $Name = ([string]$Entry.FullName).Replace('\', '/').TrimStart('/')
                if ($Name.EndsWith('/')) { continue }
                $Lower = $Name.ToLowerInvariant()
                if ($Lower.StartsWith('tlo_dbs/') -and $Lower -notin $AllowedDatabaseRelativePaths) {
                    $UnexpectedDatabaseEntries += $Name
                }
                $Leaf = [System.IO.Path]::GetFileName($Name)
                if ($Leaf -like 'TLO_Inventory_Requirements*') {
                    $UnexpectedRequirementsDocuments += $Name
                }
                if ($Name -notmatch '/' -and $Leaf -like 'TLO_Inventory_User_Manual_v*.rtf' -and $Leaf -ne $ManualName) {
                    $UnexpectedRtfManuals += $Name
                }
            }
            if ($UnexpectedDatabaseEntries.Count -gt 0) {
                throw "TLO_DBs contains unexpected entries in ${ZipPath}: $($UnexpectedDatabaseEntries -join ', ')"
            }
            if ($UnexpectedRequirementsDocuments.Count -gt 0) {
                throw "Complete ZIP $ZipPath contains a requirements document, which is not permitted: $($UnexpectedRequirementsDocuments -join ', ')"
            }
            if ($UnexpectedRtfManuals.Count -gt 0) {
                throw "Complete ZIP $ZipPath contains an RTF manual for another build: $($UnexpectedRtfManuals -join ', ')"
            }
        }
        else {
            $ForbiddenEntries = @('bootlist.csv', 'toBeInventoried.txt', 'setlists', 'logs', 'debug', 'dups', 'readyForXfer', 'staged', 'TLO_DBs')
            foreach ($Forbidden in $ForbiddenEntries) {
                $Normalized = $Forbidden.Replace('\', '/').Trim('/').ToLowerInvariant()
                $Prefix = $Normalized + '/'
                foreach ($Entry in $Archive.Entries) {
                    $Name = ([string]$Entry.FullName).Replace('\', '/').TrimStart('/').ToLowerInvariant()
                    if ($Name -eq $Normalized -or $Name -eq $Prefix -or $Name.StartsWith($Prefix)) {
                        throw "Update ZIP $ZipPath unexpectedly contains protected path: $Forbidden"
                    }
                }
            }
        }

        Test-TloZipChecksumsInPlace -Archive $Archive -Index $Index -ZipPath $ZipPath
    }
    finally {
        if ($null -ne $Archive) { $Archive.Dispose() }
    }
}

function Test-TloZipChecksums {
    param([Parameter(Mandatory = $true)][string]$ExtractedRoot)

    $ChecksumPath = Join-Path $ExtractedRoot 'checksums.txt'
    Assert-File $ChecksumPath
    foreach ($line in Get-Content -LiteralPath $ChecksumPath) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -notmatch '^([0-9a-fA-F]{64})  (.+)$') {
            throw "Malformed checksums.txt line: $line"
        }
        $ExpectedHash = $Matches[1].ToUpperInvariant()
        $RelativePath = $Matches[2].Replace('/', [System.IO.Path]::DirectorySeparatorChar)
        $FilePath = Join-Path $ExtractedRoot $RelativePath
        Assert-File $FilePath
        $ActualHash = Get-TloSha256OrThrow -FilePath $FilePath
        if ($ActualHash -ne $ExpectedHash) {
            throw "Checksum mismatch: $RelativePath"
        }
    }
}

function Test-TloCompleteZip {
    param(
        [Parameter(Mandatory = $true)][string]$ZipPath,
        [Parameter(Mandatory = $true)][string]$PlatformKey,
        [Parameter(Mandatory = $true)][string]$PlatformFolder,
        [Parameter(Mandatory = $true)][string]$ScanReceipt,
        [Parameter(Mandatory = $true)][string[]]$RequiredAppFiles
    )

    if ($PlatformKey -in @('windows', 'windows-onedir')) {
        Test-TloWindowsZipInPlace -ZipPath $ZipPath -PlatformKey $PlatformKey -ScanReceipt $ScanReceipt -RequiredAppFiles $RequiredAppFiles -IsComplete $true
        return
    }

    $ExtractedRoot = Join-Path $VerifyRoot ("complete-{0}" -f $PlatformKey)
    Expand-TloVerificationZipOrThrow -ZipPath $ZipPath -DestinationPath $ExtractedRoot

    $ExpectedRootDirectories = @(
        'apps', 'debug', 'dups', 'logs', 'readyForXfer', 'setlists', 'staged', 'TLO_DBs', 'scan-reports'
    )
    $ActualRootDirectories = @(
        Get-ChildItem -LiteralPath $ExtractedRoot -Directory | Select-Object -ExpandProperty Name
    )
    $MissingRootDirectories = @($ExpectedRootDirectories | Where-Object { $_ -notin $ActualRootDirectories })
    if ($MissingRootDirectories.Count -gt 0) {
        throw "Complete ZIP $ZipPath is missing root directories: $($MissingRootDirectories -join ', ')"
    }

    $AppsRoot = Join-Path $ExtractedRoot 'apps'
    Assert-Directory (Join-Path $AppsRoot $PlatformFolder)
    $UnexpectedPlatforms = @(
        Get-ChildItem -LiteralPath $AppsRoot -Directory |
            Where-Object { $_.Name -ne $PlatformFolder } |
            Select-Object -ExpandProperty Name
    )
    if ($UnexpectedPlatforms.Count -gt 0) {
        throw "Complete ZIP $ZipPath contains other platform app folders: $($UnexpectedPlatforms -join ', ')"
    }

    $ExpectedFiles = @(
        $ManualName,
        'TLO-FAQ.txt',
        'TLO_DBs\artists.sqlite',
        'TLO_DBs\venues.txt',
        ("scan-reports\{0}" -f $ScanReceipt),
        'scan-reports\final-package-scan.json',
        'README_FIRST.txt',
        'toBeInventoried.txt',
        'manifest.json',
        'checksums.txt'
    ) + $RequiredAppFiles
    foreach ($relativePath in $ExpectedFiles) {
        Assert-File (Join-Path $ExtractedRoot $relativePath)
    }

    if ($PlatformKey -eq 'windows') {
        $WindowsApps = Join-Path $ExtractedRoot 'apps\Windows'
        $DeleteDupesRuntime = Join-Path $WindowsApps 'tlo-deleteDupes_runtime'
        Assert-Directory $DeleteDupesRuntime
        if (-not (Get-ChildItem -LiteralPath $DeleteDupesRuntime -File -Recurse | Select-Object -First 1)) {
            throw "Windows complete ZIP has an empty tlo-deleteDupes private runtime folder: $ZipPath"
        }
        Assert-File (Join-Path $DeleteDupesRuntime 'python.exe')
        Assert-File (Join-Path $DeleteDupesRuntime 'tlo-deleteDupes.py')
    }

    if ($PlatformKey -eq 'windows-onedir') {
        $WindowsApps = Join-Path $ExtractedRoot 'apps\Windows'
        $SharedInternal = Join-Path $WindowsApps '_internal'
        Assert-Directory $SharedInternal
        if (-not (Get-ChildItem -LiteralPath $SharedInternal -File -Recurse | Select-Object -First 1)) {
            throw "Windows onedir complete ZIP has an empty shared _internal folder: $ZipPath"
        }
        $DeleteDupesRuntime = Join-Path $WindowsApps 'tlo-deleteDupes_runtime'
        Assert-Directory $DeleteDupesRuntime
        Assert-File (Join-Path $DeleteDupesRuntime 'python.exe')
        Assert-File (Join-Path $DeleteDupesRuntime 'tlo-deleteDupes.py')
        $UnexpectedApplicationDirectories = @(
            Get-ChildItem -LiteralPath $WindowsApps -Directory |
                Where-Object { $_.Name -notin @('_internal', 'tlo-deleteDupes_runtime') } |
                Select-Object -ExpandProperty FullName
        )
        if ($UnexpectedApplicationDirectories.Count -gt 0) {
            throw "Windows onedir complete ZIP contains unexpected application subdirectories: $($UnexpectedApplicationDirectories -join ', ')"
        }
    }

    $AllowedDatabaseRelativePaths = @('TLO_DBs\artists.sqlite', 'TLO_DBs\venues.txt')
    $DatabaseFiles = @(Get-ChildItem -LiteralPath (Join-Path $ExtractedRoot 'TLO_DBs') -Force -File -Recurse)
    $UnexpectedDatabaseEntries = @($DatabaseFiles | Where-Object {
        $RelativeText = $_.FullName.Substring($ExtractedRoot.Length)
        $Relative = $RelativeText.TrimStart([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
        $Relative -notin $AllowedDatabaseRelativePaths
    })
    if ($UnexpectedDatabaseEntries.Count -gt 0) {
        throw "TLO_DBs contains unexpected entries in ${ZipPath}: $($UnexpectedDatabaseEntries.FullName -join ', ')"
    }

    $UnexpectedRequirementsDocuments = @(
        Get-ChildItem -LiteralPath $ExtractedRoot -Filter 'TLO_Inventory_Requirements*' -File -Recurse -ErrorAction SilentlyContinue
    )
    if ($UnexpectedRequirementsDocuments.Count -gt 0) {
        throw "Complete ZIP $ZipPath contains a requirements document, which is not permitted: $($UnexpectedRequirementsDocuments.FullName -join ', ')"
    }
    $UnexpectedRtfManuals = @(Get-ChildItem -LiteralPath $ExtractedRoot -Filter 'TLO_Inventory_User_Manual_v*.rtf' -File | Where-Object Name -ne $ManualName)
    if ($UnexpectedRtfManuals.Count -gt 0) {
        throw "Complete ZIP $ZipPath contains an RTF manual for another build: $($UnexpectedRtfManuals.Name -join ', ')"
    }

    Test-TloZipChecksums -ExtractedRoot $ExtractedRoot
}

function Test-TloUpdateZip {
    param(
        [Parameter(Mandatory = $true)][string]$ZipPath,
        [Parameter(Mandatory = $true)][string]$PlatformKey,
        [Parameter(Mandatory = $true)][string]$PlatformFolder,
        [Parameter(Mandatory = $true)][string]$ScanReceipt,
        [Parameter(Mandatory = $true)][string[]]$RequiredAppFiles
    )

    if ($PlatformKey -in @('windows', 'windows-onedir')) {
        Test-TloWindowsZipInPlace -ZipPath $ZipPath -PlatformKey $PlatformKey -ScanReceipt $ScanReceipt -RequiredAppFiles $RequiredAppFiles -IsComplete $false
        return
    }

    $ExtractedRoot = Join-Path $VerifyRoot ("update-{0}" -f $PlatformKey)
    Expand-TloVerificationZipOrThrow -ZipPath $ZipPath -DestinationPath $ExtractedRoot

    Assert-Directory (Join-Path (Join-Path $ExtractedRoot 'apps') $PlatformFolder)
    $ExpectedFiles = @(
        ("scan-reports\{0}" -f $ScanReceipt),
        'UPDATE_MANIFEST.json',
        'README_UPDATE.txt',
        'checksums.txt'
    ) + $RequiredAppFiles
    foreach ($relativePath in $ExpectedFiles) {
        Assert-File (Join-Path $ExtractedRoot $relativePath)
    }

    if ($PlatformKey -eq 'windows') {
        $WindowsApps = Join-Path $ExtractedRoot 'apps\Windows'
        $DeleteDupesRuntime = Join-Path $WindowsApps 'tlo-deleteDupes_runtime'
        Assert-Directory $DeleteDupesRuntime
        if (-not (Get-ChildItem -LiteralPath $DeleteDupesRuntime -File -Recurse | Select-Object -First 1)) {
            throw "Windows update ZIP has an empty tlo-deleteDupes private runtime folder: $ZipPath"
        }
        Assert-File (Join-Path $DeleteDupesRuntime 'python.exe')
        Assert-File (Join-Path $DeleteDupesRuntime 'tlo-deleteDupes.py')
    }

    if ($PlatformKey -eq 'windows-onedir') {
        $WindowsApps = Join-Path $ExtractedRoot 'apps\Windows'
        $SharedInternal = Join-Path $WindowsApps '_internal'
        Assert-Directory $SharedInternal
        if (-not (Get-ChildItem -LiteralPath $SharedInternal -File -Recurse | Select-Object -First 1)) {
            throw "Windows onedir update ZIP has an empty shared _internal folder: $ZipPath"
        }
        $DeleteDupesRuntime = Join-Path $WindowsApps 'tlo-deleteDupes_runtime'
        Assert-Directory $DeleteDupesRuntime
        Assert-File (Join-Path $DeleteDupesRuntime 'python.exe')
        Assert-File (Join-Path $DeleteDupesRuntime 'tlo-deleteDupes.py')
        $UnexpectedApplicationDirectories = @(
            Get-ChildItem -LiteralPath $WindowsApps -Directory |
                Where-Object { $_.Name -notin @('_internal', 'tlo-deleteDupes_runtime') } |
                Select-Object -ExpandProperty FullName
        )
        if ($UnexpectedApplicationDirectories.Count -gt 0) {
            throw "Windows onedir update ZIP contains unexpected application subdirectories: $($UnexpectedApplicationDirectories -join ', ')"
        }
    }

    $ForbiddenEntries = @('bootlist.csv', 'toBeInventoried.txt', 'setlists', 'logs', 'debug', 'dups', 'readyForXfer', 'staged', 'TLO_DBs')
    foreach ($Forbidden in $ForbiddenEntries) {
        if (Test-Path -LiteralPath (Join-Path $ExtractedRoot $Forbidden)) {
            throw "Update ZIP $ZipPath unexpectedly contains protected path: $Forbidden"
        }
    }

    Test-TloZipChecksums -ExtractedRoot $ExtractedRoot
}

$PlatformValidation = @(
    [pscustomobject]@{
        Key = 'windows'; Folder = 'Windows'; Scan = 'windows.json'; Complete = $CompleteZipWindows; Update = $UpdateZipWindows;
        Files = @('apps\Windows\tlo-gi.exe', 'apps\Windows\tlo-research.exe', 'apps\Windows\tlo-ggi.exe', 'apps\Windows\tlo-gsi.exe', 'apps\Windows\tlo-tag.exe', 'apps\Windows\tlo-deleteDupes.cmd', 'apps\Windows\search-artist-db.exe')
    },
    [pscustomobject]@{
        Key = 'windows-onedir'; Folder = 'Windows'; Scan = 'windows-onedir.json'; Complete = $CompleteZipWindowsOneDir; Update = $UpdateZipWindowsOneDir;
        Files = @('apps\Windows\tlo-gi.exe', 'apps\Windows\tlo-research.exe', 'apps\Windows\tlo-ggi.exe', 'apps\Windows\tlo-gsi.exe', 'apps\Windows\tlo-tag.exe', 'apps\Windows\tlo-deleteDupes.cmd', 'apps\Windows\search-artist-db.exe')
    },
    [pscustomobject]@{
        Key = 'linux'; Folder = 'Linux'; Scan = 'linux.json'; Complete = $CompleteZipLinux; Update = $UpdateZipLinux;
        Files = @('apps\Linux\tlo-gi', 'apps\Linux\tlo-research', 'apps\Linux\tlo-ggi', 'apps\Linux\tlo-gsi', 'apps\Linux\tlo-tag', 'apps\Linux\tlo-deleteDupes', 'apps\Linux\search-artist-db')
    },
    [pscustomobject]@{
        Key = 'macos'; Folder = 'macOS'; Scan = 'macos.json'; Complete = $CompleteZipMacOS; Update = $UpdateZipMacOS;
        Files = @('apps\macOS\tlo-gi', 'apps\macOS\tlo-research', 'apps\macOS\tlo-ggi', 'apps\macOS\tlo-gsi', 'apps\macOS\tlo-tag', 'apps\macOS\tlo-deleteDupes', 'apps\macOS\search-artist-db', 'apps\macOS\tlo-ggi.app\Contents\Info.plist', 'apps\macOS\tlo-gsi.app\Contents\Info.plist')
    }
)

foreach ($Platform in $PlatformValidation) {
    Test-TloCompleteZip -ZipPath $Platform.Complete -PlatformKey $Platform.Key -PlatformFolder $Platform.Folder -ScanReceipt $Platform.Scan -RequiredAppFiles $Platform.Files
    Test-TloUpdateZip -ZipPath $Platform.Update -PlatformKey $Platform.Key -PlatformFolder $Platform.Folder -ScanReceipt $Platform.Scan -RequiredAppFiles $Platform.Files
}


function Get-DefenderLogInfo {
    $LogPath = Join-Path $env:LOCALAPPDATA 'Temp\MpCmdRun.log'
    $Text = ''
    if (Test-Path -LiteralPath $LogPath) {
        $Text = (Get-Content -LiteralPath $LogPath -Tail 200 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
    }
    [pscustomobject]@{
        Path = $LogPath
        Text = $Text
    }
}

function Test-DefenderUnavailableLogText {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    return ($Text -match 'WARN:\s*Product/Feature disabled' -or
            $Text -match 'Product/Feature disabled' -or
            $Text -match 'Defender.*disabled' -or
            $Text -match 'Microsoft Defender.*disabled' -or
            $Text -match 'service.*disabled')
}

function Get-DefenderThreatSummaryForTarget {
    param(
        [string]$Target,
        [datetime]$StartedAt
    )
    $Command = Get-Command Get-MpThreatDetection -ErrorAction SilentlyContinue
    if (-not $Command) { return '' }

    $TargetFull = $Target
    try { $TargetFull = [System.IO.Path]::GetFullPath($Target) } catch { }
    $TargetLower = $TargetFull.ToLowerInvariant()
    $Summaries = New-Object System.Collections.Generic.List[string]

    try {
        $Detections = @(Get-MpThreatDetection -ErrorAction Stop)
    } catch {
        return ''
    }

    foreach ($Detection in $Detections) {
        $Initial = $null
        if ($Detection.PSObject.Properties.Name -contains 'InitialDetectionTime') {
            $Initial = $Detection.InitialDetectionTime
        }
        if ($Initial -and ([datetime]$Initial -lt $StartedAt.AddMinutes(-5))) {
            continue
        }

        $ResourceText = ''
        if ($Detection.PSObject.Properties.Name -contains 'Resources') {
            $ResourceText = (($Detection.Resources | ForEach-Object { [string]$_ }) -join [Environment]::NewLine)
        }
        $ResourceLower = $ResourceText.ToLowerInvariant()
        if (-not $ResourceLower.Contains($TargetLower)) {
            continue
        }

        $ThreatName = '<unknown threat>'
        if ($Detection.PSObject.Properties.Name -contains 'ThreatName' -and $Detection.ThreatName) {
            $ThreatName = [string]$Detection.ThreatName
        }
        $Summaries.Add("Threat=$ThreatName Resources=$ResourceText") | Out-Null
    }

    return ($Summaries -join [Environment]::NewLine)
}

function Invoke-TloDefenderScanTarget {
    param(
        [string]$MpCmdRunPath,
        [string]$ScanTarget
    )
    $StartedAt = Get-Date
    & $MpCmdRunPath -Scan -ScanType 3 -File $ScanTarget -DisableRemediation
    $ScanExitCode = $LASTEXITCODE
    if ($ScanExitCode -eq 0) {
        Write-Host "Microsoft Defender scan clean: $ScanTarget"
        return
    }

    $ThreatSummary = Get-DefenderThreatSummaryForTarget -Target $ScanTarget -StartedAt $StartedAt
    $LogInfo = Get-DefenderLogInfo
    $LogText = [string]$LogInfo.Text

    if (-not [string]::IsNullOrWhiteSpace($ThreatSummary)) {
        throw "Microsoft Defender reported a threat while scanning $ScanTarget. Exit code: $ScanExitCode. $ThreatSummary"
    }

    if (Test-DefenderUnavailableLogText -Text $LogText) {
        Write-Warning "Microsoft Defender scanner is unavailable or disabled on this machine. Build verification is otherwise complete; perform a local Norton scan before distributing. Target not Defender-scanned: $ScanTarget. MpCmdRun exit code: $ScanExitCode. Log: $($LogInfo.Path)"
        return
    }

    if ($LogText -match '(?i)threat\s+(found|detected)|found\s+threat|malware|trojan|virus') {
        throw "Microsoft Defender produced a non-clean scan message for $ScanTarget. Exit code: $ScanExitCode. Review $($LogInfo.Path)."
    }

    Write-Warning "Microsoft Defender scan did not complete for $ScanTarget, but no Defender threat record was found. Build verification is otherwise complete; perform a local Norton scan before distributing. MpCmdRun exit code: $ScanExitCode. Log: $($LogInfo.Path)"
}

if (-not $SkipDefenderScan) {
    $DefenderPlatformRoot = Join-Path $env:ProgramData 'Microsoft\Windows Defender\Platform'
    $MpCmdRun = $null
    if (Test-Path -LiteralPath $DefenderPlatformRoot) {
        $MpCmdRun = Get-ChildItem -LiteralPath $DefenderPlatformRoot -Filter MpCmdRun.exe -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1
    }
    if (-not $MpCmdRun) {
        Write-Warning 'Microsoft Defender MpCmdRun.exe was not found. Build verification is otherwise complete; perform a local Norton scan before distributing.'
    } else {
        & $MpCmdRun.FullName -SignatureUpdate
        $SignatureExitCode = $LASTEXITCODE
        if ($SignatureExitCode -ne 0) {
            $LogInfo = Get-DefenderLogInfo
            if (Test-DefenderUnavailableLogText -Text ([string]$LogInfo.Text)) {
                Write-Warning "Microsoft Defender signature update could not run because Defender is unavailable or disabled. Build verification is otherwise complete; perform a local Norton scan before distributing. Exit code: $SignatureExitCode. Log: $($LogInfo.Path)"
            } else {
                Write-Warning "Defender signature update failed with exit code $SignatureExitCode. Continuing with available local Defender signatures, if scanning is available. Log: $($LogInfo.Path)"
            }
        }
        foreach ($ScanTarget in @($ReleaseAssetPaths + @($VerifyRoot))) {
            Invoke-TloDefenderScanTarget -MpCmdRunPath $MpCmdRun.FullName -ScanTarget $ScanTarget
        }
    }
}

if ($PublishRelease) {
    Invoke-TloReleaseRepositoryPublication `
        -Repository $ReleaseRepo `
        -BuildLabel $BuildToken `
        -NumericBuild $BuildNumber `
        -SourceBundleZip $BundleZip `
        -PublicationWorkRoot $WorkRoot

    Invoke-TloGitHubReleaseAssetPublication `
        -Repository $ReleaseRepo `
        -VersionNumber $VersionNumber `
        -BuildLabel $BuildToken `
        -NumericBuild $BuildNumber `
        -AssetPaths $ReleaseAssetPaths
}

Write-Host ''
Write-Host "Git-build process version: $ProcessVersion"
Write-Host 'TLO distribution completed and verified.'
foreach ($AssetPath in $ReleaseAssetPaths) {
    $AssetHash = Get-FileHash -LiteralPath $AssetPath -Algorithm SHA256
    Write-Host "Asset: $AssetPath"
    Write-Host "SHA-256: $($AssetHash.Hash)"
}
Write-Host "GitHub Actions run: $RunId"
Write-Host "Verified extraction: $VerifyRoot"
if ($PublishRelease) {
    Write-Host 'Published release assets: existing 3 complete/3 update ZIPs plus Windows onedir complete/update ZIPs.'
}
}
finally {
    if ((-not $KeepGitHubRun) -and
        (-not $GitHubActionsRunFailed) -and
        (-not $GitHubActionsRunStateUncertain) -and
        (-not $PreserveGitHubRunForRecovery) -and
        (-not [string]::IsNullOrWhiteSpace($Repo)) -and
        (-not [string]::IsNullOrWhiteSpace($GitHubActionsRunIdForCleanup))) {
        Invoke-GitHubActionsRunCleanup -Repository $Repo -RunId $GitHubActionsRunIdForCleanup
    }
    elseif ($GitHubActionsRunFailed -and (-not [string]::IsNullOrWhiteSpace($GitHubActionsRunIdForCleanup))) {
        Write-Host "Failed GitHub Actions run preserved for diagnosis: $GitHubActionsRunIdForCleanup"
    }
    elseif ($GitHubActionsRunStateUncertain -and (-not [string]::IsNullOrWhiteSpace($GitHubActionsRunIdForCleanup))) {
        Write-Host "GitHub Actions run preserved because its final state could not be confirmed: $GitHubActionsRunIdForCleanup"
    }
    elseif ($PreserveGitHubRunForRecovery -and (-not [string]::IsNullOrWhiteSpace($GitHubActionsRunIdForCleanup))) {
        Write-Host "Successful GitHub Actions run preserved because artifact recovery is incomplete: $GitHubActionsRunIdForCleanup"
    }

    if ((-not $PreserveRepositorySnapshot) -and (-not [string]::IsNullOrWhiteSpace($Repo)) -and $RepositoryContainsBuildSnapshot) {
        Invoke-GitHubRepositoryCleanup -Repository $Repo -BuildLabel $BuildToken
    }
    elseif ($PreserveRepositorySnapshot -and $RepositoryContainsBuildSnapshot) {
        Write-Host "GitHub repository snapshot preserved because run state/artifact recovery is incomplete: $Repo"
    }

    if ((-not $KeepSnapshot) -and (-not $PreserveRepositorySnapshot)) {
        try {
            Invoke-LocalBuildRootCleanup -Root $WorkRoot -PreserveFile $ResolvedBundleZipForCleanup
        }
        catch {
            Write-Warning "Local TLO-GitHub-Build cleanup did not complete: $($_.Exception.Message)"
        }
    }
}
