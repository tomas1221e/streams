import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from config import DATABASE_PATH, DATA_DIR

_db_lock = threading.RLock()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _columns(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column_if_missing(conn, table, name, definition):
    if name not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def init_db():
    with _db_lock:
        conn = connect()
        try:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                source TEXT NOT NULL,
                logo_path TEXT DEFAULT '',
                logo_position TEXT DEFAULT 'top-right',
                logo_scale REAL DEFAULT 0.15,
                enabled INTEGER DEFAULT 1,
                auto_start INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS outputs (
                id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                name TEXT NOT NULL,
                protocol TEXT DEFAULT 'rtmp',
                server TEXT NOT NULL,
                stream_key TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                mode TEXT DEFAULT 'transcode',
                video_codec TEXT DEFAULT 'libx264',
                video_bitrate TEXT DEFAULT '2500k',
                resolution TEXT DEFAULT '1280x720',
                fps INTEGER DEFAULT 30,
                preset TEXT DEFAULT 'veryfast',
                profile TEXT DEFAULT '',
                level TEXT DEFAULT '',
                gop INTEGER DEFAULT 60,
                pix_fmt TEXT DEFAULT '',
                tune TEXT DEFAULT '',
                audio_codec TEXT DEFAULT 'aac',
                audio_bitrate TEXT DEFAULT '128k',
                sample_rate INTEGER DEFAULT 48000,
                audio_channels INTEGER DEFAULT 2,
                extra_args TEXT DEFAULT '',
                auto_start INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(channel_id) REFERENCES channels(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT,
                output_id TEXT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_outputs_channel ON outputs(channel_id);
            CREATE INDEX IF NOT EXISTS idx_logs_channel ON logs(channel_id);
            """)
            # New optional enhancement columns. Existing databases are preserved.
            new_cols = {
                "quality_preset": "TEXT DEFAULT 'balanced'",
                "sharpen": "REAL DEFAULT 0",
                "denoise": "TEXT DEFAULT 'off'",
                "deblock": "TEXT DEFAULT 'off'",
                "brightness": "REAL DEFAULT 0",
                "contrast": "REAL DEFAULT 1",
                "saturation": "REAL DEFAULT 1",
                "gamma": "REAL DEFAULT 1",
                "color_boost": "REAL DEFAULT 0",
                "scaling": "TEXT DEFAULT 'lanczos'",
                "filters_enabled": "INTEGER DEFAULT 0",
            }
            for name, definition in new_cols.items():
                _add_column_if_missing(conn, "outputs", name, definition)
            conn.commit()
        finally:
            conn.close()


def _row_dict(row):
    return dict(row) if row else None


def list_channels():
    with _db_lock:
        conn = connect()
        try:
            return [_row_dict(r) for r in conn.execute(
                "SELECT * FROM channels ORDER BY created_at DESC"
            ).fetchall()]
        finally:
            conn.close()


def get_channel(channel_id):
    with _db_lock:
        conn = connect()
        try:
            return _row_dict(conn.execute(
                "SELECT * FROM channels WHERE id=?", (channel_id,)
            ).fetchone())
        finally:
            conn.close()


def create_channel(data):
    channel_id = uuid.uuid4().hex[:12]
    now = now_iso()
    with _db_lock:
        conn = connect()
        try:
            conn.execute("""
                INSERT INTO channels
                (id,name,description,source,logo_path,logo_position,logo_scale,
                 enabled,auto_start,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                channel_id, data.get("name") or "New Channel",
                data.get("description", ""), data["source"],
                data.get("logo_path", ""), data.get("logo_position", "top-right"),
                float(data.get("logo_scale", 0.15)),
                int(bool(data.get("enabled", True))),
                int(bool(data.get("auto_start", False))), now, now
            ))
            conn.commit()
        finally:
            conn.close()
    return get_channel(channel_id)


def update_channel(channel_id, data):
    current = get_channel(channel_id)
    if not current:
        return None
    merged = {**current, **data}
    with _db_lock:
        conn = connect()
        try:
            conn.execute("""
                UPDATE channels SET name=?, description=?, source=?, logo_path=?,
                logo_position=?, logo_scale=?, enabled=?, auto_start=?, updated_at=?
                WHERE id=?
            """, (
                merged["name"], merged.get("description", ""), merged["source"],
                merged.get("logo_path", ""), merged.get("logo_position", "top-right"),
                float(merged.get("logo_scale", 0.15)),
                int(bool(merged.get("enabled", True))),
                int(bool(merged.get("auto_start", False))), now_iso(), channel_id
            ))
            conn.commit()
        finally:
            conn.close()
    return get_channel(channel_id)


def delete_channel(channel_id):
    with _db_lock:
        conn = connect()
        try:
            conn.execute("DELETE FROM channels WHERE id=?", (channel_id,))
            conn.commit()
        finally:
            conn.close()


def list_outputs(channel_id):
    with _db_lock:
        conn = connect()
        try:
            return [_row_dict(r) for r in conn.execute(
                "SELECT * FROM outputs WHERE channel_id=? ORDER BY created_at ASC",
                (channel_id,)
            ).fetchall()]
        finally:
            conn.close()


def get_output(output_id):
    with _db_lock:
        conn = connect()
        try:
            return _row_dict(conn.execute(
                "SELECT * FROM outputs WHERE id=?", (output_id,)
            ).fetchone())
        finally:
            conn.close()


OUTPUT_DEFAULTS = {
    "name": "Output",
    "protocol": "rtmp",
    "server": "",
    "stream_key": "",
    "enabled": True,
    "mode": "transcode",
    "video_codec": "libx264",
    "video_bitrate": "2500k",
    "resolution": "1280x720",
    "fps": 30,
    "preset": "veryfast",
    "profile": "",
    "level": "",
    "gop": 60,
    "pix_fmt": "",
    "tune": "",
    "audio_codec": "aac",
    "audio_bitrate": "128k",
    "sample_rate": 48000,
    "audio_channels": 2,
    "extra_args": "",
    "auto_start": True,
    "quality_preset": "balanced",
    "sharpen": 0,
    "denoise": "off",
    "deblock": "off",
    "brightness": 0,
    "contrast": 1,
    "saturation": 1,
    "gamma": 1,
    "color_boost": 0,
    "scaling": "lanczos",
    "filters_enabled": 0,
}


def create_output(channel_id, data):
    output_id = uuid.uuid4().hex[:12]
    now = now_iso()
    d = {**OUTPUT_DEFAULTS, **data}
    with _db_lock:
        conn = connect()
        try:
            conn.execute("""
                INSERT INTO outputs
                (id,channel_id,name,protocol,server,stream_key,enabled,mode,video_codec,
                 video_bitrate,resolution,fps,preset,profile,level,gop,pix_fmt,tune,
                 audio_codec,audio_bitrate,sample_rate,audio_channels,extra_args,auto_start,
                 quality_preset,sharpen,denoise,deblock,brightness,contrast,saturation,gamma,
                 color_boost,scaling,filters_enabled,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                output_id, channel_id, d["name"], d["protocol"], d["server"], d["stream_key"],
                int(bool(d["enabled"])), d["mode"], d["video_codec"], d["video_bitrate"],
                d["resolution"], int(d["fps"]), d["preset"], d["profile"], d["level"],
                int(d["gop"]), d["pix_fmt"], d["tune"], d["audio_codec"], d["audio_bitrate"],
                int(d["sample_rate"]), int(d["audio_channels"]), d["extra_args"],
                int(bool(d["auto_start"])), d["quality_preset"], float(d["sharpen"]),
                d["denoise"], d["deblock"], float(d["brightness"]), float(d["contrast"]),
                float(d["saturation"]), float(d["gamma"]), float(d["color_boost"]),
                d["scaling"], int(bool(d["filters_enabled"])), now, now
            ))
            conn.commit()
        finally:
            conn.close()
    return get_output(output_id)


def update_output(output_id, data):
    current = get_output(output_id)
    if not current:
        return None
    d = {**current, **data}
    with _db_lock:
        conn = connect()
        try:
            conn.execute("""
                UPDATE outputs SET
                name=?, protocol=?, server=?, stream_key=?, enabled=?, mode=?,
                video_codec=?, video_bitrate=?, resolution=?, fps=?, preset=?,
                profile=?, level=?, gop=?, pix_fmt=?, tune=?, audio_codec=?,
                audio_bitrate=?, sample_rate=?, audio_channels=?, extra_args=?,
                auto_start=?, quality_preset=?, sharpen=?, denoise=?, deblock=?,
                brightness=?, contrast=?, saturation=?, gamma=?, color_boost=?,
                scaling=?, filters_enabled=?, updated_at=?
                WHERE id=?
            """, (
                d["name"], d["protocol"], d["server"], d["stream_key"],
                int(bool(d["enabled"])), d["mode"], d["video_codec"], d["video_bitrate"],
                d["resolution"], int(d["fps"]), d["preset"], d["profile"], d["level"],
                int(d["gop"]), d["pix_fmt"], d["tune"], d["audio_codec"],
                d["audio_bitrate"], int(d["sample_rate"]), int(d["audio_channels"]),
                d["extra_args"], int(bool(d["auto_start"])),
                d.get("quality_preset", "balanced"), float(d.get("sharpen", 0)),
                d.get("denoise", "off"), d.get("deblock", "off"),
                float(d.get("brightness", 0)), float(d.get("contrast", 1)),
                float(d.get("saturation", 1)), float(d.get("gamma", 1)),
                float(d.get("color_boost", 0)), d.get("scaling", "lanczos"),
                int(bool(d.get("filters_enabled", False))), now_iso(), output_id
            ))
            conn.commit()
        finally:
            conn.close()
    return get_output(output_id)


def delete_output(output_id):
    with _db_lock:
        conn = connect()
        try:
            conn.execute("DELETE FROM outputs WHERE id=?", (output_id,))
            conn.commit()
        finally:
            conn.close()


def add_log(level, message, channel_id=None, output_id=None):
    with _db_lock:
        conn = connect()
        try:
            conn.execute(
                "INSERT INTO logs(channel_id,output_id,level,message,created_at) VALUES(?,?,?,?,?)",
                (channel_id, output_id, level, message, now_iso())
            )
            conn.commit()
            conn.execute(
                "DELETE FROM logs WHERE id NOT IN "
                "(SELECT id FROM logs ORDER BY id DESC LIMIT 1000)"
            )
            conn.commit()
        finally:
            conn.close()


def get_logs(channel_id=None, output_id=None, limit=300):
    with _db_lock:
        conn = connect()
        try:
            if output_id:
                rows = conn.execute(
                    "SELECT * FROM logs WHERE output_id=? ORDER BY id DESC LIMIT ?",
                    (output_id, limit)
                ).fetchall()
            elif channel_id:
                rows = conn.execute(
                    "SELECT * FROM logs WHERE channel_id=? ORDER BY id DESC LIMIT ?",
                    (channel_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()
