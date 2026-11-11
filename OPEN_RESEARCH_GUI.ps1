param([string]$Dataset = "")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if ($Dataset) {
    python -m arbac_research gui $Dataset
} else {
    python -m arbac_research gui
}
