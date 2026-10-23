import tkinter as tk
from tkinter import simpledialog, messagebox
import json, os, sys, time, random, math, ctypes, winsound
import configparser
from PIL import Image, ImageTk

KEY = "#ff00fe"
TOP = 90
SIZE = 150          # 서 있는 고양이 전신 크기

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def res(name):
    return os.path.join(getattr(sys, "_MEIPASS", base_dir()), name)

CONFIG_PATH = os.path.join(base_dir(), "settings.ini")
SAVE_PATH = os.path.join(base_dir(), "cat_save.json")

DEFAULT_CONFIG = """[Settings]
Walls = 1
Ceiling = 1
Windows = 1
Idle = 1
Escape = 0
Follow = 0
HungerCry = 1
Speed = 2.2
FallSpeed = 3.0
EscapeDelay = 0.12
HungerMinutes = 60
PetOpacityPercent = 100
"""

def load_or_create_config():
    cfg = configparser.ConfigParser()
    if not os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write(DEFAULT_CONFIG)
        except Exception:
            pass
    cfg.read(CONFIG_PATH, encoding="utf-8")
    if not cfg.has_section("Settings"):
        cfg.add_section("Settings")
    return cfg

def work_area(root):
    try:
        class RECT(ctypes.Structure):
            _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                        ("r", ctypes.c_long), ("b", ctypes.c_long)]
        r = RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0)
        return r.l, r.t, r.r, r.b
    except Exception:
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()

def get_foreground_window_rect(exclude_hwnd):
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd or hwnd == exclude_hwnd:
            return None
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return None
        class RECT(ctypes.Structure):
            _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                        ("r", ctypes.c_long), ("b", ctypes.c_long)]
        r = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
        return r.l, r.t, r.r, r.b
    except Exception:
        return None

class Pet:
    def __init__(self):
        r = self.root = tk.Tk()
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-transparentcolor", KEY)
        r.config(bg=KEY)
        self.hwnd = ctypes.windll.user32.GetParent(r.winfo_id())

        self.cfg = load_or_create_config()
        self.apply_config()

        self.L, self.T, self.R, self.B = work_area(r)

        # 이미지 리사이즈
        img = Image.open(res("pet.png")).convert("RGBA")
        h = SIZE
        w = int(img.width * h / img.height)
        img = img.resize((w, h), Image.LANCZOS)
        self.W, self.H = w + 40, h + TOP

        # 애니메이션 프레임
        self.frames = {}
        for flip in (False, True):
            base = img.transpose(Image.FLIP_LEFT_RIGHT) if flip else img
            for name, (sx, sy) in {"n": (1, 1), "tall": (.94, 1.08), "squash": (1.1, .9)}.items():
                self.frames[(name, flip, 0)] = self.make(base, sx, sy, 0)
                self.frames[(name, flip, 90)] = self.make(base
