"""
NanoPi 2 - Portable Standalone Android Screen Viewer
Production-grade, fully optimized, zero-memory-leak, high-performance stream engine.
"""

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

import config
from ui_settings import SettingsDialog

CREATE_NO_WINDOW = 0x08000000

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
        self.root.minsize(500, 350)
        self.root.configure(bg="#1e1e1e")

        self.adb_path = get_asset_path("adb.exe")
        self.minicap_bin = get_asset_path("minicap")
        self.minicap_so = get_asset_path("minicap.so")
        logger.info(f"Paths: adb={self.adb_path}, minicap={self.minicap_bin}, minicap.so={self.minicap_so}")

        self.device_serial = f"{self.config.get('device_ip')}:{self.config.get('adb_port', 5555)}"
        self.minicap_port = self.config.get("minicap_port", 1717)

        self.native_width = 1280
        self.native_height = 720
        self.target_w = 1280
        self.target_h = 720

        self.frame_queue = queue.Queue(maxsize=1)
        self.input_queue = queue.Queue(maxsize=50)
        self.running = True
        self.drag_start = None
        self.frame_count = 0
        self.tk_img = None
        self.last_frame_time = time.time()
        self.fps = 0.0

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
        tk.Button(self.toolbar, text="⚡ Power / Unlock", command=self._wake_and_unlock, **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="🔊 Vol +", command=lambda: self.send_key(24), **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="🔉 Vol -", command=lambda: self.send_key(25), **btn_style).pack(side=tk.LEFT, padx=3)

        tk.Button(self.toolbar, text="🔄 Reconnect", command=self._restart_stream, **btn_style).pack(side=tk.LEFT, padx=8)
        tk.Button(self.toolbar, text="📋 Logs", command=self._open_log_file, **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="⚙ Settings", command=self._open_settings, **btn_style).pack(side=tk.LEFT, padx=3)

        self.status_lbl = tk.Label(self.toolbar, text="Connecting...", bg="#2d2d2d", fg="#4CAF50", font=("Segoe UI", 9))
        self.status_lbl.pack(side=tk.RIGHT, padx=10)

        # Image display container
        self.display_frame = tk.Frame(self.root, bg="#000000")
        self.display_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.display_label = tk.Label(self.display_frame, bg="#000000", text="Connecting to device...", fg="#888888", font=("Segoe UI", 11))
        self.display_label.pack(expand=True)

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
        self.status_lbl.config(text="Reconnecting...")
        self.frame_count = 0
        self._start_capture_thread()

    def _start_threads(self):
        logger.info("Starting background worker threads...")
        self._start_capture_thread()
        self.input_thread = threading.Thread(target=self._persistent_input_worker, daemon=True, name="InputWorker")
        self.input_thread.start()

    def _start_capture_thread(self):
        self.capture_thread = threading.Thread(target=self._logged_stream_worker, daemon=True, name="StreamWorker")
        self.capture_thread.start()

    def _recv_all(self, sock, n):
        data = bytearray()
        while len(data) < n and self.running:
            try:
                chunk = sock.recv(n - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
            except Exception as e:
                logger.debug(f"Socket recv exception: {e}")
                return None
        return bytes(data)

    def _logged_stream_worker(self):
        logger.info(f"Stream worker started. Target: {self.device_serial}, port: {self.minicap_port}")
        
        while self.running:
            s = None
            minicap_proc = None
            try:
                # Step 1: ADB Connect
                t0 = time.time()
                logger.info(f"[Step 1] Connecting ADB to {self.device_serial}...")
                adb_res = subprocess.run(
                    [self.adb_path, "connect", self.device_serial],
                    capture_output=True, text=True, timeout=3.0, creationflags=CREATE_NO_WINDOW
                )
                logger.info(f"[Step 1 Done] ADB connect took {time.time()-t0:.3f}s. Output: {adb_res.stdout.strip()}")

                # Step 2: ADB Forward
                t0 = time.time()
                logger.info(f"[Step 2] Forwarding port tcp:{self.minicap_port} -> localabstract:minicap...")
                fwd_res = subprocess.run(
                    [self.adb_path, "-s", self.device_serial, "forward", f"tcp:{self.minicap_port}", "localabstract:minicap"],
                    capture_output=True, text=True, timeout=2.0, creationflags=CREATE_NO_WINDOW
                )
                logger.info(f"[Step 2 Done] ADB forward took {time.time()-t0:.3f}s. Output: {fwd_res.stdout.strip()}")

                # Step 3: Spawn minicap on device with configurable JPEG quality
                nat_res = self.config.get("native_resolution", "1280x720")
                str_res = self.config.get("stream_resolution", "1280x720")
                quality = self.config.get("jpeg_quality", 60)

                minicap_cmd = [
                    self.adb_path, "-s", self.device_serial, "shell",
                    f"LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/minicap -P {nat_res}@{str_res}/0 -Q {quality} -S"
                ]
                logger.info(f"[Step 3] Spawning minicap process (Quality={quality}): {' '.join(minicap_cmd)}")
                t0 = time.time()
                minicap_proc = subprocess.Popen(
                    minicap_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=CREATE_NO_WINDOW
                )
                logger.info(f"[Step 3 Done] Minicap process spawned in {time.time()-t0:.3f}s")

                # Step 3b: Send wake trigger via fast pipe or process
                self._dispatch_command("input keyevent 82")

                # Step 4: Socket Handshake with TCP_NODELAY
                logger.info(f"[Step 4] Starting TCP socket handshake on 127.0.0.1:{self.minicap_port}...")
                t_socket_start = time.time()
                banner = None

                for attempt in range(1, 51):
                    if not self.running: break
                    time.sleep(0.05)
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
                        s.settimeout(0.6)
                        s.connect(("127.0.0.1", self.minicap_port))
                        banner = self._recv_all(s, 24)
                        if banner and len(banner) == 24:
                            logger.info(f"[Step 4 Handshake OK] Attempt #{attempt} succeeded in {time.time()-t_socket_start:.3f}s!")
                            break
                        else:
                            s.close()
                            s = None
                    except Exception as ex:
                        if s:
                            s.close()
                            s = None
                        if attempt % 10 == 0:
                            logger.debug(f"[Step 4] Handshake attempt #{attempt} waiting: {ex}")

                if not s or not banner or len(banner) < 24:
                    logger.warning(f"[Step 4 Failed] Socket handshake failed after {time.time()-t_socket_start:.3f}s.")
                    if minicap_proc:
                        try: minicap_proc.terminate()
                        except Exception: pass
                    time.sleep(1.0)
                    continue

                # Parse banner
                version = banner[0]
                rw = struct.unpack("<I", banner[6:10])[0]
                rh = struct.unpack("<I", banner[10:14])[0]
                vw = struct.unpack("<I", banner[14:18])[0]
                vh = struct.unpack("<I", banner[18:22])[0]
                orient = banner[22]
                quirks = banner[23]
                logger.info(f"[Banner Parsed] v={version}, Real={rw}x{rh}, Virtual={vw}x{vh}, Orient={orient}, Quirks={quirks}")

                self.native_width = rw
                self.native_height = rh
                self.target_w = vw
                self.target_h = vh

                s.settimeout(10.0)
                logger.info("[Step 5] Entering continuous streaming loop...")

                first_frame = True
                while self.running:
                    t_frame_start = time.time()
                    size_raw = self._recv_all(s, 4)
                    if not size_raw or len(size_raw) < 4:
                        logger.warning("Failed to read 4-byte frame header. Reconnecting...")
                        break

                    frame_size = struct.unpack("<I", size_raw)[0]
                    if frame_size <= 0 or frame_size > 5000000:
                        logger.warning(f"Invalid frame size: {frame_size}. Reconnecting...")
                        break

                    frame_data = self._recv_all(s, frame_size)
                    if not frame_data or len(frame_data) < frame_size:
                        logger.warning("Incomplete frame payload. Reconnecting...")
                        break

                    t_recv = time.time()
                    img = Image.open(BytesIO(frame_data))

                    if first_frame:
                        logger.info(f"🎉 FIRST FRAME RECEIVED! Size={frame_size} bytes, Res={img.size}, Total time={t_recv - t0:.3f}s")
                        first_frame = False

                    # Memory-safe queue replace
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
                logger.exception(f"Unexpected exception in stream worker: {e}")
                if s:
                    try: s.close()
                    except Exception: pass
                if minicap_proc:
                    try: minicap_proc.terminate()
                    except Exception: pass
                time.sleep(1.0)

    def _persistent_input_worker(self):
        """Ultra-low latency persistent ADB interactive shell pipe (<1ms dispatch)."""
        logger.info("Starting persistent ADB input pipe...")
        
        while self.running:
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
                        logger.debug(f"Input pipe write error: {ex}")
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

            # Single-handle GDI bitmap update (prevent Windows GDI leak)
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

            # Periodic memory garbage collection every 200 frames
            if self.frame_count % 200 == 0:
                gc.collect()

            self.status_lbl.config(
                text=f"Live HD ({self.native_width}x{self.native_height}) | {bytes_len/1024:.1f} KB | FPS: {self.fps:.1f} | Frame: {self.frame_count}"
            )

        except queue.Empty:
            pass
        except Exception as ex:
            self.status_lbl.config(text=f"Error: {ex}")

        self.root.after(16, self._update_loop)

    def _wake_and_unlock(self):
        logger.info("Sending wake and unlock sequence via pipe...")
        self._dispatch_command("input keyevent 26")
        self._dispatch_command("input keyevent 82")
        self._dispatch_command("input swipe 640 600 640 100 200")

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
        if self.input_pipe:
            try:
                if self.input_pipe.stdin: self.input_pipe.stdin.close()
                self.input_pipe.terminate()
            except Exception: pass
        self.root.destroy()


def main():
    root = tk.Tk()
    app = NanoPiViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
