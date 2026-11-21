# TLO Build 713 — opt-in, non-destructive Windows 11 acceptance diagnostics.
# Run on an ordinary user account on both PCs; records PASS/FAIL/SKIP.
# This script does not install software, change media, or modify the UNC share.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$TLOHome,
    [string]$UncFolder = '',
    [string]$MappedFolder = '',
    [string]$InstalledExe = '',
    [string]$CandidateMsi = ''
)
$ErrorActionPreference = 'Stop'
$failures = 0
function Report([string]$label, [string]$result, [string]$reason = '') {
    Write-Output ("{0}: {1} {2}" -f $result, $label, $reason)
    if ($result -eq 'FAIL') { $script:failures++ }
}
if (-not (Test-Path -LiteralPath $TLOHome -PathType Container)) {
    Report 'TLOHome exists' 'FAIL' $TLOHome
} else {
    $home = (Resolve-Path -LiteralPath $TLOHome).Path
    Report 'TLOHome exists' 'PASS' $home
    try {
        $scratch = Join-Path $home ('.tlo-acceptance-' + [guid]::NewGuid().ToString('N'))
        $content = [Text.Encoding]::UTF8.GetBytes('TLO permission acceptance diagnostic')
        [IO.File]::WriteAllBytes($scratch, $content)
        try {
            if (-not (([IO.File]::ReadAllBytes($scratch)).Length -eq $content.Length)) {
                throw 'Roundtrip marker mismatch'
            }
            Report 'Standard-user TLOHome write/read' 'PASS'
        } finally {
            if (Test-Path -LiteralPath $scratch) { Remove-Item -LiteralPath $scratch -Force }
        }
    } catch { Report 'Standard-user TLOHome write/read' 'FAIL' $_.Exception.Message }
}
foreach ($pair in @(@('UNC source', $UncFolder), @('Mapped-drive source', $MappedFolder))) {
    if (-not $pair[1]) { Report $pair[0] 'SKIP' 'No path supplied'; continue }
    try {
        $path = (Resolve-Path -LiteralPath $pair[1] -ErrorAction Stop).Path
        if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw 'Not a folder' }
        $entries = @(Get-ChildItem -LiteralPath $path -Force -ErrorAction Stop | Select-Object -First 2)
        Report $pair[0] 'PASS' ("Read-only listing: {0} (sample count {1})" -f $path, $entries.Count)
    } catch { Report $pair[0] 'FAIL' $_.Exception.Message }
}
if ($InstalledExe -and $CandidateMsi) {
    try {
        $old = Get-AuthenticodeSignature -LiteralPath $InstalledExe
        $new = Get-AuthenticodeSignature -LiteralPath $CandidateMsi
        if ($old.Status -ne 'Valid' -or $new.Status -ne 'Valid') { throw 'Authenticode signature invalid' }
        if ($old.SignerCertificate.Thumbprint -ine $new.SignerCertificate.Thumbprint) {
            Report 'MSI signer continuity' 'FAIL' 'New certificate: manual verified MSI install required'
        } else { Report 'MSI signer continuity' 'PASS' $old.SignerCertificate.Thumbprint }
    } catch { Report 'MSI signer continuity' 'FAIL' $_.Exception.Message }
} else { Report 'MSI signer continuity' 'SKIP' 'Supply both signed EXE and candidate MSI' }
Report 'MSI fresh/upgrade/repair/uninstall' 'SKIP' 'Must be tested manually; this script never installs or uninstalls'
Report 'UNC mutations and staging recovery' 'SKIP' 'Must be tested on disposable fixtures; this script is read-only'
if ($failures) { Write-Error "$failures native acceptance check(s) failed"; exit 1 }
Write-Output 'Read-only native acceptance diagnostics completed; skipped checks are NOT attested.'
exit 0
