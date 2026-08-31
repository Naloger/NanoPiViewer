"""
Configuration manager for NanoPiViewer.
"""

import json
import os
import sys

DEFAULT_CONFIG = {
    "device_ip": "192.168.1.113",
    "adb_port": 5555,
    "minicap_port": 1717,
    "native_resolution": "1280x720",
    "stream_resolution": "1280x720",
    "jpeg_quality": 60,
    "auto_connect": True,
    "keep_screen_on": True,
    "fps_limit": 60,
    "window_width": 1020,
    "window_height": 660
}

def get_config_path():
    base_dir = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
    return os.path.join(base_dir, "config.json")

def load_config():
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(data)
                return cfg
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        return True
    except Exception:
        return False
