$ErrorActionPreference = "Stop"

$BASE = "http://localhost:9000"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $RepoRoot "venv\Scripts\python.exe"
$BackendDir = Join-Path $RepoRoot "North-Star\Src\backend"
$SeedDir = Join-Path $BackendDir "data\seed"

if (Test-Path $PythonExe) {
    Write-Host "[0] Running data seeder dry-run..."
    Push-Location $BackendDir
    try {
        & $PythonExe -m app.scripts.data_seeder --dir $SeedDir --tenant tenant1 --dry-run --stats
        Write-Host "[0b] Applying data seeder..."
        & $PythonExe -m app.scripts.data_seeder --dir $SeedDir --tenant tenant1
    } catch {
        Write-Warning "Data seeder execution failed: $($_.Exception.Message)"
        throw
    } finally {
        Pop-Location
    }
} else {
    Write-Warning "Python executable not found at $PythonExe; skipping CSV seeder."
}

function Show-ErrorResponse {
    param([System.Exception]$Exception)

    $webEx = $Exception -as [System.Net.WebException]
    if ($null -eq $webEx) { return }

    $httpResponse = $webEx.Response -as [System.Net.HttpWebResponse]
    if ($null -eq $httpResponse) { return }

    try {
        $stream = $httpResponse.GetResponseStream()
        if ($null -ne $stream) {
            $reader = New-Object System.IO.StreamReader($stream)
            $body = $reader.ReadToEnd()
            if (![string]::IsNullOrWhiteSpace($body)) {
                Write-Warning "Response body: $body"
            }
        }
    } catch {
        Write-Warning "Unable to read response body: $($_.Exception.Message)"
    }
}

function Get-StatusCode {
    param([System.Exception]$Exception)

    $webEx = $Exception -as [System.Net.WebException]
    if ($null -eq $webEx) { return $null }

    $httpResponse = $webEx.Response -as [System.Net.HttpWebResponse]
    if ($null -eq $httpResponse) { return $null }

    return [int]$httpResponse.StatusCode
}

function Decode-JwtPayload {
    param([string]$Token)

    if ([string]::IsNullOrWhiteSpace($Token)) { return $null }
    $parts = $Token.Split('.')
    if ($parts.Length -lt 2) { return $null }

    $payload = $parts[1].Replace('-', '+').Replace('_', '/')
    switch ($payload.Length % 4) {
        2 { $payload += '==' }
        3 { $payload += '=' }
        1 { $payload += '===' }
    }

    try {
        $bytes = [System.Convert]::FromBase64String($payload)
        $json = [System.Text.Encoding]::UTF8.GetString($bytes)
        return $json | ConvertFrom-Json
    } catch {
        Write-Warning "Failed to decode JWT payload: $($_.Exception.Message)"
        return $null
    }
}

$uvicornProc = $null
try {
    Write-Host "[0c] Starting API server on port 9000..."
    $uvicornArgs = @('-m','uvicorn','app.main:app','--host','0.0.0.0','--port','9000')
    if (-not (Test-Path $PythonExe)) {
        throw "Python executable not found at $PythonExe"
    }
    $uvicornProc = Start-Process -FilePath $PythonExe -WorkingDirectory $BackendDir -ArgumentList $uvicornArgs -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 8
    try {
        Invoke-RestMethod -Method GET -Uri "$BASE/openapi.json" -TimeoutSec 5 | Out-Null
    } catch {
        Write-Warning "Initial API warmup probe failed: $($_.Exception.Message)"
    }

Write-Host "[1] Acquiring admin token..."
$adminTokenResp = Invoke-RestMethod -Method POST -Uri "$BASE/auth/token?username=admin_root`&password=x"
$ADMIN_TOKEN = $adminTokenResp.access_token
$AdminClaims = Decode-JwtPayload $ADMIN_TOKEN
Write-Host "Admin claims:" ($AdminClaims | ConvertTo-Json -Depth 6)
$AdminHeaders = @{ Authorization = "Bearer $ADMIN_TOKEN" }

Write-Host "[2] Listing users as Admin..."
$usersResp = Invoke-RestMethod -Method GET -Uri "$BASE/admin/users" -Headers $AdminHeaders
Write-Host ($usersResp | ConvertTo-Json -Depth 6)
$devUser = $usersResp.users | Where-Object { $_.username -eq "dev_alex" }
if ($null -eq $devUser) {
    Write-Warning "dev_alex user not found; assignment tests may fail."
} else {
    $DEV_USER_ID = $devUser.id
}
$baNancyUser = $usersResp.users | Where-Object { $_.username -eq "ba_nancy" }
if ($null -eq $baNancyUser) {
    Write-Warning "ba_nancy user missing after seeder run."
}

Write-Host "[3] Promoting dev_alex to PO..."
if ($null -ne $DEV_USER_ID) {
    $rolePatchBody = @{ role = "PO" } | ConvertTo-Json
    try {
        $patched = Invoke-RestMethod -Method PATCH -Uri "$BASE/admin/users/$DEV_USER_ID/role" -Headers ($AdminHeaders + @{ "Content-Type" = "application/json" }) -Body $rolePatchBody
        Write-Host "Updated user:" ($patched | ConvertTo-Json -Depth 4)
    } catch {
        Write-Warning "Role patch failed: $($_.Exception.Message)"
        Show-ErrorResponse $_.Exception
    }
}

Write-Host "[4] Acquiring BA (ba_nancy), PO, and dev_alex tokens..."
$baTokenResp = Invoke-RestMethod -Method POST -Uri "$BASE/auth/token?username=ba_nancy`&password=x"
$BA_TOKEN = $baTokenResp.access_token
$BAClaims = Decode-JwtPayload $BA_TOKEN
Write-Host "ba_nancy claims:" ($BAClaims | ConvertTo-Json -Depth 6)
$BAHeaders = @{ Authorization = "Bearer $BA_TOKEN" }

$poTokenResp = Invoke-RestMethod -Method POST -Uri "$BASE/auth/token?username=po_admin`&password=x"
$PO_TOKEN = $poTokenResp.access_token
$POClaims = Decode-JwtPayload $PO_TOKEN
Write-Host "po_admin claims:" ($POClaims | ConvertTo-Json -Depth 6)
$POHeaders = @{ Authorization = "Bearer $PO_TOKEN" }

$devTokenResp = Invoke-RestMethod -Method POST -Uri "$BASE/auth/token?username=dev_alex`&password=x"
$DEV_TOKEN = $devTokenResp.access_token
$DevClaims = Decode-JwtPayload $DEV_TOKEN
Write-Host "dev_alex claims:" ($DevClaims | ConvertTo-Json -Depth 6)
$DevHeaders = @{ Authorization = "Bearer $DEV_TOKEN" }
$DeveloperId = $DevClaims.developer_id
if (-not $DeveloperId) { $DeveloperId = 1 }

Write-Host "[5] Listing projects via read API..."
$projectsResp = Invoke-RestMethod -Method GET -Uri "$BASE/projects" -Headers $DevHeaders
Write-Host ($projectsResp | ConvertTo-Json -Depth 6)
$projectPX = $projectsResp | Where-Object { $_.key -eq "PX" }
$projectPB = $projectsResp | Where-Object { $_.key -eq "PB" }
if ($null -eq $projectPX -or $null -eq $projectPB) {
    Write-Warning "Expected PX and PB projects to exist."
}

Write-Host "[6] Creating assignment for dev_alex on PB (as PO)..."
if ($null -ne $projectPB) {
    $assignmentBody = @{ developer_id = $DeveloperId; project_id = $projectPB.id; role = "Engineer" } | ConvertTo-Json
    try {
        $assignmentResp = Invoke-RestMethod -Method POST -Uri "$BASE/assignments" -Headers ($DevHeaders + @{ "Content-Type" = "application/json" }) -Body $assignmentBody
        Write-Host "Assignment response:" ($assignmentResp | ConvertTo-Json -Depth 4)
    } catch {
        $statusCode = Get-StatusCode $_.Exception
        if ($statusCode -eq 409) {
            Write-Host "Assignment already exists; continuing." }
        else {
            Write-Warning "Assignment create failed: $($_.Exception.Message)"
            Show-ErrorResponse $_.Exception
        }
    }
}

Write-Host "[7] Assignment visibility checks (PO vs BA)..."
if ($null -ne $projectPB) {
    try {
        $assignmentsPO = Invoke-RestMethod -Method GET -Uri "$BASE/projects/$($projectPB.id)/assignments" -Headers $DevHeaders
        Write-Host "Assignments for PB (PO):" ($assignmentsPO | ConvertTo-Json -Depth 4)
    } catch {
        Write-Warning "PO assignment list failed: $($_.Exception.Message)"
        Show-ErrorResponse $_.Exception
    }

    try {
        $assignmentsBA = Invoke-RestMethod -Method GET -Uri "$BASE/projects/$($projectPB.id)/assignments" -Headers $BAHeaders
        Write-Host "Assignments for PB (BA):" ($assignmentsBA | ConvertTo-Json -Depth 4)
    } catch {
        Write-Warning "BA assignment list failed: $($_.Exception.Message)"
        Show-ErrorResponse $_.Exception
    }

    $assignmentBodyForBA = @{ developer_id = $DeveloperId; project_id = $projectPB.id; role = "Engineer" } | ConvertTo-Json
    try {
        Invoke-RestMethod -Method POST -Uri "$BASE/assignments" -Headers ($BAHeaders + @{ "Content-Type" = "application/json" }) -Body $assignmentBodyForBA
        Write-Warning "BA assignment creation unexpectedly succeeded."
    } catch {
        $statusCode = Get-StatusCode $_.Exception
        if ($statusCode -eq 403) {
            Write-Host "Received expected 403 for BA assignment creation."
        } else {
            Write-Warning "Unexpected status code for BA assignment creation: $statusCode"
        }
        Show-ErrorResponse $_.Exception
    }
}

Write-Host "[8] BA retrieval should succeed (read-only)."
$baRetrieveBody = @{ query = "auth differences"; targets = @("PX", "PB"); k = 6 } | ConvertTo-Json
try {
    $baRetrieve = Invoke-RestMethod -Method POST -Uri "$BASE/retrieve" -Headers ($BAHeaders + @{ "Content-Type" = "application/json" }) -Body $baRetrieveBody
    Write-Host "BA retrieve response:" ($baRetrieve | ConvertTo-Json -Depth 6)
} catch {
    Write-Warning "BA retrieval failed: $($_.Exception.Message)"
    Show-ErrorResponse $_.Exception
}

Write-Host "[9] BA project creation should be forbidden (expect 403)."
try {
    Invoke-RestMethod -Method POST -Uri "$BASE/projects?key=PX2`&name=Demo`&description=Test" -Headers $BAHeaders
    Write-Warning "BA project creation unexpectedly succeeded."
} catch {
    $statusCode = Get-StatusCode $_.Exception
    if ($statusCode -eq 403) {
        Write-Host "Received expected 403 for BA project creation."
    } else {
        Write-Warning "Unexpected status code for BA project creation: $statusCode"
    }
    Show-ErrorResponse $_.Exception
}

Write-Host "[10] BA agent query with draft tool should succeed."
$baAgentDraftBody = @{ prompt = "Find gaps PX vs PB"; allowed_tools = @("rag_search"); targets = @("PX"); k = 6; strategy = "qdrant" } | ConvertTo-Json
try {
    $baAgentDraft = Invoke-RestMethod -Method POST -Uri "$BASE/agent/query" -Headers ($BAHeaders + @{ "Content-Type" = "application/json" }) -Body $baAgentDraftBody
    Write-Host "BA agent draft response:" ($baAgentDraft | ConvertTo-Json -Depth 6)
} catch {
    Write-Warning "BA draft agent query failed: $($_.Exception.Message)"
    Show-ErrorResponse $_.Exception
}

Write-Host "[11] BA agent publish should succeed when Atlassian is configured."
$baAgentPublishBody = @{ prompt = "Create onboarding epic"; allowed_tools = @("jira_epic", "confluence_page"); targets = @("PX") } | ConvertTo-Json
try {
    $baPublishResp = Invoke-RestMethod -Method POST -Uri "$BASE/agent/query" -Headers ($BAHeaders + @{ "Content-Type" = "application/json" }) -Body $baAgentPublishBody
    Write-Host "BA publish agent query response:" ($baPublishResp | ConvertTo-Json -Depth 6)
} catch {
    $statusCode = Get-StatusCode $_.Exception
    if ($statusCode -eq 502) {
        Write-Warning "BA publish returned 502 (verify Atlassian credentials)."
        Show-ErrorResponse $_.Exception
    } else {
        Write-Warning "Unexpected status code for BA publish attempt: $statusCode"
        Show-ErrorResponse $_.Exception
        throw
    }
}

Write-Host "[12] Creating or reusing project PX as PO..."
try {
    $projectResp = Invoke-RestMethod -Method POST -Uri "$BASE/projects?key=PX`&name=Realtime%20Pricing`&description=Pricing%20Platform" -Headers $POHeaders
    Write-Host "Project response:" ($projectResp | ConvertTo-Json -Depth 4)
} catch {
    Write-Warning "Project creation failed: $($_.Exception.Message)"
    Show-ErrorResponse $_.Exception
}

Write-Host "[13] Uploading PX.md as PO..."
$uploadArgs = @(
    "-s",
    "-X", "POST",
    "-H", "Authorization: Bearer $PO_TOKEN",
    "-F", "project_key=PX",
    "-F", "file=@PX.md;type=text/markdown",
    "$BASE/upload"
)
try {
    $uploadOutput = & curl.exe @uploadArgs
    Write-Host "Upload response: $uploadOutput"
} catch {
    Write-Warning "Upload failed: $($_.Exception.Message)"
}

Write-Host "[14] Retrieval as PO..."
$poRetrieveBody = @{ query = "pricing api kafka"; targets = @("PX"); k = 6 } | ConvertTo-Json
try {
    $poRetrieve = Invoke-RestMethod -Method POST -Uri "$BASE/retrieve" -Headers ($POHeaders + @{ "Content-Type" = "application/json" }) -Body $poRetrieveBody
    Write-Host "PO retrieve response:" ($poRetrieve | ConvertTo-Json -Depth 6)
} catch {
    Write-Warning "PO retrieval failed: $($_.Exception.Message)"
    Show-ErrorResponse $_.Exception
}

Write-Host "[15] Staffing recommendations as PO..."
$staffProjectId = if ($projectPX) { $projectPX.id } else { 2 }
try {
    $staffResp = Invoke-RestMethod -Method GET -Uri "$BASE/staff/recommend?project_id=$staffProjectId" -Headers $POHeaders
    Write-Host "Staffing response:" ($staffResp | ConvertTo-Json -Depth 6)
} catch {
    Write-Warning "Staffing failed: $($_.Exception.Message)"
    Show-ErrorResponse $_.Exception
}

Write-Host "[16] Generating onboarding plan as PO..."
$onboardingDeveloperId = $DeveloperId
$onbProjectId = $staffProjectId
$onbBody = @{ developer_id = $onboardingDeveloperId; project_id = $onbProjectId; autonomy = "Ask" } | ConvertTo-Json
try {
    $onbResp = Invoke-RestMethod -Method POST -Uri "$BASE/onboarding/generate" -Headers ($POHeaders + @{ "Content-Type" = "application/json" }) -Body $onbBody
    Write-Host "Onboarding response:" ($onbResp | ConvertTo-Json -Depth 6)
} catch {
    Write-Warning "Onboarding failed: $($_.Exception.Message)"
    Show-ErrorResponse $_.Exception
}

Write-Host "[17] Skill profile as PO..."
try {
    $skillsResp = Invoke-RestMethod -Method GET -Uri "$BASE/skills/profile?developer_id=$onboardingDeveloperId" -Headers $POHeaders
    Write-Host "Skills response:" ($skillsResp | ConvertTo-Json -Depth 6)
} catch {
    Write-Warning "Skills profile failed: $($_.Exception.Message)"
    Show-ErrorResponse $_.Exception
}

Write-Host "[18] Agent query as PO (publish-capable)."
$poAgentBody = @{ prompt = "Summarize PX architecture and prepare draft artifacts"; allowed_tools = @("rag_search", "jira_epic", "confluence_page") } | ConvertTo-Json
try {
    $poAgentResp = Invoke-RestMethod -Method POST -Uri "$BASE/agent/query" -Headers ($POHeaders + @{ "Content-Type" = "application/json" }) -Body $poAgentBody
    Write-Host "PO agent response:" ($poAgentResp | ConvertTo-Json -Depth 6)
} catch {
    Write-Warning "PO agent query failed: $($_.Exception.Message)"
    Show-ErrorResponse $_.Exception
}

Write-Host "[18a] Verifying planner sanitization via direct invocation..."
Push-Location $BackendDir
try {
    $sanitizationScript = @'
from __future__ import annotations

from typing import Any, Dict

from app.config import settings
from app.ports import planner


captured: Dict[str, Dict[str, Any]] = {}


def fake_epic(*, user_claims: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    captured["jira_epic"] = kwargs
    return {"args": kwargs}


def fake_page(*, user_claims: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    captured["confluence_page"] = kwargs
    return {"args": kwargs}


def _ensure_space() -> None:
    if not getattr(settings, "atlassian_space", None):
        settings.atlassian_space = "ENG"


def _run() -> None:
    _ensure_space()
    original_epic = planner._TOOL_REGISTRY.get("jira_epic")
    original_page = planner._TOOL_REGISTRY.get("confluence_page")

    try:
        planner.register_tool("jira_epic", fake_epic)
        planner.register_tool("confluence_page", fake_page)

        plan = {
            "steps": [
                {
                    "tool": "jira_epic",
                    "args": {
                        "project_key": "${project}",
                        "summary": "TODO summary",
                        "description": "fill me later",
                    },
                },
                {
                    "tool": "confluence_page",
                    "args": {
                        "space": "<space>",
                        "title": "<page>",
                        "html": "[html]",
                        "evidence": "TODO evidence",
                    },
                },
            ],
            "output": {"summary": "PX onboarding readiness"},
            "_meta": {"task_prompt": "Prepare PX onboarding content"},
        }

        user_claims = {
            "role": "PO",
            "tenant_id": "tenant1",
            "accessible_projects": ["global", "PX"],
        }

        result = planner.execute_plan(plan, user_claims=user_claims)

        jira_args = captured["jira_epic"]
        assert jira_args["project_key"] == "PX"
        assert "todo" not in jira_args["summary"].lower()
        assert "fill me" not in jira_args["description"].lower()

        conf_args = captured["confluence_page"]
        assert conf_args["space"] == getattr(settings, "atlassian_space")
        assert "<" not in conf_args["title"]
        assert conf_args.get("html") in (None, "")
        assert "todo" not in conf_args["evidence"].lower()

        artifacts = result["artifacts"]
        assert "skipped" not in artifacts["step_1:jira_epic"]
        assert "skipped" not in artifacts["step_2:confluence_page"]

    finally:
        if original_epic is not None:
            planner.register_tool("jira_epic", original_epic)
        else:
            planner._TOOL_REGISTRY.pop("jira_epic", None)

        if original_page is not None:
            planner.register_tool("confluence_page", original_page)
        else:
            planner._TOOL_REGISTRY.pop("confluence_page", None)


if __name__ == "__main__":
    _run()
    print("planner_sanitization=ok")
'@

    $sanitizationOutput = $sanitizationScript | & $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Planner sanitization script exited with code $LASTEXITCODE"
    }
    if ($sanitizationOutput) {
        Write-Host ($sanitizationOutput -join [Environment]::NewLine)
    }
    Write-Host "Planner sanitization check passed."
} catch {
    Write-Warning "Planner sanitization validation failed: $($_.Exception.Message)"
    Throw
} finally {
    Pop-Location
}

Write-Host "[19] Recent audit log as PO..."
try {
    $auditResp = Invoke-RestMethod -Method GET -Uri "$BASE/audit?limit=20" -Headers $POHeaders
    Write-Host "Audit response:" ($auditResp | ConvertTo-Json -Depth 6)
} catch {
    Write-Warning "Audit fetch failed: $($_.Exception.Message)"
    Show-ErrorResponse $_.Exception
}

} finally {
    if ($null -ne $uvicornProc -and -not $uvicornProc.HasExited) {
        Write-Host "Stopping uvicorn process (PID=$($uvicornProc.Id))..."
        Stop-Process -Id $uvicornProc.Id -Force
    }
}
