import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
DATABASE_PATH = os.path.join(DATA_DIR, "streams.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HOST = "0.0.0.0"
PORT = 5000
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
MAX_UPLOAD_MB = 10

FFMPEG_BINARY = "ffmpeg"
FFPROBE_BINARY = "ffprobe"
FFMPEG_TIMEOUT = 30

MAX_RETRIES = 20
RETRY_DELAY = 3
HEARTBEAT_INTERVAL = 1

DEFAULT_VIDEO_CODEC = "libx264"
DEFAULT_VIDEO_BITRATE = "2500k"
DEFAULT_FPS = 30
DEFAULT_RESOLUTION = "1280x720"
DEFAULT_PRESET = "veryfast"
DEFAULT_GOP = 60
DEFAULT_AUDIO_CODEC = "aac"
DEFAULT_AUDIO_BITRATE = "128k"
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_AUDIO_CHANNELS = 2
DEFAULT_LOGO_POSITION = "top-right"
DEFAULT_LOGO_SCALE = 0.15
