import os
import subprocess
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
