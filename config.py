import os

# إعدادات الخادم
HOST = '0.0.0.0'
PORT = 5000

# مجلدات النظام
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
UPLOAD_FOLDER = os.path.join(STATIC_DIR, 'uploads')

# إعدادات المعالجة الافتراضية (Video)
DEFAULT_VIDEO_CODEC = 'libx264'
DEFAULT_VIDEO_BITRATE = '2000k'
DEFAULT_FPS = 30
DEFAULT_RESOLUTION = '1280x720'  # العرض x الارتفاع

# إعدادات المعالجة الافتراضية (Audio)
DEFAULT_AUDIO_CODEC = 'aac'
DEFAULT_AUDIO_BITRATE = '128k'
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_AUDIO_CHANNELS = 2  # 2 = Stereo, 1 = Mono

# إعدادات الشعار
DEFAULT_LOGO_POSITION = 'top-right'  # top-left, top-right, bottom-left, bottom-right, center
DEFAULT_LOGO_SCALE = 0.15  # 15% من عرض الفيديو

# إعدادات إدارة العمليات
MAX_RETRIES = 3
HEARTBEAT_INTERVAL = 10  # ثواني
FFMPEG_TIMEOUT = 30  # ثواني

# التأكد من وجود مجلد الرفع
os.makedirs(UPLOAD_FOLDER, exist_ok=True)