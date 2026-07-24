"""retry_decorator 单元测试"""

import time
from unittest.mock import Mock, patch
import pytest
from retry_decorator import retry


# ─── 基础功能测试 ───────────────────────────────────────────────────

def test_success_first_try():
    """第一次调用就成功，不触发重试"""
    mock_func = Mock(return_value="ok")
    decorated = retry(max_retries=3)(mock_func)
    assert decorated() == "ok"
    assert mock_func.call_count == 1


def test_success_after_retries():
    """失败几次后成功"""
    mock_func = Mock(side_effect=[Exception("fail1"), Exception("fail2"), "ok"])
    decorated = retry(max_retries=3, base_delay=0.01)(mock_func)
    assert decorated() == "ok"
    assert mock_func.call_count == 3


def test_all_retries_exhausted():
    """用完所有重试次数后抛出异常"""
    mock_func = Mock(side_effect=ValueError("always fail"))
    decorated = retry(max_retries=3, base_delay=0.01)(mock_func)

    with pytest.raises(ValueError, match="always fail"):
        decorated()
    assert mock_func.call_count == 4  # 初始 1 次 + 3 次重试


# ─── 异常类型过滤 ───────────────────────────────────────────────────

def test_exception_filter_pass():
    """只对指定异常重试"""
    mock_func = Mock(side_effect=[ConnectionError("conn fail"), "ok"])
    decorated = retry(max_retries=2, base_delay=0.01, exceptions=ConnectionError)(mock_func)
    assert decorated() == "ok"


def test_exception_filter_skip():
    """不在白名单中的异常不重试，直接抛出"""
    mock_func = Mock(side_effect=TypeError("type mismatch"))
    decorated = retry(max_retries=3, base_delay=0.01, exceptions=ValueError)(mock_func)

    with pytest.raises(TypeError):
        decorated()
    assert mock_func.call_count == 1  # 只调用一次，不重试


# ─── 指数退避验证 ───────────────────────────────────────────────────

def test_exponential_backoff():
    """验证延迟时间呈指数增长"""
    delays = []
    original_sleep = time.sleep

    def tracking_sleep(seconds):
        delays.append(seconds)
        # 不真的等待
        pass

    mock_func = Mock(side_effect=Exception("fail"))
    decorated = retry(max_retries=3, base_delay=1.0, jitter=False)(mock_func)

    with patch("time.sleep", tracking_sleep):
        with pytest.raises(Exception):
            decorated()

    # 无抖动时延迟应为: 1, 2, 4
    assert len(delays) == 3
    assert delays[0] == 1.0
    assert delays[1] == 2.0
    assert delays[2] == 4.0


def test_max_delay_cap():
    """验证 max_delay 上限生效"""
    delays = []
    original_sleep = time.sleep

    def tracking_sleep(seconds):
        delays.append(seconds)

    mock_func = Mock(side_effect=Exception("fail"))
    decorated = retry(max_retries=5, base_delay=1.0, max_delay=3.0, jitter=False)(mock_func)

    with patch("time.sleep", tracking_sleep):
        with pytest.raises(Exception):
            decorated()

    # 最大延迟被限制在 3.0: 1, 2, 3, 3, 3
    assert all(d <= 3.0 for d in delays)
    assert delays[0] == 1.0
    assert delays[1] == 2.0


def test_jitter_effect():
    """验证抖动生效（延迟值不严格等于指数值）"""
    delays = []
    original_sleep = time.sleep

    def tracking_sleep(seconds):
        delays.append(seconds)

    mock_func = Mock(side_effect=Exception("fail"))
    decorated = retry(max_retries=5, base_delay=1.0, jitter=True)(mock_func)

    with patch("time.sleep", tracking_sleep):
        with pytest.raises(Exception):
            decorated()

    # 有抖动，所有延迟应在 [0.5*base*exp, 1.5*base*exp) 范围内
    for i, d in enumerate(delays):
        expected = 1.0 * (2.0 ** i)
        assert 0.5 * expected <= d < 1.5 * expected, f"第 {i} 次延迟 {d} 超出范围"


# ─── 回调函数 ───────────────────────────────────────────────────────

def test_on_retry_callback():
    """验证 on_retry 回调被正确调用"""
    callback = Mock()
    mock_func = Mock(side_effect=[Exception("e1"), Exception("e2"), "ok"])
    decorated = retry(max_retries=2, base_delay=0.01, on_retry=callback)(mock_func)

    decorated()
    assert callback.call_count == 2
    # 回调参数: (异常实例, 重试次数)
    assert isinstance(callback.call_args_list[0][0][0], Exception)
    assert callback.call_args_list[0][0][1] == 1
    assert callback.call_args_list[1][0][1] == 2


# ─── 边界情况 ───────────────────────────────────────────────────────

def test_zero_max_retries():
    """max_retries=0 时不重试，但函数正常执行"""
    mock_func = Mock(return_value="ok")
    decorated = retry(max_retries=0)(mock_func)
    assert decorated() == "ok"
    assert mock_func.call_count == 1


def test_zero_max_retries_fail():
    """max_retries=0 且函数失败时直接抛出"""
    mock_func = Mock(side_effect=RuntimeError("fail"))
    decorated = retry(max_retries=0)(mock_func)
    with pytest.raises(RuntimeError):
        decorated()
    assert mock_func.call_count == 1


def test_functools_wraps_preserved():
    """验证原函数的元数据被保留"""
    def dummy():
        """docstring"""
        pass

    decorated = retry()(dummy)
    assert decorated.__name__ == "dummy"
    assert decorated.__doc__ == "docstring"


def test_arguments_passed():
    """验证参数正确传递到原函数"""
    mock_func = Mock(return_value="ok")
    decorated = retry(max_retries=3)(mock_func)
    decorated(1, 2, key="val")
    mock_func.assert_called_once_with(1, 2, key="val")


def test_negative_max_retries():
    """验证异常参数检查"""
    with pytest.raises(ValueError):
        retry(max_retries=-1)
