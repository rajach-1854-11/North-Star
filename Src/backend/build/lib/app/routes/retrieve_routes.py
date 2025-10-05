# AFTER
from fastapi import APIRouter, Depends, HTTPException
from app.domain.schemas import RetrieveReq, RetrieveResp
from app.ports.retriever import rag_search, api_response   # <-- correct module
from app.deps import require_role

router = APIRouter(prefix="/retrieve", tags=["retrieve"])

@router.post("", response_model=RetrieveResp)
def retrieve(req: RetrieveReq, user: dict = Depends(require_role("Admin", "PO", "BA", "Dev"))):
    tenant_id = user.get("tenant_id")
    accessible_projects = user.get("accessible_projects", [])
    targets = req.targets or ["global"]
    for t in targets:
        if t != "global" and t not in accessible_projects:
            raise HTTPException(status_code=403, detail=f"Access denied to project: {t}")

    payload = rag_search(
        tenant_id=tenant_id,
        user_claims=user,
        query=req.query,
        targets=targets,
        k=req.k,
        strategy=req.strategy,
        include_rosetta=req.include_rosetta,
        known_projects=req.known_projects,
    )
    return api_response(payload)
