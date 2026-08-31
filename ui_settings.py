"""
Settings Dialog for NanoPiViewer.
Fully in English with presets and fine-tuning options.
"""

import tkinter as tk
from tkinter import messagebox
import config

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, on_save_callback=None):
        super().__init__(parent)
        self.title("Settings - NanoPiViewer")
        self.geometry("450x480")
        self.resizable(False, False)
        self.configure(bg="#2d2d2d")
        self.transient(parent)
        self.grab_set()

        self.on_save_callback = on_save_callback
        self.cfg = config.load_config()

        self._build_ui()

    def _build_ui(self):
        lbl_style = {"bg": "#2d2d2d", "fg": "white", "font": ("Segoe UI", 9)}
        entry_style = {"bg": "#3c3f41", "fg": "white", "insertbackground": "white", "relief": tk.FLAT}

        # Preset Frame
        preset_frame = tk.LabelFrame(self, text=" Quick Network Presets ", bg="#2d2d2d", fg="#4CAF50", padx=10, pady=6)
        preset_frame.pack(fill=tk.X, padx=15, pady=8)

        btn_preset_style = {"bg": "#3c3f41", "fg": "white", "relief": tk.FLAT, "padx": 6, "pady": 2, "cursor": "hand2"}
        tk.Button(preset_frame, text="📶 Wi-Fi (192.168.1.113)", command=lambda: self._set_ip("192.168.1.113"), **btn_preset_style).pack(side=tk.LEFT, padx=4)
        tk.Button(preset_frame, text="🔌 Ethernet (169.254.42.120)", command=lambda: self._set_ip("169.254.42.120"), **btn_preset_style).pack(side=tk.LEFT, padx=4)

        # Connection Settings Frame
        conn_frame = tk.LabelFrame(self, text=" Connection Settings ", bg="#2d2d2d", fg="#4CAF50", padx=10, pady=6)
        conn_frame.pack(fill=tk.X, padx=15, pady=4)

        tk.Label(conn_frame, text="Device IP:", **lbl_style).grid(row=0, column=0, sticky="w", pady=3)
        self.ip_entry = tk.Entry(conn_frame, **entry_style)
        self.ip_entry.insert(0, str(self.cfg.get("device_ip", "192.168.1.113")))
        self.ip_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=3)

        tk.Label(conn_frame, text="ADB Port:", **lbl_style).grid(row=1, column=0, sticky="w", pady=3)
        self.adb_port_entry = tk.Entry(conn_frame, **entry_style)
        self.adb_port_entry.insert(0, str(self.cfg.get("adb_port", 5555)))
        self.adb_port_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=3)

        tk.Label(conn_frame, text="Minicap Port:", **lbl_style).grid(row=2, column=0, sticky="w", pady=3)
        self.minicap_port_entry = tk.Entry(conn_frame, **entry_style)
        self.minicap_port_entry.insert(0, str(self.cfg.get("minicap_port", 1717)))
        self.minicap_port_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=3)

        conn_frame.columnconfigure(1, weight=1)

        # Display & Stream Frame
        disp_frame = tk.LabelFrame(self, text=" Stream & Performance ", bg="#2d2d2d", fg="#4CAF50", padx=10, pady=6)
        disp_frame.pack(fill=tk.X, padx=15, pady=4)

        tk.Label(disp_frame, text="Native Resolution:", **lbl_style).grid(row=0, column=0, sticky="w", pady=3)
        self.native_res_entry = tk.Entry(disp_frame, **entry_style)
        self.native_res_entry.insert(0, str(self.cfg.get("native_resolution", "1280x720")))
        self.native_res_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=3)

        tk.Label(disp_frame, text="Stream Resolution:", **lbl_style).grid(row=1, column=0, sticky="w", pady=3)
        self.stream_res_entry = tk.Entry(disp_frame, **entry_style)
        self.stream_res_entry.insert(0, str(self.cfg.get("stream_resolution", "1280x720")))
        self.stream_res_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=3)

        tk.Label(disp_frame, text="JPEG Quality (10-100):", **lbl_style).grid(row=2, column=0, sticky="w", pady=3)
        self.quality_entry = tk.Entry(disp_frame, **entry_style)
        self.quality_entry.insert(0, str(self.cfg.get("jpeg_quality", 60)))
        self.quality_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=3)

        disp_frame.columnconfigure(1, weight=1)

        # Behavior Frame
        behave_frame = tk.LabelFrame(self, text=" Behavior ", bg="#2d2d2d", fg="#4CAF50", padx=10, pady=6)
        behave_frame.pack(fill=tk.X, padx=15, pady=4)

        self.stayon_var = tk.BooleanVar(value=self.cfg.get("keep_screen_on", True))
        tk.Checkbutton(
            behave_frame, text="Keep Device Screen Awake (svc power stayon)",
            variable=self.stayon_var, bg="#2d2d2d", fg="white",
            selectcolor="#3c3f41", activebackground="#2d2d2d", activeforeground="white"
        ).pack(anchor="w", pady=2)

        # Buttons
        btn_frame = tk.Frame(self, bg="#2d2d2d")
        btn_frame.pack(fill=tk.X, padx=15, pady=12)

        tk.Button(btn_frame, text="Save & Reconnect", bg="#4CAF50", fg="white", activebackground="#45a049", activeforeground="white", relief=tk.FLAT, padx=12, pady=4, command=self._save_and_close, cursor="hand2").pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_frame, text="Cancel", bg="#555555", fg="white", activebackground="#666666", activeforeground="white", relief=tk.FLAT, padx=10, pady=4, command=self.destroy, cursor="hand2").pack(side=tk.RIGHT)

    def _set_ip(self, ip_addr):
        self.ip_entry.delete(0, tk.END)
        self.ip_entry.insert(0, ip_addr)

    def _save_and_close(self):
        try:
            self.cfg["device_ip"] = self.ip_entry.get().strip()
            self.cfg["adb_port"] = int(self.adb_port_entry.get().strip())
            self.cfg["minicap_port"] = int(self.minicap_port_entry.get().strip())
            self.cfg["native_resolution"] = self.native_res_entry.get().strip()
            self.cfg["stream_resolution"] = self.stream_res_entry.get().strip()
            self.cfg["jpeg_quality"] = max(10, min(100, int(self.quality_entry.get().strip())))
            self.cfg["keep_screen_on"] = self.stayon_var.get()

            config.save_config(self.cfg)

            if self.on_save_callback:
                self.on_save_callback(self.cfg)

            self.destroy()
        except ValueError as ex:
            messagebox.showerror("Validation Error", f"Please verify your inputs:\n{ex}")
