from httpx import AsyncClient
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter

from limits import RateLimitItemPerSecond

# requests
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0"
DEFAULT_HEADERS = {"User-Agent": USER_AGENT}
REQUEST_CLIENT = AsyncClient()

# rate limits
DEFAULT_LIMITS_STORAGE = MemoryStorage()
DEFAULT_LIMITER = MovingWindowRateLimiter(DEFAULT_LIMITS_STORAGE)
DEFAULT_RATE_LIMIT = RateLimitItemPerSecond(10)
