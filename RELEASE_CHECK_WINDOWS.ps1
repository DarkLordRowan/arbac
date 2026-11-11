[CmdletBinding()]
param([int]$Workers=8)
$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    python -m pytest tests/test_levin_sidi_s_oracle.py tests/test_levin_sidi_s_factorial_kernel.py tests/test_levin_sidi_s_mpmath_reference.py tests/test_algorithm_literature.py -q -rs
    if ($LASTEXITCODE -ne 0) { throw 'Sidi-S / literature suite failed' }
    python -m pytest tests research_tests -q -rs --tb=short
    if ($LASTEXITCODE -ne 0) { throw 'Full suite failed' }
    & (Join-Path $PSScriptRoot 'VERIFY_LOCAL_INTEGRATION.ps1') -Workers $Workers
    if ($LASTEXITCODE -ne 0) { throw 'Integration smoke failed' }
    Write-Host 'PASS: ready for an audited Magister commit' -ForegroundColor Green
}
finally { Pop-Location }
