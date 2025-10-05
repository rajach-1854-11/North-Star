Param(
    [string]$Artifacts,
    [string]$BaseUrl
)

$ErrorActionPreference = "Stop"

$venvPath = "C:\Users\rchan\OneDrive\Desktop\Git-Rajach-1854-11\venv"
$backendPath = "C:\Users\rchan\OneDrive\Desktop\Git-Rajach-1854-11\North-Star\Src\backend"

. "$venvPath\Scripts\Activate.ps1"

$exitCode = 1
Push-Location $backendPath
try {
    $argsList = @()
    if ($Artifacts) {
        $argsList += "--artifacts"
        $argsList += $Artifacts
    }
    if ($BaseUrl) {
        $argsList += "--base-url"
        $argsList += $BaseUrl
    }
    python -m app.scripts.run_api_smoke @argsList
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $exitCode
