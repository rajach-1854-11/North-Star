Param()
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$artifactDir = "artifacts/e2e/$ts"
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
python -m app.scripts.run_e2e --artifacts $artifactDir
