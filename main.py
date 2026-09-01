"""
NanoPi 2 - Portable Standalone Android Screen Viewer
Production-grade, crash-proof, zero-leak stream engine.
"""

import ctypes
import gc
import json
import logging
import os
import queue
import socket
import struct
import subprocess
import sys
import threading
import time
import tkinter as tk
from io import BytesIO
from PIL import Image, ImageTk

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

import config
from ui_settings import SettingsDialog

CREATE_NO_WINDOW = 0x08000000
COM_LOCK = threading.Lock()

def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

LOG_FILE = os.path.join(get_base_dir(), "NanoPiViewer.log")

# Configure root logger
logger = logging.getLogger("NanoPiViewer")
logger.setLevel(logging.DEBUG)

# File handler
fh = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s.%(msecs)03d [%(levelname)s] [%(threadName)s] %(message)s", datefmt="%H:%M:%S")
fh.setFormatter(formatter)
logger.addHandler(fh)

# Console handler
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

def get_asset_path(filename):
    base_dir = get_base_dir()
    local_asset = os.path.join(base_dir, "assets", filename)
    if os.path.exists(local_asset):
        return local_asset

    if hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, "assets", filename)
        if os.path.exists(bundled):
            return bundled
        direct = os.path.join(sys._MEIPASS, filename)
        if os.path.exists(direct):
            return direct

    global_tool = os.path.join(r"C:\Users\Asus\.gemini\tools\platform-tools", filename)
    if os.path.exists(global_tool):
        return global_tool
    global_mc = os.path.join(r"C:\Users\Asus\.gemini\tools\minicap", filename)
    if os.path.exists(global_mc):
        return global_mc

    return filename

class NanoPiViewerApp:
    def __init__(self, root):
        self.root = root
        logger.info("Initializing NanoPiViewerApp...")

        self.config = config.load_config()
        logger.info(f"Loaded config: {json.dumps(self.config)}")

        self.root.title(f"NanoPi 2 - Live Screen HD ({self.config.get('device_ip')})")
        self.root.geometry(f"{self.config.get('window_width', 1020)}x{self.config.get('window_height', 660)}")
        self.root.minsize(600, 400)
        self.root.configure(bg="#1e1e1e")

        self.adb_path = get_asset_path("adb.exe")
        self.minicap_bin = get_asset_path("minicap")
        self.minicap_so = get_asset_path("minicap.so")
        logger.info(f"Binary paths: adb='{self.adb_path}', minicap='{self.minicap_bin}', minicap.so='{self.minicap_so}'")

        self.device_serial = f"{self.config.get('device_ip')}:{self.config.get('adb_port', 5555)}"
        self.minicap_port = self.config.get("minicap_port", 1717)

        self.native_width = 1280
        self.native_height = 720
        self.target_w = 1280
        self.target_h = 720

        self.frame_queue = queue.Queue(maxsize=1)
        self.input_queue = queue.Queue(maxsize=50)
        self.running = True
        self.stream_stop_event = threading.Event()
        self.capture_thread = None
        self.input_thread = None
        self.keepalive_thread = None
        
        self.drag_start = None
        self.frame_count = 0
        self.tk_img = None
        self.last_frame_time = time.time()
        self.fps = 0.0
        self.has_active_stream = False

        self.current_stream_sock = None
        self.current_minicap_proc = None
        self.last_serial_heal_time = 0.0

        self.input_pipe = None

        self._setup_ui()
        self._start_threads()
        self._update_loop()

    def _setup_ui(self):
        self.toolbar = tk.Frame(self.root, bg="#2d2d2d", pady=4)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        btn_style = {
            "bg": "#3c3f41", "fg": "white",
            "activebackground": "#4e5254", "activeforeground": "white",
            "relief": tk.FLAT, "padx": 8, "pady": 2, "cursor": "hand2"
        }

        tk.Button(self.toolbar, text="◀ Back", command=lambda: self.send_key(4), **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="⌂ Home", command=lambda: self.send_key(3), **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="▢ Apps", command=lambda: self.send_key(187), **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="☰ Menu", command=lambda: self.send_key(82), **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="⚡ Wake Screen", command=self._wake_screen_safely, **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="🔊 Vol +", command=lambda: self.send_key(24), **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="🔉 Vol -", command=lambda: self.send_key(25), **btn_style).pack(side=tk.LEFT, padx=3)

        tk.Button(self.toolbar, text="🔄 Reconnect", command=self._restart_stream, **btn_style).pack(side=tk.LEFT, padx=8)
        tk.Button(self.toolbar, text="📋 Logs", command=self._open_log_file, **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="⚙ Settings", command=self._open_settings, **btn_style).pack(side=tk.LEFT, padx=3)

        self.status_lbl = tk.Label(self.toolbar, text="Connecting...", bg="#2d2d2d", fg="#4CAF50", font=("Segoe UI", 9))
        self.status_lbl.pack(side=tk.RIGHT, padx=10)

        # Image display container
        self.display_frame = tk.Frame(self.root, bg="#121212")
        self.display_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        offline_msg = (
            f"🔍 Connecting to NanoPi 2 ({self.device_serial})...\n\n"
            "• If the board is asleep, press the physical POWER button on the board.\n"
            "• Or click [⚡ Wake Screen] in the toolbar.\n"
            "• Screen mirroring will automatically start when the device responds."
        )
        self.display_label = tk.Label(
            self.display_frame, bg="#121212", fg="#A0A0A0",
            text=offline_msg, font=("Segoe UI", 11), justify=tk.CENTER
        )
        self.display_label.pack(fill=tk.BOTH, expand=True)

        # Mouse & Keyboard bindings
        self.display_label.bind("<ButtonPress-1>", self._on_mouse_down)
        self.display_label.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.display_label.bind("<Button-3>", lambda e: self.send_key(4))
        self.display_label.bind("<Button-2>", lambda e: self.send_key(3))
        self.root.bind("<Key>", self._on_key)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _open_log_file(self):
        try:
            os.startfile(LOG_FILE)
        except Exception as e:
            logger.error(f"Failed to open log file: {e}")

    def _open_settings(self):
        SettingsDialog(self.root, on_save_callback=self._apply_new_config)

    def _apply_new_config(self, new_cfg):
        logger.info(f"Applying new config: {json.dumps(new_cfg)}")
        self.config = new_cfg
        self.device_serial = f"{self.config.get('device_ip')}:{self.config.get('adb_port', 5555)}"
        self.minicap_port = self.config.get("minicap_port", 1717)
        self.root.title(f"NanoPi 2 - Live Screen HD ({self.config.get('device_ip')})")
        self._restart_stream()

    def _restart_stream(self):
        logger.info("Restart stream requested by user.")
        self._set_status("Reconnecting...", fg="#FFA726")
        self.frame_count = 0
        self.has_active_stream = False
        self._start_capture_thread()

    def _set_status(self, text, fg="#4CAF50"):
        try:
            self.status_lbl.config(text=text, fg=fg)
        except Exception:
            pass

    def _start_threads(self):
        logger.info("Starting background threads...")
        self.input_thread = threading.Thread(target=self._persistent_input_worker, daemon=True, name="InputWorker")
        self.input_thread.start()

        self.keepalive_thread = threading.Thread(target=self._keepalive_worker, daemon=True, name="KeepAliveWorker")
        self.keepalive_thread.start()

        self._start_capture_thread()

    def _keepalive_worker(self):
        """Periodically keeps Android awake without spawning heavy Dalvik processes."""
        while self.running:
            time.sleep(30)
            if self.has_active_stream:
                try:
                    self._dispatch_command("svc power stayon true")
                except Exception:
                    pass

    def _start_capture_thread(self):
        self.stream_stop_event.set()
        
        # Instantly unblock any active socket or process
        if self.current_stream_sock:
            try: self.current_stream_sock.close()
            except Exception: pass
            self.current_stream_sock = None

        if self.current_minicap_proc:
            try: self.current_minicap_proc.terminate()
            except Exception: pass
            self.current_minicap_proc = None

        if self.capture_thread and self.capture_thread.is_alive() and threading.current_thread() != self.capture_thread:
            try:
                self.capture_thread.join(timeout=0.3)
            except Exception:
                pass

        self.stream_stop_event.clear()
        self.capture_thread = threading.Thread(target=self._logged_stream_worker, daemon=True, name="StreamWorker")
        self.capture_thread.start()

    def _is_device_ready(self):
        try:
            p = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True, text=True, timeout=2.0, creationflags=CREATE_NO_WINDOW
            )
            for line in p.stdout.splitlines():
                if self.device_serial in line and "\tdevice" in line:
                    return True
                # Auto-detect if another device is ready on 5555
                if "\tdevice" in line and ":5555" in line:
                    other_serial = line.split("\t")[0].strip()
                    if other_serial != self.device_serial:
                        logger.info(f"[Auto-Switch] Switching to online device {other_serial}")
                        self.device_serial = other_serial
                        return True
        except Exception:
            pass
        return False

    def _connect_adb(self):
        if self._is_device_ready():
            return True

        logger.info(f"[Connect] Running: adb connect {self.device_serial}...")
        try:
            p = subprocess.run(
                [self.adb_path, "connect", self.device_serial],
                capture_output=True, text=True, timeout=2.5, creationflags=CREATE_NO_WINDOW
            )
            logger.info(f"[Connect Result]: {p.stdout.strip()} {p.stderr.strip()}")
        except Exception as ex:
            logger.warning(f"[Connect Timeout/Notice]: {ex}")

        return self._is_device_ready()

    def _recv_all(self, sock, n):
        data = bytearray()
        while len(data) < n and self.running and not self.stream_stop_event.is_set():
            try:
                chunk = sock.recv(n - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
            except Exception as e:
                logger.debug(f"Socket recv notice: {e}")
                return None
        return bytes(data)

    def _logged_stream_worker(self):
        logger.info(f"Stream worker started. Target: {self.device_serial}, port: {self.minicap_port}")
        
        while self.running and not self.stream_stop_event.is_set():
            s = None
            minicap_proc = None
            try:
                # Step 0: Ensure Device is Connected & Awake
                if not self._is_device_ready():
                    self._set_status(f"Searching for {self.device_serial}...", fg="#FFA726")
                    if not self._connect_adb():
                        if not self.has_active_stream:
                            offline_msg = (
                                f"💤 NanoPi 2 is Asleep or Offline ({self.device_serial})\n\n"
                                "• Press the physical POWER button on the board to wake Wi-Fi.\n"
                                "• Or click [⚡ Wake Screen] in the top toolbar.\n"
                                "• Stream will automatically start as soon as the device is awake."
                            )
                            self.root.after(0, lambda msg=offline_msg: self.display_label.config(text=msg, image=""))
                        time.sleep(1.5)
                        continue

                if self.stream_stop_event.is_set():
                    break

                self._set_status("Initializing stream...", fg="#4CAF50")

                # Step 1: Forward port with unique abstract socket name
                sock_name = f"mc_{int(time.time()) % 100000}"
                t0 = time.time()
                logger.info(f"[Step 1] Forwarding port tcp:{self.minicap_port} -> localabstract:{sock_name}...")
                subprocess.run(
                    [self.adb_path, "-s", self.device_serial, "forward", f"tcp:{self.minicap_port}", f"localabstract:{sock_name}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0, creationflags=CREATE_NO_WINDOW
                )
                logger.info(f"[Step 1 Done] ADB forward took {time.time()-t0:.3f}s")

                if self.stream_stop_event.is_set():
                    break

                # Step 2: Spawn minicap with unique socket name
                nat_res = self.config.get("native_resolution", "1280x720")
                str_res = self.config.get("stream_resolution", "1280x720")
                quality = self.config.get("jpeg_quality", 60)

                minicap_cmd = [
                    self.adb_path, "-s", self.device_serial, "shell",
                    f"LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/minicap -n {sock_name} -P {nat_res}@{str_res}/0 -Q {quality} -S"
                ]
                logger.info(f"[Step 2] Spawning minicap (Quality={quality}, Socket={sock_name}): {' '.join(minicap_cmd)}")
                minicap_proc = subprocess.Popen(
                    minicap_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=CREATE_NO_WINDOW
                )
                self.current_minicap_proc = minicap_proc

                # Give minicap 0.4s to initialize abstract socket
                time.sleep(0.4)

                if self.stream_stop_event.is_set():
                    break

                # Wake screen gently (KEYCODE_WAKEUP = 224 + KEYCODE_MENU = 82)
                self._dispatch_command("input keyevent 224")
                self._dispatch_command("input keyevent 82")
                self._dispatch_command("svc power stayon true")

                # Step 3: Socket Handshake
                logger.info(f"[Step 3] Connecting TCP socket 127.0.0.1:{self.minicap_port}...")
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
                s.settimeout(2.5)

                self.current_stream_sock = s
                s.connect(("127.0.0.1", self.minicap_port))
                banner = self._recv_all(s, 24)

                if not banner or len(banner) < 24:
                    logger.warning(f"[Step 3 Failed] Incomplete banner. Retrying...")
                    s.close()
                    if minicap_proc:
                        try: minicap_proc.terminate()
                        except Exception: pass
                    time.sleep(1.0)
                    continue

                rw = struct.unpack("<I", banner[6:10])[0]
                rh = struct.unpack("<I", banner[10:14])[0]
                vw = struct.unpack("<I", banner[14:18])[0]
                vh = struct.unpack("<I", banner[18:22])[0]
                logger.info(f"[Banner Parsed] Real={rw}x{rh}, Virtual={vw}x{vh}")

                self.native_width = rw
                self.native_height = rh
                self.target_w = vw
                self.target_h = vh

                s.settimeout(10.0)
                logger.info("[Step 4] Entering continuous streaming loop...")

                first_frame = True
                while self.running and not self.stream_stop_event.is_set():
                    t_frame_start = time.time()
                    size_raw = self._recv_all(s, 4)
                    if not size_raw or len(size_raw) < 4:
                        logger.warning("Frame stream ended or timed out. Reconnecting...")
                        break

                    frame_size = struct.unpack("<I", size_raw)[0]
                    if frame_size <= 0 or frame_size > 5000000:
                        break

                    frame_data = self._recv_all(s, frame_size)
                    if not frame_data or len(frame_data) < frame_size:
                        break

                    t_recv = time.time()
                    img = Image.open(BytesIO(frame_data))

                    if first_frame:
                        logger.info(f"[OK] FIRST FRAME RECEIVED! Size={frame_size} bytes, Res={img.size}, Total time={t_recv - t0:.3f}s")
                        first_frame = False
                        self.has_active_stream = True

                    try:
                        old_item = self.frame_queue.get_nowait()
                        if old_item and old_item[0]:
                            old_item[0].close()
                    except queue.Empty:
                        pass

                    self.frame_queue.put((img, len(frame_data), t_recv - t_frame_start))

                s.close()
                if minicap_proc:
                    try: minicap_proc.terminate()
                    except Exception: pass

            except Exception as e:
                logger.exception(f"Stream worker exception: {e}")
                self.has_active_stream = False
                if s:
                    try: s.close()
                    except Exception: pass
                if minicap_proc:
                    try: minicap_proc.terminate()
                    except Exception: pass
                time.sleep(1.0)
            finally:
                self.current_stream_sock = None
                self.current_minicap_proc = None

    def _persistent_input_worker(self):
        logger.info("Starting persistent ADB input worker...")
        
        while self.running:
            if not self._is_device_ready():
                time.sleep(1.0)
                continue

            pipe = None
            try:
                pipe = subprocess.Popen(
                    [self.adb_path, "-s", self.device_serial, "shell"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW
                )
                self.input_pipe = pipe

                while self.running and pipe.poll() is None:
                    try:
                        cmd_line = self.input_queue.get(timeout=0.5)
                        if pipe.stdin and not pipe.stdin.closed:
                            pipe.stdin.write(f"{cmd_line}\n".encode("utf-8"))
                            pipe.stdin.flush()
                        self.input_queue.task_done()
                    except queue.Empty:
                        continue
                    except Exception as ex:
                        logger.debug(f"Input pipe write notice: {ex}")
                        break

            except Exception as e:
                logger.debug(f"Input pipe exception: {e}")
            finally:
                if pipe:
                    try:
                        if pipe.stdin: pipe.stdin.close()
                        pipe.terminate()
                    except Exception: pass
                self.input_pipe = None
                time.sleep(0.5)

    def _dispatch_command(self, cmd_str):
        try:
            self.input_queue.put_nowait(cmd_str)
        except queue.Full:
            pass

    def _update_loop(self):
        if not self.running:
            return

        try:
            img, bytes_len, dt = self.frame_queue.get_nowait()

            fw = self.display_frame.winfo_width()
            fh = self.display_frame.winfo_height()

            if fw < 50 or fh < 50:
                fw = 960
                fh = 540

            scale = min(fw / self.target_w, fh / self.target_h)
            nw = max(10, int(self.target_w * scale))
            nh = max(10, int(self.target_h * scale))

            # Hardware bilinear scaling
            if img.size != (nw, nh):
                resized = img.resize((nw, nh), Image.Resampling.BILINEAR)
                img.close()
                del img
                render_img = resized
            else:
                render_img = img

            new_tk = ImageTk.PhotoImage(render_img)
            self.display_label.config(image=new_tk, text="")
            self.tk_img = new_tk
            
            render_img.close()
            del render_img

            self.frame_count += 1
            now = time.time()
            frame_dt = now - self.last_frame_time
            if frame_dt > 0.001:
                self.fps = 0.9 * self.fps + 0.1 * (1.0 / frame_dt)
            self.last_frame_time = now

            if self.frame_count % 200 == 0:
                gc.collect()

            self._set_status(
                f"Live HD ({self.native_width}x{self.native_height}) | {bytes_len/1024:.1f} KB | FPS: {self.fps:.1f} | Frame: {self.frame_count}",
                fg="#4CAF50"
            )

        except queue.Empty:
            pass
        except Exception as ex:
            self._set_status(f"Render Error: {ex}", fg="#FF5252")

        self.root.after(16, self._update_loop)

    def _wake_screen_safely(self):
        """Safely wakes the screen and unlocks without toggling power or restarting ADB daemons."""
        logger.info("Executing safe screen wake sequence (KEYCODE_WAKEUP + MENU + SWIPE)...")
        # KEYCODE_WAKEUP = 224 (Turns screen ON only, never off!)
        self._dispatch_command("input keyevent 224")
        # KEYCODE_MENU = 82 (Dismiss lock screen)
        self._dispatch_command("input keyevent 82")
        # Swipe up
        self._dispatch_command("input swipe 640 600 640 100 200")
        self._dispatch_command("svc power stayon true")

        # Send non-destructive serial pulse ONLY if cooldown has passed
        now = time.time()
        if SERIAL_AVAILABLE and (now - self.last_serial_heal_time > 8.0) and COM_LOCK.acquire(blocking=False):
            try:
                self.last_serial_heal_time = now
                s = serial.Serial('COM3', 115200, timeout=0.5)
                # Only wake and keep alive, never kill adbd in wake handler!
                s.write(b"\nsu\ninput keyevent 224\ninput keyevent 82\nsvc power stayon true\n")
                time.sleep(0.1)
                s.close()
                logger.info("Safe serial wake pulse sent on COM3.")
            except Exception as e:
                logger.debug(f"Serial wake note: {e}")
            finally:
                COM_LOCK.release()

    def _on_mouse_down(self, event):
        self.drag_start = (event.x, event.y, time.time())

    def _on_mouse_up(self, event):
        if not self.drag_start:
            return
        x1, y1, t1 = self.drag_start
        x2, y2 = event.x, event.y
        duration = int((time.time() - t1) * 1000)

        lw = self.display_label.winfo_width()
        lh = self.display_label.winfo_height()

        if lw <= 0 or lh <= 0:
            return

        dx1 = int((x1 / lw) * self.native_width)
        dy1 = int((y1 / lh) * self.native_height)
        dx2 = int((x2 / lw) * self.native_width)
        dy2 = int((y2 / lh) * self.native_height)

        dx1 = max(0, min(self.native_width, dx1))
        dy1 = max(0, min(self.native_height, dy1))
        dx2 = max(0, min(self.native_width, dx2))
        dy2 = max(0, min(self.native_height, dy2))

        dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
        if dist < 8:
            self._dispatch_command(f"input tap {dx1} {dy1}")
        else:
            dur = max(100, min(600, duration))
            self._dispatch_command(f"input swipe {dx1} {dy1} {dx2} {dy2} {dur}")

        self.drag_start = None

    def _on_key(self, event):
        key_map = {
            "BackSpace": 67, "Return": 66, "Escape": 4, "Tab": 61,
            "Up": 19, "Down": 20, "Left": 21, "Right": 22
        }
        if event.keysym in key_map:
            self.send_key(key_map[event.keysym])
            return

        char = event.char
        if char and char.isprintable():
            self._dispatch_command(f'input text "{char}"')

    def send_key(self, keycode):
        self._dispatch_command(f"input keyevent {keycode}")

    def _on_close(self):
        logger.info("Application closing...")
        self.running = False
        self.stream_stop_event.set()
        if self.input_pipe:
            try:
                if self.input_pipe.stdin: self.input_pipe.stdin.close()
                self.input_pipe.terminate()
            except Exception: pass
        self.root.destroy()


# Global Windows Mutex for single instance
MUTEX_HANDLE = None

def acquire_single_instance_mutex():
    global MUTEX_HANDLE
    mutex_name = "Global\\NanoPiViewer_SingleInstance_Mutex"
    MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        return False
    return True


def main():
    if not acquire_single_instance_mutex():
        logger.warning("Another instance of NanoPiViewer is already running. Exiting.")
        root = tk.Tk()
        root.withdraw()
        tk.messagebox.showinfo("NanoPiViewer", "NanoPiViewer is already running!\nPlease check your taskbar.")
        root.destroy()
        return

    # Pre-warm ADB server
    adb = get_asset_path("adb.exe")
    try:
        subprocess.run([adb, "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass

    root = tk.Tk()
    app = NanoPiViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
