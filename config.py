import os

HOST = "0.0.0.0"
PORT = 5000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
UPLOAD_FOLDER = os.path.join(STATIC_DIR, "uploads")
DATA_DIR = os.path.join(BASE_DIR, "data")
DATABASE_PATH = os.path.join(DATA_DIR, "streams.db")

FFMPEG_BINARY = os.environ.get("FFMPEG_BINARY", "ffmpeg")
FFPROBE_BINARY = os.environ.get("FFPROBE_BINARY", "ffprobe")

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

MAX_RETRIES = 5
RETRY_DELAY = 5
HEARTBEAT_INTERVAL = 5
FFMPEG_TIMEOUT = 30
LOG_LINES = 500

MAX_UPLOAD_MB = 10

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
