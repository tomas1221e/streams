import subprocess
import threading
import time
import copy
import logging
from concurrent.futures import ThreadPoolExecutor
from collections import deque

from config import MAX_RETRIES, HEARTBEAT_INTERVAL
from core.ffmpeg_utils import build_ffmpeg_command, generate_preview

# إعداد نظام السجلات (Logs) المخزن في الذاكرة لعرضه بالواجهة
class LogBuffer:
    def __init__(self, max_lines=200):
        self.buffer = deque(maxlen=max_lines)
        self.lock = threading.Lock()
    
    def add(self, level, message):
        with self.lock:
            self.buffer.append(f"[{level}] {message}")
    
    def get_all(self):
        with self.lock:
            return list(self.buffer)

# إنشاء كائن السجلات العام
system_logs = LogBuffer()

# إعداد الـ Logger الداخلي
logger = logging.getLogger('StreamManager')
logger.setLevel(logging.INFO)

# حالة القنوات (لكل مفتاح)
# structure: {
#   'key': {
#       'source': 'url',
#       'status': 'stopped' | 'running' | 'error' | 'starting',
#       'process': None (Popen object),
#       'thread': None,
#       'retries': 0,
#       'video_settings': {...},
#       'audio_settings': {...},
#       'logo_settings': {...},
#       'preview': 'base64_image' or None
#   }
# }
channels = {}
channels_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=10)

def get_channels_status():
    """إرجاع نسخة آمنة من حالة جميع القنوات للواجهة"""
    with channels_lock:
        # نحذف الـ Process و Thread من النسخة لأنها غير قابلة للـ JSON
        safe_status = {}
        for key, data in channels.items():
            safe_status[key] = {
                'source': data.get('source'),
                'status': data.get('status', 'stopped'),
                'retries': data.get('retries', 0),
                'preview': data.get('preview'),  # قد يكون كبيراً، لكننا نرسله
                'video': data.get('video_settings'),
                'audio': data.get('audio_settings'),
                'logo': data.get('logo_settings', {}).get('path') is not None
            }
        return safe_status

def add_channel(key, source, video_settings, audio_settings, logo_settings):
    """إضافة قناة جديدة (أو تحديث قناة موجودة) وبدء تشغيلها"""
    with channels_lock:
        # إذا كانت موجودة، نوقفها أولاً
        if key in channels:
            _stop_channel_unsafe(key)
        
        channels[key] = {
            'source': source,
            'status': 'starting',
            'process': None,
            'thread': None,
            'retries': 0,
            'video_settings': video_settings,
            'audio_settings': audio_settings,
            'logo_settings': logo_settings,
            'preview': None
        }
    
    # بدء تشغيل القناة في خيط منفصل
    future = executor.submit(_run_stream, key)
    # نربط الـ future بالـ channel لمتابعته (اختياري)
    return True

def _run_stream(key):
    """الخيط الرئيسي لتشغيل وبث قناة معينة مع إعادة محاولة ذكية"""
    while True:
        with channels_lock:
            if key not in channels:
                return  # تم حذف القناة
            data = channels[key]
            source = data['source']
            video_settings = data['video_settings']
            audio_settings = data['audio_settings']
            logo_settings = data['logo_settings']
            data['status'] = 'starting'
            system_logs.add('INFO', f"جاري تشغيل القناة {key} ...")

        # بناء الأمر
        cmd = build_ffmpeg_command(source, key, video_settings, audio_settings, logo_settings)
        
        # تشغيل العملية
        try:
            # استخدام CREATE_NO_WINDOW في Windows لتجنب ظهور نافذة (اختياري)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # تحديث الحالة
            with channels_lock:
                if key in channels:
                    channels[key]['process'] = proc
                    channels[key]['status'] = 'running'
                    channels[key]['retries'] = 0
                    # تحديث المعاينة في الخلفية (بدون تعطيل الخيط)
                    threading.Thread(target=_update_preview, args=(key,), daemon=True).start()
            
            system_logs.add('INFO', f"✅ بدأ بث القناة {key} بنجاح.")
            
            # مراقبة العملية أثناء التشغيل (قراءة stderr لتسجيل الأخطاء)
            for line in proc.stderr:
                if not line:
                    continue
                # تسجيل الأخطاء التحذيرية فقط
                if 'error' in line.lower() or 'failed' in line.lower():
                    system_logs.add('ERROR', f"[{key}] {line.strip()}")
                else:
                    system_logs.add('INFO', f"[{key}] {line.strip()}")
            
            # إذا خرجنا من الحلقة، يعني أن العملية توقفت
            proc.wait()
            
            # التحقق من سبب التوقف
            with channels_lock:
                if key not in channels:
                    return
                data = channels[key]
                if data['status'] == 'stopped':
                    system_logs.add('INFO', f"🛑 توقف بث القناة {key} يدويًا.")
                    return
                
                # محاولة إعادة التشغيل
                retries = data.get('retries', 0)
                if retries < MAX_RETRIES:
                    data['retries'] = retries + 1
                    data['status'] = 'error'
                    system_logs.add('WARNING', f"⚠️ توقف بث {key}، إعادة محاولة {retries+1}/{MAX_RETRIES} ...")
                    time.sleep(5)  # انتظار قصير قبل إعادة المحاولة
                    continue  # إعادة تشغيل الحلقة
                else:
                    data['status'] = 'error'
                    system_logs.add('ERROR', f"❌ فشل بث {key} بعد {MAX_RETRIES} محاولات.")
                    return
                    
        except Exception as e:
            system_logs.add('ERROR', f"🔥 خطأ في تشغيل {key}: {str(e)}")
            with channels_lock:
                if key in channels:
                    channels[key]['status'] = 'error'
            time.sleep(5)

def _update_preview(key):
    """تحديث صورة المعاينة للقناة في الخلفية"""
    with channels_lock:
        if key not in channels:
            return
        data = channels[key]
        source = data['source']
        logo_settings = data.get('logo_settings')
    
    preview = generate_preview(source, logo_settings)
    with channels_lock:
        if key in channels:
            channels[key]['preview'] = preview

def stop_channel(key):
    """إيقاف قناة معينة"""
    with channels_lock:
        _stop_channel_unsafe(key)

def _stop_channel_unsafe(key):
    """إيقاف قناة (بدون قفل، يُستخدم داخليًا)"""
    if key not in channels:
        return
    data = channels[key]
    data['status'] = 'stopped'
    proc = data.get('process')
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except:
            try:
                proc.kill()
            except:
                pass
    data['process'] = None
    system_logs.add('INFO', f"🛑 تم إيقاف القناة {key}.")

def delete_channel(key):
    """حذف قناة نهائيًا"""
    with channels_lock:
        if key in channels:
            _stop_channel_unsafe(key)
            del channels[key]
            system_logs.add('INFO', f"🗑️ تم حذف القناة {key}.")

def get_logs():
    """إرجاع السجلات من الذاكرة"""
    return system_logs.get_all()

# تشغيل خيط نبضات القلب (Heartbeat) لمراقبة العمليات الميتة
def heartbeat_loop():
    """خيط دوري للتأكد من أن العمليات ما زالت حية، وإعادة تشغيلها إذا لزم الأمر"""
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        with channels_lock:
            for key, data in list(channels.items()):
                if data['status'] == 'running':
                    proc = data.get('process')
                    if proc is None:
                        system_logs.add('WARNING', f"💔 العملية مفقودة للقناة {key}، إعادة تشغيل ...")
                        # إعادة تشغيل
                        threading.Thread(target=_run_stream, args=(key,), daemon=True).start()
                    else:
                        poll = proc.poll()
                        if poll is not None:
                            system_logs.add('WARNING', f"💔 العملية منتهية للقناة {key} (كود {poll})، إعادة تشغيل ...")
                            # إعادة تشغيل
                            threading.Thread(target=_run_stream, args=(key,), daemon=True).start()

# بدء خيط النبض
threading.Thread(target=heartbeat_loop, daemon=True).start()