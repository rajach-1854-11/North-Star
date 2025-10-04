import redis
from app.config import settings

client = redis.from_url(settings.redis_url)
print(sorted(client.keys("rq:*")[:10]))
