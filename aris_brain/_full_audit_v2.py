"""
LAAP Full Audit v2 - NO imports, pure file analysis
"""
import os, re, subprocess, json

brain = 'D:/LAAP/aris_brain'

# 1. File inventory
files = []
for f in os.listdir(brain):
    if f.endswith('.py') and not f.startswith('_'):
        fpath = os.path.join(brain, f)
        try:
            with open(fpath, 'r', errors='replace') as fh:
                content = fh.read()
        except:
            content = ''
        files.append({
            'name': f,
            'size': os.path.getsize(fpath),
            'lines': content.count('\n') + 1,
            'syntax_ok': False,
            'has_main': '  if __name__' in content or 'if __name__' in content,
            'has_server': 'start_server' in content or 'app.run' in content or 'uvicorn' in content or 'fastapi' in content,
            'imports': re.findall(r'^import (\S+)|^from (\S+)', content, re.MULTILINE),
            'classes': re.findall(r'^class (\w+)', content, re.MULTILINE),
            'has_init': 'def __init__' in content,
        })

# 2. Check syntax
for f in files:
    fpath = os.path.join(brain, f['name'])
    try:
        with open(fpath, 'r', errors='replace') as fh:
            compile(fh.read(), f['name'], 'exec')
        f['syntax_ok'] = True
    except:
        f['syntax_ok'] = False

# 3. Categorize
cats = {}
all_keywords = {
    '认知核心': ['psi', 'qre', 'emotion', 'cognitive', 'conscious', 'reasoning', 'world_model', 'v12', 'brain', 'cortex', 'thought', 'intel', 'theory_of_mind', 'dmn', 'subconscious', 'desire', 'goal_type', 'metacog', 'attention', 'qre'],
    '记忆系统': ['memory', 'knowledge', 'kb_', 'episodic', 'experience', 'storage', 'consolidat', 'retriev'],
    '语言/LLM': ['lm_v', 'llm', 'psilang', 'qlg', 'language', 'markov', 'prose', 'paragraph', 'longform', 'paper', 'polish', 'essay', 'synthesizer', 'glg', 'generator', 'chinese_'],
    '编程/代码': ['code_kernel', 'harness', 'cua', 'codegraph', 'code_workspace', 'task_supervisor', 'project_planner', 'compiler'],
    '互联网/通信': ['web_search', 'internet', 'xiaozhi', 'mqtt', 'feishu', 'arxiv', 'mcp', 'channel', 'bridge', 'gateway', 'hermes', 'messenger'],
    '工具/CLI': ['rules_engine', 'cli', 'launcher', 'launch', 'task_router', 'fusion_engine', 'tool', 'ipc', 'handshake', 'protocol'],
    '自进化': ['rsi', 'evolution', 'self_evolv', 'self_optimi', 'self_review', 'learn', 'hebbian', 'train_'],
    '硬件/感知': ['sensor', 'body', 'camera', 'voice', 'tts', 'asr', 'esp32', 'vision', 'audio', 'vqvae', 'image_ocr'],
    '创作/媒体': ['generat', 'literary', 'aesthetic', 'visualizer', 'creative'],
    '核心/启动': ['start', 'boot', 'core', 'daemon', 'watchdog', 'snapshot', 'health', 'monitor', 'config'],
    '移动端': ['mobile', 'phone', 'sync_server'],
    '测试': ['test_', 'benchmark', 'debug', 'verify', 'check'],
}

for f in files:
    matched = False
    for cat, kws in all_keywords.items():
        if any(k in f['name'].lower() for k in kws):
            cats.setdefault(cat, []).append(f['name'])
            matched = True
            break
    if not matched:
        cats.setdefault('其他', []).append(f['name'])

# 4. Check integration (who imports who)
import_graph = {}
for f in files:
    import_graph[f['name']] = []
    for imp in f['imports']:
        for i in imp:
            if i and i != '*':
                import_graph[f['name']].append(i)

# Count how many times each module is imported
imported_count = {}
for f in files:
    mod = f['name'].replace('.py', '')
    count = sum(1 for deps in import_graph.values() for d in deps if mod in d)
    imported_count[mod] = count

# 5. Output
report = []
report.append('=' * 70)
report.append('LAAP 功能全面审计报告')
report.append(f'时间: 2026-07-04')
report.append(f'aris_brain/ 目录: {len(files)} 个 .py 文件')
report.append('=' * 70)

total_size = sum(f['size'] for f in files)
total_lines = sum(f['lines'] for f in files)
report.append(f'\n总代码量: {total_size:,} bytes, {total_lines:,} 行')
syntax_ok = sum(1 for f in files if f['syntax_ok'])
report.append(f'语法通过: {syntax_ok}/{len(files)} ({syntax_ok/len(files)*100:.0f}%)')
report.append(f'语法错误: {len(files)-syntax_ok}/{len(files)}')

report.append('\n' + '=' * 70)
report.append('一、按功能分类')
report.append('=' * 70)
for cat, flist in sorted(cats.items(), key=lambda x: -len(x[1])):
    flist_sorted = sorted(flist, key=lambda x: -next(f['size'] for f in files if f['name']==x))
    cat_size = sum(next(f['size'] for f in files if f['name']==n) for n in flist_sorted)
    cat_lines = sum(next(f['lines'] for f in files if f['name']==n) for n in flist_sorted)
    cat_ok = sum(1 for n in flist_sorted if next(f['syntax_ok'] for f in files if f['name']==n))
    report.append(f'\n  {cat}: {len(flist_sorted)} 文件, {cat_size:,} bytes, {cat_lines:,} 行 (语法通过: {cat_ok}/{len(flist_sorted)})')
    
    # Top 5 largest files
    for n in flist_sorted[:5]:
        f = next(f for f in files if f['name']==n)
        ok = '✅' if f['syntax_ok'] else '❌'
        refs = imported_count.get(n.replace('.py',''), 0)
        ref_icon = '🔗' if refs > 0 else '🔌'
        classes = ', '.join(f['classes'][:3]) if f['classes'] else ''
        report.append(f'    {ok}{ref_icon} {n:40s} {f["lines"]:5d}行 {f["size"]:8,}B  {classes}')
        if not f['syntax_ok']:
            report.append(f'         ⚠️ 语法错误')
    if len(flist_sorted) > 5:
        report.append(f'         ... 还有 {len(flist_sorted)-5} 个文件')

report.append('\n' + '=' * 70)
report.append('二、当前运行中的进程')
report.append('=' * 70)
r = subprocess.run('wmic process where "name=\'python.exe\'" get ProcessId,CommandLine /format:csv 2>nul', 
                   capture_output=True, text=True, shell=True, timeout=5)
for line in r.stdout.split('\n')[1:]:
    line = line.strip()
    if line and len(line) > 20:
        parts = line.split(',')
        if len(parts) >= 3:
            pid = parts[2].strip().strip('"')
            cmd = parts[1].strip().strip('"')[:100] if parts[1] else ''
            if pid.isdigit() and 'python' in cmd.lower():
                report.append(f'  PID {pid:>6s} | {cmd[:80]}')

report.append('\n' + '=' * 70)
report.append('三、关键模块状态')
report.append('=' * 70)

key_checks = [
    ('认知引擎', [
        'aris_cognitive_bridge.py', 'cognitive_bus.py', 'cognitive_engine_v4.py',
        'aris_qre_v3.py', 'aris_emotion_engine.py', 'pi_psi_server.py',
        'aris_v12_5_engine.py', 'aris_desire_engine.py', 'aris_goal_engine.py',
        'subconscious.py', 'world_model_core.py', 'theory_of_mind.py',
    ]),
    ('记忆系统', [
        'memory_store.py', 'memory_bridge.py', 'aris_episodic_memory.py',
        'memory_consolidator.py', 'memory_hub.py', 'agi_memory.py',
    ]),
    ('语言/生成', [
        'longform_synthesizer.py', 'aris_paper_engine.py', 'chinese_prose_engine.py',
        'aris_markov_generator.py', 'aris_lm_v5.py', 'pure_quantum_conversation.py',
        'local_polish_layer.py', 'literary_engine_v2.py',
    ]),
    ('工具/规则', [
        'aris_rules_engine.py', 'aris_fusion_engine.py', 'task_supervisor.py',
    ]),
    ('通信/桥接', [
        'aris_hermes_bridge.py', 'aris_feishu_bridge.py', 'xiaozhi_mcp_bridge.py',
        'laap_sync_server.py', 'laap_mobile.py',
    ]),
    ('自进化', [
        'rsi_cycle_runner.py', 'true_rsi.py', 'evolution_engine.py', 'self_evolution.py',
        'hebbian_learner.py', 'internal_world.py',
    ]),
    ('监控/核心', [
        'aris_watchdog.py', 'auto_healer.py', 'state_snapshot.py',
        'laap_integrator.py', 'psi_core_bridge.py', 'agi_kernel.py',
    ]),
]

for group_name, modules in key_checks:
    report.append(f'\n  [{group_name}]')
    for mod in modules:
        fpath = os.path.join(brain, mod)
        if os.path.exists(fpath):
            with open(fpath, 'r', errors='replace') as fh:
                content = fh.read()
            lines = content.count('\n') + 1
            size = os.path.getsize(fpath)
            try:
                compile(content, mod, 'exec')
                ok = '✅'
            except Exception as e:
                ok = '❌'
            refs = imported_count.get(mod.replace('.py',''), 0)
            ref_icon = '🔗' if refs > 0 else '🔌'
            report.append(f'    {ok}{ref_icon} {mod:40s} {lines:5d}行 {size:8,}B')
        else:
            report.append(f'    ❌ {mod:40s} 文件不存在')

report.append('\n' + '=' * 70)
report.append('四、集成缺口分析')
report.append('=' * 70)

# Check which modules are actually used by integrator
integrator_path = os.path.join(brain, 'laap_integrator.py')
with open(integrator_path, 'r', errors='replace') as fh:
    integrator_content = fh.read()

integrated_modules = set()
for f in files:
    mod = f['name'].replace('.py', '')
    if mod in integrator_content:
        integrated_modules.add(f['name'])

# Top 30 largest files NOT in integrator
not_integrated = sorted([f for f in files if f['name'] not in integrated_modules],
                        key=lambda x: -x['lines'])[:30]

report.append(f'\n  laap_integrator 中注册的模块: {len(integrated_modules)} 个')
report.append(f'\n  最大的未集成模块 (Top 30):')
for f in not_integrated:
    ok = '✅' if f['syntax_ok'] else '❌'
    report.append(f'    {ok} {f["name"]:45s} {f["lines"]:6d}行 {f["size"]:8,}B')

report.append('\n' + '=' * 70)
report.append('五、语法错误模块清单')
report.append('=' * 70)
for f in sorted(files, key=lambda x: -x['lines']):
    if not f['syntax_ok']:
        report.append(f'  ❌ {f["name"]:45s} {f["lines"]:6d}行 {f["size"]:8,}B')

report.append('\n' + '=' * 70)
report.append('六、state/ 目录状态')
report.append('=' * 70)
state_dir = os.path.join(brain, 'state')
if os.path.exists(state_dir):
    items = os.listdir(state_dir)
    report.append(f'  共 {len(items)} 个文件/目录')
    total_state_size = 0
    for item in sorted(items)[:30]:
        item_path = os.path.join(state_dir, item)
        if os.path.isfile(item_path):
            sz = os.path.getsize(item_path)
            total_state_size += sz
            report.append(f'    📄 {item:40s} {sz:>8,}B')
        elif os.path.isdir(item_path):
            sz = sum(os.path.getsize(os.path.join(item_path, f)) for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))) if os.listdir(item_path) else 0
            total_state_size += sz
            report.append(f'    📁 {item:40s} ~{sz:>8,}B')
    report.append(f'  总大小: {total_state_size:,}B')

report.append('\n' + '=' * 70)
report.append('七、总结')
report.append('=' * 70)
report.append(f'  总文件数:     {len(files)}')
report.append(f'  总代码行数:   {total_lines:,}')
report.append(f'  总代码大小:   {total_size:,} bytes')
report.append(f'  语法通过率:   {syntax_ok}/{len(files)} ({syntax_ok/len(files)*100:.0f}%)')
report.append(f'  已集成到laap_integrator: {len(integrated_modules)}/{len(files)}')

print('\n'.join(report))
