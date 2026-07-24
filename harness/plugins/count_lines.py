"""
LAAP 插件示例 — 代码行数统计工具

用法：丢到 harness/plugins/ 目录自动加载
效果：注册一个 count_lines 工具
"""

def register(registry):
    """插件入口 — 自动被 PluginLoader 调用。"""
    from tool_registry import ToolSchema

    schema = ToolSchema(
        name="count_lines",
        description="统计代码文件行数",
        parameters={
            "path": {"type": "string", "description": "文件或目录路径", "required": True},
            "ext": {"type": "string", "description": "文件扩展名过滤 (如 .py)"},
        },
        category="code",
    )
    registry.register(schema, handler=count_lines_handler)
    print(f"  [Plugin] ✅ count_lines 已注册")


def count_lines_handler(path: str, ext: str = "") -> dict:
    """统计代码行数。"""
    from pathlib import Path

    p = Path(path)
    if p.is_file():
        files = [p]
    elif p.is_dir():
        pattern = f"*{ext}" if ext else "*"
        files = list(p.rglob(pattern))
    else:
        return {"error": f"路径不存在: {path}"}

    total_lines = 0
    total_files = 0
    for f in files:
        try:
            lines = len(f.read_text(encoding="utf-8").splitlines())
            total_lines += lines
            total_files += 1
        except Exception:
            pass

    return {
        "files": total_files,
        "lines": total_lines,
        "average": total_lines // max(1, total_files),
    }
