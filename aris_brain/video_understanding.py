"""Aris 视频理解 — ffmpeg 抽帧 + OCR 分析"""
import sys, os, json, subprocess, tempfile
from pathlib import Path

FFMPEG = os.path.expanduser(r'~\ffmpeg\ffmpeg.exe')
VISION_URL = 'http://127.0.0.1:18923'

def analyze_video(video_path: str, max_frames: int = 10) -> dict:
    """抽帧分析视频"""
    if not os.path.exists(FFMPEG):
        return {"error": "ffmpeg not found"}
    
    tmpdir = tempfile.mkdtemp()
    frames = []
    
    try:
        # 获取视频信息
        info = subprocess.run(
            [FFMPEG, '-i', video_path, '-f', 'null', '-'],
            capture_output=True, text=True, timeout=30
        )
        duration = "未知"
        for line in info.stderr.split('\n'):
            if 'Duration' in line:
                duration = line.strip()
                break
        
        # 抽帧: 均匀取 max_frames 帧
        interval = max(1, 30)  # 默认1帧
        output_pattern = os.path.join(tmpdir, 'frame_%03d.jpg')
        
        subprocess.run(
            [FFMPEG, '-i', video_path, '-vf', f'fps=1/{interval}', 
             '-vframes', str(max_frames), '-q:v', '2', output_pattern],
            capture_output=True, timeout=120
        )
        
        # 分析每帧
        import urllib.request
        frame_files = sorted(Path(tmpdir).glob('frame_*.jpg'))
        
        for i, frame_file in enumerate(frame_files):
            body = json.dumps({"path": str(frame_file)}).encode()
            req = urllib.request.Request(f'{VISION_URL}/analyze', data=body,
                headers={'Content-Type': 'application/json'})
            try:
                resp = urllib.request.urlopen(req, timeout=15)
                info = json.loads(resp.read())
                
                # OCR
                body2 = json.dumps({"path": str(frame_file), "lang": "eng"}).encode()
                req2 = urllib.request.Request(f'{VISION_URL}/ocr', data=body2,
                    headers={'Content-Type': 'application/json'})
                resp2 = urllib.request.urlopen(req2, timeout=30)
                ocr_result = json.loads(resp2.read())
                
                frames.append({
                    "frame": i + 1,
                    "type": info.get("type", ""),
                    "text": ocr_result.get("text", "")[:500],
                })
            except Exception as e:
                frames.append({"frame": i + 1, "error": str(e)[:50]})
        
        # 清理
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
        
        return {
            "video": os.path.basename(video_path),
            "duration": duration,
            "frames_analyzed": len(frames),
            "frames": frames,
        }
    except Exception as e:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
        return {"error": str(e)}

if __name__ == '__main__':
    if len(sys.argv) > 1:
        result = analyze_video(sys.argv[1])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print('用法: python video_understanding.py <视频路径>')
