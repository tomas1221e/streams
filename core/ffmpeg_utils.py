import base64
import os
import shlex
import subprocess
import json

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

def build_video_filters(output):
    """
    Build optional FFmpeg video filters.

    All values are optional.
    """

    filters = []

    # -----------------------------
    # Brightness / Contrast / Gamma
    # -----------------------------

    brightness = float(output.get("brightness") or 0)

    contrast = float(output.get("contrast") or 1)

    saturation = float(
        output.get("saturation") or 1
    )

    gamma = float(
        output.get("gamma") or 1
    )

    if (
        brightness != 0
        or contrast != 1
        or saturation != 1
        or gamma != 1
    ):
        filters.append(
            "eq="
            f"brightness={brightness}:"
            f"contrast={contrast}:"
            f"saturation={saturation}:"
            f"gamma={gamma}"
        )

    # -----------------------------
    # Sharpen
    # -----------------------------

    sharpen = float(
        output.get("sharpen") or 0
    )

    if sharpen > 0:

        sharpen = min(
            max(sharpen, 0),
            5
        )

        filters.append(
            f"unsharp=5:5:{sharpen}:5:5:0"
        )

    # -----------------------------
    # Denoise
    # -----------------------------

    denoise = (
        output.get("denoise") or "off"
    ).lower()

    if denoise == "light":

        filters.append(
            "hqdn3d=1.2:1.2:3:3"
        )

    elif denoise == "medium":

        filters.append(
            "hqdn3d=2:2:4:4"
        )

    elif denoise == "strong":

        filters.append(
            "hqdn3d=3:3:6:6"
        )

    # -----------------------------
    # Deblock
    # -----------------------------

    deblock = (
        output.get("deblock") or "off"
    ).lower()

    if deblock == "light":

        filters.append(
            "pp=hb/vb/dr"
        )

    elif deblock == "medium":

        filters.append(
            "pp=hb/vb/ha"
        )

    # -----------------------------
    # Color Enhancement
    # -----------------------------

    color_boost = float(
        output.get("color_boost") or 0
    )

    if color_boost > 0:

        color_boost = min(
            max(color_boost, 0),
            2
        )

        filters.append(
            f"colorbalance="
            f"rs={color_boost}:"
            f"gs={color_boost}:"
            f"bs={color_boost}"
        )

    # -----------------------------
    # Edge Enhancement
    # -----------------------------

    edge = (
        output.get("edge_enhance")
        or "off"
    ).lower()

    if edge == "light":

        filters.append(
            "edgedetect=low=0.1:high=0.4"
        )

    # -----------------------------
    # Film Grain / Texture
    # -----------------------------

    grain = float(
        output.get("grain") or 0
    )

    if grain > 0:

        grain = min(
            max(grain, 0),
            10
        )

        filters.append(
            f"noise="
            f"alls={int(grain)}:"
            f"allf=t"
        )

    # -----------------------------
    # Lanczos scaling
    # -----------------------------

    resolution = (
        output.get("resolution") or ""
    )

    if resolution:

        filters.append(
            f"scale={resolution}:"
            "flags=lanczos"
        )

    return filters

def build_ffmpeg_command(channel, output):
        video_filters = build_video_filters(output)
    source = channel["source"]
    mode = output.get("mode", "transcode")

    fps = int(output.get("fps") or DEFAULT_FPS)
    resolution = output.get("resolution") or DEFAULT_RESOLUTION

    logo_path = channel.get("logo_path") or ""
    has_logo = bool(logo_path and os.path.exists(logo_path))

    cmd = [
        FFMPEG_BINARY,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-rw_timeout",
        str(FFMPEG_TIMEOUT * 1000000),
        "-i",
        source,
    ]

    # Logo means we must process the video.
    if has_logo:
        scale = float(channel.get("logo_scale") or 0.15)
        position = channel.get("logo_position") or "top-right"

        cmd += [
            "-i",
            logo_path,
            "-filter_complex",
            (
                f"[1:v]scale=iw*{scale}:ih*{scale}[logo];"
                f"[0:v][logo]{_overlay_position(position)}[vout]"
            ),
            "-map",
            "[vout]",
            "-map",
            "0:a?",
        ]
    else:
        cmd += [
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
        ]

    # ---------------------------------------------------------
    # COPY
    # ---------------------------------------------------------

    if mode == "copy" and not has_logo:

        cmd += [
            "-c:v",
            "copy",
            "-c:a",
            "copy",
        ]

    # ---------------------------------------------------------
    # VIDEO COPY + AUDIO TRANSCODE
    # ---------------------------------------------------------

    elif mode == "audio_copy" and not has_logo:

        cmd += [
            "-c:v",
            "copy",
            "-c:a",
            output.get("audio_codec") or DEFAULT_AUDIO_CODEC,
            "-b:a",
            output.get("audio_bitrate") or DEFAULT_AUDIO_BITRATE,
            "-ar",
            str(
                int(
                    output.get("sample_rate")
                    or DEFAULT_SAMPLE_RATE
                )
            ),
            "-ac",
            str(
                int(
                    output.get("audio_channels")
                    or DEFAULT_AUDIO_CHANNELS
                )
            ),
        ]

    # ---------------------------------------------------------
    # FULL TRANSCODE
    # ---------------------------------------------------------

    else:

        codec = output.get("video_codec") or DEFAULT_VIDEO_CODEC

if video_filters:
            cmd += [
                "-vf",
                ",".join(video_filters)
            ]

        cmd += [
            "-c:v",
            codec,
            "-b:v",
            output.get("video_bitrate")
            or DEFAULT_VIDEO_BITRATE,
            "-r",
            str(fps),
            "-s",
            resolution,
            "-g",
            str(
                int(
                    output.get("gop")
                    or DEFAULT_GOP
                )
            ),
        ]

        preset = output.get("preset")

        if preset and codec != "copy":
            cmd += [
                "-preset",
                preset,
            ]

        profile = output.get("profile")
        if profile:
            cmd += [
                "-profile:v",
                str(profile),
            ]

        level = output.get("level")
        if level:
            cmd += [
                "-level:v",
                str(level),
            ]

        pix_fmt = output.get("pix_fmt")
        if pix_fmt:
            cmd += [
                "-pix_fmt",
                str(pix_fmt),
            ]

        tune = output.get("tune")
        if tune:
            cmd += [
                "-tune",
                str(tune),
            ]

        cmd += [
            "-c:a",
            output.get("audio_codec")
            or DEFAULT_AUDIO_CODEC,
            "-b:a",
            output.get("audio_bitrate")
            or DEFAULT_AUDIO_BITRATE,
            "-ar",
            str(
                int(
                    output.get("sample_rate")
                    or DEFAULT_SAMPLE_RATE
                )
            ),
            "-ac",
            str(
                int(
                    output.get("audio_channels")
                    or DEFAULT_AUDIO_CHANNELS
                )
            ),
        ]

    # ---------------------------------------------------------
    # EXTRA FFMPEG ARGUMENTS
    # ---------------------------------------------------------

    extra = (
        output.get("extra_args") or ""
    ).strip()

    if extra:
        cmd += shlex.split(extra)

    # ---------------------------------------------------------
    # OUTPUT FORMAT
    # ---------------------------------------------------------

    protocol = (
        output.get("protocol") or "rtmp"
    ).lower()

    if protocol in ("rtmp", "rtmps"):

        cmd += [
            "-f",
            "flv",
            "-flvflags",
            "no_duration_filesize",
        ]

    elif protocol in ("mpegts", "srt"):

        cmd += [
            "-f",
            "mpegts",
        ]

    cmd += [
        output_url(output)
    ]

    return cmd


def generate_preview(source, logo_settings=None):

    try:

        cmd = [
            FFMPEG_BINARY,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-rw_timeout",
            str(FFMPEG_TIMEOUT * 1000000),
            "-i",
            source,
        ]

        logo_path = (
            (logo_settings or {})
            .get("path", "")
        )

        if logo_path and os.path.exists(
            logo_path
        ):

            scale = float(
                (logo_settings or {})
                .get("scale", 0.15)
            )

            position = (
                (logo_settings or {})
                .get(
                    "position",
                    "top-right",
                )
            )

            cmd += [
                "-i",
                logo_path,
                "-filter_complex",
                (
                    f"[1:v]scale=iw*{scale}:ih*{scale}[logo];"
                    f"[0:v][logo]"
                    f"{_overlay_position(position)}"
                ),
            ]

        cmd += [
            "-frames:v",
            "1",
            "-vf",
            "scale=640:-2",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=FFMPEG_TIMEOUT,
        )

        if (
            result.returncode != 0
            or not result.stdout
        ):
            return None

        return (
            "data:image/png;base64,"
            + base64.b64encode(
                result.stdout
            ).decode()
        )

    except Exception:
        return None


def probe(source):

    cmd = [
        FFPROBE_BINARY,
        "-v",
        "error",
        "-show_entries",
        (
            "stream=index,codec_name,codec_type,"
            "width,height,r_frame_rate,bit_rate"
        ),
        "-of",
        "json",
        source,
    ]

    try:

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT,
        )

        if result.returncode != 0:

            return {
                "error": result.stderr[-1000:]
            }

        return json.loads(
            result.stdout or "{}"
        )

    except Exception as exc:

        return {
            "error": str(exc)
        }
