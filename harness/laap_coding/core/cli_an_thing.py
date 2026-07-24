"""
LAAP CLI-an-thing — GUI 操作 → CLI 等价物映射表
=================================================

核心原则：任何 GUI 操作几乎都有 CLI 等价物。
  - CLI 命令 = 0 token
  - CUA 操作 = ~2000 token/次

所以：能走 CLI 就不走 CUA。
"""

# ── 映射表（按操作分类） ──

CLI_MAP = {
    # ── 文件管理 ──
    "创建文件": "echo {content} > {path}",
    "创建目录": "mkdir -p {path}",
    "删除文件": "rm {path}",
    "删除目录": "rm -rf {path}",
    "复制文件": "cp {src} {dst}",
    "移动/重命名": "mv {src} {dst}",
    "查看文件": "cat {path}",
    "编辑文件": "echo '{content}' > {path} || write_file({path}, '{content}')",
    "查找文件": "find {dir} -name '{pattern}'",
    "修改权限": "chmod {mode} {path}",
    "压缩": "zip -r {output}.zip {dir}",
    "解压": "unzip {file}.zip -d {dir}",
    "打包tar": "tar -czf {output}.tar.gz {dir}",

    # ── 进程管理 ──
    "查看进程": "tasklist | findstr {name}",
    "杀进程": "taskkill /F /PID {pid}",
    "杀进程(按名)": "taskkill /F /IM {name}.exe",
    "查看端口": "netstat -ano | findstr :{port}",
    "启动服务": "net start {service}",
    "停止服务": "net stop {service}",
    "查看CPU": "wmic cpu get loadpercentage",
    "查看内存": "wmic OS get FreePhysicalMemory,TotalVisibleMemorySize",
    "查看磁盘": "wmic logicaldisk get size,freespace,caption",

    # ── 网络 ──
    "查看IP": "ipconfig",
    "Ping": "ping {host}",
    "查看路由": "route print",
    "DNS查询": "nslookup {host}",
    "查看连接": "netstat -an",
    "设置代理": "set HTTP_PROXY={proxy} && set HTTPS_PROXY={proxy}",
    "下载文件": "curl -O {url}",
    "发送请求": "curl {url}",

    # ── 系统设置 ──
    "打开设置": "start ms-settings:",
    "打开网络设置": "start ms-settings:network",
    "打开显示设置": "start ms-settings:display",
    "打开声音设置": "start ms-settings:sound",
    "打开蓝牙": "start ms-settings:bluetooth",
    "打开更新": "start ms-settings:windowsupdate",
    "查看系统信息": "systeminfo | findstr /B /C:\"OS Name\"",
    "查看环境变量": "set | findstr {var}",
    "设置环境变量": "setx {var} {value}",
    "重启": "shutdown /r /t 5",
    "关机": "shutdown /s /t 5",
    "休眠": "shutdown /h",

    # ── 注册表 ──
    "查看注册表": "reg query {key}",
    "修改注册表": "reg add {key} /v {name} /t {type} /d {value} /f",
    "删除注册表": "reg delete {key} /v {name} /f",

    # ── 包管理 ──
    "安装软件": "winget install {package}",
    "卸载软件": "winget uninstall {package}",
    "查找软件": "winget search {query}",
    "更新软件": "winget upgrade {package}",
    "通过pip安装": "pip install {package}",
    "通过npm安装": "npm install -g {package}",
    "通过cargo安装": "cargo install {crate}",

    # ── 开发 ──
    "克隆仓库": "git clone {url}",
    "提交代码": "git add . && git commit -m '{msg}'",
    "推送": "git push",
    "拉取": "git pull",
    "查看Git状态": "git status",
    "查看Git差异": "git diff",
    "创建分支": "git checkout -b {branch}",
    "切换分支": "git checkout {branch}",
    "构建项目": "cd {dir} && cargo build",
    "运行测试": "cd {dir} && cargo test",
    "安装依赖": "cd {dir} && pip install -r requirements.txt",
    "格式化代码": "cd {dir} && rustfmt *.rs",
    "检查语法": "cd {dir} && python -m py_compile {file}",

    # ── 窗口管理 ──
    "切换窗口": "powershell -Command \"(New-Object -ComObject Shell.Application).Windows() | ? {{$_.Name -like '*{name}*'}} | % {{$_.Quit}}\"",
    "列出窗口": "powershell -Command \"Get-Process | Where-Object {{$_.MainWindowTitle}} | Format-Table Id, ProcessName, MainWindowTitle -AutoSize\"",
    "最小化窗口": "powershell -Command \"$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys('%%{space}n')\"",
    "关闭窗口": "powershell -Command \"(Get-Process -Id {pid}).CloseMainWindow()\"",
}

# ── 查找最佳 CLI 匹配 ──

def find_cli(intent: str) -> str | None:
    """根据用户意图找到最匹配的 CLI 命令。

    Args:
        intent: 用户的操作意图，如"打开设置"、"安装vscode"

    Returns:
        CLI 命令模板，或 None
    """
    for key, cmd in CLI_MAP.items():
        if key in intent or intent in key:
            return cmd
    return None

# ── 类别索引 ──

CATEGORIES = {
    "文件": ["创建文件", "创建目录", "删除文件", "复制文件", "查看文件", "查找文件"],
    "进程": ["查看进程", "杀进程", "查看端口"],
    "网络": ["查看IP", "Ping", "下载文件", "发送请求"],
    "系统": ["打开设置", "查看系统信息", "重启", "关机"],
    "软件": ["安装软件", "卸载软件", "查找软件"],
    "开发": ["克隆仓库", "提交代码", "构建项目", "运行测试"],
    "窗口": ["切换窗口", "列出窗口", "关闭窗口"],
}


if __name__ == "__main__":
    print(f"LAAP CLI-an-thing 映射表")
    print(f"{'='*50}")
    print(f"  条目数: {len(CLI_MAP)}")
    print(f"  分类数: {len(CATEGORIES)}")
    print(f"\n  {'类别':10s} {'条目数':>8s}")
    print(f"  {'-'*20}")
    for cat, items in CATEGORIES.items():
        print(f"  {cat:10s} {len(items):>8d}")
    print()
    # 找匹配测试
    tests = ["安装vscode", "查看进程", "打开设置", "提交代码"]
    for t in tests:
        cmd = find_cli(t)
        print(f"  \"{t}\" → {cmd if cmd else '(未找到)'}")
