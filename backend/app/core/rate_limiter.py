import asyncio
import time
from typing import Any, Callable, Coroutine, Tuple
from dataclasses import dataclass, field

@dataclass(order=True)
class PrioritizedRequest:
    priority: int
    created_at: float = field(compare=False)
    func: Callable[..., Coroutine[Any, Any, Any]] = field(compare=False)
    args: tuple = field(compare=False)
    kwargs: dict = field(compare=False)
    future: asyncio.Future = field(compare=False)

class TokenBucketRateLimiter:
    """
    Token Bucket 알고리즘을 사용한 비동기 Rate Limiter.
    """
    def __init__(self, requests_per_second: float):
        self.capacity = requests_per_second
        self.tokens = requests_per_second
        self.last_refill = time.monotonic()
        self.refill_rate = requests_per_second
        self._lock = asyncio.Lock()

    async def acquire(self):
        while True:
            async with self._lock:
                now = time.monotonic()
                time_passed = now - self.last_refill
                
                # 토큰 리필
                self.tokens = min(self.capacity, self.tokens + time_passed * self.refill_rate)
                self.last_refill = now

                if self.tokens >= 1:
                    self.tokens -= 1
                    return
            
            # 토큰이 부족하면 잠시 대기
            await asyncio.sleep(0.1)

class KiwoomAPIGateway:
    """
    모든 키움 API 호출을 중앙 제어하는 Priority Queue 기반 게이트웨이.
    """
    def __init__(self, requests_per_second: float = 4.0):
        self.queue: asyncio.PriorityQueue[PrioritizedRequest] = asyncio.PriorityQueue()
        self.rate_limiter = TokenBucketRateLimiter(requests_per_second)
        self._worker_task: asyncio.Task | None = None
        self._start_lock: asyncio.Lock | None = None

    async def start(self):
        """백그라운드 워커 시작 (동시 호출 시 worker가 한 번만 생성되도록 Lock 보호)"""
        if self._start_lock is None:
            self._start_lock = asyncio.Lock()
        async with self._start_lock:
            if self._worker_task is None or self._worker_task.done():
                self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        """백그라운드 워커 종료"""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def execute(self, priority: int, func: Callable, *args, **kwargs) -> Any:
        """
        요청을 큐에 넣고 결과가 나올 때까지 대기.
        priority: 0(최상, 주문취소), 1(주문), 2(시세), 3(대량조회), 4(과거수집)
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        request = PrioritizedRequest(
            priority=priority,
            created_at=time.monotonic(),
            func=func,
            args=args,
            kwargs=kwargs,
            future=future
        )
        
        await self.queue.put(request)
        return await future

    async def _worker_loop(self):
        """큐에서 요청을 꺼내 Rate Limit을 지키며 실행하는 루프"""
        while True:
            request = await self.queue.get()
            
            try:
                # Rate Limit 통과 대기
                await self.rate_limiter.acquire()
                
                # API 실행
                result = await request.func(*request.args, **request.kwargs)
                if not request.future.done():
                    request.future.set_result(result)
            except Exception as e:
                if not request.future.done():
                    request.future.set_exception(e)
            finally:
                self.queue.task_done()

# 전역 싱글톤 게이트웨이 인스턴스
kiwoom_gateway = KiwoomAPIGateway(requests_per_second=4.0)
