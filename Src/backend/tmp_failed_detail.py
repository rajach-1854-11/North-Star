import redis
from rq import Queue
from rq.registry import FailedJobRegistry
from rq.job import Job
from app.config import settings

client = redis.from_url(settings.redis_url)
queue = Queue("events", connection=client)
failed = FailedJobRegistry(queue=queue)
ids = failed.get_job_ids()[-3:]
for job_id in ids:
    job = Job.fetch(job_id, connection=client)
    print("job", job_id)
    print(job.exc_info)
