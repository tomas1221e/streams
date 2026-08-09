import os,time
from flask import Flask,jsonify,render_template,request
from werkzeug.utils import secure_filename
from config import HOST,PORT,STATIC_DIR,TEMPLATES_DIR,UPLOAD_FOLDER,MAX_UPLOAD_MB
from core.database import (
    init_db,get_channel,create_channel,update_channel,delete_channel,list_outputs,get_output,
    create_output,update_output,delete_output,get_logs,add_output_key,remove_output_key,replace_output_key
)
from core.stream_manager import manager,autostart

app=Flask(__name__,static_folder=STATIC_DIR,template_folder=TEMPLATES_DIR)
app.config["UPLOAD_FOLDER"]=UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"]=MAX_UPLOAD_MB*1024*1024
init_db()

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/state")
def api_state():
    status=manager.status(); channels=list(status.values())
    return jsonify({
        "channels":status,
        "dashboard":{
            "channels":len(channels),"running_channels":sum(1 for c in channels if c["running"]),
            "outputs":sum(len(c["outputs"]) for c in channels),
            "running_outputs":sum(1 for c in channels for o in c["outputs"] if o["status"]=="running")
        },
        "performance":manager.performance(),
        "logs":get_logs(limit=80)
    })

@app.route("/api/performance")
def api_performance(): return jsonify(manager.performance())

@app.route("/api/dashboard")
def dashboard():
    status=manager.status(); channels=list(status.values())
    return jsonify({"channels":len(channels),"running_channels":sum(1 for c in channels if c["running"]),
                    "outputs":sum(len(c["outputs"]) for c in channels),
                    "running_outputs":sum(1 for c in channels for o in c["outputs"] if o["status"]=="running"),
                    "performance":manager.performance()})

@app.route("/api/channels")
def api_channels(): return jsonify(manager.status())

@app.route("/api/channels",methods=["POST"])
def api_create_channel():
    data=request.get_json(silent=True) or {}; source=(data.get("source") or "").strip()
    if not source:return jsonify({"error":"المصدر مطلوب"}),400
    channel=create_channel(data)
    if data.get("start"):manager.start_channel(channel["id"])
    return jsonify(manager.status()[channel["id"]]),201

@app.route("/api/channels/<channel_id>",methods=["GET","PUT","DELETE"])
def api_channel(channel_id):
    channel=get_channel(channel_id)
    if not channel:return jsonify({"error":"القناة غير موجودة"}),404
    if request.method=="GET":
        return jsonify({**channel,"enabled":bool(channel["enabled"]),"auto_start":bool(channel["auto_start"]),
                        "outputs":list_outputs(channel_id)})
    if request.method=="DELETE":
        manager.stop_channel(channel_id); delete_channel(channel_id); return jsonify({"status":"deleted"})
    return jsonify(update_channel(channel_id,request.get_json(silent=True) or {}))

@app.route("/api/channels/<channel_id>/start",methods=["POST"])
def start_channel(channel_id):
    if not get_channel(channel_id):return jsonify({"error":"القناة غير موجودة"}),404
    return jsonify({"status":"started","results":manager.start_channel(channel_id)})

@app.route("/api/channels/<channel_id>/stop",methods=["POST"])
def stop_channel(channel_id):
    if not get_channel(channel_id):return jsonify({"error":"القناة غير موجودة"}),404
    manager.stop_channel(channel_id); return jsonify({"status":"stopped"})

@app.route("/api/channels/<channel_id>/preview",methods=["POST"])
def preview_channel(channel_id):
    image=manager.preview(channel_id)
    return jsonify({"preview":image}) if image else (jsonify({"error":"تعذر الحصول على المعاينة"}),400)

@app.route("/api/channels/<channel_id>/probe",methods=["POST"])
def probe_channel(channel_id): return jsonify(manager.probe(channel_id))

@app.route("/api/channels/<channel_id>/outputs",methods=["GET","POST"])
def api_outputs(channel_id):
    if not get_channel(channel_id):return jsonify({"error":"القناة غير موجودة"}),404
    if request.method=="GET":return jsonify(list_outputs(channel_id))
    data=request.get_json(silent=True) or {}
    if not (data.get("server") or "").strip():return jsonify({"error":"Server URL مطلوب"}),400
    output=create_output(channel_id,data)
    if data.get("start"):manager.start_output(output["id"])
    return jsonify(output),201

@app.route("/api/outputs/<output_id>",methods=["GET","PUT","DELETE"])
def api_output(output_id):
    output=get_output(output_id)
    if not output:return jsonify({"error":"البث غير موجود"}),404
    if request.method=="GET":return jsonify(output)
    if request.method=="DELETE":
        manager.stop_output(output_id);delete_output(output_id);return jsonify({"status":"deleted"})
    data=request.get_json(silent=True) or {}
    # Never overwrite the stored key just because the UI only submitted settings.
    data.pop("stream_key",None)
    old=output; updated=update_output(output_id,data)
    if manager.is_running(output_id):
        changed=any(old.get(k)!=updated.get(k) for k in ("server","mode","video_codec","video_bitrate","resolution","fps","preset",
                                                           "quality_preset","sharpen","denoise","deblock","brightness","contrast",
                                                           "saturation","gamma","scaling","audio_bitrate","extra_args","stream_key"))
        if changed: manager.restart_output(output_id)
    return jsonify(updated)

@app.route("/api/outputs/<output_id>/key",methods=["POST"])
def change_key(output_id):
    output=get_output(output_id)
    if not output:return jsonify({"error":"البث غير موجود"}),404
    key=(request.get_json(silent=True) or {}).get("stream_key","").strip()
    if not key:return jsonify({"error":"المفتاح فارغ"}),400
    keys=output["stream_keys"]
    if keys: keys[0]=key
    else: keys=[key]
    updated=update_output(output_id,{"stream_keys":keys})
    if manager.is_running(output_id):manager.restart_output(output_id)
    return jsonify({"status":"updated","output_id":output_id})

@app.route("/api/outputs/<output_id>/keys",methods=["GET","POST"])
def output_keys(output_id):
    output=get_output(output_id)
    if not output:return jsonify({"error":"البث غير موجود"}),404
    if request.method=="GET":
        return jsonify({"keys":[{"index":i,"key":k} for i,k in enumerate(output["stream_keys"])],"count":len(output["stream_keys"])})
    key=(request.get_json(silent=True) or {}).get("stream_key","").strip()
    if not key:return jsonify({"error":"المفتاح فارغ"}),400
    updated=add_output_key(output_id,key)
    if manager.is_running(output_id):manager.restart_output(output_id)
    return jsonify({"keys":[{"index":i,"key":k} for i,k in enumerate(updated["stream_keys"])]})

@app.route("/api/outputs/<output_id>/keys/<int:index>",methods=["PUT","DELETE"])
def output_key_item(output_id,index):
    output=get_output(output_id)
    if not output:return jsonify({"error":"البث غير موجود"}),404
    if request.method=="DELETE":updated=remove_output_key(output_id,index)
    else:
        key=(request.get_json(silent=True) or {}).get("stream_key","").strip()
        if not key:return jsonify({"error":"المفتاح فارغ"}),400
        updated=replace_output_key(output_id,index,key)
    if manager.is_running(output_id):manager.restart_output(output_id)
    return jsonify({"keys":[{"index":i,"key":k} for i,k in enumerate(updated["stream_keys"])]})

@app.route("/api/outputs/<output_id>/start",methods=["POST"])
def start_output(output_id):
    ok,msg=manager.start_output(output_id)
    return jsonify({"status":"started" if ok else "error","message":msg}),(200 if ok else 400)

@app.route("/api/outputs/<output_id>/stop",methods=["POST"])
def stop_output(output_id): manager.stop_output(output_id);return jsonify({"status":"stopped"})

@app.route("/api/outputs/<output_id>/restart",methods=["POST"])
def restart_output(output_id):
    ok,msg=manager.restart_output(output_id)
    return jsonify({"status":"started" if ok else "error","message":msg}),(200 if ok else 400)

@app.route("/api/logs")
def api_logs():
    try:limit=min(int(request.args.get("limit",200)),1000)
    except Exception:limit=200
    return jsonify(get_logs(channel_id=request.args.get("channel_id"),output_id=request.args.get("output_id"),limit=limit))

@app.route("/upload_logo",methods=["POST"])
def upload_logo():
    file=request.files.get("logo")
    if not file or not file.filename:return jsonify({"error":"لم يتم اختيار ملف"}),400
    ext=os.path.splitext(file.filename)[1].lower()
    if ext not in {".png",".jpg",".jpeg",".webp"}:return jsonify({"error":"الصيغة غير مدعومة"}),400
    filename=f"logo_{int(time.time()*1000)}_{secure_filename(file.filename)}";path=os.path.join(UPLOAD_FOLDER,filename)
    file.save(path);return jsonify({"path":path,"filename":filename})

if __name__=="__main__":
    autostart();print(f"🚀 Stream Manager V4: http://localhost:{PORT}")
    app.run(host=HOST,port=PORT,debug=False,threaded=True)
