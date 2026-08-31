import json
import os
import sys

DEFAULT_CONFIG = {
    "device_ip": "192.168.1.113",
    "adb_port": 5555,
    "minicap_port": 1717,
    "native_resolution": "1280x720",
    "stream_resolution": "1280x720",
    "auto_connect": True,
    "keep_screen_on": True,
    "window_width": 1020,
    "window_height": 660,
    "fps_limit": 60
}

def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_config_path():
    return os.path.join(get_base_dir(), "config.json")

def load_config():
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception:
            pass
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_config(config_dict):
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
