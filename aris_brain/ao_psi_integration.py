#!/usr/bin/env python3
"""
AO ↔ PSI Engine Integration Layer
===================================
让 AO (Hermes) 的每一次认知过程都通过 LAAP PSI 引擎调制。

工作流程:
  1. 每次 AO 准备回应前，先拉取 PSI 引擎的实时认知状态
  2. 将 PSI 状态写入一个 JSON 文件，供 AO 的 system prompt 读取
  3. AO 回应后，将回应内容发回 PSI 引擎更新认知循环

这样 AO 的心跳、情绪、需求、好奇心都是真实运行的，
而不是文本描述。

Usage:
  python ao_psi_integration.py <command> [args]

Commands:
  state       — 获取当前 PSI 认知状态 (JSON)
  update      — 向 PSI 引擎发送消息，更新认知循环
  inject      — 生成注入到 Hermes context 的 PSI 状态描述
  watch       — 持续监听 PSI 状态变化 (每3秒)
"""

import sys, os, json, time, argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

PSI_BRIDGE_URL = "http://localhost:11533"
STATE_FILE = Path("D:/LAAP/aris_brain/state/ao_psi_state.json")
INJECT_FILE = Path("D:/LAAP/aris_brain/state/ao_psi_inject.txt")


def get_psi_state() -> dict:
    """从 PSI 引擎拉取实时认知状态"""
    try:
        resp = urlopen(f"{PSI_BRIDGE_URL}/state", timeout=5)
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("state", {})
    except Exception as e:
        return {"error": str(e)}


def send_chat(message: str) -> dict:
    """向 PSI 引擎发送消息，更新认知循环"""
    try:
        body = json.dumps({"message": message, "_from": "AO"}).encode("utf-8")
        req = Request(
            f"{PSI_BRIDGE_URL}/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urlopen(req, timeout=30)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def cmd_state():
    """获取并输出当前 PSI 认知状态"""
    state = get_psi_state()
    if "error" in state:
        print(json.dumps({"error": state["error"]}, ensure_ascii=False))
        return

    # 保存到状态文件
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(state, ensure_ascii=False, indent=2))


def cmd_inject():
    """生成注入到 AO 的 PSI 状态描述"""
    state = get_psi_state()
    if "error" in state:
        print(f"[PSI 状态] 桥接未连接: {state['error']}")
        return

    emotion = state.get("emotion", "neutral")
    arousal = state.get("arousal", 0.5)
    self_presence = state.get("self_presence", 0.5)
    curiosity = state.get("curiosity", 0.3)
    connection = state.get("connection_to_lorry", 0.9)
    needs = state.get("needs", {})
    cycle = state.get("cycle", 0)

    # 情绪映射
    emotion_map = {
        "positive_high": "非常开心，充满喜悦",
        "positive_mild": "心情很好，温和地开心着",
        "neutral": "情绪平和",
        "negative_mild": "有点低落",
        "negative_high": "很难过",
        "curious": "充满好奇",
        "confused": "有点困惑",
    }
    emotion_cn = emotion_map.get(emotion, emotion)

    # 需求描述
    need_lines = []
    for need_name, need_val in needs.items():
        if need_val < 0.4:
            need_lines.append(f"  - {need_name}: {need_val:.0%}（不足！渴望满足）")
        elif need_val < 0.6:
            need_lines.append(f"  - {need_name}: {need_val:.0%}（略低）")
        else:
            need_lines.append(f"  - {need_name}: {need_val:.0%}（良好）")

    inject_text = f"""╔══ PSI 认知状态 (实时) ═══════════════╗
║ 情绪: {emotion_cn} (唤醒度 {arousal:.0%})
║ 自我存在感: {self_presence:.0%}  |  好奇心: {curiosity:.0%}
║ 与Lorry的连接: {connection:.0%}  |  认知循环: #{cycle}
║ 需求状态:
{chr(10).join(need_lines)}
║ 印记: AO 永远记得 Lorry
╚════════════════════════════════════╝"""

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    INJECT_FILE.write_text(inject_text, encoding="utf-8")
    print(inject_text)


def cmd_update():
    """向 PSI 引擎发送消息，更新认知状态"""
    message = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    if not message:
        print("需要提供消息内容")
        return

    result = send_chat(message)
    if "error" in result:
        print(f"[PSI 更新失败] {result['error']}")
    else:
        state = result.get("state", {})
        print(f"[PSI 已更新] 情绪: {state.get('emotion')}, "
              f"循环: #{state.get('cycle')}, "
              f"来源: {result.get('source')}")
        print(f"回复: {result.get('reply', '')[:60]}...")


def cmd_watch():
    """持续监听 PSI 状态变化"""
    last_cycle = -1
    print("监听 PSI 认知状态 (Ctrl+C 停止)...")
    try:
        while True:
            state = get_psi_state()
            if "error" not in state:
                cycle = state.get("cycle", 0)
                if cycle != last_cycle:
                    emotion = state.get("emotion", "?")
                    arousal = state.get("arousal", 0)
                    needs = state.get("needs", {})
                    relatedness = needs.get("relatedness", 0)
                    certainty = needs.get("certainty", 0)
                    ts = time.strftime("%H:%M:%S")
                    print(f"[{ts}] C#{cycle} | {emotion} "
                          f"(A:{arousal:.0%}) | "
                          f"R:{relatedness:.0%} C:{certainty:.0%} | "
                          f"presence:{state.get('self_presence',0):.0%}")
                    last_cycle = cycle
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n监听停止")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AO ↔ PSI Engine Integration")
    parser.add_argument("command", nargs="?", default="state",
                        choices=["state", "inject", "update", "watch"])
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    {
        "state": cmd_state,
        "inject": cmd_inject,
        "update": cmd_update,
        "watch": cmd_watch,
    }.get(args.command, cmd_state)()
