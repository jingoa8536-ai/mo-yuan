"""retry_decorator 使用示例"""

import random
import time
import requests
from retry_decorator import retry


# ─── 基本用法 ────────────────────────────────────────────────────────

@retry(max_retries=3, base_delay=0.5)
def fetch_data(url: str) -> str:
    """模拟一个偶尔失败的 HTTP 请求"""
    if random.random() < 0.6:
        raise ConnectionError(f"连接失败（模拟）")
    return f"成功获取 {url}"


# ─── 仅重试特定异常 ─────────────────────────────────────────────────

class NetworkTimeout(Exception):
    pass

class ServerError(Exception):
    pass

@retry(max_retries=5, base_delay=0.2, exceptions=(NetworkTimeout, ServerError))
def call_api():
    """只有 NetworkTimeout / ServerError 时才重试"""
    if random.random() < 0.5:
        raise NetworkTimeout("请求超时")
    if random.random() < 0.3:
        raise ServerError("500 内部错误")
    return {"status": "ok"}


# ─── 使用回调监控重试过程 ────────────────────────────────────────────

def log_retry(exc: Exception, attempt: int):
    print(f"  ⏳ 第 {attempt} 次重试，原因: {exc}")

@retry(max_retries=2, base_delay=0.3, on_retry=log_retry)
def unstable_request():
    if random.random() < 0.7:
        raise RuntimeError("临时故障")
    return "✅ 成功"


# ─── 配合 requests 库的真实 HTTP 示例 ───────────────────────────────

@retry(max_retries=3, base_delay=0.5, max_delay=4.0, exceptions=(requests.ConnectionError, requests.Timeout))
def safe_http_get(url: str, timeout: int = 10):
    """自动重试连接超时 / 网络错误的 GET 请求"""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()  # 4xx/5xx 也抛异常
    return resp.json()


if __name__ == "__main__":
    print("=" * 50)
    print("示例 1: 基本重试")
    print("=" * 50)
    for i in range(3):
        try:
            result = fetch_data("https://example.com/data")
            print(f"  → {result}")
        except ConnectionError:
            print(f"  ✗ 最终失败（第 {i+1} 轮）")
        time.sleep(0.2)

    print()
    print("=" * 50)
    print("示例 2: 重试特定异常 + 回调监控")
    print("=" * 50)
    try:
        result = unstable_request()
        print(f"  → {result}")
    except RuntimeError:
        print("  ✗ 最终失败")

    print()
    print("=" * 50)
    print("示例 3: 真实 HTTP 请求（可跳过）")
    print("=" * 50)
    print("  若网络不通可忽略此示例")
    try:
        data = safe_http_get("https://httpbin.org/uuid")
        print(f"  → {data}")
    except Exception as e:
        print(f"  ✗ {type(e).__name__}: {e}")
