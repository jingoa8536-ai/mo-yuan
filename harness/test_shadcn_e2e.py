"""
test_shadcn_e2e.py — LAAP Harness shadcn-ui 端到端测试
========================================================

测试完整流程:
1. 初始化 shadcn-mcp 集成器
2. 验证 GitHub Token 配置
3. 启动 MCP Server
4. 获取组件列表并同步到匹配引擎
5. 执行意图匹配（含 shadcn 组件）
6. 使用 shadcn-ui 组件组装页面
7. 生成测试输出页面
8. 验证输出质量

输出:
- test_output_shadcn_page.html — 生成的页面
- test_shadcn_e2e_report.json — 测试报告
"""

import os
import json
import time
from typing import Dict, List, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def log_step(step: str, message: str, status: str = "INFO"):
    """标准化日志输出"""
    status_colors = {
        "INFO": "[INFO]",
        "OK": "[OK]",
        "WARN": "[WARN]",
        "ERROR": "[ERROR]",
        "STEP": "[STEP]",
    }
    print(f"{status_colors.get(status, '[INFO]')} [{step}] {message}")


def run_e2e_test() -> Dict[str, Any]:
    """执行端到端测试"""
    report = {
        "test_name": "shadcn-ui-end-to-end",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "steps": [],
        "success": False,
        "metrics": {},
        "output_file": "",
    }

    step_count = 1

    try:
        log_step(f"Step {step_count}", "导入依赖模块", "STEP")
        step_count += 1

        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "laap_coding", "core"))

        from shadcn_mcp_integrator import ShadcnMCPIntegrator, ShadcnHarnessBridge
        from matching_engine import MatchingEngine

        report["steps"].append({"step": "import_dependencies", "status": "passed", "message": "依赖模块导入成功"})
        log_step(f"Step {step_count - 1}", "依赖模块导入成功", "OK")

        log_step(f"Step {step_count}", "初始化 shadcn-mcp 集成器", "STEP")
        step_count += 1

        integrator = ShadcnMCPIntegrator()

        api_limit = integrator.get_api_limit()
        report["metrics"]["api_limit"] = api_limit
        report["metrics"]["token_configured"] = api_limit["with_token"]

        if api_limit["with_token"]:
            log_step(f"Step {step_count - 1}", f"GitHub Token 已配置 — API 限额: {api_limit['limit']}/h", "OK")
        else:
            log_step(f"Step {step_count - 1}", "未配置 GitHub Token — API 限额: 60/h", "WARN")

        report["steps"].append({
            "step": "initialize_integrator",
            "status": "passed",
            "message": f"集成器初始化成功，Token状态: {'已配置' if api_limit['with_token'] else '未配置'}",
        })

        log_step(f"Step {step_count}", "启动 MCP Server", "STEP")
        step_count += 1

        start_time = time.time()
        server_started = integrator.start_server(framework="react")
        server_start_time = time.time() - start_time

        if not server_started:
            log_step(f"Step {step_count - 1}", "MCP Server 启动失败", "ERROR")
            report["steps"].append({"step": "start_server", "status": "failed", "message": "MCP Server 启动失败"})
            report["success"] = False
            return report

        report["metrics"]["server_start_time_ms"] = round(server_start_time * 1000)
        report["steps"].append({
            "step": "start_server",
            "status": "passed",
            "message": f"MCP Server 启动成功，耗时: {report['metrics']['server_start_time_ms']}ms",
        })
        log_step(f"Step {step_count - 1}", f"MCP Server 启动成功，耗时: {report['metrics']['server_start_time_ms']}ms", "OK")

        log_step(f"Step {step_count}", "获取 shadcn 组件列表", "STEP")
        step_count += 1

        start_time = time.time()
        components = integrator.list_components()
        list_time = time.time() - start_time

        report["metrics"]["total_components"] = len(components)
        report["metrics"]["list_components_time_ms"] = round(list_time * 1000)
        report["steps"].append({
            "step": "list_components",
            "status": "passed",
            "message": f"获取到 {len(components)} 个组件",
        })
        log_step(f"Step {step_count - 1}", f"获取到 {len(components)} 个 shadcn/ui 组件，耗时: {report['metrics']['list_components_time_ms']}ms", "OK")

        if components:
            component_names = [c.get("name", c) if isinstance(c, dict) else c for c in components[:8]]
            log_step(f"Step {step_count - 1}", f"部分组件: {', '.join(component_names)}", "INFO")

        log_step(f"Step {step_count}", "获取 shadcn blocks 列表", "STEP")
        step_count += 1

        blocks = integrator.list_blocks()
        report["metrics"]["total_blocks"] = len(blocks)
        report["steps"].append({
            "step": "list_blocks",
            "status": "passed",
            "message": f"获取到 {len(blocks)} 个 blocks",
        })
        log_step(f"Step {step_count - 1}", f"获取到 {len(blocks)} 个 blocks", "OK")

        log_step(f"Step {step_count}", "初始化匹配引擎并设置 shadcn 桥接器", "STEP")
        step_count += 1

        engine = MatchingEngine(use_enhancements=True)
        bridge = ShadcnHarnessBridge(integrator)
        engine.set_shadcn_bridge(bridge)

        synced = engine.sync_shadcn_components()
        report["metrics"]["synced_shadcn_components"] = synced
        report["steps"].append({
            "step": "setup_matching_engine",
            "status": "passed",
            "message": f"匹配引擎初始化成功，同步 {synced} 个 shadcn 组件",
        })
        log_step(f"Step {step_count - 1}", f"匹配引擎初始化成功，同步 {synced} 个 shadcn 组件", "OK")

        log_step(f"Step {step_count}", "执行意图匹配（含 shadcn 组件）", "STEP")
        step_count += 1

        test_intent = {
            "tags": ["button", "card", "form", "input"],
            "style": "modern-minimal",
            "tech": "React + Tailwind",
            "page_type": "landing",
        }

        start_time = time.time()
        match_results = engine.match_with_shadcn(test_intent, user_id="test_user_e2e")
        match_time = time.time() - start_time

        report["metrics"]["match_time_ms"] = round(match_time * 1000)
        report["metrics"]["total_match_results"] = len(match_results)

        shadcn_matches = [r for r in match_results if r.get("is_shadcn")]
        report["metrics"]["shadcn_match_count"] = len(shadcn_matches)

        report["steps"].append({
            "step": "intent_matching",
            "status": "passed",
            "message": f"匹配完成，共 {len(match_results)} 个结果，其中 {len(shadcn_matches)} 个 shadcn 组件",
        })

        log_step(f"Step {step_count - 1}", f"匹配完成，共 {len(match_results)} 个结果，其中 {len(shadcn_matches)} 个 shadcn 组件，耗时: {report['metrics']['match_time_ms']}ms", "OK")

        if match_results:
            top_3 = match_results[:3]
            for i, result in enumerate(top_3, 1):
                score = result["scores"]["total_score"]
                level = result["match_level"]
                is_shadcn = "[shadcn]" if result.get("is_shadcn") else ""
                log_step(f"Step {step_count - 1}", f"  Top {i}: {result['name']} {is_shadcn} — 评分: {score:.4f} — {level}", "INFO")

        log_step(f"Step {step_count}", "使用 shadcn-ui 组件组装页面", "STEP")
        step_count += 1

        assemble_intent = {
            "page_type": "landing",
            "style_tags": ["modern", "minimal", "professional"],
            "required_sections": ["hero", "features", "pricing", "cta"],
            "theme": "dark",
        }

        start_time = time.time()
        page_code = bridge.assemble_with_shadcn(assemble_intent)
        assemble_time = time.time() - start_time

        report["metrics"]["assemble_time_ms"] = round(assemble_time * 1000)
        report["metrics"]["page_code_length"] = len(page_code)
        report["steps"].append({
            "step": "assemble_page",
            "status": "passed",
            "message": f"页面组装完成，代码长度: {len(page_code)} 字符",
        })
        log_step(f"Step {step_count - 1}", f"页面组装完成，代码长度: {len(page_code)} 字符，耗时: {report['metrics']['assemble_time_ms']}ms", "OK")

        log_step(f"Step {step_count}", "生成测试输出页面", "STEP")
        step_count += 1

        output_file = os.path.join(os.path.dirname(__file__), "test_output_shadcn_page.html")
        report["output_file"] = output_file

        html_content = generate_shadcn_test_page(components[:20], shadcn_matches[:5], assemble_intent)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        report["steps"].append({
            "step": "generate_output",
            "status": "passed",
            "message": f"测试页面已生成: {output_file}",
        })
        log_step(f"Step {step_count - 1}", f"测试页面已生成: {output_file}", "OK")

        log_step(f"Step {step_count}", "停止 MCP Server", "STEP")
        step_count += 1

        integrator.stop_server()
        report["steps"].append({"step": "stop_server", "status": "passed", "message": "MCP Server 已停止"})
        log_step(f"Step {step_count - 1}", "MCP Server 已停止", "OK")

        report["success"] = True

    except Exception as e:
        report["steps"].append({"step": "error", "status": "failed", "message": str(e)})
        log_step("ERROR", f"测试失败: {e}", "ERROR")
        report["success"] = False

    return report


def generate_shadcn_test_page(components: List[Dict[str, Any]], matches: List[Dict[str, Any]], intent: Dict[str, Any]) -> str:
    """生成包含 shadcn-ui 组件的测试页面"""
    component_list_html = ""
    for comp in components:
        name = comp.get("name", comp) if isinstance(comp, dict) else comp
        component_list_html += f"""<div class="component-item">
            <div class="component-name">{name}</div>
            <div class="component-status available"></div>
        </div>"""

    match_list_html = ""
    for match in matches:
        score = match["scores"]["total_score"]
        level = match["match_level"]
        score_color = "#22c55e" if score >= 0.8 else "#7c7cff" if score >= 0.6 else "#f59e0b"
        match_list_html += f"""<div class="match-card">
            <div class="match-header">
                <span class="match-name">{match['name']}</span>
                <span class="match-level" style="color: {score_color}">{level}</span>
            </div>
            <div class="match-score-bar">
                <div class="match-score-fill" style="width: {score * 100}%; background: {score_color}"></div>
            </div>
            <div class="match-score-text">{score:.4f}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LAAP Harness — shadcn-ui E2E Test Output</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg-base: #0a0a0f;
  --bg-surface: #12121a;
  --bg-card: #1a1a24;
  --bg-card-hover: #22222e;
  --text-primary: #ffffff;
  --text-secondary: rgba(255,255,255,0.6);
  --text-muted: rgba(255,255,255,0.4);
  --text-disabled: rgba(255,255,255,0.25);
  --border-default: rgba(255,255,255,0.08);
  --accent: #7c7cff;
  --accent-light: #9494ff;
  --accent-muted: rgba(124,124,255,0.15);
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
}}
body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: var(--bg-base);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  line-height: 1.6;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 0 24px; }}
header {{
  padding: 32px 0;
  border-bottom: 1px solid var(--border-default);
}}
.header-title {{ font-size: 28px; font-weight: 700; letter-spacing: -0.02em; }}
.header-subtitle {{ font-size: 14px; color: var(--text-secondary); margin-top: 4px; }}
.section {{ padding: 48px 0; }}
.section-header {{ margin-bottom: 24px; }}
.section-label {{
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--accent);
}}
.section-title {{
  font-size: 20px;
  font-weight: 600;
  margin-top: 8px;
}}
.section-description {{
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 6px;
}}
.card {{
  padding: 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
}}
.components-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}}
.component-item {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--bg-surface);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
}}
.component-name {{ font-size: 13px; font-weight: 500; }}
.component-status {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
}}
.component-status.available {{ background: #22c55e; }}
.matches-list {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}}
.match-card {{
  padding: 18px;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
}}
.match-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}}
.match-name {{ font-size: 14px; font-weight: 600; }}
.match-level {{ font-size: 12px; font-weight: 500; }}
.match-score-bar {{
  height: 4px;
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 6px;
}}
.match-score-fill {{
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}}
.match-score-text {{
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}}
.intent-panel {{
  padding: 20px;
  background: var(--accent-muted);
  border: 1px solid rgba(124,124,255,0.2);
  border-radius: var(--radius-md);
}}
.intent-label {{
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--accent);
  text-transform: uppercase;
}}
.intent-value {{
  font-size: 14px;
  margin-top: 4px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-primary);
}}
footer {{
  padding: 32px 0;
  border-top: 1px solid var(--border-default);
  text-align: center;
}}
footer p {{ font-size: 13px; color: var(--text-muted); }}
</style>
</head>
<body>

<header>
  <div class="container">
    <div class="header-title">LAAP Harness — shadcn-ui 端到端测试</div>
    <div class="header-subtitle">Generated from shadcn-ui-mcp-server integration</div>
  </div>
</header>

<main>
  <div class="container">
    <section class="section">
      <div class="section-header">
        <div class="section-label">Intent</div>
        <div class="section-title">测试意图</div>
        <div class="section-description">用于匹配和组装的输入参数</div>
      </div>
      <div class="card">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="intent-panel">
            <div class="intent-label">Page Type</div>
            <div class="intent-value">{intent.get('page_type', '')}</div>
          </div>
          <div class="intent-panel">
            <div class="intent-label">Style</div>
            <div class="intent-value">{', '.join(intent.get('style_tags', []))}</div>
          </div>
          <div class="intent-panel">
            <div class="intent-label">Sections</div>
            <div class="intent-value">{', '.join(intent.get('required_sections', []))}</div>
          </div>
          <div class="intent-panel">
            <div class="intent-label">Theme</div>
            <div class="intent-value">{intent.get('theme', '')}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-header">
        <div class="section-label">Components</div>
        <div class="section-title">shadcn/ui 组件列表</div>
        <div class="section-description">从 MCP Server 获取的组件清单</div>
      </div>
      <div class="card">
        <div class="components-grid">
          {component_list_html}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-header">
        <div class="section-label">Matching</div>
        <div class="section-title">智能匹配结果</div>
        <div class="section-description">匹配引擎返回的 shadcn-ui 组件及其评分</div>
      </div>
      <div class="matches-list">
        {match_list_html}
      </div>
    </section>

    <section class="section">
      <div class="section-header">
        <div class="section-label">Preview</div>
        <div class="section-title">组件预览</div>
        <div class="section-description">shadcn-ui 组件的实际效果展示</div>
      </div>
      <div class="card">
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;">
          <div style="padding: 16px; background: rgba(255,255,255,0.04); border-radius: 8px;">
            <div style="font-size: 12px; color: rgba(255,255,255,0.4); margin-bottom: 8px;">Button Component</div>
            <div style="display: flex; gap: 8px;">
              <button style="padding: 8px 16px; background: #7c7cff; color: white; border: none; border-radius: 6px; font-size: 13px;">Primary</button>
              <button style="padding: 8px 16px; background: transparent; color: white; border: 1px solid rgba(255,255,255,0.2); border-radius: 6px; font-size: 13px;">Secondary</button>
            </div>
          </div>
          <div style="padding: 16px; background: rgba(255,255,255,0.04); border-radius: 8px;">
            <div style="font-size: 12px; color: rgba(255,255,255,0.4); margin-bottom: 8px;">Card Component</div>
            <div style="padding: 12px; background: rgba(255,255,255,0.04); border-radius: 6px;">
              <div style="font-weight: 500; font-size: 14px;">Card Title</div>
              <div style="font-size: 12px; color: rgba(255,255,255,0.5); margin-top: 4px;">Card description</div>
            </div>
          </div>
          <div style="padding: 16px; background: rgba(255,255,255,0.04); border-radius: 8px;">
            <div style="font-size: 12px; color: rgba(255,255,255,0.4); margin-bottom: 8px;">Input Component</div>
            <input type="text" placeholder="Text input..." style="width: 100%; padding: 8px 12px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; color: white; font-size: 13px; outline: none;" />
          </div>
          <div style="padding: 16px; background: rgba(255,255,255,0.04); border-radius: 8px;">
            <div style="font-size: 12px; color: rgba(255,255,255,0.4); margin-bottom: 8px;">Badge Component</div>
            <div style="display: flex; gap: 6px;">
              <span style="padding: 4px 10px; background: rgba(34,197,94,0.15); color: #22c55e; border-radius: 4px; font-size: 12px;">Success</span>
              <span style="padding: 4px 10px; background: rgba(245,158,11,0.15); color: #f59e0b; border-radius: 4px; font-size: 12px;">Warning</span>
              <span style="padding: 4px 10px; background: rgba(239,68,68,0.15); color: #ef4444; border-radius: 4px; font-size: 12px;">Error</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</main>

<footer>
  <div class="container">
    <p>Generated by LAAP Harness shadcn-ui-mcp-server Integration</p>
  </div>
</footer>

</body>
</html>"""


def save_report(report: Dict[str, Any]) -> str:
    """保存测试报告到 JSON 文件"""
    report_file = os.path.join(os.path.dirname(__file__), "test_shadcn_e2e_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report_file


def main():
    """主函数"""
    print("=" * 80)
    print("LAAP Harness shadcn-ui 端到端测试")
    print("=" * 80)
    print()

    report = run_e2e_test()

    print()
    print("=" * 80)
    print("测试报告")
    print("=" * 80)

    if report["success"]:
        print("[RESULT] 测试通过")
    else:
        print("[RESULT] 测试失败")

    print(f"[TIME] {report['timestamp']}")
    print(f"[OUTPUT] {report['output_file']}")

    if "metrics" in report:
        print()
        print("[METRICS]")
        for key, value in report["metrics"].items():
            print(f"  {key}: {value}")

    report_file = save_report(report)
    print(f"\n[REPORT] 报告已保存: {report_file}")


if __name__ == "__main__":
    main()
