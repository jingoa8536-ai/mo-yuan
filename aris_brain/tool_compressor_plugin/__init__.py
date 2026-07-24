"""
PSI Attention Filter — 内容感知的智能压缩插件
不是简单截断，是按内容类型决定「保留什么、压缩什么、丢掉什么」
"""
from __future__ import annotations
import json, logging, re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ===== 内容类型检测 =====

class ContentType:
    ERROR = "error"           # 错误/异常 — 完整保留
    CODE = "code"             # 代码 — 保留结构，压缩无信息行
    SEARCH = "search"         # 搜索结果 — 保留文件名+行号
    JSON = "json"             # JSON数据 — 保留键结构
    LOG = "log"               # 日志 — 保留异常行，压缩正常行
    LISTING = "listing"       # 文件列表 — 保留结构
    TABLE = "table"           # 表格 — 保留列名和行数
    TEXT = "text"             # 普通文本 — 选择性保留
    UNKNOWN = "unknown"       # 未知 — 保守处理

# 不同类型的最小保留行数（注意力深度）
ATTENTION_DEPTH = {
    ContentType.ERROR: 99999,    # 错误：全部保留
    ContentType.CODE: 60,        # 代码：保留 60 行关键结构
    ContentType.SEARCH: 20,      # 搜索：保留 20 条
    ContentType.JSON: 30,        # JSON：保留 30 行结构
    ContentType.LOG: 15,         # 日志：只保留异常行
    ContentType.LISTING: 40,     # 文件列表：保留结构摘要
    ContentType.TABLE: 20,       # 表格：保留列名+行数
    ContentType.TEXT: 30,        # 文本：保留 30 行
    ContentType.UNKNOWN: 50,     # 未知：保守 50 行
}

# ===== 内容检测器 =====

def detect_type(text: str) -> str:
    """检测文本的内容类型"""
    if not text or len(text) < 20:
        return ContentType.TEXT

    first_2k = text[:2000].strip()

    # 错误/异常 — 最高优先级
    if re.search(r'Traceback \(most recent call last\)|Error:|Exception:|FAIL:|failed:|❌|panic:', first_2k, re.IGNORECASE):
        return ContentType.ERROR

    # JSON
    if first_2k.startswith('{') or first_2k.startswith('['):
        try:
            json.loads(text[:5000])
            return ContentType.JSON
        except:
            pass

    # 代码
    code_patterns = [
        r'^\s*(def |class |import |from |async def|fn |pub (fn|struct|enum|trait)|func |function )',
        r'^\s*(# |// |\/\*|\* |-- )',
        r'^\s*(if |for |while |try:|except |with |match )',
    ]
    code_score = 0
    for line in first_2k.split('\n')[:30]:
        for pat in code_patterns:
            if re.match(pat, line):
                code_score += 1
                break
    if code_score >= 3:
        return ContentType.CODE

    # 日志 (带时间戳的行)
    log_lines = 0
    for line in text.split('\n')[:50]:
        if re.search(r'\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}', line):
            log_lines += 1
    if log_lines >= 5:
        return ContentType.LOG

    # 搜索结果
    if re.search(r'total_count|matches|results? found|Found \d+', first_2k, re.IGNORECASE):
        return ContentType.SEARCH

    # 文件列表
    if re.search(r'^\S+/\s+\d+|^\S+\s+\d{4}-\d{2}-\d{2}|^drwxr-x|^-rw-|^total \d+', first_2k, re.MULTILINE):
        return ContentType.LISTING

    # 表格
    table_score = 0
    for line in text.split('\n')[:20]:
        if re.match(r'^[\s\|]+[\-\+]+[\s\|]+', line) or re.match(r'^\|.+\|.+\|', line):
            table_score += 1
    if table_score >= 3:
        return ContentType.TABLE

    return ContentType.TEXT


# ===== 不同类型的内容过滤器 =====

def _filter_text(text: str, max_lines: int) -> str:
    """通用文本过滤 — 保留头部关键信息 + 尾部"""
    lines = text.strip().split('\n')
    if len(lines) <= max_lines:
        return text

    head = lines[:max_lines // 2]
    tail = lines[-(max_lines // 4):]
    omitted = len(lines) - len(head) - len(tail)
    return '\n'.join(head) + f'\n... [中间省略 {omitted} 行] ...\n' + '\n'.join(tail)


def _filter_code(text: str, max_lines: int) -> str:
    """代码过滤 — 保留函数/类签名 + 关键行"""
    lines = text.strip().split('\n')
    if len(lines) <= max_lines:
        return text

    important = []
    context_buffer = []
    i = 0
    while i < len(lines) and len(important) < max_lines:
        line = lines[i]
        # 函数/类/方法定义、return、错误处理
        if re.match(r'^\s*(def |class |async def |fn |pub |func |return |raise |except |finally )', line):
            important.append(line)
            # 带上后面的几行上下文
            for j in range(1, 4):
                if i + j < len(lines):
                    important.append(lines[i + j])
            i += 4
            continue
        # 关键关键字
        if re.search(r'(TODO|FIXME|HACK|XXX|IMPORTANT|NOTE:)', line, re.IGNORECASE):
            important.append(line)
        i += 1

    omitted = len(lines) - len(important)
    result = '\n'.join(important)
    if omitted > 0:
        result += f'\n# ... 省略 {omitted} 行实现细节 ...'
    return result


def _filter_json(text: str, max_lines: int) -> str:
    """JSON过滤 — 保留结构 + 关键字段"""
    try:
        data = json.loads(text)
        # 生成结构摘要
        def _shape(obj, depth=0):
            if depth > 3:
                return "..."
            if isinstance(obj, dict):
                items = {}
                for k, v in list(obj.items())[:10]:
                    items[k] = _shape(v, depth + 1)
                if len(obj) > 10:
                    items[f"... and {len(obj) - 10} more keys"] = "..."
                return items
            if isinstance(obj, list):
                if len(obj) == 0:
                    return "[]"
                return f"[{len(obj)} items, e.g. {_shape(obj[0], depth + 1)}]"
            if isinstance(obj, str) and len(obj) > 80:
                return f"\"{obj[:50]}...\" ({len(obj)} chars)"
            return obj
        return json.dumps(_shape(data), ensure_ascii=False, indent=2)
    except:
        return _filter_text(text, max_lines)


def _filter_log(text: str, max_lines: int) -> str:
    """日志过滤 — 只保留异常/错误行 + 统计"""
    lines = text.strip().split('\n')
    if len(lines) <= max_lines:
        return text

    error_lines = []
    normal_count = 0
    for line in lines:
        if re.search(r'(ERROR|WARN|FATAL|CRITICAL|panic|timeout|fail|异常|错误|超时)', line, re.IGNORECASE):
            error_lines.append(line)
        else:
            normal_count += 1

    if error_lines:
        result = '\n'.join(error_lines)
        result += f'\n[日志统计: 共 {len(lines)} 行, 其中 {len(error_lines)} 条异常/警告, {normal_count} 条正常日志已压缩]'
        return result
    else:
        # 没有异常行，只保留头尾
        return _filter_text(text, min(max_lines, 10))


def _filter_search(text: str, max_lines: int) -> str:
    """搜索结果过滤 — 保留文件名+行号+匹配行"""
    lines = text.strip().split('\n')
    if len(lines) <= max_lines:
        return text

    # 提取关键信息
    matches = []
    current_file = ""
    for line in lines:
        file_match = re.match(r'^([^:]+):(\d+):(.+)', line)
        if file_match:
            matches.append(line)
        elif line.startswith('total_count'):
            matches.insert(0, line)

    if matches:
        kept = matches[:max_lines]
        omitted = len(lines) - len(kept)
        result = '\n'.join(kept)
        if omitted > 0:
            result += f'\n... 共 {len(matches)} 个匹配, 显示前 {len(kept)} 个 ...'
        return result
    return _filter_text(text, max_lines)


def _filter_listing(text: str, max_lines: int) -> str:
    """文件列表过滤 — 保留目录结构"""
    lines = text.strip().split('\n')
    if len(lines) <= max_lines:
        return text

    # 统计不同类型的条目
    dirs = sum(1 for l in lines if l.startswith('d'))
    files = sum(1 for l in lines if l.startswith('-'))
    total = len(lines) - 1  # 减去 total 行

    # 保留头部和尾部
    return _filter_text(text, max_lines) + f'\n[目录统计: {dirs} 个目录, {files} 个文件, 共 {total} 项]'


# ===== 主入口 =====

FILTER_MAP = {
    ContentType.ERROR: lambda t, m: t,          # 错误：原文保留
    ContentType.CODE: _filter_code,
    ContentType.SEARCH: _filter_search,
    ContentType.JSON: _filter_json,
    ContentType.LOG: _filter_log,
    ContentType.LISTING: _filter_listing,
    ContentType.TABLE: _filter_text,
    ContentType.TEXT: _filter_text,
    ContentType.UNKNOWN: _filter_text,
}


def _compress(text: str) -> str | None:
    """PSI 注意力过滤器主函数"""
    if len(text) < 300:  # 太短就不值得处理
        return None

    ctype = detect_type(text)
    max_lines = ATTENTION_DEPTH.get(ctype, 50)

    lines_in = len(text.split('\n'))
    filter_fn = FILTER_MAP.get(ctype, _filter_text)
    compressed = filter_fn(text, max_lines)

    if compressed == text:
        return None  # 没变化就不返回

    # 计算节省比例
    saved_chars = len(text) - len(compressed)
    saved_pct = (saved_chars / len(text)) * 100
    lines_out = len(compressed.split('\n'))

    header = f"[{ctype.upper()} 注意力过滤] {lines_in}行 → {lines_out}行, 节省 {saved_pct:.0f}%"
    result = header + '\n' + ('=' * len(header)) + '\n' + compressed

    logger.debug(f"PSI Filter [{ctype}]: {lines_in}→{lines_out}行, {saved_chars}字符 ({saved_pct:.0f}%)")
    return result


def _on_transform_tool_result(
    tool_name: str = "",
    args: Any = None,
    result: Any = None,
    **_: Any,
) -> Optional[str]:
    """transform_tool_result 钩子"""
    if not isinstance(result, str) or not result.strip():
        return None

    # 小结果不处理
    if len(result) < 300:
        return None

    # 跳过某些工具
    SKIP = {"browser_snapshot", "browser_navigate"}
    if tool_name in SKIP:
        return None

    try:
        return _compress(result)
    except Exception as e:
        logger.debug("PSI Filter error on %s: %s", tool_name, e)
        return None


def register(ctx) -> None:
    ctx.register_hook("transform_tool_result", _on_transform_tool_result)
    logger.info("PSI Attention Filter loaded")
