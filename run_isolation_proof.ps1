param(
    [switch]$SkipTests,
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RepoRoot "North-Star\Src\backend"
$VenvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
$PythonExe = $VenvPython
if (-not (Test-Path $PythonExe)) {
    Write-Warning "Python executable not found at $VenvPython; falling back to system python."
    $PythonExe = "python"
}

$Args = @('-m', 'app.scripts.isolation_proof')
if ($SkipTests.IsPresent) {
    $Args += '--skip-tests'
}
if ($OutputDir) {
    $Args += @('--output-dir', $OutputDir)
}

Push-Location $BackendDir
try {
    Write-Host "[Isolation Proof] Generating report..."
    & $PythonExe @Args
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "Isolation proof run exited with code $ExitCode"
    }
    Write-Host "[Isolation Proof] Completed successfully."
} finally {
    Pop-Location
}
