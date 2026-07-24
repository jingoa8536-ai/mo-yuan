"""Aris 视觉微服务 — 系统 Python 运行, Hermes 通过 HTTP 调用"""
import sys, json, base64, io, os, subprocess, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from PIL import Image
import numpy as np

# EasyOCR 独立 venv 路径
OCR_VENV_PYTHON = os.path.expanduser(r'D:\LAAP\aris_brain\ocr_env\Scripts\python.exe')

# Tesseract 路径
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if not os.path.exists(TESSERACT_PATH):
    TESSERACT_PATH = os.path.expanduser(r'~\AppData\Local\Tesseract-OCR\tesseract.exe')

OCR_AVAILABLE = os.path.exists(TESSERACT_PATH)


def run_easyocr(image_path, lang='ch_sim+en'):
    """使用独立 venv 中的 EasyOCR 提取文字"""
    runner = os.path.join(os.path.dirname(__file__), 'easyocr_runner.py')
    # 移除 PYTHONPATH 中的 hermes-agent-main 路径，防止 torch/_C 目录冲突
    env = os.environ.copy()
    pp = env.get('PYTHONPATH', '')
    clean_pp = os.pathsep.join([
        p for p in pp.split(os.pathsep) 
        if p.strip() and 'hermes-agent' not in p.lower()
    ])
    env['PYTHONPATH'] = clean_pp
    try:
        r = subprocess.run(
            [OCR_VENV_PYTHON, runner, image_path],
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace',
            env=env
        )
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout.strip())
        error_msg = r.stderr[:1000] if r.stderr else "unknown error"
        return {"error": error_msg}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}


def run_tesseract(image_path, lang='eng'):
    """使用已安装的 tesseract 识别文字"""
    tess_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    tess_data = os.path.expanduser(r'~\AppData\Local\Tesseract-OCR\tessdata')
    if not os.path.exists(tess_path):
        tess_path = os.path.expanduser(r'~\AppData\Local\Tesseract-OCR\tesseract.exe')
    if not os.path.exists(tess_path):
        return None
    try:
        env = os.environ.copy()
        if os.path.exists(tess_data):
            env['TESSDATA_PREFIX'] = tess_data
        r = subprocess.run(
            [tess_path, image_path, 'stdout', '--psm', '3', '-l', lang],
            capture_output=True, text=True, timeout=60,
            encoding='utf-8', errors='replace', env=env
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception as e:
        return None

class VisionHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        data = json.loads(body)
        
        if self.path == '/analyze':
            result = self.analyze(data)
        elif self.path == '/ocr':
            result = self.ocr(data)
        elif self.path == '/ocr_enhanced':
            result = self.ocr_enhanced(data)
        elif self.path == '/health':
            result = {"status": "ok", "easyocr": True, "easyocr_venv": str(OCR_VENV_PYTHON)}
        elif self.path == '/video':
            result = self.analyze_video(data)
        else:
            result = {"error": "unknown path"}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False).encode())
    
    def analyze(self, data):
        path = data.get('path', '')
        try:
            img = Image.open(path)
            arr = np.array(img.convert('L'))
            w, h = img.size
            white = int((arr > 200).sum())
            black = int((arr < 50).sum())
            total = arr.size
            return {
                "size": f"{w}x{h}",
                "format": img.format or "unknown",
                "mode": img.mode,
                "white_pct": round(white/total*100, 1),
                "black_pct": round(black/total*100, 1),
                "type": "dark_ui" if black/total > 0.5 else ("light_content" if white/total > 0.5 else "mixed"),
                "ocr_available": os.path.exists(TESSERACT_PATH),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def ocr(self, data):
        path = data.get('path', '')
        lang = data.get('lang', 'eng')
        text = run_tesseract(path, lang)
        if text is None:
            return {"error": "tesseract not available"}
        return {"text": text, "length": len(text)}
    
    def ocr_enhanced(self, data):
        """EasyOCR 增强版文字提取"""
        path = data.get('path', '')
        if not os.path.exists(path):
            return {"error": "file not found"}
        result = run_easyocr(path)
        return {
            "source": os.path.basename(path),
            "text": "\n".join(item["text"] for item in result) if isinstance(result, list) else str(result),
            "items": result,
            "total_items": len(result) if isinstance(result, list) else 0,
        }
    
    def analyze_video(self, data):
        path = data.get('path', '')
        max_frames = data.get('max_frames', 10)
        lang = data.get('lang', 'eng')
        ffmpeg = os.path.expanduser(r'~\ffmpeg\ffmpeg.exe')
        
        if not os.path.exists(ffmpeg):
            return {"error": "ffmpeg not found"}
        if not os.path.exists(path):
            return {"error": "file not found"}
        
        tmpdir = tempfile.mkdtemp()
        frames = []
        
        try:
            # 获取时长
            info = subprocess.run([ffmpeg, '-i', path], capture_output=True, text=True, timeout=30)
            duration = "未知"
            for line in info.stderr.split('\n'):
                if 'Duration' in line:
                    duration = line.strip()
                    break
            
            # 均匀抽帧
            out_pat = os.path.join(tmpdir, 'f_%03d.jpg')
            subprocess.run([ffmpeg, '-i', path, '-vf', 'fps=1/2', '-vframes', str(max_frames),
                          '-q:v', '2', out_pat], capture_output=True, timeout=120)
            
            for f in sorted(Path(tmpdir).glob('f_*.jpg')):
                img = Image.open(f)
                arr = np.array(img.convert('L'))
                w, h = img.size
                white = int((arr > 200).sum())
                black = int((arr < 50).sum())
                total = arr.size
                
                text = run_tesseract(str(f), lang) or ""
                frames.append({
                    "frame": int(f.stem.split('_')[1]),
                    "size": f"{w}x{h}",
                    "type": "dark_ui" if black/total > 0.5 else "light",
                    "text": text[:300],
                })
            
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {"video": os.path.basename(path), "duration": duration, "frames": frames}
        except Exception as e:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {"error": str(e)}
    
    def log_message(self, *a):
        pass

    def do_GET(self):
        """健康检查端点"""
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "easyocr": True,
                "easyocr_venv": str(OCR_VENV_PYTHON)
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()

port = 18923
server = HTTPServer(('127.0.0.1', port), VisionHandler)
print(f'{"✅" if OCR_AVAILABLE else "⚠️"} Aris Vision Microservice on :{port} (EasyOCR via {OCR_VENV_PYTHON})')
server.serve_forever()
