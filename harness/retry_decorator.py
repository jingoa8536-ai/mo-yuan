"""
retry_decorator - 自动重试失败的 HTTP 请求装饰器
支持指数退避、最大重试次数、可配置异常类型等。
"""

import functools
import random
import time
from typing import Optional, Type, Union, Tuple, Callable


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: Optional[float] = None,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    装饰器：自动重试失败的函数调用（适用于 HTTP 请求等场景）。

    参数
    ----------
    max_retries : int
        最大重试次数，默认为 3。
    base_delay : float
        初始退避延迟（秒），默认为 1.0。
    max_delay : Optional[float]
        最大退避延迟（秒）。为 None 时不设上限。
    exponential_base : float
        指数退避的底数，默认为 2.0。
    jitter : bool
        是否引入随机抖动（±50%），默认为 True。
    exceptions : Exception 类型或元组
        只有捕获这些异常时才触发重试，默认为 Exception（即所有异常）。
    on_retry : Optional[Callable[[Exception, int], None]]
        每次重试前的回调函数，参数为 (异常实例, 当前重试次数)。
    """
    if max_retries < 0:
        raise ValueError("max_retries 必须 >= 0")
    if base_delay < 0:
        raise ValueError("base_delay 必须 >= 0")

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        raise  # 已用完重试次数，抛出原异常

                    # 计算退避延迟
                    delay = base_delay * (exponential_base ** attempt)
                    if max_delay is not None:
                        delay = min(delay, max_delay)
                    if jitter:
                        # 在 [0.5 * delay, 1.5 * delay) 之间随机抖动
                        delay = delay * (0.5 + random.random())

                    if on_retry:
                        on_retry(e, attempt + 1)

                    time.sleep(delay)

        return wrapper
    return decorator
