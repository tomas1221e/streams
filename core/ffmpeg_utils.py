import os
import subprocess
import base64
import shlex
from config import (
    UPLOAD_FOLDER,
    DEFAULT_VIDEO_CODEC, DEFAULT_VIDEO_BITRATE, DEFAULT_FPS, DEFAULT_RESOLUTION,
    DEFAULT_AUDIO_CODEC, DEFAULT_AUDIO_BITRATE, DEFAULT_SAMPLE_RATE, DEFAULT_AUDIO_CHANNELS,
    DEFAULT_LOGO_POSITION, DEFAULT_LOGO_SCALE, FFMPEG_TIMEOUT
)

def build_ffmpeg_command(source, output_key, video_settings, audio_settings, logo_settings=None):
    """
    بناء أمر FFmpeg النهائي للتشغيل المستمر.
    """
    # استخراج إعدادات الفيديو
    video_codec = video_settings.get('codec', DEFAULT_VIDEO_CODEC)
    video_bitrate = video_settings.get('bitrate', DEFAULT_VIDEO_BITRATE)
    fps = video_settings.get('fps', DEFAULT_FPS)
    resolution = video_settings.get('resolution', DEFAULT_RESOLUTION)

    # استخراج إعدادات الصوت
    audio_codec = audio_settings.get('codec', DEFAULT_AUDIO_CODEC)
    audio_bitrate = audio_settings.get('bitrate', DEFAULT_AUDIO_BITRATE)
    sample_rate = audio_settings.get('sample_rate', DEFAULT_SAMPLE_RATE)
    channels = audio_settings.get('channels', DEFAULT_AUDIO_CHANNELS)

    # الأمر الأساسي (إدخال مع timeout وتكرار تلقائي)
    cmd = [
        'ffmpeg',
        '-stream_loop', '-1',           # تكرار المصدر إذا انتهى
        '-i', source,                   # مصدر الدخل (رابط أو ملف)
        '-timeout', str(FFMPEG_TIMEOUT * 1000000),  # ميكروثانية
        '-stimeout', str(FFMPEG_TIMEOUT * 1000000),
        '-f', 'flv',                    # صيغة الخرج لـ RTMP
    ]

    # --- إعدادات الفيديو ---
    cmd.extend(['-c:v', video_codec])
    cmd.extend(['-b:v', video_bitrate])
    cmd.extend(['-r', str(fps)])
    if resolution:
        cmd.extend(['-s', resolution])
    cmd.extend(['-preset', 'veryfast'])  # تقليل الضغط على المعالج
    cmd.extend(['-g', str(fps * 2)])      # keyframe كل ثانيتين

    # --- إعدادات الصوت ---
    cmd.extend(['-c:a', audio_codec])
    cmd.extend(['-b:a', audio_bitrate])
    cmd.extend(['-ar', str(sample_rate)])
    cmd.extend(['-ac', str(channels)])

    # --- معالجة الشعار (إذا وجد) ---
    if logo_settings and os.path.exists(logo_settings.get('path', '')):
        logo_path = logo_settings['path']
        position = logo_settings.get('position', DEFAULT_LOGO_POSITION)
        scale = logo_settings.get('scale', DEFAULT_LOGO_SCALE)

        # حساب موضع الشعار (overlay)
        # W = عرض الفيديو, H = ارتفاع الفيديو, w = عرض الشعار, h = ارتفاع الشعار
        overlay_filter = ''
        if position == 'top-left':
            overlay_filter = 'overlay=10:10'
        elif position == 'top-right':
            overlay_filter = 'overlay=W-w-10:10'
        elif position == 'bottom-left':
            overlay_filter = 'overlay=10:H-h-10'
        elif position == 'bottom-right':
            overlay_filter = 'overlay=W-w-10:H-h-10'
        elif position == 'center':
            overlay_filter = 'overlay=(W-w)/2:(H-h)/2'
        else:  # default top-right
            overlay_filter = 'overlay=W-w-10:10'

        # إعادة قياس الشعار مع الحفاظ على النسبة
        scale_filter = f"scale=iw*{scale}:ih*{scale}"
        
        # بناء مرشح معقد (complex filter)
        filter_complex = f"[1:v]{scale_filter}[logo];[0:v][logo]{overlay_filter}"
        
        # إدراج مدخل الشعار كدخل ثانوي، وتطبيق الفلتر
        cmd.insert(cmd.index('-i') + 2, logo_path)  # نضيف مصدر الشعار بعد مصدر الفيديو الرئيسي
        
        # بما أننا أضفنا مدخلًا جديدًا، نحتاج إلى إعادة ترتيب أوامر الفلتر (نضعها قبل خرج الفيديو)
        # سنقوم ببناء الأمر بطريقة مختلفة قليلاً.
        # الطريقة الأسهل: نضع الفلتر قبل -f flv
        # لكن بما أننا أضفنا مدخل الشعار، يجب إزالة -f flv مؤقتًا وإضافته في النهاية
        # دعنا نبني الأمر من الصفر بطريقة أنظف لتجنب التعقيد.
        return _build_complex_command(source, output_key, video_settings, audio_settings, logo_settings)

    # إذا لم يكن هناك شعار
    cmd.append(output_key)
    return cmd

def _build_complex_command(source, output_key, video_settings, audio_settings, logo_settings):
    """دالة مساعدة لبناء الأمر مع الفلاتر المعقدة (خاصة للشعار)"""
    video_codec = video_settings.get('codec', DEFAULT_VIDEO_CODEC)
    video_bitrate = video_settings.get('bitrate', DEFAULT_VIDEO_BITRATE)
    fps = video_settings.get('fps', DEFAULT_FPS)
    resolution = video_settings.get('resolution', DEFAULT_RESOLUTION)

    audio_codec = audio_settings.get('codec', DEFAULT_AUDIO_CODEC)
    audio_bitrate = audio_settings.get('bitrate', DEFAULT_AUDIO_BITRATE)
    sample_rate = audio_settings.get('sample_rate', DEFAULT_SAMPLE_RATE)
    channels = audio_settings.get('channels', DEFAULT_AUDIO_CHANNELS)

    cmd = [
        'ffmpeg',
        '-stream_loop', '-1',
        '-i', source,
        '-timeout', str(FFMPEG_TIMEOUT * 1000000),
        '-stimeout', str(FFMPEG_TIMEOUT * 1000000),
    ]

    logo_path = logo_settings.get('path')
    position = logo_settings.get('position', DEFAULT_LOGO_POSITION)
    scale = logo_settings.get('scale', DEFAULT_LOGO_SCALE)

    if logo_path and os.path.exists(logo_path):
        cmd.extend(['-i', logo_path])
        
        # بناء الفلتر
        scale_filter = f"[1:v]scale=iw*{scale}:ih*{scale}[logo]"
        
        overlay_map = ''
        if position == 'top-left':
            overlay_map = 'overlay=10:10'
        elif position == 'top-right':
            overlay_map = 'overlay=W-w-10:10'
        elif position == 'bottom-left':
            overlay_map = 'overlay=10:H-h-10'
        elif position == 'bottom-right':
            overlay_map = 'overlay=W-w-10:H-h-10'
        elif position == 'center':
            overlay_map = 'overlay=(W-w)/2:(H-h)/2'
        else:
            overlay_map = 'overlay=W-w-10:10'
            
        filter_complex = f"{scale_filter};[0:v][logo]{overlay_map}"
        
        cmd.extend(['-filter_complex', filter_complex])
        # في حالة استخدام filter_complex، يجب تحديد map للفيديو والصوت
        cmd.extend(['-map', '[out]'])  # خرج الفيديو من الفلتر
        cmd.extend(['-map', '0:a'])    # خرج الصوت من المصدر الأساسي
    else:
        # بدون شعار، نستخدم الفلاتر البسيطة
        if resolution:
            cmd.extend(['-s', resolution])
        cmd.extend(['-r', str(fps)])

    # إعدادات التشفير
    cmd.extend(['-c:v', video_codec])
    cmd.extend(['-b:v', video_bitrate])
    cmd.extend(['-preset', 'veryfast'])
    cmd.extend(['-g', str(fps * 2)])
    
    cmd.extend(['-c:a', audio_codec])
    cmd.extend(['-b:a', audio_bitrate])
    cmd.extend(['-ar', str(sample_rate)])
    cmd.extend(['-ac', str(channels)])
    
    cmd.extend(['-f', 'flv', output_key])
    return cmd

def generate_preview(source, logo_settings=None):
    """
    توليد معاينة (لقطة واحدة) من مصدر البث مع تطبيق الشعار إذا وجد.
    تعيد الصورة بصيغة base64 لعرضها في الواجهة.
    """
    try:
        # نستخدم أمرًا منفصلًا لالتقاط إطار واحد
        cmd = [
            'ffmpeg',
            '-i', source,
            '-vframes', '1',           # لقطة واحدة فقط
            '-f', 'image2pipe',
            '-vcodec', 'png',          # صيغة PNG للجودة العالية
            '-'
        ]

        # إذا كان هناك شعار، نضيفه إلى المعاينة
        if logo_settings and os.path.exists(logo_settings.get('path', '')):
            logo_path = logo_settings['path']
            position = logo_settings.get('position', DEFAULT_LOGO_POSITION)
            scale = logo_settings.get('scale', DEFAULT_LOGO_SCALE)
            
            # نبني فلتر مشابه لما سبق ولكن بدون خيارات التشفير الثقيلة
            # نضيف مدخل الشعار في البداية
            preview_cmd = [
                'ffmpeg',
                '-i', source,
                '-i', logo_path,
                '-filter_complex',
                f"[1:v]scale=iw*{scale}:ih*{scale}[logo];[0:v][logo]overlay=W-w-10:10" if position == 'top-right' else 
                f"[1:v]scale=iw*{scale}:ih*{scale}[logo];[0:v][logo]overlay=10:10" if position == 'top-left' else
                f"[1:v]scale=iw*{scale}:ih*{scale}[logo];[0:v][logo]overlay=10:H-h-10" if position == 'bottom-left' else
                f"[1:v]scale=iw*{scale}:ih*{scale}[logo];[0:v][logo]overlay=W-w-10:H-h-10" if position == 'bottom-right' else
                f"[1:v]scale=iw*{scale}:ih*{scale}[logo];[0:v][logo]overlay=(W-w)/2:(H-h)/2",
                '-vframes', '1',
                '-f', 'image2pipe',
                '-vcodec', 'png',
                '-'
            ]
            cmd = preview_cmd

        # تنفيذ الأمر
        result = subprocess.run(cmd, capture_output=True, timeout=FFMPEG_TIMEOUT)
        
        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            # قد يفشل إذا كان المصدر لا يعمل، نعيد None
            if "Invalid data" in error_msg or "Connection refused" in error_msg or "403" in error_msg:
                return None
            return None
            
        # تحويل الصورة إلى base64
        img_base64 = base64.b64encode(result.stdout).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
        
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None