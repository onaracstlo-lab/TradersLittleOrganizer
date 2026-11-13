# Launched by updated TLO application AFTER verifying the trusted signed update
# manifest and downloading a Windows MSI via temp file + atomic rename.
# Designed to run outside the PyInstaller/TLO process to avoid locked files.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$MsiPath,
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedSha256,
    [Parameter(Mandatory)][ValidateRange(1, 2147483647)][int]$WaitForPid,
    [Parameter(Mandatory)][string]$InstallRoot,
    [string]$RestartExe = '',
    [ValidateRange(10, 900)][int]$ShutdownTimeoutSeconds = 300
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
trap {
    $message = "TLO MSI automatic update failed: $($_.Exception.Message)"
    $failureLog = Join-Path ([IO.Path]::GetTempPath()) 'TLO-MSI-Update-LastError.txt'
    $message | Out-File -LiteralPath $failureLog -Encoding UTF8
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            "$message`n`nDetails: $failureLog", 'Traders Little Organizer Update',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
    } catch { [Console]::Error.WriteLine($message) }
    exit 1
}
$InstallerState = Get-ItemProperty -LiteralPath 'HKCU:\Software\TradersLittleOrganizer\Installer' -ErrorAction Stop
if ($InstallerState.InstallMethod -ne 'msi') { throw 'Not an MSI-owned installation.' }
$registeredRoot = [string]$InstallerState.InstallPath
$root = ([IO.Path]::GetFullPath($InstallRoot)).TrimEnd([char]'\') + '\'
if ($root -ine (([IO.Path]::GetFullPath($registeredRoot)).TrimEnd([char]'\') + '\')) {
    throw 'Installation root no longer matches MSI registry ownership; refusing update.'
}
$msi = (Resolve-Path -LiteralPath $MsiPath).Path
if ([IO.Path]::GetExtension($msi) -ne '.msi') { throw 'A .msi package is required.' }

# Authentication is TWO gates: pinned-signature verified release manifest's hash
# at the app level, plus Authenticode signature on this MSI and local rehash.
$actual = (Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash
if ($actual -ine $ExpectedSha256) { throw 'Downloaded MSI hash mismatch; refusing to execute.' }
$signature = Get-AuthenticodeSignature -LiteralPath $msi
if ($signature.Status -ne 'Valid') { throw "MSI Authenticode signature not valid: $($signature.Status)" }

$deadline = (Get-Date).AddSeconds($ShutdownTimeoutSeconds)
while (Get-Process -Id $WaitForPid -ErrorAction SilentlyContinue) {
    if ((Get-Date) -gt $deadline) { throw 'TLO did not exit; leaving installed version unchanged.' }
    Start-Sleep -Milliseconds 500
}
# A different TLO GUI, CLI, or helper process may still have files locked.
# Enumerate actual executable paths to avoid matching unrelated portable TLOs.
while ($true) {
    $otherTlo = @(Get-CimInstance -ClassName Win32_Process | Where-Object {
        $_.ExecutablePath -and $_.ExecutablePath.StartsWith(
            $root, [StringComparison]::OrdinalIgnoreCase)
    })
    if ($otherTlo.Count -eq 0) { break }
    if ((Get-Date) -gt $deadline) {
        throw 'Another MSI-installed TLO process is still running; upgrade canceled safely.'
    }
    Start-Sleep -Seconds 2
}
# Revalidate the file immediately before running Windows Installer.
if ((Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash -ine $ExpectedSha256) {
    throw 'MSI changed while waiting for application exit.'
}
$log = Join-Path ([IO.Path]::GetTempPath()) ('TLO-MSI-Update-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
$quoted = '"' + $msi + '"'
$args = @('/i', $quoted, '/qn', '/norestart', '/L*v', ('"' + $log + '"'))
$result = Start-Process -FilePath 'msiexec.exe' -ArgumentList $args -Wait -PassThru
if ($result.ExitCode -notin @(0,3010)) {
    throw "MSI upgrade failed (Windows Installer code $($result.ExitCode)); see $log. Existing MSI retained at $msi."
}
if ($RestartExe -and $result.ExitCode -eq 0) {
    if ($RestartExe.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $RestartExe -PathType Leaf)) {
        Start-Process -FilePath $RestartExe
    }
}
# Deliberately do not delete the MSI immediately after handoff; it is useful
# for diagnostics, recovery, and MSI source repair if the cache is unavailable.
