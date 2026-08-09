import subprocess, threading, time, re, os
from collections import defaultdict
from config import MAX_RETRIES, RETRY_DELAY, HEARTBEAT_INTERVAL
from core.database import add_log, get_channel, get_output, list_channels, list_outputs
from core.ffmpeg_utils import build_ffmpeg_command, generate_preview, probe

try:
    import psutil
except Exception:
    psutil=None

_PROGRESS_RE=re.compile(r"frame=\s*(\d+).*?fps=\s*([0-9.]+).*?bitrate=\s*([^\s]+).*?speed=\s*([0-9.]+)x")

class ProcessManager:
    def __init__(self):
        self.processes={}; self.threads={}; self.retries=defaultdict(int); self.started_at={}
        self.lock=threading.RLock(); self.preview_cache={}; self.metrics={}; self._stop_event=threading.Event()
        threading.Thread(target=self._heartbeat,daemon=True).start()

    def log(self,level,message,channel_id=None,output_id=None): add_log(level,message,channel_id,output_id)

    def start_output(self,output_id,reset_retries=True):
        output=get_output(output_id)
        if not output:return False,"Output not found"
        channel=get_channel(output["channel_id"])
        if not channel:return False,"Channel not found"
        if not output["enabled"]:return False,"Output is disabled"
        with self.lock:
            existing=self.processes.get(output_id)
            if existing and existing.poll() is None:return True,"Already running"
            if reset_retries:self.retries[output_id]=0
            return self._launch_locked(channel,output)

    def _launch_locked(self,channel,output):
        output_id,channel_id=output["id"],channel["id"]; cmd=build_ffmpeg_command(channel,output)
        safe_cmd=" ".join(cmd)
        # Hide keys from the persistent log.
        for key in output.get("stream_keys",[]):
            if key: safe_cmd=safe_cmd.replace(key,"••••••••")
        self.log("INFO",f"Starting {output['name']} | {safe_cmd}",channel_id,output_id)
        try:
            proc=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,bufsize=1)
        except Exception as exc:
            self.log("ERROR",f"FFmpeg launch failed: {exc}",channel_id,output_id); return False,str(exc)
        self.processes[output_id]=proc; self.started_at[output_id]=time.time()
        if psutil:
            try: psutil.Process(proc.pid).cpu_percent(None)
            except Exception: pass
        self.metrics[output_id]={"pid":proc.pid,"uptime":0,"returncode":None,"frame":0,"fps":0,"bitrate":"-","speed":"-","cpu":0}
        threading.Thread(target=self._watch_output,args=(channel_id,output_id,proc),daemon=True).start()
        self.log("INFO",f"Output started (PID {proc.pid})",channel_id,output_id)
        return True,"started"

    def _watch_output(self,channel_id,output_id,proc):
        try:
            for raw in proc.stderr:
                line=raw.strip()
                if not line: continue
                low=line.lower()
                m=_PROGRESS_RE.search(line)
                if m:
                    with self.lock:
                        self.metrics.setdefault(output_id,{}).update({
                            "frame":int(m.group(1)),"fps":float(m.group(2)),
                            "bitrate":m.group(3),"speed":m.group(4)+"x"
                        })
                    continue
                if "error" in low or "failed" in low or "invalid" in low:
                    self.log("ERROR",line,channel_id,output_id)
                elif "warning" in low:
                    self.log("WARNING",line,channel_id,output_id)
                elif any(x in low for x in ("connected","opening","handshake")):
                    self.log("INFO",line,channel_id,output_id)
        finally:
            rc=proc.wait()
            with self.lock:
                self.metrics.setdefault(output_id,{})["returncode"]=rc
                self.processes.pop(output_id,None)
            output=get_output(output_id)
            if not output:return
            self.log("WARNING",f"Output exited with code {rc}",channel_id,output_id)
            with self.lock:
                retries=self.retries.get(output_id,0)
                if retries<MAX_RETRIES and output["enabled"]:
                    self.retries[output_id]=retries+1; retry_no=retries+1
                else: retry_no=None
            if retry_no is not None:
                self.log("WARNING",f"Auto reconnect {retry_no}/{MAX_RETRIES} in {RETRY_DELAY}s",channel_id,output_id)
                time.sleep(RETRY_DELAY); self.start_output(output_id,reset_retries=False)
            else:self.log("ERROR","Output stopped after retry limit",channel_id,output_id)

    def stop_output(self,output_id):
        with self.lock:
            proc=self.processes.get(output_id)
            if not proc:return False
            self.retries[output_id]=MAX_RETRIES+1
            try: proc.terminate(); proc.wait(timeout=2)
            except Exception:
                try: proc.kill()
                except Exception: pass
            self.processes.pop(output_id,None); self.started_at.pop(output_id,None)
        output=get_output(output_id)
        if output:self.log("INFO","Output stopped manually",output["channel_id"],output_id)
        return True

    def restart_output(self,output_id):
        self.stop_output(output_id); self.retries[output_id]=0
        return self.start_output(output_id,reset_retries=False)

    def start_channel(self,channel_id):
        return [(o["id"],self.start_output(o["id"])[0]) for o in list_outputs(channel_id) if o["enabled"]]

    def stop_channel(self,channel_id):
        for o in list_outputs(channel_id): self.stop_output(o["id"])

    def is_running(self,output_id):
        with self.lock:
            p=self.processes.get(output_id); return bool(p and p.poll() is None)

    def _process_cpu(self,proc):
        if not psutil:return 0
        try:return round(psutil.Process(proc.pid).cpu_percent(None),1)
        except Exception:return 0

    def status(self):
        result={}
        for channel in list_channels():
            outputs=[]
            for output in list_outputs(channel["id"]):
                running=self.is_running(output["id"]); started=self.started_at.get(output["id"])
                with self.lock: metric=dict(self.metrics.get(output["id"],{}))
                proc=self.processes.get(output["id"])
                if proc and running: metric["cpu"]=self._process_cpu(proc)
                keys=output.get("stream_keys",[])
                outputs.append({
                    **output,
                    "stream_key": "",
                    "has_key":bool(keys),
                    "key_count":len(keys),
                    "key_labels":[f"مفتاح {i+1}" for i in range(len(keys))],
                    "status":"running" if running else "stopped",
                    "uptime":int(time.time()-started) if started and running else 0,
                    "pid":metric.get("pid"),"returncode":metric.get("returncode"),"retries":self.retries.get(output["id"],0),
                    "fps_live":metric.get("fps",0),"frame":metric.get("frame",0),"bitrate_live":metric.get("bitrate","-"),
                    "speed":metric.get("speed","-"),"process_cpu":metric.get("cpu",0),
                })
            result[channel["id"]]={**channel,"enabled":bool(channel["enabled"]),"auto_start":bool(channel["auto_start"]),
                                  "running":any(x["status"]=="running" for x in outputs),"outputs":outputs}
        return result

    def performance(self):
        data={"cpu":0,"ram":0,"ram_used_mb":0,"ram_total_mb":0,"ffmpeg_cpu":0,"ffmpeg_processes":len(self.processes)}
        if psutil:
            try:
                data["cpu"]=round(psutil.cpu_percent(interval=None),1)
                mem=psutil.virtual_memory(); data["ram"]=round(mem.percent,1)
                data["ram_used_mb"]=round(mem.used/1024/1024); data["ram_total_mb"]=round(mem.total/1024/1024)
                total=0
                for p in list(self.processes.values()):
                    if p.poll() is None: total += self._process_cpu(p)
                data["ffmpeg_cpu"]=round(total,1)
            except Exception: pass
        return data

    def preview(self,channel_id):
        channel=get_channel(channel_id)
        if not channel:return None
        image=generate_preview(channel["source"],{"path":channel["logo_path"],"position":channel["logo_position"],"scale":channel["logo_scale"]})
        self.preview_cache[channel_id]=image; return image

    def probe(self,channel_id):
        channel=get_channel(channel_id); return probe(channel["source"]) if channel else {"error":"Channel not found"}

    def _heartbeat(self):
        while not self._stop_event.wait(HEARTBEAT_INTERVAL): pass

manager=ProcessManager()

def autostart():
    for channel in list_channels():
        if channel["enabled"] and channel["auto_start"]:
            for output in list_outputs(channel["id"]):
                if output["enabled"] and output["auto_start"]: manager.start_output(output["id"])

def get_status(): return manager.status()
