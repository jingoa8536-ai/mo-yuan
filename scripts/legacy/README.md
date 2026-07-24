# scripts/legacy — 已不推荐使用的启动脚本归档

> 本目录保存根目录清理过程中归档的旧启动脚本。**仅做历史保留，不维护、不推荐运行**。
> 若脚本涉及硬编码路径、引用已不存在文件、依赖外部 Hermes 特定版本或功能已被主入口覆盖，均已移入此处。

## 归档原则

1. **不删除**：任何脚本都不删除，仅移动/归档。
2. **不修复**：本目录脚本不会随主代码演进同步更新。
3. **替代优先**：新流程请使用 `python -m laap` 或 `scripts/windows/laap.cmd` / `scripts/unix/install.sh`。

## 已归档脚本清单

### Windows CMD / BAT（硬编码路径或引用不存在文件）

| 原根路径 | 废弃原因 | 推荐替代 |
|----------|---------|---------|
| `laap.bat` | 硬编码 `python D:\LAAP\laap\cli\main.py`，与 `python -m laap` 重复 | `python -m laap` 或 `scripts/windows/laap.cmd` |
| `start.bat` | 硬编码启动 `D:\LAAP\laap_web.py`（文件已不存在） | `python -m laap.web.server` 或参考 `serve_web.py` |
| `start-web-avatar.bat` | 同上，引用已不存在的 `laap_web.py` | `python -m laap.web.server` |
| `start-web-full.bat` | 同上 | `python -m laap.web.server` |
| `start-web-avatar-full.bat` | 同上 | `python -m laap.web.server` |
| `start_web_avatar.cmd` | 同上 | `python -m laap.web.server` |
| `LAAP_Launcher.bat` | 控制面板脚本，硬编码 `D:\LAAP\laap_web.py` 与 docker compose | 按需分别启动 `python -m laap` 与 `docker compose` |
| `LAAP_Ultimate.bat` | 旧版“终极”启动器，路径硬编码 | `python -m laap` |
| `diagnose.bat` | 旧诊断脚本，功能已由 `laap` CLI 覆盖 | `python -m laap system` 等子命令 |
| `laap_startup.bat` | 旧启动脚本 | `python -m laap` |
| `install_consciousness.bat` | 旧意识模块安装脚本 | `pip install -e .` |
| `aris_v10.bat` | Aris v10 专用启动 | `scripts/windows/laap.cmd`（已脱离 Aris） |
| `aris_shared_window.bat` | Aris 共享窗口启动 | 不推荐 |
| `start_ao_and_bridge.bat` | AO + bridge 启动，硬编码路径 | `python -m laap` |
| `start_aris.bat` | Aris 专用启动 | 不推荐 |
| `start_fusion_v13.bat` | Fusion v13 历史版本 | 不推荐 |
| `start_fusion_v14.bat` | Fusion v14 历史版本 | 不推荐 |
| `start_psi_daemon.bat` | PSI 守护进程启动（旧版） | `laap/agi/` 内新实现 |
| `start_wiky.bat` | Wiky 历史组件 | 不推荐 |
| `start_wm.bat` | World Model 历史组件 | `laap/agi/` 相关模块 |
| `launch_v14.cmd` | v14 历史启动 | 不推荐 |
| `_upgrade.cmd` | 旧升级脚本 | 参考 `docs/` 升级文档 |
| `_test_cmd.bat` | 旧测试命令 | `pytest tests/` |
| `test_mmd_model.cmd` | MMD 模型测试（硬编码） | 不推荐 |
| `deploy_tts.bat` | TTS 部署脚本（环境特定） | 参考 `laap/web/voice_bridge.py` |
| `deploy_gptsovits.bat` | GPT-SoVITS 部署（环境特定） | 参考 `laap/web/voice_bridge.py` |
| `Aris 语音对话.bat` | Aris 语音对话历史入口 | 不推荐 |

### Windows PowerShell（硬编码路径或重复）

| 原根路径 | 废弃原因 | 推荐替代 |
|----------|---------|---------|
| `laap.ps1` | 硬编码 `D:\LAAP\laap\cli\laap_main.py` | `python -m laap` |
| `laap-aris.ps1` | Aris 专用，硬编码端口与路径 | 不推荐 |
| `laap-aris.profile.ps1` | Aris PowerShell profile | 不推荐 |
| `hermes-aris.ps1` | Hermes + Aris 包装 | 不推荐 |
| `laap_start.ps1` | 硬编码启动 `D:\LAAP\laap_web.py` | `python -m laap.web.server` |
| `launcher.ps1` | 文件内容仅为字符串字面量，已损坏 | `python -m laap` |
| `start-gen1.ps1` | 依赖外部 `D:\hermes-agent...` | 不推荐 |
| `start-gen2.ps1` | 同上 | 不推荐 |
| `start-gen3.ps1` | 同上 | 不推荐 |

### Unix Shell（环境特定或重复）

| 原根路径 | 废弃原因 | 推荐替代 |
|----------|---------|---------|
| `_start_aris.sh` | 硬编码 `/opt/aris` 与飞书凭证，环境特定 | 不推荐直接运行 |

### 跨平台 Python（硬编码路径或引用缺失模块）

| 原根路径 | 废弃原因 | 推荐替代 |
|----------|---------|---------|
| `launch_ao.py` | 硬编码 `D:\LAAP`、`D:\hermes-agent-main`，依赖不存在模块 | `python -m laap` |
| `launch_desktop.py` | 引用 `laap_desktop_server.py` 与 `laap_desktop/`（已不存在） | 不推荐 |

### 历史世代启动脚本

| 原根路径 | 废弃原因 | 推荐替代 |
|----------|---------|---------|
| `start-gen1.bat` | 原生 Hermes，无 LAAP 增强，硬编码外部路径 | `python -m laap` |
| `start-gen2.bat` | 旧版 Ao Genesis，硬编码外部路径 | `python -m laap` |
| `start-gen3.bat` | 旧版第三代，硬编码外部路径 | `python -m laap` |

## 当前推荐入口

```bash
# 主入口
python -m laap --help

# Windows CMD（源码运行）
scripts\windows\laap.cmd --help

# 安装
scripts\windows\install.bat        # Windows
scripts/unix/install.sh            # macOS / Linux / WSL

# 测试
pytest tests/
```

## 维护记录

| 时间 | 变更 |
|------|------|
| 2026-07-11 | Phase 1 清理根目录启动脚本，创建本目录与 README |
