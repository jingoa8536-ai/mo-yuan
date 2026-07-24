from functools import lru_cache

# 方案一：使用 functools.lru_cache 自动记忆化
@lru_cache(maxsize=None)
def fib_cache(n: int) -> int:
    """计算斐波那契数列的第 n 项（使用 @lru_cache 装饰器实现记忆化）"""
    if n < 0:
        raise ValueError("n 必须是非负整数")
    if n == 0:
        return 0
    if n == 1:
        return 1
    return fib_cache(n - 1) + fib_cache(n - 2)


# 方案二：手动实现 memoization（字典缓存）
def fib_memo(n: int, memo: dict | None = None) -> int:
    """计算斐波那契数列的第 n 项（使用字典手动实现记忆化）"""
    if n < 0:
        raise ValueError("n 必须是非负整数")

    if memo is None:
        memo = {}

    # 基础情况
    if n == 0:
        return 0
    if n == 1:
        return 1

    # 如果已经计算过，直接返回缓存结果
    if n in memo:
        return memo[n]

    # 递归计算并缓存
    memo[n] = fib_memo(n - 1, memo) + fib_memo(n - 2, memo)
    return memo[n]


# 方案三：使用类封装，带重置功能
class Fibonacci:
    """斐波那契计算器，支持记忆化并可在需要时清空缓存"""

    def __init__(self):
        self._memo: dict[int, int] = {0: 0, 1: 1}

    def __call__(self, n: int) -> int:
        if n < 0:
            raise ValueError("n 必须是非负整数")
        if n not in self._memo:
            self._memo[n] = self(n - 1) + self(n - 2)
        return self._memo[n]

    def clear_cache(self):
        """清空已缓存的记忆"""
        self._memo = {0: 0, 1: 1}


if __name__ == "__main__":
    # 简单测试
    for n in range(10):
        print(f"fib({n}) = {fib_cache(n)}")

    print()

    # 验证一致性
    for n in range(10):
        assert fib_cache(n) == fib_memo(n) == Fibonacci()(n)

    # 大数测试（验证记忆化优化生效，递归深度不会爆炸）
    print(f"fib(50)  = {fib_cache(50)}")
    print(f"fib(100) = {fib_cache(100)}")
    print(f"fib(200) = {fib_cache(200)}")
