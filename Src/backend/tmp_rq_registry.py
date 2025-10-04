import redis
from rq import Queue
from rq.registry import FinishedJobRegistry, FailedJobRegistry
from rq.job import Job
from app.config import settings

client = redis.from_url(settings.redis_url)
queue = Queue("events", connection=client)
finished = FinishedJobRegistry(queue=queue)
failed = FailedJobRegistry(queue=queue)
last_finished = finished.get_job_ids()[-5:]
print("finished_ids", last_finished)
for job_id in last_finished:
    job = Job.fetch(job_id, connection=client)
    print(job_id, job.meta.get("idempotency_key"), job.func_name)
print("failed_ids", failed.get_job_ids()[-5:])
