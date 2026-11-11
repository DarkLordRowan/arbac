param(
    [Parameter(Mandatory=$true)][string]$Config,
    [Parameter(Mandatory=$true)][string]$Output,
    [int]$Workers = 8,
    [int]$ChunkTasks = 32,
    [string]$Epsilon = "1e-8",
    [string]$GroupBy = "method_id,backend,dps",
    [switch]$RunTests,
    [switch]$ProfileOps,
    [string]$ArbacRoot = ""
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (!(Test-Path $Config)) { throw "Missing JSON config: $Config" }
if ($Workers -lt 1 -or $ChunkTasks -lt 1) { throw "Workers and ChunkTasks must be positive" }

# Support keeping Arbacv2 (research GUI) and arbac-Magister (main algorithms)
# in separate sibling folders. Does not overwrite or modify either repository.
if ($ArbacRoot) {
    if (!(Test-Path (Join-Path $ArbacRoot "arbacc\__init__.py"))) {
        throw "ArbacRoot does not contain arbacc/__init__.py: $ArbacRoot"
    }
    $env:PYTHONPATH = "$(Resolve-Path $ArbacRoot);$($env:PYTHONPATH)"
} else {
    $SiblingRoot = Join-Path (Split-Path $PSScriptRoot -Parent) "arbac-Magister"
    if (Test-Path (Join-Path $SiblingRoot "arbacc\__init__.py")) {
        $env:PYTHONPATH = "$(Resolve-Path $SiblingRoot);$($env:PYTHONPATH)"
    }
}

python -c "import mpmath, pyarrow, matplotlib, arbac_research, arbacc; print('Dependencies OK')"
if ($LASTEXITCODE -ne 0) { throw "Install dependencies: python -m pip install -r requirements-research.txt" }

if ($RunTests) {
    python -m pytest research_tests -q
    if ($LASTEXITCODE -ne 0) { throw "Research unit tests failed" }
}

Write-Host "[RUN] Full JSON plan -> compressed Parquet, resumable"
$RunArgs = @('run', $Config, '--output', $Output, '--workers', "$Workers", '--chunk-tasks', "$ChunkTasks")
if ($ProfileOps) { $RunArgs += '--profile-ops' }
python -u -m arbac_research @RunArgs
if ($LASTEXITCODE -ne 0) { throw "Run failed; restart with SAME config and output to resume" }

Write-Host "[ANALYZE] Offline recomputation of research metrics"
New-Item -ItemType Directory -Path $Output -Force | Out-Null
python -m arbac_research analyze $Output --epsilon $Epsilon --group $GroupBy `
    --task-csv (Join-Path $Output "task_metrics.csv") `
    --group-csv (Join-Path $Output "group_metrics.csv") `
    --summary-parquet (Join-Path $Output "summary.parquet")
if ($LASTEXITCODE -ne 0) { throw "Offline analysis failed; trace remains safe" }

Write-Host "[DONE] $Output"
Write-Host "View: python -m arbac_research gui $Output"
