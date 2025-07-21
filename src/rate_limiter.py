
import time
import redis
import logging
from functools import wraps

log = logging.getLogger(__name__)


class RateLimiter:

    def __init__(self,
                 key_prefix: str,
                 max_requests: int,
                 interval_seconds: int,
                 user_id: str = "global",
                 redis_host: str = "redis_job",
                 redis_port: int = 6379,
                 redis_db: int = 0):
        """
        :param key_prefix: namespace prefix for Redis key
        :param max_requests: allowed number of requests per interval
        :param interval_seconds: time window for rate limiting
        :param user_id: optional identifier for user-specific rate limits
        """

        self.key = f"{key_prefix}:{user_id}"
        self.max_requests = max_requests
        self.interval = interval_seconds

        self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)


    def acquire(self):

        now = int(time.time())

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(self.key, 0, now - self.interval)
        pipe.zcard(self.key)
        pipe.zadd(self.key, {str(now): now})
        pipe.expire(self.key, self.interval)
        _, count, _, _ = pipe.execute()

        if count >= self.max_requests:

            oldest = self.redis.zrange(self.key, 0, 0, withscores=True)

            if oldest:
                wait_time = int(oldest[0][1]) + self.interval - now
                log.warning(f"[RateLimiter] Rate limit exceeded. Sleeping for {wait_time} seconds...")
                time.sleep(wait_time)
                return self.acquire()  # retry after sleep


def rate_limited(method):

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        self.rate_limiter.acquire()
        return method(self, *args, **kwargs)

    return wrapper
