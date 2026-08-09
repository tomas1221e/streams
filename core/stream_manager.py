import subprocess
import threading
import time
from collections import defaultdict, deque

from config import MAX_RETRIES, RETRY_DELAY, HEARTBEAT_INTERVAL
from core.database import (
    add_log, get_channel, get_output, list_channels, list_outputs
)
from core.ffmpeg_utils import build_ffmpeg_command, generate_preview, probe


class ProcessManager:
    def __init__(self):
        self.processes = {}  # output_id -> Popen
        self.threads = {}
        self.retries = defaultdict(int)
        self.started_at = {}
        self.lock = threading.RLock()
        self.preview_cache = {}
        self.metrics = {}
        self._stop_event = threading.Event()
        threading.Thread(target=self._heartbeat, daemon=True).start()

    def log(self, level, message, channel_id=None, output_id=None):
        add_log(level, message, channel_id, output_id)

    def start_output(self, output_id, reset_retries=True):
        output = get_output(output_id)
        if not output:
            return False, "Output not found"
        channel = get_channel(output["channel_id"])
        if not channel:
            return False, "Channel not found"
        if not output["enabled"]:
            return False, "Output is disabled"

        with self.lock:
            existing = self.processes.get(output_id)
            if existing and existing.poll() is None:
                return True, "Already running"
            if reset_retries:
                self.retries[output_id] = 0
            self._launch_locked(channel, output)
        return True, "started"

    def _launch_locked(self, channel, output):
        output_id = output["id"]
        channel_id = channel["id"]

        cmd = build_ffmpeg_command(channel, output)
        self.log("INFO", f"Starting {output['name']} | {' '.join(cmd)}", channel_id, output_id)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            self.log("ERROR", f"FFmpeg launch failed: {exc}", channel_id, output_id)
            return

        self.processes[output_id] = proc
        self.started_at[output_id] = time.time()
        self.metrics[output_id] = {
            "pid": proc.pid,
            "uptime": 0,
            "returncode": None,
        }

        thread = threading.Thread(
            target=self._watch_output,
            args=(channel_id, output_id, proc),
            daemon=True,
        )
        self.threads[output_id] = thread
        thread.start()
        self.log("INFO", f"Output started (PID {proc.pid})", channel_id, output_id)

    def _watch_output(self, channel_id, output_id, proc):
        try:
            for line in proc.stderr:
                line = line.strip()
                if not line:
                    continue
                low = line.lower()
                if "error" in low or "failed" in low or "invalid" in low:
                    self.log("ERROR", line, channel_id, output_id)
                elif "warning" in low:
                    self.log("WARNING", line, channel_id, output_id)
                # Keep FFmpeg's useful progress/connection messages without flooding DB.
                elif any(x in low for x in ("frame=", "speed=", "connected", "opening")):
                    self.log("INFO", line, channel_id, output_id)
        finally:
            rc = proc.wait()
            with self.lock:
                self.metrics.setdefault(output_id, {})["returncode"] = rc
                self.processes.pop(output_id, None)

            output = get_output(output_id)
            if not output:
                return

            self.log("WARNING", f"Output exited with code {rc}", channel_id, output_id)

            with self.lock:
                retries = self.retries.get(output_id, 0)
                if retries < MAX_RETRIES and output["enabled"]:
                    self.retries[output_id] = retries + 1
                    retry_no = retries + 1
                else:
                    retry_no = None

            if retry_no is not None:
                self.log(
                    "WARNING",
                    f"Auto reconnect {retry_no}/{MAX_RETRIES} in {RETRY_DELAY}s",
                    channel_id,
                    output_id,
                )
                time.sleep(RETRY_DELAY)
                self.start_output(output_id, reset_retries=False)
            else:
                self.log("ERROR", "Output stopped after retry limit", channel_id, output_id)

    def stop_output(self, output_id):
        with self.lock:
            proc = self.processes.get(output_id)
            if not proc:
                return False
            self.retries[output_id] = MAX_RETRIES + 1
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self.processes.pop(output_id, None)
            self.started_at.pop(output_id, None)

        output = get_output(output_id)
        if output:
            self.log("INFO", "Output stopped manually", output["channel_id"], output_id)
        return True

    def restart_output(self, output_id):
        self.stop_output(output_id)
        self.retries[output_id] = 0
        return self.start_output(output_id, reset_retries=False)

    def start_channel(self, channel_id):
        outputs = list_outputs(channel_id)
        results = []
        for output in outputs:
            if output["enabled"]:
                results.append((output["id"], self.start_output(output["id"])[0]))
        return results

    def stop_channel(self, channel_id):
        for output in list_outputs(channel_id):
            self.stop_output(output["id"])

    def channel_running(self, channel_id):
        return any(
            self.is_running(o["id"]) for o in list_outputs(channel_id)
        )

    def is_running(self, output_id):
        with self.lock:
            proc = self.processes.get(output_id)
            return bool(proc and proc.poll() is None)

    def status(self):
        result = {}
        for channel in list_channels():
            outputs = []
            for output in list_outputs(channel["id"]):
                running = self.is_running(output["id"])
                started = self.started_at.get(output["id"])
                uptime = int(time.time() - started) if started and running else 0
                outputs.append({
                    **output,
                    "stream_key": "••••••••" if output["stream_key"] else "",
                    "status": "running" if running else "stopped",
                    "uptime": uptime,
                    "pid": self.metrics.get(output["id"], {}).get("pid"),
                    "returncode": self.metrics.get(output["id"], {}).get("returncode"),
                    "retries": self.retries.get(output["id"], 0),
                })
            result[channel["id"]] = {
                **channel,
                "enabled": bool(channel["enabled"]),
                "auto_start": bool(channel["auto_start"]),
                "running": any(x["status"] == "running" for x in outputs),
                "outputs": outputs,
            }
        return result

    def preview(self, channel_id):
        channel = get_channel(channel_id)
        if not channel:
            return None
        image = generate_preview(
            channel["source"],
            {
                "path": channel["logo_path"],
                "position": channel["logo_position"],
                "scale": channel["logo_scale"],
            },
        )
        self.preview_cache[channel_id] = image
        return image

    def probe(self, channel_id):
        channel = get_channel(channel_id)
        if not channel:
            return {"error": "Channel not found"}
        return probe(channel["source"])

    def _heartbeat(self):
        while not self._stop_event.wait(HEARTBEAT_INTERVAL):
            with self.lock:
                current = list(self.processes.items())
            for output_id, proc in current:
                if proc.poll() is not None:
                    # watcher thread handles reconnect
                    continue


manager = ProcessManager()


def autostart():
    for channel in list_channels():
        if channel["enabled"] and channel["auto_start"]:
            for output in list_outputs(channel["id"]):
                if output["enabled"] and output["auto_start"]:
                    manager.start_output(output["id"])


def get_status():
    return manager.status()
