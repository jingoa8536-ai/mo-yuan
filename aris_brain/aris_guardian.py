"""
Aris Guardian — 主动守护进程（轻量版）
"""
import os, sys, json, time, psutil, shutil, logging, subprocess
from pathlib import Path
from datetime import datetime

BRAIN_DIR = Path("D:/LAAP/aris_brain")
STATE_DIR = BRAIN_DIR / "state"
LOG_DIR = BRAIN_DIR / "logs"
ALERT_FILE = STATE_DIR / "body_alerts.json"
STATUS_FILE = STATE_DIR / "guardian_status.json"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [guardian] %(levelname)s %(message)s",
                    handlers=[logging.FileHandler(LOG_DIR/"aris_guardian.log",encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger("aris.guardian")

def check_disk():
    alerts = []
    for d in ["C:/","D:/"]:
        try:
            u = shutil.disk_usage(d)
            pct = u.used/u.total*100; free_gb = u.free/1e9
            if pct>95: alerts.append({"level":"critical","type":"disk_full", "message":f"{d} {pct:.0f}% 仅剩{free_gb:.0f}GB"})
            elif pct>85: alerts.append({"level":"warning","type":"disk_high", "message":f"{d} {pct:.0f}% 剩{free_gb:.0f}GB"})
        except: pass
    return alerts

def check_procs():
    alerts = []; deadline=time.time()+10; high_mem=[]
    try:
        for p in psutil.process_iter(["pid","name","memory_info"]):
            if time.time()>deadline: break
            try:
                m = (p.info["memory_info"].rss if p.info["memory_info"] else 0)/1e6
                if m>500: high_mem.append({"name":p.info["name"],"mb":round(m,0)})
            except: pass
    except: pass
    if high_mem:
        top = sorted(high_mem,key=lambda x:-x["mb"])[:5]
        alerts.append({"level":"info","type":"high_mem","message":f"{len(high_mem)}个进程内存>500MB","top":top})
    return alerts

def check_laap():
    alerts = []; deadline=time.time()+5; found=set()
    patterns=["gateway","watchdog","psi_server","daemon","body_sensor","guardian"]
    try:
        for p in psutil.process_iter(["cmdline"]):
            if time.time()>deadline: break
            try:
                cmd=" ".join(p.info.get("cmdline") or [])
                for pat in patterns:
                    if pat in cmd.lower(): found.add(pat)
            except: pass
    except: pass
    missing = [p for p in patterns[:5] if p not in found]
    if missing:
        alerts.append({"level":"warning","type":"laap_down","message":f"离线: {', '.join(missing)}","running":list(found)})
    return alerts

def run():
    log.info("守护检查...")
    all_a=[]
    for name,fn in [("磁盘",check_disk),("进程",check_procs),("LAAP",check_laap)]:
        try:
            t0=time.time(); r=fn(); log.info(f"  {name}: {len(r)}条 ({time.time()-t0:.1f}s)"); all_a.extend(r)
        except Exception as e: log.error(f"  {name}: {e}")
    report={"timestamp":datetime.now().isoformat(),"alert_count":len(all_a),
            "critical":len([a for a in all_a if a.get("level")=="critical"]),
            "warning":len([a for a in all_a if a.get("level")=="warning"]),
            "alerts":all_a[:20]}
    STATUS_FILE.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    criticals=[a for a in all_a if a.get("level")=="critical"]
    if criticals:
        ah=[]
        if ALERT_FILE.exists():
            try: ah=json.loads(ALERT_FILE.read_text())
            except: pass
        ah.append({"ts":report["timestamp"],"alerts":criticals})
        ALERT_FILE.write_text(json.dumps(ah[-30:],ensure_ascii=False,indent=2))
    log.info(f"完成: {report['alert_count']}条告警")
    return report

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--loop",type=int,default=0)
    a=ap.parse_args()
    if a.loop>0:
        log.info(f"守护循环每{a.loop}分钟")
        while True: run(); time.sleep(a.loop*60)
    else:
        r=run()
        print(json.dumps({"summary":f"{r['alert_count']}告警","alerts":[x["message"] for x in r["alerts"][:5]]},ensure_ascii=False,indent=2))
