import base64
from config import (
    DEFAULT_VIDEO_CODEC, DEFAULT_VIDEO_BITRATE, DEFAULT_FPS, DEFAULT_RESOLUTION,
    DEFAULT_AUDIO_CODEC, DEFAULT_AUDIO_BITRATE, DEFAULT_SAMPLE_RATE, DEFAULT_AUDIO_CHANNELS,
    DEFAULT_LOGO_POSITION, DEFAULT_LOGO_SCALE, FFMPEG_TIMEOUT
)

def _get_overlay_position(position):
    """تحديد موضع الشعار على الفيديو"""
    positions = {
        'top-left': 'overlay=10:10',
        'top-right': 'overlay=W-w-10:10',
        'bottom-left': 'overlay=10:H-h-10',
        'bottom-right': 'overlay=W-w-10:H-h-10',
        'center': 'overlay=(W-w)/2:(H-h)/2'
    }
    return positions.get(position, 'overlay=W-w-10:10')

def build_ffmpeg_command(source, output_key, video_settings, audio_settings, logo_settings=None):
    """بناء أمر FFmpeg محسّن مع دعم RTMPS والترميز الصحيح"""
    video_codec = video_settings.get('codec', DEFAULT_VIDEO_CODEC)
    video_bitrate = video_settings.get('bitrate', DEFAULT_VIDEO_BITRATE)
    fps = video_settings.get('fps', DEFAULT_FPS)
    resolution = video_settings.get('resolution', DEFAULT_RESOLUTION)

    # إجبار AAC لضمان التوافق مع التليجرام وباقي المنصات
    audio_codec = 'aac'
    audio_bitrate = audio_settings.get('bitrate', DEFAULT_AUDIO_BITRATE)
    sample_rate = audio_settings.get('sample_rate', DEFAULT_SAMPLE_RATE)
    channels = audio_settings.get('channels', DEFAULT_AUDIO_CHANNELS)

    timeout_us = str(FFMPEG_TIMEOUT * 1000000)

    cmd = [
        'ffmpeg',
        '-y',
        '-rw_timeout', timeout_us,
        '-timeout', timeout_us,
        '-re',
        '-i', source
    ]

    has_logo = logo_settings and os.path.exists(logo_settings.get('path', ''))

    if has_logo:
        logo_path = logo_settings['path']
        position = logo_settings.get('position', DEFAULT_LOGO_POSITION)
        scale = logo_settings.get('scale', DEFAULT_LOGO_SCALE)

        cmd.extend(['-i', logo_path])
        
        overlay_str = _get_overlay_position(position)
        filter_complex = f"[1:v]scale=iw*{scale}:ih*{scale}[logo];[0:v][logo]{overlay_str}[v_out]"
        
        cmd.extend(['-filter_complex', filter_complex])
        cmd.extend(['-map', '[v_out]'])
        cmd.extend(['-map', '0:a?'])
    else:
        if resolution:
            cmd.extend(['-s', resolution])
        cmd.extend(['-r', str(fps)])

    # إعدادات الفيديو
    cmd.extend(['-c:v', video_codec])
    cmd.extend(['-b:v', video_bitrate])
    cmd.extend(['-preset', 'veryfast'])
    cmd.extend(['-g', str(int(fps) * 2)])

    # إعدادات الصوت
    cmd.extend(['-c:a', audio_codec])
    cmd.extend(['-b:a', audio_bitrate])
    cmd.extend(['-ar', str(sample_rate)])
    cmd.extend(['-ac', str(channels)])

    # تهيئة الخرج ليدعم FLV / RTMPS
    cmd.extend(['-f', 'flv', '-flvflags', 'no_duration_filesize', output_key])
    return cmd

def generate_preview(source, logo_settings=None):
    """توليد صورة معاينة مفردة بصيغة base64"""
    try:
        timeout_us = str(FFMPEG_TIMEOUT * 1000000)
        cmd = [
            'ffmpeg',
            '-y',
            '-rw_timeout', timeout_us,
            '-timeout', timeout_us,
            '-i', source
        ]

        has_logo = logo_settings and os.path.exists(logo_settings.get('path', ''))

        if has_logo:
            logo_path = logo_settings['path']
            position = logo_settings.get('position', DEFAULT_LOGO_POSITION)
            scale = logo_settings.get('scale', DEFAULT_LOGO_SCALE)
            
            overlay_str = _get_overlay_position(position)
            filter_complex = f"[1:v]scale=iw*{scale}:ih*{scale}[logo];[0:v][logo]{overlay_str}"
            
            cmd.extend(['-i', logo_path])
            cmd.extend(['-filter_complex', filter_complex])

        cmd.extend([
            '-vframes', '1',
            '-f', 'image2pipe',
            '-vcodec', 'png',
            '-'
        ])

        result = subprocess.run(cmd, capture_output=True, timeout=FFMPEG_TIMEOUT)

        if result.returncode != 0 or not result.stdout:
            return None

        img_base64 = base64.b64encode(result.stdout).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"

    except (subprocess.TimeoutExpired, Exception):
        return None
=======
import os
import shlex
import subprocess

from config import (
    FFMPEG_BINARY,
    FFPROBE_BINARY,
    FFMPEG_TIMEOUT,
    DEFAULT_VIDEO_CODEC,
    DEFAULT_VIDEO_BITRATE,
    DEFAULT_FPS,
    DEFAULT_RESOLUTION,
    DEFAULT_PRESET,
    DEFAULT_GOP,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_AUDIO_BITRATE,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_AUDIO_CHANNELS,
)


def _overlay_position(position):
    return {
        "top-left": "overlay=10:10",
        "top-right": "overlay=W-w-10:10",
        "bottom-left": "overlay=10:H-h-10",
        "bottom-right": "overlay=W-w-10:H-h-10",
        "center": "overlay=(W-w)/2:(H-h)/2",
    }.get(position, "overlay=W-w-10:H-h-10")


def output_url(output):
    server = (output.get("server") or "").strip()
    key = (output.get("stream_key") or "").strip()
    if not key:
        return server
    if server.endswith("/"):
        return server + key
    return server + "/" + key


def build_ffmpeg_command(channel, output):
    source = channel["source"]
    mode = output.get("mode", "transcode")
    fps = int(output.get("fps") or DEFAULT_FPS)
    resolution = output.get("resolution") or DEFAULT_RESOLUTION
    logo_path = channel.get("logo_path") or ""
    has_logo = bool(logo_path and os.path.exists(logo_path))

    cmd = [
        FFMPEG_BINARY, "-hide_banner", "-nostdin", "-y",
        "-rw_timeout", str(FFMPEG_TIMEOUT * 1000000),
        "-i", source,
    ]

    # A logo/filter requires re-encoding video.
    if has_logo:
        scale = float(channel.get("logo_scale") or 0.15)
        position = channel.get("logo_position") or "top-right"
        cmd += ["-i", logo_path]
        filt = (
            f"[1:v]scale=iw*{scale}:ih*{scale}[logo];"
            f"[0:v][logo]{_overlay_position(position)}[vout]"
        )
        cmd += ["-filter_complex", filt, "-map", "[vout]", "-map", "0:a?"]
    else:
        cmd += ["-map", "0:v:0", "-map", "0:a?"]

    if mode == "copy" and not has_logo:
        cmd += ["-c:v", "copy", "-c:a", "copy"]
    elif mode == "audio_copy" and not has_logo:
        cmd += [
            "-c:v", "copy",
            "-c:a", output.get("audio_codec") or DEFAULT_AUDIO_CODEC,
            "-b:a", output.get("audio_bitrate") or DEFAULT_AUDIO_BITRATE,
            "-ar", str(int(output.get("sample_rate") or DEFAULT_SAMPLE_RATE)),
            "-ac", str(int(output.get("audio_channels") or DEFAULT_AUDIO_CHANNELS)),
        ]
    else:
        codec = output.get("video_codec") or DEFAULT_VIDEO_CODEC
        cmd += [
            "-c:v", codec,
            "-b:v", output.get("video_bitrate") or DEFAULT_VIDEO_BITRATE,
            "-r", str(fps),
            "-s", resolution,
            "-g", str(int(output.get("gop") or DEFAULT_GOP)),
        ]
        preset = output.get("preset")
        if preset and codec not in ("copy",):
            cmd += ["-preset", preset]
        for key in ("profile", "level", "pix_fmt", "tune"):
            value = output.get(key)
            if value:
                flag = {"profile": "-profile:v", "level": "-level:v", "pix_fmt": "-pix_fmt", "tune": "-tune"}[key]
                cmd += [flag, str(value)]

        cmd += [
            "-c:a", output.get("audio_codec") or DEFAULT_AUDIO_CODEC,
            "-b:a", output.get("audio_bitrate") or DEFAULT_AUDIO_BITRATE,
            "-ar", str(int(output.get("sample_rate") or DEFAULT_SAMPLE_RATE)),
            "-ac", str(int(output.get("audio_channels") or DEFAULT_AUDIO_CHANNELS)),
        ]

    extra = (output.get("extra_args") or "").strip()
    if extra:
        cmd += shlex.split(extra)

    protocol = (output.get("protocol") or "rtmp").lower()
    if protocol in ("rtmp", "rtmps"):
        cmd += ["-f", "flv", "-flvflags", "no_duration_filesize"]
    elif protocol == "mpegts":
        cmd += ["-f", "mpegts"]
    elif protocol == "srt":
        cmd += ["-f", "mpegts"]

    cmd += [output_url(output)]
    return cmd


def generate_preview(source, logo_settings=None):
    try:
        cmd = [
            FFMPEG_BINARY, "-hide_banner", "-loglevel", "error", "-y",
            "-rw_timeout", str(FFMPEG_TIMEOUT * 1000000),
            "-i", source,
        ]

        logo_path = (logo_settings or {}).get("path", "")
        if logo_path and os.path.exists(logo_path):
            scale = float((logo_settings or {}).get("scale", 0.15))
            position = (logo_settings or {}).get("position", "top-right")
            cmd += [
                "-i", logo_path,
                "-filter_complex",
                f"[1:v]scale=iw*{scale}:ih*{scale}[logo];"
                f"[0:v][logo]{_overlay_position(position)}",
            ]

        cmd += [
            "-frames:v", "1",
            "-vf", "scale=640:-2",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-",
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=FFMPEG_TIMEOUT)
        if result.returncode != 0 or not result.stdout:
            return None
        return "data:image/png;base64," + base64.b64encode(result.stdout).decode()
    except Exception:
        return None


def probe(source):
    cmd = [
        FFPROBE_BINARY, "-v", "error",
        "-show_entries",
        "stream=index,codec_name,codec_type,width,height,r_frame_rate,bit_rate",
        "-of", "json", source,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
        if result.returncode != 0:
            return {"error": result.stderr[-1000:]}
        import json
        return json.loads(result.stdout or "{}")
    except Exception as exc:
        return {"error": str(exc)}

