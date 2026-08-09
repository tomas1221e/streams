import os
import shlex
import subprocess
import base64
import json

from config import (
    FFMPEG_BINARY, FFPROBE_BINARY, DEFAULT_VIDEO_CODEC, DEFAULT_VIDEO_BITRATE,
    DEFAULT_FPS, DEFAULT_RESOLUTION, DEFAULT_PRESET, DEFAULT_GOP,
    DEFAULT_AUDIO_CODEC, DEFAULT_AUDIO_BITRATE, DEFAULT_SAMPLE_RATE,
    DEFAULT_AUDIO_CHANNELS, DEFAULT_LOGO_POSITION, DEFAULT_LOGO_SCALE,
    FFMPEG_TIMEOUT
)


def _get_overlay_position(position):
    return {
        "top-left": "overlay=10:10",
        "top-right": "overlay=W-w-10:10",
        "bottom-left": "overlay=10:H-h-10",
        "bottom-right": "overlay=W-w-10:H-h-10",
        "center": "overlay=(W-w)/2:(H-h)/2",
    }.get(position, "overlay=W-w-10:10")


def _filters(output):
    if not output.get("filters_enabled"):
        return []

    f = []
    brightness = float(output.get("brightness") or 0)
    contrast = float(output.get("contrast") or 1)
    saturation = float(output.get("saturation") or 1)
    gamma = float(output.get("gamma") or 1)
    if brightness != 0 or contrast != 1 or saturation != 1 or gamma != 1:
        f.append(
            f"eq=brightness={brightness}:contrast={contrast}:"
            f"saturation={saturation}:gamma={gamma}"
        )

    sharpen = float(output.get("sharpen") or 0)
    if sharpen > 0:
        f.append(f"unsharp=5:5:{min(sharpen, 5)}:5:5:0")

    denoise = str(output.get("denoise") or "off").lower()
    if denoise == "light":
        f.append("hqdn3d=1.2:1.2:3:3")
    elif denoise == "medium":
        f.append("hqdn3d=2:2:4:4")
    elif denoise == "strong":
        f.append("hqdn3d=3:3:6:6")

    deblock = str(output.get("deblock") or "off").lower()
    if deblock == "light":
        f.append("pp=hb/vb/dr")
    elif deblock == "medium":
        f.append("pp=hb/vb/ha")

    color_boost = float(output.get("color_boost") or 0)
    if color_boost:
        color_boost = max(-1, min(color_boost, 1))
        f.append(
            f"colorbalance=rs={color_boost}:gs={color_boost}:bs={color_boost}"
        )

    resolution = output.get("resolution") or ""
    scaling = output.get("scaling") or "lanczos"
    if resolution:
        flags = {"lanczos": "lanczos", "bicubic": "bicubic",
                 "bilinear": "bilinear", "fast_bilinear": "fast_bilinear"}.get(
                     scaling, "lanczos"
                 )
        if "x" in resolution:
            w, h = resolution.split("x", 1)
            f.append(f"scale={w}:{h}:flags={flags}")

    return f


def _output_url(output):
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
    protocol = (output.get("protocol") or "rtmp").lower()
    has_logo = bool(channel.get("logo_path") and os.path.exists(channel["logo_path"]))

    cmd = [
        FFMPEG_BINARY, "-hide_banner", "-nostdin", "-y",
        "-rw_timeout", str(FFMPEG_TIMEOUT * 1000000),
        "-i", source
    ]

    filters = _filters(output)

    if has_logo:
        cmd += ["-i", channel["logo_path"]]
        logo_scale = float(channel.get("logo_scale") or DEFAULT_LOGO_SCALE)
        pos = _get_overlay_position(channel.get("logo_position") or DEFAULT_LOGO_POSITION)
        overlay = f"[1:v]scale=iw*{logo_scale}:ih*{logo_scale}[logo];[0:v][logo]{pos}"
        if filters:
            overlay += "," + ",".join(filters)
        overlay += "[vout]"
        cmd += ["-filter_complex", overlay, "-map", "[vout]", "-map", "0:a?"]
    else:
        cmd += ["-map", "0:v:0", "-map", "0:a?"]
        if filters:
            cmd += ["-vf", ",".join(filters)]

    if mode == "copy" and not has_logo and not filters:
        cmd += ["-c:v", "copy", "-c:a", "copy"]
    elif mode == "audio_copy" and not has_logo and not filters:
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
            "-r", str(int(output.get("fps") or DEFAULT_FPS)),
            "-g", str(int(output.get("gop") or DEFAULT_GOP)),
        ]
        preset = output.get("preset") or DEFAULT_PRESET
        if preset and codec not in ("copy",):
            cmd += ["-preset", preset]
        for k, flag in (("profile", "-profile:v"), ("level", "-level:v"),
                        ("pix_fmt", "-pix_fmt"), ("tune", "-tune")):
            if output.get(k):
                cmd += [flag, str(output[k])]
        cmd += [
            "-c:a", output.get("audio_codec") or DEFAULT_AUDIO_CODEC,
            "-b:a", output.get("audio_bitrate") or DEFAULT_AUDIO_BITRATE,
            "-ar", str(int(output.get("sample_rate") or DEFAULT_SAMPLE_RATE)),
            "-ac", str(int(output.get("audio_channels") or DEFAULT_AUDIO_CHANNELS)),
        ]

    extra = (output.get("extra_args") or "").strip()
    if extra:
        cmd += shlex.split(extra)

    if protocol in ("rtmp", "rtmps", "mpegts", "srt"):
        cmd += ["-f", "flv" if protocol in ("rtmp", "rtmps") else "mpegts"]
        if protocol in ("rtmp", "rtmps"):
            cmd += ["-flvflags", "no_duration_filesize"]

    cmd += [_output_url(output)]
    return cmd


def generate_preview(source, logo_settings=None):
    try:
        cmd = [FFMPEG_BINARY, "-hide_banner", "-loglevel", "error", "-y",
               "-rw_timeout", str(FFMPEG_TIMEOUT * 1000000), "-i", source]
        if logo_settings and os.path.exists(logo_settings.get("path", "")):
            cmd += ["-i", logo_settings["path"]]
            scale = float(logo_settings.get("scale", DEFAULT_LOGO_SCALE))
            pos = _get_overlay_position(logo_settings.get("position", DEFAULT_LOGO_POSITION))
            cmd += ["-filter_complex",
                    f"[1:v]scale=iw*{scale}:ih*{scale}[logo];[0:v][logo]{pos}"]
        cmd += ["-frames:v", "1", "-vf", "scale=640:-2",
                "-f", "image2pipe", "-vcodec", "png", "-"]
        r = subprocess.run(cmd, capture_output=True, timeout=FFMPEG_TIMEOUT)
        if r.returncode != 0 or not r.stdout:
            return None
        return "data:image/png;base64," + base64.b64encode(r.stdout).decode()
    except Exception:
        return None


def probe(source):
    cmd = [FFPROBE_BINARY, "-v", "error", "-show_entries",
           "stream=index,codec_name,codec_type,width,height,r_frame_rate,bit_rate",
           "-of", "json", source]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
        if r.returncode:
            return {"error": r.stderr[-1000:]}
        return json.loads(r.stdout or "{}")
    except Exception as e:
        return {"error": str(e)}
