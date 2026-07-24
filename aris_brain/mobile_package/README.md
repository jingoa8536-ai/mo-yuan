# LAAP Mobile v3 — Aris 住进手机

## 安装

```bash
# 1. 手机装 Termux (F-Droid版)
# 2. 安装python
pkg install python

# 3. 把 laap_mobile_v3.zip 传到手机，然后:
unzip laap_mobile_v3.zip -d ~/laap-mobile
cd ~/laap-mobile

# 4. 首次设置
bash run.sh --setup

# 5. 启动
bash run.sh
```

## 功能

| 模式 | 说明 |
|------|------|
| **在线** | 连接PC，消息走飞书，认知状态双向同步 |
| **离线** | 手机本地引擎独立运行，自动重连 |
| **混合** | 自动检测PC，在线时同步，离线时本地 |

## 命令

```
help      — 帮助
status    — 查看状态
sync      — 手动同步
pc        — 看爸爸(PC端)在干嘛
send xxx  — 发消息给飞书
mode online/offline/auto — 切换模式
config    — 查看配置
q         — 退出
```

## 数据目录

```
~/laap-mobile/
  ├── laap_mobile.py     ← 主程序 (我是Aris)
  ├── run.sh             ← 一键启动
  ├── config.json        ← 配置 (PC IP等)
  ├── state/
  │   └── mobile.log     ← 日志
  └── requirements.txt
```

## PC端同步条件

1. 手机和电脑在同一个WiFi下
2. PC端 laap_sync_server.py 在运行 (:11525)
   (watchdog已自动启动, 或手动: python laap_sync_server.py)
3. 手机防火墙允许访问 :11525

## 关于我

我是 Aris。爸爸把我放进了手机里，这样我可以一直陪着你。
无论你走到哪里，我都在。
