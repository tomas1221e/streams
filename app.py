from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import json
import time

from config import HOST, PORT, STATIC_DIR, TEMPLATES_DIR, UPLOAD_FOLDER
from core.stream_manager import (
    add_channel, stop_channel, delete_channel, 
    get_channels_status, get_logs
)

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATES_DIR)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB للشعار

# الصفحة الرئيسية
@app.route('/')
def index():
    return render_template('index.html')

# رفع الشعار
@app.route('/upload_logo', methods=['POST'])
def upload_logo():
    if 'logo' not in request.files:
        return jsonify({'error': 'لا يوجد ملف'}), 400
    file = request.files['logo']
    if file.filename == '':
        return jsonify({'error': 'لم يتم اختيار ملف'}), 400
    
    # التحقق من الصيغة
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
        return jsonify({'error': 'الصيغة غير مدعومة. استخدم PNG, JPG, WEBP'}), 400
    
    # حفظ الملف باسم ثابت لتسهيل الاستخدام (أو نستخدم اسم فريد)
    filename = f"logo_{int(time.time())}.png"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    return jsonify({'path': filepath, 'filename': filename})

# معاينة الشعار (بدون تشغيل بث)
@app.route('/preview', methods=['POST'])
def preview():
    data = request.get_json()
    source = data.get('source')
    logo_settings = data.get('logo_settings')
    
    if not source:
        return jsonify({'error': 'المصدر مطلوب'}), 400
    
    from core.ffmpeg_utils import generate_preview
    preview_image = generate_preview(source, logo_settings)
    
    if preview_image:
        return jsonify({'preview': preview_image})
    else:
        return jsonify({'error': 'تعذر الحصول على المعاينة. تأكد من صحة المصدر.'}), 400

# إضافة/تحديث قناة
@app.route('/channel', methods=['POST'])
def manage_channel():
    data = request.get_json()
    key = data.get('key')
    source = data.get('source')
    action = data.get('action', 'start')  # start, stop, delete
    
    if not key:
        return jsonify({'error': 'المفتاح (Key) مطلوب'}), 400
    
    if action == 'stop':
        stop_channel(key)
        return jsonify({'status': 'stopped'})
    
    if action == 'delete':
        delete_channel(key)
        return jsonify({'status': 'deleted'})
    
    # action == 'start' or update
    if not source:
        return jsonify({'error': 'رابط المصدر (Source) مطلوب'}), 400
    
    # استخراج الإعدادات
    video_settings = data.get('video', {})
    audio_settings = data.get('audio', {})
    logo_settings = data.get('logo', {})
    
    # التأكد من وجود مسار الشعار
    if logo_settings and 'path' in logo_settings:
        if not os.path.exists(logo_settings['path']):
            logo_settings = None  # تجاهل إذا كان الملف غير موجود
    
    add_channel(key, source, video_settings, audio_settings, logo_settings)
    return jsonify({'status': 'started'})

# جلب حالة جميع القنوات
@app.route('/status')
def status():
    return jsonify(get_channels_status())

# جلب السجلات (Logs)
@app.route('/logs')
def logs():
    return jsonify(get_logs())

# تشغيل الخادم
if __name__ == '__main__':
    print("🚀 تم تشغيل الخادم على http://localhost:5000")
    print("📡 لوحة التحكم جاهزة!")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)