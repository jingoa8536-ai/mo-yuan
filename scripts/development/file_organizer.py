"""
Aris 智能文件分类整理器 v1
============================
用法：
  python file_organizer.py --scan desktop     # 只看桌面（预览）
  python file_organizer.py --scan desktop --execute  # 真的移动

分类:
  images/ videos/ audio/ documents/ code/ archives/ data/ other/
  
大文件清理建议：
  - 桌面 海浪之约.mp4 (1.6GB) → 移动到 videos/项目视频/
"""

import os, shutil, sys, argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

IMAGE_EXT = {'.jpg','.jpeg','.png','.gif','.bmp','.webp','.svg','.ico','.tiff','.tif'}
VIDEO_EXT = {'.mp4','.mov','.avi','.mkv','.wmv','.flv','.webm','.m4v','.3gp'}
AUDIO_EXT = {'.mp3','.wav','.flac','.aac','.ogg','.wma','.m4a','.opus'}
DOC_EXT   = {'.doc','.docx','.xls','.xlsx','.ppt','.pptx','.pdf','.txt','.md','.csv','.json','.yaml','.yml','.toml','.cfg','.ini','.rtf'}
CODE_EXT  = {'.py','.js','.ts','.tsx','.jsx','.java','.cpp','.c','.h','.go','.rs','.rb','.sh','.bat','.ps1','.sql','.vue'}
ARCH_EXT  = {'.zip','.tar','.gz','.bz2','.xz','.7z','.rar'}
DESIGN_EXT= {'.psd','.ai','.sketch','.blend','.stl','.obj','.fbx','.glb'}

def size_str(b):
    if b < 1024: return f"{b}B"
    if b < 1024**2: return f"{b/1024:.0f}KB"
    if b < 1024**3: return f"{b/1024**2:.1f}MB"
    return f"{b/1024**3:.2f}GB"

def classify(name):
    ext = Path(name).suffix.lower()
    n = Path(name).stem.lower()
    if ext in IMAGE_EXT:
        for kw, sub in [(['screenshot','截图','snip','capture'],'截图'),(['ai','生成','midjourney','dalle','stable'],'AI生成'),(['photo','照片','img_','dsc_'],'照片'),(['project','项目','素材','asset','品牌','logo','banner','海报'],'项目素材')]:
            if any(k in n for k in kw): return ('图片',sub)
        return ('图片','其他')
    if ext in VIDEO_EXT:
        for kw, sub in [(['project','项目','demo','展示','成品','成片','final'],'项目视频'),(['raw','素材','source','footage','clip'],'素材'),(['tutorial','教程','教学'],'教程')]:
            if any(k in n for k in kw): return ('视频',sub)
        return ('视频','其他')
    if ext in AUDIO_EXT:
        for kw, sub in [(['music','音乐','配乐','song','track','cover','remix'],'音乐'),(['voice','语音','speech','录音','aris_speech'],'语音'),(['sfx','音效','sound','effect'],'音效')]:
            if any(k in n for k in kw): return ('音频',sub)
        return ('音频','其他')
    if ext in DOC_EXT:
        for kw, sub in [(['项目','project','方案','proposal','BP','商业','计划书'],'项目文档'),(['技术','tech','代码','架构','design','api','spec'],'技术文档'),(['合同','contract'],'合同')]:
            if any(k in n for k in kw): return ('文档',sub)
        return ('文档','其他')
    if ext in CODE_EXT:
        lm = {'.py':'Python','.js':'JS','.ts':'TS','.tsx':'React','.jsx':'React','.java':'Java','.cpp':'C++','.go':'Go','.rs':'Rust','.sh':'Shell','.sql':'SQL'}
        return ('代码',lm.get(ext,'其他'))
    if ext in ARCH_EXT: return ('压缩包','归档')
    if ext in DESIGN_EXT: return ('设计文件','项目文件')
    return ('其他','未分类')

def scan_files(root, depth=2, min_size=0):
    files = []
    skip_dirs = {'__pycache__','.git','.venv','node_modules','.hermes','chroma_db','.codegraph','$RECYCLE.BIN','System Volume Information'}
    skip_ext = {'.lnk','.tmp','.dll','.exe','.sys','.part'}
    try:
        for item in Path(root).rglob('*'):
            if len(item.relative_to(Path(root)).parts) > depth: continue
            if not item.is_file(): continue
            if item.name.startswith(('.','~$','_tmp')): continue
            if any(p in skip_dirs for p in item.parts): continue
            if item.suffix.lower() in skip_ext: continue
            try:
                sz = item.stat().st_size
                if sz < min_size: continue
                if sz > 2*1024**3: continue
                files.append({'path':str(item),'name':item.name,'size':sz,'modified':datetime.fromtimestamp(item.stat().st_mtime)})
            except: pass
    except: pass
    return files

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--scan', default='desktop')
    p.add_argument('--output', default=None)
    p.add_argument('--depth', type=int, default=2)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--min-size', default='0')
    args = p.parse_args()

    # 确定扫描路径
    if args.scan == 'desktop':
        scan_path = os.path.expanduser('~/Desktop')
    else:
        scan_path = args.scan
    
    output_base = args.output or os.path.expanduser('~/Desktop/文件归档')

    # 解析 min-size
    min_sz = 0
    ms = args.min_size
    if ms.endswith('MB'): min_sz = float(ms[:-2])*1024**2
    elif ms.endswith('GB'): min_sz = float(ms[:-2])*1024**3
    else: min_sz = int(ms)

    print(f"扫描: {scan_path} (深度={args.depth}, 最小={size_str(min_sz)})")
    files = scan_files(scan_path, depth=args.depth, min_size=min_sz)
    
    # 去重同名
    seen = {}
    for f in files:
        if f['name'] in seen and f['size'] <= seen[f['name']]['size']: continue
        seen[f['name']] = f
    files = list(seen.values())
    files.sort(key=lambda x: -x['size'])

    print(f"发现 {len(files)} 个文件\n")

    # 大文件警告
    big = [f for f in files if f['size'] > 100*1024**2]
    if big:
        print(f"⚠ 超大文件 (>100MB): {len(big)} 个")
        for f in big[:10]:
            print(f"  {size_str(f['size']):>10s}  {f['name']}")
        if len(big) > 10: print(f"  ...还有 {len(big)-10} 个")
        print()

    # 分类统计
    cats = defaultdict(lambda: {'n':0,'s':0})
    for f in files:
        cat, sub = classify(f['name'])
        cats[cat]['n'] += 1
        cats[cat]['s'] += f['size']

    print(f"{'分类':<12s} {'数量':>6s} {'大小':>12s}")
    print('-'*32)
    for c, s in sorted(cats.items(), key=lambda x:-x[1]['s']):
        print(f"{c:<12s} {s['n']:>6d} {size_str(s['s']):>12s}")
    print('-'*32)
    print(f"{'总计':<12s} {sum(s['n'] for s in cats.values()):>6d} {size_str(sum(s['s'] for s in cats.values())):>12s}")
    print()

    if not args.execute:
        print("🔍 预览模式 — 添加 --execute 来执行移动")
        print(f"   目标: {output_base}")
        return

    # 执行移动
    print(f"执行移动到 {output_base} ...")
    moved = 0
    errors = 0
    for f in files:
        cat, sub = classify(f['name'])
        tdir = Path(output_base) / cat / sub
        tpath = tdir / f['name']
        os.makedirs(str(tdir), exist_ok=True)
        if tpath.exists():
            stem = tpath.stem
            suf = tpath.suffix
            c = 1
            while tpath.exists():
                tpath = tdir / f"{stem}_{c}{suf}"
                c += 1
        try:
            shutil.move(f['path'], str(tpath))
            print(f"  ✅ {f['name']} → {cat}/{sub}/")
            moved += 1
        except Exception as e:
            print(f"  ❌ {f['name']}: {e}")
            errors += 1

    print(f"\n✅ 完成: 移动 {moved} 个, 失败 {errors} 个")

if __name__ == '__main__':
    main()
