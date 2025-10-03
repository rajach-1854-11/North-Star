from app.application.local_kb import store_chunks
from app.deps import SessionLocal
from app.domain import models as m


def main() -> None:
    with SessionLocal() as db:
        project = db.query(m.Project).filter(m.Project.key == "PX").first()
        text = "# Sample\n\nNorth Star platform overview."
        store_chunks(db, tenant_id=project.tenant_id, project=project, text=text, source="manual")


if __name__ == "__main__":
    main()