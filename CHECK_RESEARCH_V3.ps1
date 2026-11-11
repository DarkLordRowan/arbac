param(
    [string]$ArbacRoot = "C:\Users\DLR_ACER\Desktop\arbac-Magister",
    [int]$Workers = 8
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (!(Test-Path (Join-Path $ArbacRoot 'arbacc\__init__.py'))) {
    throw "ArbacRoot не содержит arbacc: $ArbacRoot"
}
$env:PYTHONPATH = "$(Resolve-Path $ArbacRoot);$($env:PYTHONPATH)"
function Check-Exit([string]$Stage) {
    if ($LASTEXITCODE -ne 0) { throw "FAIL at $Stage (exit $LASTEXITCODE)" }
}
Write-Host '[1] Unit tests'
python -m pytest research_tests -q
Check-Exit 'pytest'
Write-Host '[2] Read-only plugin inventory'
python -m arbac_research audit --base $ArbacRoot --json .\out\arbacc_base_audit_v3.json
Check-Exit 'audit'
Write-Host '[3] Unprofiled smoke / fresh directory'
python -m arbac_research run .\examples\research_smoke.json --output .\out\research_smoke_v3_plain --workers $Workers
Check-Exit 'plain run'
Write-Host '[4] Profiled smoke / fresh directory'
python -m arbac_research run .\examples\research_smoke.json --output .\out\research_smoke_v3_profiled --workers $Workers --profile-ops
Check-Exit 'profile run'
Write-Host '[5] Compare NUMERIC TRACES exactly'
python -m arbac_research verify-profile .\out\research_smoke_v3_plain .\out\research_smoke_v3_profiled
Check-Exit 'verify-profile'
Write-Host '[6] Offline analysis and output'
python -m arbac_research analyze .\out\research_smoke_v3_profiled --detailed `
   --task-csv .\out\research_smoke_v3_profiled\task_metrics.csv `
   --group-csv .\out\research_smoke_v3_profiled\group_metrics.csv
Check-Exit 'analyze'
python -m arbac_research inspect .\out\research_smoke_v3_profiled
Check-Exit 'inspect'
Write-Host 'PASS: v3 profile does not change numerical trace. GUI: python -m arbac_research gui .\out\research_smoke_v3_profiled'
