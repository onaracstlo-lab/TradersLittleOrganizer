<#
Required external Build Process hook, after ArtistDB-Master files copied:
  & "$SourceRoot\tools\Stage-TLO-CityDatabase.ps1" -SourceRoot $SourceRoot
Optional: -DistRoot $DistRoot (to place a physical database in the native dist).
#>
param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [string]$DistRoot = ''
)
$ErrorActionPreference = 'Stop'
$Script = Join-Path $SourceRoot 'tools\stage_city_database.py'
if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) { throw "Missing required city staging script: $Script" }
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python is required to stage the city database' }
$arguments = @($Script,'--source-root',$SourceRoot)
if ($DistRoot) { $arguments += @('--dist-root',$DistRoot) }
& $python.Source @arguments
if ($LASTEXITCODE -ne 0) { throw "City database staging failed: exit $LASTEXITCODE" }
$cityPath = Join-Path $SourceRoot 'TLO_DBs\cities.csv'
if (-not (Test-Path -LiteralPath $cityPath -PathType Leaf)) { throw "Missing staged city DB $cityPath" }
Write-Host "Staged physical city DB: $cityPath"
