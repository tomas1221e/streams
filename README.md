# Stream Manager V2

نسخة مطورة فوق مشروع streams الأصلي.

## المزايا
- SQLite للحفظ الدائم.
- Channels مستقلة عن Outputs.
- أكثر من Output لكل قناة.
- Start / Stop / Restart لكل Output.
- Start/Stop لكل القناة.
- Stream Key منفصل عن Server URL.
- Modes: COPY / VIDEO COPY + AUDIO / FULL TRANSCODE.
- H.264 / H.265 / NVENC / QSV / AMF كخيارات.
- Resolution / FPS / Bitrate / Preset / GOP / Profile / Level / Pixel Format / Tune.
- Audio codec / bitrate / sample rate / channels.
- Extra FFmpeg arguments.
- Logo overlay.
- Preview.
- FFprobe.
- Logs محفوظة في SQLite.
- Auto reconnect.
- Auto start بعد إعادة تشغيل البرنامج.

## التشغيل

1. تأكد أن Python 3.10+ وFFmpeg مثبتان.
2. ثبت المتطلبات:
   pip install -r requirements.txt
3. شغل:
   python app.py
4. افتح:
   http://YOUR_SERVER_IP:5000

## مهم
إذا كنت على Linux:
sudo apt update
sudo apt install ffmpeg python3 python3-pip

## COPY
COPY مناسب فقط عندما تكون codecs/الحاوية متوافقة مع المنصة المستهدفة.
إذا وضعت Logo، سيضطر الفيديو إلى إعادة الترميز.

## Extra Args
يمكنك وضع خيارات FFmpeg إضافية، مثل:
-maxrate 3000k -bufsize 6000k

لا تضع `-i` أو رابط output داخل Extra Args.
