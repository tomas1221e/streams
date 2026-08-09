import os
import time

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from config import HOST, PORT, STATIC_DIR, TEMPLATES_DIR, UPLOAD_FOLDER, MAX_UPLOAD_MB
from core.database import (
    init_db, get_channel, create_channel, update_channel, delete_channel,
    list_outputs, get_output, create_output, update_output, delete_output, get_logs
)
from core.stream_manager import manager, autostart

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATES_DIR)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    status = manager.status()
    channels = list(status.values())
    return jsonify({
        "channels": status,
        "dashboard": {
            "channels": len(channels),
            "running_channels": sum(1 for c in channels if c["running"]),
            "outputs": sum(len(c["outputs"]) for c in channels),
            "running_outputs": sum(
                1 for c in channels for o in c["outputs"] if o["status"] == "running"
            ),
        },
        "logs": get_logs(limit=120),
    })


@app.route("/api/dashboard")
def dashboard():
    status = manager.status()
    channels = list(status.values())
    return jsonify({
        "channels": len(channels),
        "running_channels": sum(1 for c in channels if c["running"]),
        "outputs": sum(len(c["outputs"]) for c in channels),
        "running_outputs": sum(
            1 for c in channels for o in c["outputs"] if o["status"] == "running"
        ),
    })


@app.route("/api/channels")
def api_channels():
    return jsonify(manager.status())


@app.route("/api/channels", methods=["POST"])
def api_create_channel():
    data = request.get_json(silent=True) or {}
    source = (data.get("source") or "").strip()
    if not source:
        return jsonify({"error": "المصدر مطلوب"}), 400
    channel = create_channel(data)
    if data.get("start"):
        manager.start_channel(channel["id"])
    return jsonify(manager.status()[channel["id"]]), 201


@app.route("/api/channels/<channel_id>", methods=["GET", "PUT", "DELETE"])
def api_channel(channel_id):
    channel = get_channel(channel_id)
    if not channel:
        return jsonify({"error": "القناة غير موجودة"}), 404
    if request.method == "GET":
        return jsonify({
            **channel,
            "enabled": bool(channel["enabled"]),
            "auto_start": bool(channel["auto_start"]),
            "outputs": list_outputs(channel_id),
        })
    if request.method == "DELETE":
        manager.stop_channel(channel_id)
        delete_channel(channel_id)
        return jsonify({"status": "deleted"})
    return jsonify(update_channel(channel_id, request.get_json(silent=True) or {}))


@app.route("/api/channels/<channel_id>/start", methods=["POST"])
def start_channel(channel_id):
    if not get_channel(channel_id):
        return jsonify({"error": "القناة غير موجودة"}), 404
    results = manager.start_channel(channel_id)
    return jsonify({"status": "started", "results": results})


@app.route("/api/channels/<channel_id>/stop", methods=["POST"])
def stop_channel(channel_id):
    if not get_channel(channel_id):
        return jsonify({"error": "القناة غير موجودة"}), 404
    manager.stop_channel(channel_id)
    return jsonify({"status": "stopped"})


@app.route("/api/channels/<channel_id>/preview", methods=["POST"])
def preview_channel(channel_id):
    image = manager.preview(channel_id)
    if not image:
        return jsonify({"error": "تعذر الحصول على المعاينة"}), 400
    return jsonify({"preview": image})


@app.route("/api/channels/<channel_id>/probe", methods=["POST"])
def probe_channel(channel_id):
    return jsonify(manager.probe(channel_id))


@app.route("/api/channels/<channel_id>/outputs", methods=["GET", "POST"])
def api_outputs(channel_id):
    if not get_channel(channel_id):
        return jsonify({"error": "القناة غير موجودة"}), 404
    if request.method == "GET":
        return jsonify(list_outputs(channel_id))
    data = request.get_json(silent=True) or {}
    if not (data.get("server") or "").strip():
        return jsonify({"error": "Server URL مطلوب"}), 400
    output = create_output(channel_id, data)
    if data.get("start"):
        manager.start_output(output["id"])
    return jsonify(output), 201


@app.route("/api/outputs/<output_id>", methods=["GET", "PUT", "DELETE"])
def api_output(output_id):
    output = get_output(output_id)
    if not output:
        return jsonify({"error": "البث غير موجود"}), 404
    if request.method == "GET":
        return jsonify(output)
    if request.method == "DELETE":
        manager.stop_output(output_id)
        delete_output(output_id)
        return jsonify({"status": "deleted"})
    data = request.get_json(silent=True) or {}
    old = output
    updated = update_output(output_id, data)
    if old and old.get("stream_key") != updated.get("stream_key") and manager.is_running(output_id):
        manager.restart_output(output_id)
    return jsonify(updated)


@app.route("/api/outputs/<output_id>/key", methods=["POST"])
def change_key(output_id):
    output = get_output(output_id)
    if not output:
        return jsonify({"error": "البث غير موجود"}), 404
    data = request.get_json(silent=True) or {}
    key = (data.get("stream_key") or "").strip()
    if not key:
        return jsonify({"error": "المفتاح فارغ"}), 400
    updated = update_output(output_id, {"stream_key": key})
    if manager.is_running(output_id):
        manager.restart_output(output_id)
    return jsonify({"status": "updated", "output_id": output_id})


@app.route("/api/outputs/<output_id>/start", methods=["POST"])
def start_output(output_id):
    ok, msg = manager.start_output(output_id)
    return jsonify({"status": "started" if ok else "error", "message": msg}), (200 if ok else 400)


@app.route("/api/outputs/<output_id>/stop", methods=["POST"])
def stop_output(output_id):
    manager.stop_output(output_id)
    return jsonify({"status": "stopped"})


@app.route("/api/outputs/<output_id>/restart", methods=["POST"])
def restart_output(output_id):
    ok, msg = manager.restart_output(output_id)
    return jsonify({"status": "started" if ok else "error", "message": msg}), (200 if ok else 400)


@app.route("/api/logs")
def api_logs():
    return jsonify(get_logs(
        channel_id=request.args.get("channel_id"),
        output_id=request.args.get("output_id"),
        limit=min(int(request.args.get("limit", 300)), 1000),
    ))


@app.route("/upload_logo", methods=["POST"])
def upload_logo():
    file = request.files.get("logo")
    if not file or not file.filename:
        return jsonify({"error": "لم يتم اختيار ملف"}), 400
    allowed = {".png", ".jpg", ".jpeg", ".webp"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return jsonify({"error": "الصيغة غير مدعومة"}), 400
    filename = f"logo_{int(time.time()*1000)}_{secure_filename(file.filename)}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    return jsonify({"path": path, "filename": filename})


if __name__ == "__main__":
    autostart()
    print(f"🚀 Stream Manager V3: http://localhost:{PORT}")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
