import tkinter as tk
from tkinter import ttk, messagebox
import config

class SettingsDialog:
    def __init__(self, parent, on_save_callback=None):
        self.parent = parent
        self.on_save_callback = on_save_callback
        self.config_data = config.load_config()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings - NanoPi Screen Viewer")
        self.dialog.geometry("460x420")
        self.dialog.resizable(False, False)
        self.dialog.configure(bg="#2d2d2d")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._setup_ui()

    def _setup_ui(self):
        lbl_style = {"bg": "#2d2d2d", "fg": "#ffffff", "font": ("Segoe UI", 9)}
        entry_style = {"bg": "#3c3f41", "fg": "#ffffff", "insertbackground": "white", "relief": tk.FLAT}

        container = tk.Frame(self.dialog, bg="#2d2d2d", padx=20, pady=15)
        container.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(
            container, text="⚙ Connection & Display Settings",
            bg="#2d2d2d", fg="#4CAF50", font=("Segoe UI", 12, "bold")
        ).pack(anchor=tk.W, pady=(0, 15))

        # Device IP
        f_ip = tk.Frame(container, bg="#2d2d2d")
        f_ip.pack(fill=tk.X, pady=4)
        tk.Label(f_ip, text="Device IP Address:", width=20, anchor=tk.W, **lbl_style).pack(side=tk.LEFT)
        self.ip_entry = tk.Entry(f_ip, **entry_style)
        self.ip_entry.insert(0, self.config_data.get("device_ip", "192.168.1.113"))
        self.ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ADB Port
        f_adb = tk.Frame(container, bg="#2d2d2d")
        f_adb.pack(fill=tk.X, pady=4)
        tk.Label(f_adb, text="ADB Port:", width=20, anchor=tk.W, **lbl_style).pack(side=tk.LEFT)
        self.adb_port_entry = tk.Entry(f_adb, **entry_style)
        self.adb_port_entry.insert(0, str(self.config_data.get("adb_port", 5555)))
        self.adb_port_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Minicap Port
        f_mc = tk.Frame(container, bg="#2d2d2d")
        f_mc.pack(fill=tk.X, pady=4)
        tk.Label(f_mc, text="Minicap Port:", width=20, anchor=tk.W, **lbl_style).pack(side=tk.LEFT)
        self.mc_port_entry = tk.Entry(f_mc, **entry_style)
        self.mc_port_entry.insert(0, str(self.config_data.get("minicap_port", 1717)))
        self.mc_port_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Native Resolution
        f_res = tk.Frame(container, bg="#2d2d2d")
        f_res.pack(fill=tk.X, pady=4)
        tk.Label(f_res, text="Native Resolution:", width=20, anchor=tk.W, **lbl_style).pack(side=tk.LEFT)
        self.res_entry = tk.Entry(f_res, **entry_style)
        self.res_entry.insert(0, self.config_data.get("native_resolution", "1280x720"))
        self.res_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Stream Resolution
        f_sres = tk.Frame(container, bg="#2d2d2d")
        f_sres.pack(fill=tk.X, pady=4)
        tk.Label(f_sres, text="Stream Resolution:", width=20, anchor=tk.W, **lbl_style).pack(side=tk.LEFT)
        self.sres_entry = tk.Entry(f_sres, **entry_style)
        self.sres_entry.insert(0, self.config_data.get("stream_resolution", "1280x720"))
        self.sres_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Keep awake checkbox
        self.awake_var = tk.BooleanVar(value=self.config_data.get("keep_screen_on", True))
        cb_awake = tk.Checkbutton(
            container, text="Prevent screen sleep (Stay Awake)",
            variable=self.awake_var, bg="#2d2d2d", fg="white", selectcolor="#3c3f41",
            activebackground="#2d2d2d", activeforeground="white"
        )
        cb_awake.pack(anchor=tk.W, pady=(10, 4))

        # Auto connect checkbox
        self.auto_var = tk.BooleanVar(value=self.config_data.get("auto_connect", True))
        cb_auto = tk.Checkbutton(
            container, text="Auto-connect on startup",
            variable=self.auto_var, bg="#2d2d2d", fg="white", selectcolor="#3c3f41",
            activebackground="#2d2d2d", activeforeground="white"
        )
        cb_auto.pack(anchor=tk.W, pady=2)

        # Buttons
        btn_box = tk.Frame(container, bg="#2d2d2d", pady=15)
        btn_box.pack(side=tk.BOTTOM, fill=tk.X)

        btn_style = {"relief": tk.FLAT, "padx": 15, "pady": 4, "cursor": "hand2"}

        tk.Button(
            btn_box, text="Save & Apply", bg="#4CAF50", fg="white",
            activebackground="#45a049", activeforeground="white",
            command=self._save, **btn_style
        ).pack(side=tk.RIGHT, padx=5)

        tk.Button(
            btn_box, text="Cancel", bg="#555555", fg="white",
            activebackground="#666666", activeforeground="white",
            command=self.dialog.destroy, **btn_style
        ).pack(side=tk.RIGHT, padx=5)

    def _save(self):
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter a valid IP address.")
            return

        try:
            adb_port = int(self.adb_port_entry.get().strip())
            mc_port = int(self.mc_port_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Port numbers must be numeric.")
            return

        new_config = {
            "device_ip": ip,
            "adb_port": adb_port,
            "minicap_port": mc_port,
            "native_resolution": self.res_entry.get().strip() or "1280x720",
            "stream_resolution": self.sres_entry.get().strip() or "1280x720",
            "keep_screen_on": self.awake_var.get(),
            "auto_connect": self.auto_var.get(),
            "window_width": self.config_data.get("window_width", 1020),
            "window_height": self.config_data.get("window_height", 660),
            "fps_limit": self.config_data.get("fps_limit", 60)
        }

        if config.save_config(new_config):
            self.dialog.destroy()
            if self.on_save_callback:
                self.on_save_callback(new_config)
        else:
            messagebox.showerror("Error", "Failed to save configuration.")
