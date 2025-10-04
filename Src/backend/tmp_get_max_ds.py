from datetime import datetime
from worker.handlers.skill_extractor import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("SELECT max(last_seen_at) FROM developer_skill")).scalar()
print(result.isoformat() if result else "None")
