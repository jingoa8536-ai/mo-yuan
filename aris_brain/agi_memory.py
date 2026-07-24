"""
Thread-Safe Memory Manager v3 — JSON 文件持久化
=================================================
完全绕过 SQLite 的多线程限制。使用 JSON + threading.Lock。
"""

import json, time, os, threading, numpy as np
from pathlib import Path

DB_PATH = Path("D:/LAAP/aris_brain/state/agi_memory_v3.json")
_lock = threading.Lock()

DEFAULT = {"concepts": {}, "memories": [], "version": 3}

def _read():
    if DB_PATH.exists():
        try: return json.loads(DB_PATH.read_text(encoding="utf-8"))
        except: pass
    return dict(DEFAULT)

def _write(data):
    DB_PATH.write_text(json.dumps(data, ensure_ascii=False, cls=_Encoder), encoding="utf-8")

class _Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return {"__ndarray__": True, "data": obj.tolist(), "dtype": str(obj.dtype)}
        return super().default(obj)

def _decode(data):
    if isinstance(data, dict) and data.get("__ndarray__"):
        return np.array(data["data"], dtype=np.float32)
    return data

def save_vm(vm, dim=1024):
    with _lock:
        data = _read()
        # Save concepts
        for name in vm.concept_network:
            emb = vm.registers.get(f"__concept_{name}")
            if emb is not None:
                emb_list = emb.tolist() if hasattr(emb, 'tolist') else emb
                tags = vm.concept_network[name].get('tags', [])
                if isinstance(tags, list):
                    tags = [str(t) for t in tags]
                data["concepts"][str(name)] = {
                    "emb": emb_list, "valence": float(vm.concept_network[name].get('valence', 0.0)),
                    "tags": tags, "updated": time.time(),
                }
        # Save memories
        data["memories"] = []
        for content, emb, imp in vm.associative_memory:
            data["memories"].append({
                "content": str(content)[:200], "emb": emb.tolist() if hasattr(emb, 'tolist') else emb,
                "importance": float(imp), "created": time.time(),
            })
        # Keep top 10000
        data["memories"] = sorted(data["memories"], key=lambda m: -m["importance"])[:10000]
        data["version"] = 3
        _write(data)

def load_vm(vm, dim=1024):
    with _lock:
        data = _read()
        c = m = 0
        for name, info in data.get("concepts", {}).items():
            emb = np.array(info.get("emb", []), dtype=np.float32)
            if len(emb) == dim:
                vm.registers[f"__concept_{name}"] = emb
                vm.concept_network[name] = {
                    "valence": info.get("valence", 0.0),
                    "tags": info.get("tags", []),
                    "metadata": {},
                }
                c += 1
        for mem in data.get("memories", []):
            emb = np.array(mem.get("emb", []), dtype=np.float32)
            if len(emb) == dim:
                vm.associative_memory.append((mem["content"], emb, mem["importance"]))
                m += 1
    return {"concepts": c, "memories": m}

def decay(days=60, keep=20000):
    with _lock:
        data = _read()
        cutoff = time.time() - days * 86400
        data["memories"] = [m for m in data["memories"] 
                           if m.get("created", time.time()) >= cutoff or m["importance"] >= 0.3]
        data["memories"] = sorted(data["memories"], key=lambda m: -m["importance"])[:keep]
        _write(data)

def get_stats():
    with _lock:
        data = _read()
        return {"concepts": len(data.get("concepts", {})),
                "memories": len(data.get("memories", [])),
                "db_size": DB_PATH.stat().st_size if DB_PATH.exists() else 0}
