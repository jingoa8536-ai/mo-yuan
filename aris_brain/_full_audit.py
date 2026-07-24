"""
LAAP Full Audit v1.0
Comprehensive audit of all modules, engines, and capabilities
"""
import os, sys, json, subprocess, importlib.util, time, re

sys.path.insert(0, 'D:/LAAP/aris_brain')
brain = 'D:/LAAP/aris_brain'
results = {
    'total_py_files': 0,
    'total_lines': 0,
    'total_bytes': 0,
    'importable': 0,
    'import_fail': 0,
    'categories': {},
    'running_processes': [],
    'state_files': [],
    'key_modules': {},
    'gaps': [],
}

# 1. FILE INVENTORY
all_files = []
for f in sorted(os.listdir(brain)):
    if f.endswith('.py') and not f.startswith('_') and f != '__init__.py':
        fpath = os.path.join(brain, f)
        size = os.path.getsize(fpath)
        with open(fpath, 'r', errors='replace') as fh:
            lines = fh.readlines()
            line_count = len(lines)
        all_files.append((f, size, line_count))

results['total_py_files'] = len(all_files)
results['total_bytes'] = sum(s for _, s, _ in all_files)
results['total_lines'] = sum(l for _, _, l in all_files)

# 2. CATEGORIZE
cats = {
    '🧠 认知核心 (PSI/QRE/情感/意识)': {},
    '💾 记忆系统': {},
    '🗣️ 语言/文本生成': {},
    '💻 编程/代码智能': {},
    '🌐 互联网/通信/桥接': {},
    '🛠️ 工具/CLI/集成': {},
    '🔄 自进化/学习': {},
    '🏠 硬件/语音/视觉': {},
    '🎨 创作/媒体': {},
    '⚙️ 核心/启动/监控': {},
    '📱 移动端': {},
    '🧪 测试/基准': {},
}

cat_keywords = {
    '🧠 认知核心 (PSI/QRE/情感/意识)': ['psi', 'qre', 'emotion', 'cognitive', 'conscious', 'reasoning', 'inference', 'world_model', 'brain', 'cortex', 'v12', 'thought', 'intel', 'identity', 'theory_of_mind', 'dmn', 'subconscious', 'desire', 'goal', 'metacog'],
    '💾 记忆系统': ['memory', 'knowledge', 'kb_', 'episodic', 'experience', 'storage', 'consolidat', 'retriev'],
    '🗣️ 语言/文本生成': ['lm_v', 'llm', 'psilang', 'qlg', 'language', 'markov', 'prose', 'paragraph', 'longform', 'paper', 'polish', 'essay', 'synthesizer', 'glg', 'chinese_'],
    '💻 编程/代码智能': ['code_kernel', 'harness', 'cua', 'codegraph', 'code_workspace', 'task_supervisor', 'project_planner', 'compiler', 'static'],
    '🌐 互联网/通信/桥接': ['web_search', 'internet', 'xiaozhi', 'mqtt', 'feishu', 'arxiv', 'mcp', 'channel', 'bridge', 'gateway', 'hermes'],
    '🛠️ 工具/CLI/集成': ['rules_engine', 'cli', 'launcher', 'launch', 'task_router', 'fusion_engine', 'tool', 'ipc', 'handshake', 'protocol'],
    '🔄 自进化/学习': ['rsi', 'evolution', 'self_evolv', 'self_optimi', 'self_review', 'learn', 'train', 'hebbian', 'autonomy'],
    '🏠 硬件/语音/视觉': ['sensor', 'body', 'camera', 'voice', 'tts', 'asr', 'esp32', 'vision', 'audio', 'vqvae', 'image'],
    '🎨 创作/媒体': ['generat', 'creative', 'literary', 'music', 'video', 'aesthetic', 'visual'],
    '⚙️ 核心/启动/监控': ['start', 'boot', 'core', 'config', 'daemon', 'watchdog', 'snapshot', 'health', 'monitor'],
    '📱 移动端': ['mobile', 'phone', 'sync'],
    '🧪 测试/基准': ['test', 'benchmark', 'debug', 'verify', 'check'],
}

for f, size, lines in all_files:
    matched = False
    for cat, files_dict in cats.items():
        if cat == '📦 未分类':
            continue
        if any(k in f.lower() for k in cat_keywords[cat]):
            files_dict[f] = {'size': size, 'lines': lines}
            matched = True
            break
    if not matched:
        if '📦 未分类' not in cats:
            cats['📦 未分类'] = {}
        cats['📦 未分类'][f] = {'size': size, 'lines': lines}

results['categories'] = {k: {'count': len(v), 'total_lines': sum(d['lines'] for d in v.values()), 'files': v} for k, v in cats.items()}

# 3. IMPORT CHECK (quick - use importlib)
importable = 0
fail = 0
failed_details = []
for f, size, lines in all_files[:80]:  # Check top 80
    mod = f.replace('.py', '')
    try:
        importlib.import_module(mod)
        importable += 1
    except Exception as e:
        fail += 1
        failed_details.append((f, str(e)[:60]))

results['importable'] = importable
results['import_fail'] = fail

# 4. CHECK RUNNING PROCESSES
r = subprocess.run('wmic process where "name=\'python.exe\'" get ProcessId,CommandLine /format:csv 2>nul', 
                   capture_output=True, text=True, shell=True, timeout=10)
for line in r.stdout.split('\n'):
    if 'python' in line.lower() and len(line) > 20:
        parts = line.split(',')
        if len(parts) >= 3:
            cmd = parts[1][:100] if len(parts[1]) > 100 else parts[1]
            pid = parts[2].strip().strip('"')
            if pid.isdigit():
                results['running_processes'].append({'pid': int(pid), 'cmd': cmd.strip('"')})

# 5. STATE FILES
state_dir = os.path.join(brain, 'state')
if os.path.exists(state_dir):
    for f in sorted(os.listdir(state_dir))[:20]:
        fpath = os.path.join(state_dir, f)
        results['state_files'].append({'file': f, 'size': os.path.getsize(fpath)})

# 6. KEY MODULE DEEP CHECK
key_modules = {
    'laap_integrator': 'laap_integrator.py',
    'cognitive_bus': 'cognitive_bus.py',
    'aris_emotion_engine': 'aris_emotion_engine.py',
    'aris_rules_engine': 'aris_rules_engine.py',
    'aris_fusion_engine': 'aris_fusion_engine.py',
    'aris_paper_engine': 'aris_paper_engine.py',
    'longform_synthesizer': 'longform_synthesizer.py',
    'memory_store': 'memory_store.py',
    'aris_episodic_memory': 'aris_episodic_memory.py',
    'aris_desire_engine': 'aris_desire_engine.py',
    'aris_goal_engine': 'aris_goal_engine.py',
    'rsi_cycle_runner': 'rsi_cycle_runner.py',
    'laap_sync_server': 'laap_sync_server.py',
    'laap_mobile': 'laap_mobile.py',
    'aris_hermes_bridge': 'aris_hermes_bridge.py',
    'aris_feishu_bridge': 'aris_feishu_bridge.py',
    'psi_core_bridge': 'psi_core_bridge.py',
    'agi_kernel': 'agi_kernel.py',
    'aris_watchdog': 'aris_watchdog.py',
    'state_snapshot': 'state_snapshot.py',
    'hebbian_learner': 'hebbian_learner.py',
    'internal_world': 'internal_world.py',
    'emotional_engine': 'emotional_engine.py',
    'aris_subconscious': 'aris_subconscious.py',
    'chinese_prose_engine': 'chinese_prose_engine.py',
}

for name, fname in key_modules.items():
    fpath = os.path.join(brain, fname)
    if not os.path.exists(fpath):
        results['key_modules'][name] = {'status': 'NOT FOUND', 'size': 0, 'lines': 0}
        continue
    
    size = os.path.getsize(fpath)
    with open(fpath, 'r', errors='replace') as fh:
        content = fh.read()
        lines = content.count('\n') + 1
    
    # Check imports
    imports = re.findall(r'^(?:from|import) (\S+)', content, re.MULTILINE)
    
    # Check if has main class/func
    has_class = bool(re.search(r'^\s*class\s+\w+', content, re.MULTILINE))
    has_def = bool(re.search(r'^\s*(?:async\s+)?def\s+\w+', content, re.MULTILINE))
    
    # Check if it can be imported
    can_import = False
    err = ''
    try:
        spec = importlib.util.spec_from_file_location(name, fpath)
        if spec:
            # Don't actually import, just check syntax
            compile(content, fname, 'exec')
            can_import = True
    except Exception as e:
        err = str(e)[:80]
    
    results['key_modules'][name] = {
        'file': fname,
        'size': size,
        'lines': lines,
        'has_class': has_class,
        'has_def': has_def,
        'syntax_ok': can_import,
        'error': err,
        'imports': imports[:10],
    }

print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
