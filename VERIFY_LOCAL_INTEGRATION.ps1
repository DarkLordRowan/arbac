param(
    [int]$Workers = 8,
    [switch]$RunGuiTests
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = "$root;$env:PYTHONPATH"
function Assert-LastExit([string]$label) {
    if ($LASTEXITCODE -ne 0) { throw "$label failed with exit code $LASTEXITCODE" }
}
Write-Host '[1] Plugin import and local paths'
python -c "import arbacc, arbac_research; print(arbacc.__file__); print(arbac_research.__file__)"
Assert-LastExit 'import'
Write-Host '[2] Research tests'
python -m pytest research_tests -q
Assert-LastExit 'research tests'
Write-Host '[3] Core tests (except GUI)'
python -m pytest tests --ignore=tests/gui -q
Assert-LastExit 'core tests'
if ($RunGuiTests) {
  Write-Host '[4] GUI tests'
  python -m pytest tests/gui -q
  Assert-LastExit 'GUI tests'
}
Write-Host '[5] Mathematical trace equality + ZSTD Parquet'
& "$root\CHECK_RESEARCH_V3.ps1" -ArbacRoot $root -Workers $Workers
Assert-LastExit 'profile parity check'
Write-Host '[PASS] All requested local integration checks passed.'
