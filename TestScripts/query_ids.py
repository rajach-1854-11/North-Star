import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "North-Star" / "Src" / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.deps import SessionLocal
from app.domain import models as m


def main() -> None:
    db = SessionLocal()
    try:
        projects = [(p.id, p.key, p.name) for p in db.query(m.Project).order_by(m.Project.id).all()]
        developers = [(d.id, d.display_name) for d in db.query(m.Developer).order_by(m.Developer.id).all()]
    finally:
        db.close()

    print("Projects:")
    for proj in projects:
        print(proj)
    print("Developers:")
    for dev in developers:
        print(dev)


if __name__ == "__main__":
    main()
