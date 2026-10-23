"""
바탕화면 펫 프로그램 (확장 버전)
- 고양이 / 강아지 실제 사진 기반 자연스러운 물리 동작
- 커스텀 알림창 (정각, 점심, 퇴근) & 화면 가장자리 빛(Glow) 효과
- 세부 움직임 조절 (슬라이딩 도망, 커서 따라오기, 근무시간 얌전 모드, 전체화면 자동 숨기기)
- Windows 시작 프로그램 등록 및 설정 창 완벽 대응
"""
import tkinter as tk
from tkinter import ttk
import json, os, sys, time, random, math, ctypes
from PIL import Image, ImageTk

WIN = sys.platform == "win32"
KEY = "#ff00fe"          # 투명 크로마키 색
FONT = "맑은 고딕"
TOP = 110                # 말풍선 + 점프 공간
MAX_PETS = 5
MILESTONES = [50, 100, 200, 300, 500, 1000, 2000, 3000, 5000, 10000]

if WIN:
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

SAVE = os.path.join(base_dir(), "pet_save.json")

# 확장된 기본 설정값
DEFAULTS = {
    # 기본
    "speed": 3, "activity": 5, "size": 140, "opacity": 100,
    "click_reaction": "폴짝", "hunger_min": 60, "snack": 25,
    "cry_always": False, "hidden_reactions": True,
    "locked": False, "safe_mode": False,
    "show_inti": False, "idle_nap_min": 10,
    
    # 움직임 세부 설정 (사진 2)
    "allow_wall": True, "allow_ceil": True, "allow_window": True,
    "allow_sit": True, "short_sit": False,
    "flee_mouse": True, "follow_mouse": False,
    "work_safe_mode": False, "auto_hide_fullscreen": False,
    "spd_walk": 2.0, "spd_spin": 3.0, "spd_slide": 3.0,
    "slide_delay": 0.12,

    # 알림 및 자동 시작 설정 (사진 1)
    "autostart": False,
    "notify_hour_popup": True,
    "work_hour_mute": False,
    "work_mute_start": 9, "work_mute_end": 18,
    "glow_edge": True,
    "glow_color": "피치·핑크·보라·하늘",
    "glow_width": "넓게",
    "glow_intensity": "선명하게",
    
    "notify_lunch": True, "lunch_time": "12:00", "lunch_msg": "점심 먹으러 가자!",
    "notify_leave": True, "leave_time": "18:00", "leave_msg": "퇴근이다! 오늘도 수고했어",
    
    "notify_hungry": True, "notify_hour": True, "sound": True,
}

SECRETS = {
    "spin": ("빙글빙글", "머리 위에서 마우스를 한 바퀴 돌려보기"),
    "dance": ("몰래 하는 군무", "친구가 둘 이상일 때 마우스를 4초 동안 가만히 두기"),
    "tickle": ("간지럼", "친구를 빠르게 5번 클릭하기"),
}

# Windows 레지스트리 / 창 제어 API
if WIN:
    user32 = ctypes.windll.user32
    try:
        dwm = ctypes.windll.dwmapi
    except Exception:
        dwm = None

    class RECT(ctypes.Structure):
        _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                    ("r", ctypes.c_long), ("b", ctypes.c_long)]

    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    user32.GetForegroundWindow.restype = ctypes.c_void_p

def set_autostart(enable=True):
    if not WIN: return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        app_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        if enable:
            winreg.SetValueEx(key, "DesktopPetApp", 0, winreg.REG_SZ, f'"{app_path}"')
        else:
            try:
                winreg.DeleteValue(key, "DesktopPetApp")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass

def is_fullscreen_app_active():
    if not WIN: return False
    try:
        fg = user32.GetForegroundWindow()
        if not fg: return False
        r = RECT()
        user32.GetWindowRect(fg, ctypes.byref(r))
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        return (r.l <= 0 and r.t <= 0 and r.r >= sw and r.b >= sh)
    except Exception:
        return False

def work_area(root):
    if WIN:
        try:
            r = RECT()
            user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0)
            return r.l, r.t, r.r, r.b
        except Exception:
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 40

def list_windows(min_top):
    out = []
    if not WIN: return out
    pid = os.getpid()

    def cb(hwnd, lp):
        try:
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            if user32.GetWindowTextLengthW(hwnd) == 0:
                return True
            ex = user32.GetWindowLongW(hwnd, -20)
            if (ex & 0x80) and not (ex & 0x40000):
                return True
            p = ctypes.c_ulong(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid:
                return True
            if dwm:
                c = ctypes.c_int(0)
                dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(c), 4)
                if c.value:
                    return True
            r = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.r - r.l < 250 or r.b - r.t < 120 or r.t < min_top + 30:
                return True
            out.append((hwnd, (r.l, r.t, r.r, r.b)))
        except Exception:
            pass
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return out

def window_rect(hwnd):
    if not WIN: return None
    try:
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd): return None
        r = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        return (r.l, r.t, r.r, r.b)
    except Exception:
        return None

# ---------------------------------------------------------------- 화면 테두리 빛 (Glow Effect)
class EdgeGlowWindow:
    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass
        self.win.config(bg=KEY)
        
        self.sw = root.winfo_screenwidth()
        self.sh = root.winfo_screenheight()
        self.win.geometry(f"{self.sw}x{self.sh}+0+0")
        
        self.cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg=KEY, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.win.withdraw()

    def show(self, palette_mode="피치·핑크·보라·하늘", width_mode="넓게"):
        self.cv.delete("all")
        glow_thick = 24 if width_mode == "넓게" else 14
        
        # 그라데이션 및 색상 밴드 구성
        colors = ["#ff9aa2", "#ffb7b2", "#ffdac1", "#e2f0cb", "#b5ead7", "#c7ceea"]
        steps = glow_thick // 2
        for i in range(steps):
            c = colors[i % len(colors)]
            pad = i * 2
            self.cv.create_rectangle(pad, pad, self.sw - pad, self.sh - pad, outline=c, width=2)
            
        self.win.deiconify()
        self.win.attributes("-topmost", True)

    def hide(self):
        self.win.withdraw()

# ---------------------------------------------------------------- 별도 알림창 (사진 1)
class CustomAlertPopup:
    def __init__(self, root, on_close=None):
        self.root = root
        self.on_close = on_close
        self.win = tk.Toplevel(root)
        self.win.title("정각 알림")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.config(bg="#f8f9fa")
        
        # 둥근 카드 모양 프레임
        f = tk.Frame(self.win, bg="#ffffff", bd=1, relief="solid")
        f.pack(fill="both", expand=True, padx=4, pady=4)
        
        # 닫기 (X)
        top_bar = tk.Frame(f, bg="#ffffff")
        top_bar.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(top_bar, text="알림", font=(FONT, 9, "bold"), bg="#ffffff", fg="#666666").pack(side="left")
        close_btn = tk.Label(top_bar, text="✕", font=(FONT, 11), bg="#ffffff", fg="#999999", cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self.close())
        
        self.lbl_title = tk.Label(f, text="정각 알림", font=(FONT, 10), bg="#ffffff", fg="#888888")
        self.lbl_title.pack(anchor="w", padx=18, pady=(8, 0))
        
        self.lbl_time = tk.Label(f, text="11:00", font=(FONT, 38, "bold"), bg="#ffffff", fg="#222222")
        self.lbl_time.pack(anchor="w", padx=14, pady=2)
        
        self.lbl_sub = tk.Label(f, text="오전 11시야!\n(미리보기)", font=(FONT, 10), bg="#ffffff", fg="#555555", justify="left")
        self.lbl_sub.pack(anchor="w", padx=18, pady=(0, 16))
        
        btn = tk.Button(f, text="확인했어", font=(FONT, 10, "bold"), bg="#2d3238", fg="#ffffff",
                        activebackground="#454b52", activeforeground="#ffffff", relief="flat",
                        padx=18, pady=6, cursor="hand2", command=self.close)
        btn.pack(anchor="e", padx=18, pady=(0, 14))

    def show(self, time_str, sub_text, title="알림"):
        self.lbl_title.config(text=title)
        self.lbl_time.config(text=time_str)
        self.lbl_sub.config(text=sub_text)
        
        w, h = 300, 220
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        # 화면 좌측 상단 살짝 안쪽에 띄우기
        self.win.geometry(f"{w}x{h}+60+{sh // 4}")
        self.win.deiconify()
        self.win.attributes("-topmost", True)

    def close(self):
        self.win.withdraw()
        if self.on_close:
            self.on_close()

# ---------------------------------------------------------------- 펫 한 마리
class Pet:
    def __init__(self, g, idx):
        self.g, self.idx = g, idx
        w = self.win = tk.Toplevel(g.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass
        w.config(bg=KEY)
        self.cv = tk.Canvas(w, width=g.W, height=g.H, bg=KEY, highlightthickness=0)
        self.cv.pack()
        self.item = self.cv.create_image(g.W // 2, g.H, anchor="s")

        self.x = random.randint(int(g.L), max(int(g.L), int(g.R - g.W)))
        self.y = self.ground()
        self.vy = 0
        self.sq = 0
        self.dir = random.choice([-1, 1])
        self.bubble, self.bu, self.drawn = "", 0, None
        self.clicks = []
        self.moved, self.off, self.start_pos = False, (0, 0), (0, 0)
        self.last_geo = None
        self.fxk = set()
        self.flee_cooldown = 0
        self.start("idle")

        c = self.cv
        c.bind("<ButtonPress-1>", self.press)
        c.bind("<B1-Motion>", self.motion)
        c.bind("<ButtonRelease-1>", self.release)
        c.bind("<Button-3>", self.menu)

    def ground(self):
        return self.g.B - self.g.H + 10

    def place(self):
        geo = (int(self.x), int(self.y))
        if geo != self.last_geo:
            self.last_geo = geo
            self.win.geometry(f"{self.g.W}x{self.g.H}+{geo[0]}+{geo[1]}")

    def resize(self):
        g = self.g
        self.cv.config(width=g.W, height=g.H)
        self.y = self.ground()
        self.last_geo = None
        self.start("idle")

    def say(self, text, secs=2.0):
        self.bubble, self.bu = text, time.time() + secs

    def face(self, dx, dy):
        g = self.g
        return g.W // 2 + dx, g.H - g.ih * 0.55 + dy

    def start(self, act, **kw):
        g, s = self.g, self.g.s
        self.act, self.t, self.kw = act, 0, kw
        sc = (11 - s["activity"]) / 5.0
        if act == "idle":
            self.dur = int(random.randint(35, 95) * sc)
        elif act == "walk":
            self.dir = random.choice([-1, 1])
            self.dur = random.randint(90, 250)
        elif act == "sit":
            base_dur = random.randint(30, 60) if s["short_sit"] else random.randint(110, 240)
            self.dur = int(base_dur * sc)
        elif act == "hop":
            self.dur = 22 * kw.get("n", random.randint(1, 3))
        elif act == "cry":
            if kw.get("kind") == "hungry":
                self.dur = 140
                self.say("배고파요 ㅠㅠ 간식 줘요", 3)
            else:
                self.dur = 100
                self.say("으앙… 놀랐잖아요", 2)
        elif act == "laugh":
            self.dur = 70
            self.say("헤헤! 너무 좋아요♥", 2)
        elif act == "eat":
            self.dur = 55
        elif act == "slide":
            self.dir = kw.get("dir", random.choice([-1, 1]))
            self.dur = int(34 / max(0.5, s.get("spd_slide", 3.0) / 3.0))
            self.say("슝~ 달리기!", 1.5)
        elif act == "dizzy":
            self.dur = 100
            self.say("어질어질… 빙글빙글", 2.5)
        elif act == "spin":
            self.dur = int(75 / max(0.5, s.get("spd_spin", 3.0) / 3.0))
            self.say("위이이잉! 날아간다~", 2)
        elif act == "dance":
            self.dur = 200
        elif act == "wall":
            self.phase = "go"
            self.side = "left" if self.x + g.W / 2 < (g.L + g.R) / 2 else "right"
            self.dir = -1 if self.side == "left" else 1
            self.say("벽 타기!", 1.5)
        elif act == "ceil":
            self.phase = "rise"
            self.x0, self.y0 = self.x, self.y
            self.dir = random.choice([-1, 1])
            self.say("천장으로 올라가요!", 1.5)
        elif act == "perch":
            wins = list_windows(g.T)
            if not wins:
                self.say("올라갈 창이 없어요", 2)
                return self.start("hop", n=2)
            self.hw, rect = random.choice(wins)
            l, t, r, b = rect
            cx = random.randint(l + 60, max(l + 60, r - 60))
            self.tx = cx - g.W / 2
            self.ty = t + 5 - g.H
            self.x0, self.y0 = self.x, self.y
            self.phase = "jump"
            self.pdur = random.randint(200, 450)
            self.say("창 위로 올라가자!", 1.5)
        elif act == "fall":
            self.vy = 0

    def next(self):
        g, s = self.g, self.g.s
        if g.hungry() and random.random() < 0.55:
            return self.start("cry", kind="hungry")
            
        # 평일 얌전 모드 확인
        work_safe = False
        if s["work_safe_mode"]:
            lt = time.localtime()
            if lt.tm_wday < 5 and (9 <= lt.tm_hour < 18):
                work_safe = True

        if s["locked"] or s["safe_mode"] or work_safe:
            ch = [("idle", 50), ("hop", 20)]
            if s["allow_sit"]: ch.append(("sit", 30))
        else:
            ch = [("walk", 40), ("idle", 14), ("hop", 8), ("slide", 6), ("dizzy", 3), ("spin", 3)]
            if s["allow_sit"]: ch.append(("sit", 12))
            if s["allow_wall"]: ch.append(("wall", 5))
            if s["allow_ceil"]: ch.append(("ceil", 4))
            if s["allow_window"] and WIN: ch.append(("perch", 7))
            
        names = [c[0] for c in ch]
        weights = [c[1] for c in ch]
        self.start(random.choices(names, weights)[0])

    def press(self, e):
        self.off = (e.x_root - self.x, e.y_root - self.y)
        self.start_pos = (e.x_root, e.y_root)
        self.moved = False

    def motion(self, e):
        if not self.moved and abs(e.x_root - self.start_pos[0]) + abs(e.y_root - self.start_pos[1]) > 6:
            self.moved = True
            self.start("drag")
        if self.moved:
            self.x = e.x_root - self.off[0]
            self.y = e.y_root - self.off[1]
            self.place()

    def release(self, e):
        if self.moved:
            self.start("fall")
            return
        g, s = self.g, self.g.s
        now = time.time()
        self.clicks = [c for c in self.clicks if now - c < 2.5] + [now]
        if s["hidden_reactions"] and len(self.clicks) >= 5:
            self.clicks = []
            g.found("tickle", self)
            return self.start("laugh")
        r = s["click_reaction"]
        if r == "랜덤":
            r = random.choice(["폴짝", "울기", "어질어질"])
        if r == "울기":
            self.start("cry", kind="click")
        elif r == "어질어질":
            self.start("dizzy")
        else:
            self.say(random.choice(["신난다!", "함께 놀자!", "쓰다듬어줘서 좋아♥"]), 1.5)
            self.start("hop", n=1)

    def menu(self, e):
        g = self.g
        m = tk.Menu(self.win, tearoff=0, font=(FONT, 10))
        m.add_command(label=f"♥ 친밀도 {g.inti}  ·  함께 {g.mins}분", state="disabled")
        m.add_command(label="친구 한 마리 더 부르기", command=g.add_pet)
        m.add_command(label="이 친구 보내기", command=lambda: g.remove_pet(self))
        m.add_command(label="모두 숨기기", command=g.hide_all)
        m.add_separator()
        m.add_command(label="알림 설정...", command=g.open_notify)
        m.add_command(label="화면 가운데로 모으기", command=g.gather)
        m.add_command(label="움직임 · 반응 설정...", command=g.open_motion)
        m.add_checkbutton(label="위치 고정 (자동 이동 멈추기)", variable=g.lock_var, command=g.sync_flags)
        m.add_command(label="친구 기록 · 생활 설정...", command=g.open_record)
        m.add_command(label="도우미 · 할 일 · 메모 · 타이머...", command=g.open_helper)
        m.add_command(label=f"간식 주기  ·  포만감 {int(g.sat)}/100", command=lambda: g.feed(self))
        
        sub = tk.Menu(m, tearoff=0, font=(FONT, 10))
        for label, act, kw in ACT_MENU:
            sub.add_command(label=label, command=lambda a=act, k=kw: self.start(a, **k))
        m.add_cascade(label="동작 바로 보기", menu=sub)
        
        m.add_checkbutton(label="안전 모드 (바닥에서만 놀기)", variable=g.safe_var, command=g.sync_flags)
        m.add_separator()
        m.add_command(label="종료", command=g.quit)
        self.win.focus_force()
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def a_idle(self):
        self.y = self.ground()
        k = math.sin(self.t * 0.12)
        if self.t >= self.dur:
            self.next()
        return 0, 0, 0, 1 - 0.015 * k, 1 + 0.02 * k

    def a_walk(self):
        g = self.g
        self.y = self.ground()
        sp = g.s["speed"] * (g.s["spd_walk"] / 2.0) * (0.6 if g.hungry() else 1.0)
        
        # 커서 따라오기 모드
        if g.s["follow_mouse"]:
            px, _ = self.win.winfo_pointerxy()
            cx = self.x + g.W / 2
            if abs(px - cx) > 40:
                self.dir = 1 if px > cx else -1
                
        self.x += self.dir * sp
        if self.x < g.L - 25: self.dir = 1
        if self.x > g.R - g.W + 25: self.dir = -1
        k = math.sin(self.t * 0.28)
        if self.t >= self.dur:
            self.next()
        return 0, -abs(k) * 5, 2 * k, 1, 1

    def a_sit(self):
        self.y = self.ground()
        k = math.sin(self.t * 0.1)
        if self.t > 50:
            self.fxk.add("zzz")
        if self.t >= self.dur:
            self.next()
        return 0, 2, 0, 1.04, 0.94 + 0.015 * k

    def a_hop(self):
        self.y = self.ground()
        jl = 22
        n = self.kw.get("n", 1)
        if self.t >= jl * n:
            self.sq = 5
            self.start("idle")
            return 0, 0, 0, 1, 1
        u = (self.t % jl) / jl
        dy = -4 * 55 * u * (1 - u)
        return 0, dy, 0, (0.94 if u < 0.5 else 1.02), (1.08 if u < 0.5 else 0.98)

    def a_cry(self):
        self.y = self.ground()
        self.fxk.add("tears")
        dx = 2 if (self.t // 2) % 2 else -2
        if self.t >= self.dur:
            self.next() if self.kw.get("kind") == "hungry" else self.start("idle")
        return dx, 0, 0, 1, 0.96

    def a_laugh(self):
        self.y = self.ground()
        self.fxk.add("hearts")
        dx = 2 if (self.t // 2) % 2 else -2
        if self.t >= self.dur:
            self.start("idle")
        return dx, -abs(math.sin(self.t * 0.4)) * 6, 0, 1.02, 1.0

    def a_eat(self):
        self.y = self.ground()
        self.fxk.add("cookie")
        if self.t >= self.dur:
            self.say("냠냠! 맛있다♥", 2)
            self.start("idle")
        return 0, -abs(math.sin(self.t * 0.5)) * 4, 0, 1, 1

    def a_slide(self):
        g = self.g
        self.y = self.ground()
        base_s = 16 * (g.s["spd_slide"] / 3.0)
        sp = base_s * (1 - self.t / self.dur)
        self.x += self.dir * sp
        self.x = max(g.L - 25, min(g.R - g.W + 25, self.x))
        self.fxk.add("dust")
        if self.t >= self.dur:
            self.sq = 6
            self.start("idle")
        return 0, 0, -18 * self.dir, 1.06, 0.9

    def a_dizzy(self):
        self.y = self.ground()
        self.fxk.add("stars")
        if self.t >= self.dur:
            self.start("idle")
        return 0, 0, 10 * math.sin(self.t * 0.45), 1, 1

    def a_spin(self):
        self.y = self.ground()
        t, d = self.t, self.dur
        if t < 20: lift = 4 * t
        elif t < 55: lift = 80
        else: lift = 80 * (1 - (t - 55) / (d - 55))
        if t >= d:
            self.sq = 6
            self.start("idle")
        rot_spd = 40 * (self.g.s["spd_spin"] / 3.0)
        return math.sin(t * 0.2) * 8, -lift, (t * rot_spd) % 360, 1, 1

    def a_dance(self):
        self.y = self.ground()
        self.fxk.add("notes")
        u = self.g.tm * 7 + self.idx * math.pi
        if self.t >= self.dur:
            self.start("idle")
        f = math.sin(u)
        return 0, -abs(f) * 12, 10 * f, 1, 1

    def a_drag(self):
        return 0, 0, math.sin(self.t * 0.3) * 8, 1, 1.04

    def a_fall(self):
        self.vy += 2.5
        self.y += self.vy
        if self.y >= self.ground():
            self.y = self.ground()
            self.sq = 6
            self.start("idle")
        return 0, 0, 0, 0.95, 1.05

    def a_wall(self):
        g = self.g
        left = self.side == "left"
        ang = -90 if left else 90
        fw = g.frame(ang, flip=False).width()
        tx = g.L - (g.W - fw) / 2 if left else g.R - (g.W + fw) / 2
        sp_climb = 2.5 * (g.s["spd_walk"] / 2.0)
        if self.phase == "go":
            self.y = self.ground()
            step = 7 if tx > self.x else -7
            if abs(tx - self.x) <= 7:
                self.x = tx
                self.phase = "climb"
                avail = max(60, self.ground() - g.T)
                self.climb_to = self.ground() - random.randint(int(avail * .35), int(avail * .85))
                self.ht = 0
            else:
                self.x += step
            k = math.sin(self.t * 0.4)
            return 0, -abs(k) * 4, 2 * k, 1, 1
        self.x = tx
        if self.phase == "climb":
            self.y -= sp_climb
            if self.y <= self.climb_to or self.y <= g.T:
                self.phase = "hang"
            return math.sin(self.t * 0.4) * 2, 0, ang, 1, 1
        self.ht += 1
        if self.ht > 25:
            self.start("fall")
        return 0, 0, ang, 1, 1

    def a_ceil(self):
        g = self.g
        fh = g.frame(180, flip=False).height()
        ty = g.T - (g.H - fh)
        if self.phase == "rise":
            u = min(1, self.t / 25)
            self.y = self.y0 + (ty - self.y0) * u
            if u >= 1:
                self.phase, self.ct = "crawl", 0
            return 0, -math.sin(math.pi * u) * 20, 180 * u, 1, 1
        self.y = ty
        self.x += self.dir * 2 * (g.s["spd_walk"] / 2.0)
        if self.x < g.L - 25: self.dir = 1
        if self.x > g.R - g.W + 25: self.dir = -1
        self.ct += 1
        if self.ct > 150:
            self.start("fall")
        return 0, math.sin(self.t * 0.3) * 2, 180, 1, 1

    def a_perch(self):
        g = self.g
        if self.phase == "jump":
            u = min(1, self.t / 30)
            self.x = self.x0 + (self.tx - self.x0) * u
            self.y = self.y0 + (self.ty - self.y0) * u
            if u >= 1:
                r = window_rect(self.hw)
                if r is None:
                    self.start("fall")
                    return 0, 0, 0, 1, 1
                self.phase, self.pt = "walk", 0
                self.rect = r
                self.rel = self.x - r[0]
                self.dir = random.choice([-1, 1])
                self.sq = 4
            return 0, -math.sin(math.pi * u) * 45, 0, 1, 1
        if self.t % 5 == 0:
            r = window_rect(self.hw)
            if r is None:
                self.start("fall")
                return 0, 0, 0, 1, 1
            self.rect = r
        l, t, r_, b = self.rect
        self.rel += self.dir * 1.6 * (g.s["spd_walk"] / 2.0)
        lo, hi = -g.W / 2 + 30, (r_ - l) - g.W / 2 - 30
        if self.rel < lo: self.rel, self.dir = lo, 1
        if self.rel > hi: self.rel, self.dir = hi, -1
        self.x = l + self.rel
        self.y = t + 5 - g.H
        self.pt += 1
        if self.pt > self.pdur:
            self.start("fall")
        k = math.sin(self.t * 0.28)
        return 0, -abs(k) * 3, 2 * k, 1, 1

    def update(self):
        g = self.g
        now = time.time()
        self.fxk = set()
        
        # 커서가 가까이 오면 슬라이딩으로 도망가기 로직 (사진 2)
        if g.s["flee_mouse"] and self.act in ("idle", "walk", "sit") and now > self.flee_cooldown:
            px, py = self.win.winfo_pointerxy()
            cx, cy = self.x + g.W / 2, self.y + g.H / 2
            if math.hypot(px - cx, py - cy) < 70:
                flee_dir = -1 if px > cx else 1
                self.flee_cooldown = now + g.s.get("slide_delay", 0.12) + 1.5
                self.start("slide", dir=flee_dir)

        pose = getattr(self, "a_" + self.act)()
        self.t += 1
        dx, dy, ang, sx, sy = pose
        if self.sq > 0 and abs(ang) < 1 and self.act not in ("drag",):
            sx, sy = 1.1, 0.9
            self.sq -= 1
        if g.hungry() and g.s["cry_always"] and self.act in ("walk", "idle", "sit"):
            self.fxk.add("tears")

        flip = self.dir > 0
        fr = g.frame(ang, sx, sy, flip)
        self.cv.itemconfig(self.item, image=fr)
        self.cv.coords(self.item, g.W // 2 + dx, g.H + dy)
        self.place()
        self.draw_fx(dx, dy, ang, now)
        self.draw_bubble(now)

    def draw_fx(self, dx, dy, ang, now):
        g, cv = self.g, self.cv
        cv.delete("fx")
        cx, fy = self.face(dx, dy)
        t = self.t
        
        # 친밀도 숫자 상시 표시 (사진 2)
        if g.s["show_inti"]:
            cv.create_text(g.W // 2, g.H - g.ih - 10, text=f"♥ {g.inti}", fill="#ff4081",
                           font=(FONT, 9, "bold"), tags="fx")
                           
        if "tears" in self.fxk and abs(ang) < 1:
            for i, s in enumerate((-1, 1)):
                ex = cx + s * g.ih * 0.14
                ey = fy + ((t * 3 + i * 9) % 32)
                cv.create_oval(ex - 3, ey - 4, ex + 3, ey + 4, fill="#6cc5ff", outline="#3b9be0", tags="fx")
        if "hearts" in self.fxk:
            for i in range(3):
                hx = cx + (i - 1) * 26
                hy = fy - 20 - ((t * 1.5 + i * 12) % 40)
                cv.create_text(hx, hy, text="♥", fill="#ff5c8a", font=(FONT, 14, "bold"), tags="fx")
        if "stars" in self.fxk:
            for i in range(3):
                a = t * 0.2 + i * 2.1
                cv.create_text(cx + math.cos(a) * 34, fy - g.ih * 0.33 + math.sin(a) * 9,
                               text="★", fill="#ffd23c", font=(FONT, 13), tags="fx")
        if "zzz" in self.fxk:
            for i in range(3):
                zy = fy - 10 - ((t * 0.7 + i * 14) % 42)
                cv.create_text(cx + 26 + i * 7, zy, text="z", fill="#5b6c8f", font=(FONT, 9 + i * 2, "bold"), tags="fx")
        if "cookie" in self.fxk:
            r = max(2, 10 * (1 - self.t / max(1, self.dur)))
            ky = fy + 0.14 * g.ih
            cv.create_oval(cx - r, ky - r, cx + r, ky + r, fill="#d9953f", outline="#a8691c", tags="fx")
        if "notes" in self.fxk:
            for i in range(3):
                nx = cx + (i - 1) * 34
                ny = g.H - g.ih - 8 - ((t * 1.2 + i * 15) % 25)
                cv.create_text(nx, ny, text="♪", fill="#7a5cff", font=(FONT, 15, "bold"), tags="fx")
        if "dust" in self.fxk:
            for i in range(4):
                px = cx - self.dir * (g.iw * 0.4 + i * 12)
                py = g.H - 6 - i * 3
                rr = 6 - i
                cv.create_oval(px - rr, py - rr, px + rr, py + rr, fill="#d8d3c8", outline="", tags="fx")
        if now < g.bouquet_until and self.idx == 0:
            bx, by = g.W // 2 + g.iw * 0.45, g.H - 22
            for k in range(5):
                a = k * 1.256
                cv.create_oval(bx + math.cos(a) * 7 - 5, by + math.sin(a) * 7 - 5,
                               bx + math.cos(a) * 7 + 5, by + math.sin(a) * 7 + 5,
                               fill="#ff8fb8", outline="#e0568f", tags="fx")
            cv.create_oval(bx - 4, by - 4, bx + 4, by + 4, fill="#ffe066", outline="", tags="fx")
            cv.create_line(bx, by + 8, bx, by + 24, fill="#3aa655", width=3, tags="fx")

    def draw_bubble(self, now):
        g, cv = self.g, self.cv
        text = self.bubble if now < self.bu else ""
        if not text and g.hungry() and g.s["notify_hungry"] and self.act in ("idle", "sit", "cry"):
            text = "배고파요 ㅠㅠ 간식 줘요"
        if text != self.drawn:
            cv.delete("b")
            if text:
                t = cv.create_text(g.W // 2, 24, text=text, tags="b", width=g.W - 24,
                                   justify="center", font=(FONT, 10, "bold"), fill="#333333")
                x1, y1, x2, y2 = cv.bbox(t)
                rc = cv.create_rectangle(x1 - 8, y1 - 4, x2 + 8, y2 + 4, fill="white", outline="#ffb300", width=2, tags="b")
                cv.tag_lower(rc, t)
            self.drawn = text

ACT_MENU = [
    ("앉아서 쉬기", "sit", {}),
    ("클릭할 때 달달 떨며 우는 모습", "cry", {"kind": "click"}),
    ("배고플 때 우는 모습", "cry", {"kind": "hungry"}),
    ("폴짝 뛰기", "hop", {"n": 2}),
    ("슬라이딩", "slide", {}),
    ("어질어질", "dizzy", {}),
    ("헬리콥터 돌기", "spin", {}),
    ("벽 타기", "wall", {}),
    ("천장 타기", "ceil", {}),
    ("창 타기", "perch", {}),
    ("몰래 하는 군무", "dance", {}),
]

# ---------------------------------------------------------------- 전체 관리 (Game)
class Game:
    def __init__(self):
        r = self.root = tk.Tk()
        r.withdraw()
        self.L, self.T, self.R, self.B = work_area(r)
        d = {}
        try:
            with open(SAVE, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            pass
        self.s = dict(DEFAULTS)
        self.s.update(d.get("s", {}))
        self.sat = float(d.get("sat", 100))
        self.inti = int(d.get("inti", 0))
        self.mins = int(d.get("mins", 0))
        self.secrets = list(d.get("secrets", []))
        self.todos = list(d.get("todos", []))
        self.memo = d.get("memo", "")
        self.lock_var = tk.BooleanVar(value=self.s["locked"])
        self.safe_var = tk.BooleanVar(value=self.s["safe_mode"])

        # 이미지 파일 로드
        self.photo_base = None
        target_name = None
        for cand in ["pet.png", "PET.PNG", "pet_2.png", "PET_2.PNG"]:
            p = res(cand)
            if os.path.exists(p):
                target_name = p
                break

        if not target_name:
            search_dir = getattr(sys, "_MEIPASS", base_dir())
            if os.path.exists(search_dir):
                pngs = [f for f in os.listdir(search_dir) if f.lower().endswith(".png")]
                if pngs:
                    target_name = os.path.join(search_dir, pngs[0])

        if target_name and os.path.exists(target_name):
            try:
                self.photo_base = Image.open(target_name).convert("RGBA")
            except Exception:
                self.photo_base = None

        if self.photo_base is None:
            self.photo_base = Image.new("RGBA", (140, 140), (255, 180, 0, 255))

        self.cache = {}
        self.set_size(self.s["size"])
        self.pets = []
        self.wins = {}
        self.acc, self.last, self.tm = 0.0, time.time(), 0.0
        self.bouquet_until = 0
        self.timer_end = 0
        self.last_hour = -1
        self.last_min_check = -1
        self.last_hungry_note = 0
        self.still, self.lastp = 0.0, (0, 0)
        self.dancing, self.dance_cool = False, 0
        self.circ = {}
        self.restore_win = None
        
        # 가장자리 빛 & 커스텀 알림 팝업 초기화
        self.edge_glow = EdgeGlowWindow(r)
        self.alert_popup = CustomAlertPopup(r, on_close=self.on_alert_closed)

        for i in range(max(1, min(MAX_PETS, int(d.get("pets", 1))))):
            self.pets.append(Pet(self, i))

        self.apply_opacity()
        self.loop()

    def set_size(self, size):
        h = int(size)
        self.ih = h
        w = int(self.photo_base.width * h / max(1, self.photo_base.height))
        self.iw = w
        self.W, self.H = w + 50, h + TOP
        self.cache.clear()

    def apply_opacity(self):
        op = max(0.1, min(1.0, self.s.get("opacity", 100) / 100.0))
        for p in self.pets:
            try:
                p.win.attributes("-alpha", op)
            except Exception:
                pass

    def frame(self, angle=0, sx=1.0, sy=1.0, flip=False):
        a = int(round(angle / 4.0) * 4) % 360
        key = (a, round(sx, 2), round(sy, 2), flip)
        fr = self.cache.get(key)
        if fr is None:
            if len(self.cache) > 600:
                self.cache.clear()
            im = self.photo_base
            if flip:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            tw = max(1, int(self.iw * sx))
            th = max(1, int(self.ih * sy))
            im = im.resize((tw, th), Image.LANCZOS)
            if a != 0:
                im = im.rotate(a, expand=True, resample=Image.BICUBIC)
            mask = im.getchannel("A").point(lambda v: 255 if v > 110 else 0)
            bg = Image.new("RGB", im.size, KEY)
            bg.paste(im.convert("RGB"), mask=mask)
            fr = ImageTk.PhotoImage(bg)
            self.cache[key] = fr
        return fr

    def apply_size(self):
        self.set_size(self.s["size"])
        for p in self.pets:
            p.resize()

    def hungry(self):
        return self.s["hunger_min"] <= 0 or self.sat < 20

    def save(self):
        self.s["locked"] = bool(self.lock_var.get())
        self.s["safe_mode"] = bool(self.safe_var.get())
        try:
            with open(SAVE, "w", encoding="utf-8") as f:
                json.dump({"s": self.s, "sat": self.sat, "inti": self.inti,
                           "mins": self.mins, "secrets": self.secrets,
                           "todos": self.todos, "memo": self.memo,
                           "pets": len(self.pets)}, f, ensure_ascii=False)
        except Exception:
            pass

    def sync_flags(self):
        self.s["locked"] = bool(self.lock_var.get())
        self.s["safe_mode"] = bool(self.safe_var.get())
        if self.s["safe_mode"]:
            for p in self.pets:
                if p.act in ("wall", "ceil", "perch"):
                    p.start("fall")
        self.save()

    def next_milestone(self):
        for m in MILESTONES:
            if m > self.inti:
                return m
        return None

    def trigger_custom_alert(self, title, time_str, msg):
        self.alert_popup.show(time_str, msg, title=title)
        if self.s.get("glow_edge", True):
            self.edge_glow.show(self.s.get("glow_color", "피치·핑크·보라·하늘"), self.s.get("glow_width", "넓게"))
        if WIN and self.s["sound"]:
            try:
                import winsound
                winsound.Beep(880, 200)
                winsound.Beep(1320, 300)
            except Exception:
                pass

    def on_alert_closed(self):
        self.edge_glow.hide()

    def found(self, key, pet):
        if key not in self.secrets:
            self.secrets.append(key)
            pet.say(f"비밀 발견! {SECRETS[key][0]}", 3)
            self.save()

    def feed(self, pet=None):
        pet = pet or self.pets[0]
        if self.sat >= 100:
            pet.say("배불러요~!", 2)
            return
        self.sat = min(100, self.sat + self.s["snack"])
        pet.say("냠냠! 간식 최고예요", 2.5)
        pet.start("eat")
        self.save()

    def add_pet(self):
        if len(self.pets) >= MAX_PETS:
            self.pets[0].say(f"최대 {MAX_PETS}마리예요", 2)
            return
        p = Pet(self, len(self.pets))
        self.pets.append(p)
        self.apply_opacity()
        p.say("안녕! 놀자~", 2)
        p.start("hop", n=2)
        self.save()

    def remove_pet(self, pet):
        if len(self.pets) <= 1:
            pet.say("마지막 친구는 못 보내요", 2)
            return
        self.pets.remove(pet)
        pet.win.destroy()
        for i, p in enumerate(self.pets):
            p.idx = i
        self.save()

    def gather(self):
        for i, p in enumerate(self.pets):
            p.x = (self.L + self.R - self.W) / 2 + (i - len(self.pets) / 2) * 60
            p.y = p.ground()
            p.start("idle")
            p.say("여기 왔어요!", 1.5)

    def hide_all(self):
        for p in self.pets:
            p.win.withdraw()
        w = self.restore_win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.geometry(f"140x36+{int(self.R - 150)}+{int(self.B - 46)}")
        tk.Button(w, text="친구 다시 부르기", font=(FONT, 9, "bold"),
                  command=self.show_all).pack(fill="both", expand=True)

    def show_all(self):
        if self.restore_win:
            self.restore_win.destroy()
            self.restore_win = None
        for p in self.pets:
            p.win.deiconify()
            p.win.attributes("-topmost", True)

    def quit(self):
        self.save()
        self.root.destroy()

    def loop(self):
        now = time.time()
        dt = min(1.0, now - self.last)
        self.last = now
        self.tm += dt
        s = self.s

        # 전체화면 실행 감지 시 자동 숨기기 (사진 2)
        if s["auto_hide_fullscreen"]:
            if is_fullscreen_app_active():
                for p in self.pets:
                    if p.win.winfo_viewable(): p.win.withdraw()
            else:
                for p in self.pets:
                    if not p.win.winfo_viewable() and self.restore_win is None:
                        p.win.deiconify()

        if s["hunger_min"] > 0:
            self.sat = max(0.0, self.sat - dt * 100 / (s["hunger_min"] * 60))
        self.acc += dt
        if self.acc >= 60:
            self.acc -= 60
            self.inti += 1
            self.mins += 1
            if self.inti in MILESTONES:
                self.bouquet_until = now + 8
                self.pets[0].say(f"꽃다발 선물! 친밀도 {self.inti}", 4)
                self.pets[0].start("hop", n=3)
            self.save()

        lt = time.localtime()
        cur_hm = f"{lt.tm_hour:02d}:{lt.tm_min:02d}"

        # 1분 단위 스케줄 체크 (정각, 점심, 퇴근)
        if lt.tm_min != self.last_min_check:
            self.last_min_check = lt.tm_min
            
            # 1) 정각 알림
            if lt.tm_min == 0 and lt.tm_hour != self.last_hour:
                self.last_hour = lt.tm_hour
                is_weekday = lt.tm_wday < 5
                mute = s["work_hour_mute"] and is_weekday and (s["work_mute_start"] <= lt.tm_hour <= s["work_mute_end"])
                
                if not mute:
                    ampm = "오전" if lt.tm_hour < 12 else "오후"
                    disp_h = lt.tm_hour if lt.tm_hour <= 12 else lt.tm_hour - 12
                    sub_text = f"{ampm} {disp_h}시야!"
                    if s.get("notify_hour_popup", True):
                        self.trigger_custom_alert("정각 알림", f"{lt.tm_hour:02d}:00", sub_text)
                    elif s.get("notify_hour", True):
                        self.pets[0].say(f"{lt.tm_hour}시 정각이에요!", 4)

            # 2) 점심 알림
            if s.get("notify_lunch", True) and cur_hm == s.get("lunch_time", "12:00"):
                self.trigger_custom_alert("점심 알림", cur_hm, s.get("lunch_msg", "점심 먹으러 가자!"))

            # 3) 퇴근 알림
            if s.get("notify_leave", True) and cur_hm == s.get("leave_time", "18:00"):
                self.trigger_custom_alert("퇴근 알림", cur_hm, s.get("leave_msg", "퇴근이다! 오늘도 수고했어"))

        if self.hungry() and s["notify_hungry"] and now - self.last_hungry_note > 300 and s["hunger_min"] > 0:
            self.last_hungry_note = now
            self.pets[0].say("배고파요… 간식 주세요", 4)
            
        if self.timer_end and now >= self.timer_end:
            self.timer_end = 0
            self.pets[0].say("⏰ 타이머 끝났어요!", 5)
            for p in self.pets:
                p.start("hop", n=3)
            if WIN and s["sound"]:
                try:
                    import winsound
                    winsound.Beep(880, 300)
                    winsound.Beep(1175, 400)
                except Exception:
                    pass

        self.mouse_reactions(now, dt)
        for p in list(self.pets):
            p.update()
        self.root.after(33, self.loop)

    def mouse_reactions(self, now, dt):
        s = self.s
        if not s["hidden_reactions"]:
            return
        px, py = self.root.winfo_pointerxy()
        moved = abs(px - self.lastp[0]) + abs(py - self.lastp[1])
        self.lastp = (px, py)
        if moved < 3:
            self.still += dt
        else:
            self.still = 0
            if self.dancing and moved > 20:
                self.dancing = False
                for p in self.pets:
                    if p.act == "dance":
                        p.start("idle")
                        
        # 4초 가만히 있으면 군무
        if len(self.pets) >= 2 and self.still >= 4 and not self.dancing and now > self.dance_cool:
            self.dancing = True
            self.dance_cool = now + 30
            for p in self.pets:
                if p.act in ("walk", "idle", "sit", "hop"):
                    p.start("dance")
            self.found("dance", self.pets[0])

        if self.dancing and not any(p.act == "dance" for p in self.pets):
            self.dancing = False

        # 마우스 뺑뺑이(spin) 감지
        for p in self.pets:
            hx = p.x + self.W / 2
            hy = p.y + self.H - self.ih * 0.64
            d = math.hypot(px - hx, py - hy)
            c = self.circ.setdefault(id(p), {"a": None, "tot": 0.0, "t": now})
            if d < 110 and d > 8 and p.act in ("walk", "idle", "sit"):
                a = math.atan2(py - hy, px - hx)
                if c["a"] is not None and now - c["t"] < 0.6:
                    da = (a - c["a"] + math.pi) % (2 * math.pi) - math.pi
                    c["tot"] += da
                else:
                    c["tot"] = 0.0
                c["a"], c["t"] = a, now
                if abs(c["tot"]) > 2 * math.pi:
                    c["tot"] = 0.0
                    self.found("spin", p)
                    p.start("dizzy")
            elif d >= 110:
                c["a"], c["tot"] = None, 0.0

    def dialog(self, key, title, width=420, height=None):
        w = self.wins.get(key)
        if w is not None and w.winfo_exists():
            w.lift()
            return None
        w = tk.Toplevel(self.root)
        w.title(title)
        w.attributes("-topmost", True)
        w.geometry(f"{width}x{height}" if height else f"{width}x500")
        w.config(bg="#fffaf7")
        self.wins[key] = w
        return w

    # ------------------------------------------------ 설정 UI 1: 자동 시작 / 알림 설정 (사진 1)
    def open_notify(self):
        w = self.dialog("notify", "전주치이카와 · 자동 시작 / 알림 설정", 460, 680)
        if w is None: return
        f = (FONT, 9)
        s = self.s

        v_hour = tk.BooleanVar(value=s["notify_hour"])
        v_auto = tk.BooleanVar(value=s["autostart"])
        v_hour_pop = tk.BooleanVar(value=s["notify_hour_popup"])
        v_work_mute = tk.BooleanVar(value=s["work_hour_mute"])
        v_m_start = tk.IntVar(value=s["work_mute_start"])
        v_m_end = tk.IntVar(value=s["work_mute_end"])
        
        v_glow = tk.BooleanVar(value=s["glow_edge"])
        v_glow_col = tk.StringVar(value=s["glow_color"])
        v_glow_w = tk.StringVar(value=s["glow_width"])
        v_glow_i = tk.StringVar(value=s["glow_intensity"])
        
        v_lunch = tk.BooleanVar(value=s["notify_lunch"])
        v_lunch_t = tk.StringVar(value=s["lunch_time"])
        v_lunch_m = tk.StringVar(value=s["lunch_msg"])
        
        v_leave = tk.BooleanVar(value=s["notify_leave"])
        v_leave_t = tk.StringVar(value=s["leave_time"])
        v_leave_m = tk.StringVar(value=s["leave_msg"])
        
        v_nap = tk.BooleanVar(value=True)
        v_nap_m = tk.IntVar(value=s.get("idle_nap_min", 10))

        # 메인 컨테이너
        top_f = tk.Frame(w, bg="#fffaf7")
        top_f.pack(fill="both", expand=True, padx=16, pady=12)

        # 1. 정각 알림 블록
        tk.Checkbutton(top_f, text="정각 알림 (매시간 현재 시각 알려주기)", variable=v_hour,
                       font=(FONT, 9, "bold"), bg="#fffaf7").pack(anchor="w")
        tk.Label(top_f, text="표시 방식과 평일 제외 시간은 아래에서 선택하세요.", font=(FONT, 8),
                 fg="#777", bg="#fffaf7").pack(anchor="w", padx=20)

        tk.Checkbutton(top_f, text="Windows 로그인 시 자동으로 켜기", variable=v_auto,
                       font=f, bg="#fffaf7").pack(anchor="w", padx=16, pady=(4, 0))
        tk.Checkbutton(top_f, text="별도 정각 알림창 사용 (직접 닫을 때까지 유지)", variable=v_hour_pop,
                       font=f, bg="#fffaf7").pack(anchor="w", padx=16)

        # 평일 제외 시간대
        f_mute = tk.Frame(top_f, bg="#fffaf7")
        f_mute.pack(anchor="w", padx=16, pady=2)
        tk.Checkbutton(f_mute, text="평일(월~금) 아래 시간에는 정각 알림 끄기", variable=v_work_mute,
                       font=f, bg="#fffaf7").pack(anchor="w")
        
        f_span = tk.Frame(top_f, bg="#fffaf7")
        f_span.pack(anchor="w", padx=36, pady=2)
        ttk.Spinbox(f_span, from_=0, to=23, width=4, textvariable=v_m_start).pack(side="left")
        tk.Label(f_span, text="시 ~ ", font=f, bg="#fffaf7").pack(side="left")
        ttk.Spinbox(f_span, from_=0, to=23, width=4, textvariable=v_m_end).pack(side="left")
        tk.Label(f_span, text="시 (양 끝 정각 포함)", font=f, bg="#fffaf7").pack(side="left", padx=4)

        # 미리보기 버튼 행
        f_prev = tk.Frame(top_f, bg="#fffaf7")
        f_prev.pack(fill="x", padx=20, pady=4)
        tk.Label(f_prev, text="9~18 설정: 평일 09~18시 제외, 주말은 알림", font=(FONT, 8), fg="#777", bg="#fffaf7").pack(side="left")
        tk.Button(f_prev, text="정각창 미리보기", font=(FONT, 8),
                  command=lambda: self.trigger_custom_alert("정각 알림", "11:00", "오전 11시야!\n(미리보기)")).pack(side="right")

        # 2. 테두리 빛 효과 블록
        tk.Checkbutton(top_f, text="알림창을 닫을 때까지 화면 가장자리 빛 유지", variable=v_glow,
                       font=(FONT, 9, "bold"), bg="#fffaf7").pack(anchor="w", pady=(8, 2))
        
        f_gopt1 = tk.Frame(top_f, bg="#fffaf7")
        f_gopt1.pack(anchor="w", padx=24, pady=2)
        tk.Label(f_gopt1, text="빛 색상", font=f, bg="#fffaf7").pack(side="left")
        ttk.Combobox(f_gopt1, textvariable=v_glow_col, values=["피치·핑크·보라·하늘", "단색 네온", "골드 웜"],
                     state="readonly", width=18).pack(side="left", padx=8)

        f_gopt2 = tk.Frame(top_f, bg="#fffaf7")
        f_gopt2.pack(anchor="w", padx=24, pady=2)
        tk.Label(f_gopt2, text="퍼지는 폭", font=f, bg="#fffaf7").pack(side="left")
        ttk.Combobox(f_gopt2, textvariable=v_glow_w, values=["보통", "넓게"], state="readonly", width=8).pack(side="left", padx=6)
        tk.Label(f_gopt2, text="진하기", font=f, bg="#fffaf7").pack(side="left", padx=(10, 0))
        ttk.Combobox(f_gopt2, textvariable=v_glow_i, values=["은은하게", "선명하게"], state="readonly", width=8).pack(side="left", padx=6)

        # 3. 점심 알림
        f_l = tk.Frame(top_f, bg="#fffaf7")
        f_l.pack(fill="x", pady=(10, 2))
        tk.Checkbutton(f_l, text="점심 알림", variable=v_lunch, font=(FONT, 9, "bold"), bg="#fffaf7").pack(side="left")
        tk.Label(f_l, text="시간", font=f, bg="#fffaf7").pack(side="left", padx=(10, 2))
        tk.Entry(f_l, textvariable=v_lunch_t, width=8, font=f).pack(side="left")
        
        f_lm = tk.Frame(top_f, bg="#fffaf7")
        f_lm.pack(fill="x", padx=24, pady=2)
        tk.Label(f_lm, text="문구", font=f, bg="#fffaf7").pack(side="left")
        tk.Entry(f_lm, textvariable=v_lunch_m, font=f).pack(side="left", fill="x", expand=True, padx=6)

        # 4. 퇴근 알림
        f_lv = tk.Frame(top_f, bg="#fffaf7")
        f_lv.pack(fill="x", pady=(10, 2))
        tk.Checkbutton(f_lv, text="퇴근 알림", variable=v_leave, font=(FONT, 9, "bold"), bg="#fffaf7").pack(side="left")
        tk.Label(f_lv, text="시간", font=f, bg="#fffaf7").pack(side="left", padx=(10, 2))
        tk.Entry(f_lv, textvariable=v_leave_t, width=8, font=f).pack(side="left")

        f_lvm = tk.Frame(top_f, bg="#fffaf7")
        f_lvm.pack(fill="x", padx=24, pady=2)
        tk.Label(f_lvm, text="문구", font=f, bg="#fffaf7").pack(side="left")
        tk.Entry(f_lvm, textvariable=v_leave_m, font=f).pack(side="left", fill="x", expand=True, padx=6)

        # 5. 낮잠 알림
        f_nap = tk.Frame(top_f, bg="#fffaf7")
        f_nap.pack(anchor="w", pady=(8, 2))
        tk.Checkbutton(f_nap, text="낮잠", variable=v_nap, font=(FONT, 9, "bold"), bg="#fffaf7").pack(side="left")
        ttk.Spinbox(f_nap, from_=1, to=120, width=5, textvariable=v_nap_m).pack(side="left", padx=6)
        tk.Label(f_nap, text="분 동안 입력이 없으면 잠들어요", font=f, bg="#fffaf7").pack(side="left")
        
        tk.Label(top_f, text="시간은 12:00처럼 시:분으로 적어 주세요.", font=(FONT, 8), fg="#888", bg="#fffaf7").pack(anchor="w", pady=(4, 8))

        # 하단 버튼 바
        btn_bar = tk.Frame(w, bg="#fffaf7")
        btn_bar.pack(fill="x", padx=16, pady=(0, 16))
        
        tk.Button(btn_bar, text="점심 미리보기", font=f,
                  command=lambda: self.trigger_custom_alert("점심 알림", v_lunch_t.get(), v_lunch_m.get())).pack(side="left", padx=2)
        tk.Button(btn_bar, text="퇴근 미리보기", font=f,
                  command=lambda: self.trigger_custom_alert("퇴근 알림", v_leave_t.get(), v_leave_m.get())).pack(side="left", padx=2)

        def save_alert_settings():
            s["notify_hour"] = v_hour.get()
            s["autostart"] = v_auto.get()
            set_autostart(v_auto.get())
            s["notify_hour_popup"] = v_hour_pop.get()
            s["work_hour_mute"] = v_work_mute.get()
            try:
                s["work_mute_start"] = int(v_m_start.get())
                s["work_mute_end"] = int(v_m_end.get())
            except Exception: pass
            s["glow_edge"] = v_glow.get()
            s["glow_color"] = v_glow_col.get()
            s["glow_width"] = v_glow_w.get()
            s["glow_intensity"] = v_glow_i.get()
            s["notify_lunch"] = v_lunch.get()
            s["lunch_time"] = v_lunch_t.get().strip()
            s["lunch_msg"] = v_lunch_m.get().strip()
            s["notify_leave"] = v_leave.get()
            s["leave_time"] = v_leave_t.get().strip()
            s["leave_msg"] = v_leave_m.get().strip()
            s["idle_nap_min"] = int(v_nap_m.get())
            self.save()
            w.destroy()

        tk.Button(btn_bar, text="취소", font=f, width=6, command=w.destroy).pack(side="right", padx=3)
        tk.Button(btn_bar, text="저장", font=f, width=6, bg="#e9ecef", command=save_alert_settings).pack(side="right", padx=3)

    # ------------------------------------------------ 설정 UI 2: 움직임과 반응 (사진 2)
    def open_motion(self):
        w = self.dialog("motion", "전주치이카와 · 움직임과 반응", 420, 680)
        if w is None: return
        f = (FONT, 9)
        s = self.s

        v_wall = tk.BooleanVar(value=s["allow_wall"])
        v_ceil = tk.BooleanVar(value=s["allow_ceil"])
        v_win = tk.BooleanVar(value=s["allow_window"])
        v_sit = tk.BooleanVar(value=s["allow_sit"])
        v_short_sit = tk.BooleanVar(value=s["short_sit"])
        v_flee = tk.BooleanVar(value=s["flee_mouse"])
        v_follow = tk.BooleanVar(value=s["follow_mouse"])
        v_safe = tk.BooleanVar(value=s["safe_mode"])
        v_work_safe = tk.BooleanVar(value=s["work_safe_mode"])
        v_fullscreen = tk.BooleanVar(value=s["auto_hide_fullscreen"])
        v_show_inti = tk.BooleanVar(value=s["show_inti"])
        v_lock = tk.BooleanVar(value=s["locked"])
        
        v_op = tk.IntVar(value=s.get("opacity", 100))
        v_spd_walk = tk.DoubleVar(value=s.get("spd_walk", 2.0))
        v_spd_spin = tk.DoubleVar(value=s.get("spd_spin", 3.0))
        v_spd_slide = tk.DoubleVar(value=s.get("spd_slide", 3.0))
        v_slide_d = tk.DoubleVar(value=s.get("slide_delay", 0.12))
        v_cr = tk.StringVar(value=s["click_reaction"])

        # 스크롤 가능한 컨테이너
        top_f = tk.Frame(w, bg="#fffaf7")
        top_f.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Label(top_f, text="친구가 어떻게 놀지 골라줘", font=(FONT, 9, "bold"), bg="#fffaf7").pack(anchor="w", pady=(0, 4))
        
        checks = [
            ("화면 양옆 벽 타기", v_wall),
            ("화면 천장 타기", v_ceil),
            ("열린 창 옆을 올라가고 창 위에서 걷기 · 쉬기", v_win),
            ("혼자 앉아서 쉬기", v_sit),
            ("앉아있는 시간 줄이기 (기존 6~11초)", v_short_sit),
            ("커서가 가까이 오면 슬라이딩으로 도망가기", v_flee),
            ("커서를 따라오기", v_follow),
            ("얌전 모드: 바닥에만 머물고 도망가지 않기", v_safe),
            ("평일 09:00~18:00에는 자동으로 얌전 모드", v_work_safe),
            ("전체화면 영상 · 게임을 볼 때 자동으로 숨기기", v_fullscreen),
            ("친구 옆에 친밀도 숫자 표시", v_show_inti),
            ("친구 위치 고정 (마우스로 옮길 수 있어요)", v_lock),
        ]
        for txt, var in checks:
            tk.Checkbutton(top_f, text=txt, variable=var, font=f, bg="#fffaf7").pack(anchor="w", pady=1)

        # 캐릭터 진하기 (투명도)
        f_op = tk.Frame(top_f, bg="#fffaf7")
        f_op.pack(anchor="w", pady=(8, 2))
        tk.Label(f_op, text="캐릭터 진하기", font=f, bg="#fffaf7").pack(side="left")
        ttk.Spinbox(f_op, from_=10, to=100, width=5, textvariable=v_op).pack(side="left", padx=6)
        tk.Label(f_op, text="% · 낮을수록 투명해요", font=(FONT, 8), fg="#777", bg="#fffaf7").pack(side="left")

        # 속도 조절 라벨
        tk.Label(top_f, text="속도 조절 · 숫자가 클수록 빨라져요", font=(FONT, 9, "bold"), bg="#fffaf7").pack(anchor="w", pady=(10, 2))

        speeds = [
            ("걷기 · 기어오르기", v_spd_walk),
            ("헬리콥터 낙하", v_spd_spin),
            ("슬라이딩", v_spd_slide),
        ]
        for txt, var in speeds:
            fr_sp = tk.Frame(top_f, bg="#fffaf7")
            fr_sp.pack(fill="x", pady=2)
            tk.Label(fr_sp, text=txt, font=f, width=16, anchor="w", bg="#fffaf7").pack(side="left")
            ttk.Spinbox(fr_sp, from_=0.5, to=10.0, increment=0.5, width=6, textvariable=var).pack(side="left", padx=6)
            tk.Label(fr_sp, text="배", font=f, bg="#fffaf7").pack(side="left")

        f_sd = tk.Frame(top_f, bg="#fffaf7")
        f_sd.pack(fill="x", pady=(6, 2))
        tk.Label(f_sd, text="슬라이딩 반응 대기", font=f, width=16, anchor="w", bg="#fffaf7").pack(side="left")
        ttk.Spinbox(f_sd, from_=0.01, to=1.0, increment=0.01, width=6, textvariable=v_slide_d).pack(side="left", padx=6)
        tk.Label(f_sd, text="초", font=f, bg="#fffaf7").pack(side="left")

        # 클릭했을 때 반응
        f_cr = tk.Frame(top_f, bg="#fffaf7")
        f_cr.pack(anchor="w", pady=(8, 12))
        tk.Label(f_cr, text="클릭했을 때 반응", font=f, bg="#fffaf7").pack(side="left", padx=(0, 6))
        ttk.Combobox(f_cr, textvariable=v_cr, values=["폴짝", "울기", "어질어질", "랜덤"], state="readonly", width=10).pack(side="left")

        # 하단 저장 / 취소 버튼 바
        btn_bar = tk.Frame(w, bg="#fffaf7")
        btn_bar.pack(fill="x", padx=16, pady=(0, 14))

        def save_motion_settings():
            s["allow_wall"] = v_wall.get()
            s["allow_ceil"] = v_ceil.get()
            s["allow_window"] = v_win.get()
            s["allow_sit"] = v_sit.get()
            s["short_sit"] = v_short_sit.get()
            s["flee_mouse"] = v_flee.get()
            s["follow_mouse"] = v_follow.get()
            s["safe_mode"] = v_safe.get()
            s["work_safe_mode"] = v_work_safe.get()
            s["auto_hide_fullscreen"] = v_fullscreen.get()
            s["show_inti"] = v_show_inti.get()
            s["locked"] = v_lock.get()
            self.lock_var.set(v_lock.get())
            self.safe_var.set(v_safe.get())
            
            try:
                s["opacity"] = int(v_op.get())
                s["spd_walk"] = float(v_spd_walk.get())
                s["spd_spin"] = float(v_spd_spin.get())
                s["spd_slide"] = float(v_spd_slide.get())
                s["slide_delay"] = float(v_slide_d.get())
            except Exception: pass
            
            s["click_reaction"] = v_cr.get()
            self.apply_opacity()
            self.sync_flags()
            w.destroy()

        tk.Button(btn_bar, text="취소", font=f, width=7, command=w.destroy).pack(side="right", padx=4)
        tk.Button(btn_bar, text="저장", font=f, width=7, bg="#e9ecef", command=save_motion_settings).pack(side="right", padx=4)

    # ------------------------------------------------ 설정 UI 3: 친구 기록 / 도우미
    def open_record(self):
        w = self.dialog("record", "친구 기록 · 생활 설정", 440, 600)
        if w is None: return
        f = (FONT, 10)
        big = tk.Label(w, font=(FONT, 16, "bold"), bg="#fffaf7")
        big.pack(anchor="w", padx=20, pady=(18, 4))
        info = tk.Label(w, font=f, bg="#fffaf7", justify="left")
        info.pack(anchor="w", padx=20)
        tk.Button(w, text="간식 주기", font=f, command=lambda: self.feed()).pack(anchor="w", padx=20, pady=8)
        tk.Label(w, text="생활 설정", font=(FONT, 10, "bold"), bg="#fffaf7").pack(anchor="w", padx=20, pady=(6, 0))
        tk.Label(w, text=f"간식은 포만감 +{self.s['snack']}씩, 최대 100까지 채워줘요.\n"
                         "함께한 시간 1분마다 친밀도도 1씩 쌓여요.", font=f, bg="#fffaf7", justify="left").pack(anchor="w", padx=20)
        row = tk.Frame(w, bg="#fffaf7")
        row.pack(anchor="w", padx=20, pady=8)
        tk.Label(row, text="간식 없이 배고파지기까지", font=f, bg="#fffaf7").pack(side="left")
        hv = tk.IntVar(value=self.s["hunger_min"])
        ttk.Spinbox(row, from_=0, to=600, width=5, textvariable=hv).pack(side="left", padx=8)
        tk.Label(row, text="분", font=f, bg="#fffaf7").pack(side="left")
        cv_ = tk.BooleanVar(value=self.s["cry_always"])
        hr_ = tk.BooleanVar(value=self.s["hidden_reactions"])
        tk.Checkbutton(w, text="배고프면 계속 우는 모습", variable=cv_, font=f, bg="#fffaf7").pack(anchor="w", padx=16)
        tk.Checkbutton(w, text="숨겨진 반응 사용", variable=hr_, font=f, bg="#fffaf7").pack(anchor="w", padx=16)

        def apply():
            try:
                self.s["hunger_min"] = max(0, int(hv.get()))
            except Exception: pass
            self.s["cry_always"] = cv_.get()
            self.s["hidden_reactions"] = hr_.get()
            self.save()
            msg.config(text="저장했어요!")

        tk.Button(w, text="생활 설정 저장", font=f, command=apply).pack(anchor="w", padx=20, pady=8)
        msg = tk.Label(w, text="", font=(FONT, 9), bg="#fffaf7", fg="#2a7")
        msg.pack(anchor="w", padx=20)
        sec = tk.Label(w, font=f, bg="#fffaf7", justify="left", wraplength=390)
        sec.pack(anchor="w", padx=20, pady=(10, 0))

        def refresh():
            if not w.winfo_exists(): return
            big.config(text=f"♥ 친밀도 {self.inti}   ·   함께 {self.mins}분")
            nm = self.next_milestone()
            info.config(text=f"포만감 {int(self.sat)} / 100\n"
                             f"다음 꽃다발: {'친밀도 %d' % nm if nm else '모두 받았어요!'}\n"
                             + ("지금 간식을 줄 수 있어요." if self.sat < 100 else "배가 불러요."))
            lines = [f"발견한 비밀 {len(self.secrets)} / {len(SECRETS)}"]
            for k, (nme, hint) in SECRETS.items():
                lines.append(f"  · {nme}: {hint}" if k in self.secrets else "  · ???")
            sec.config(text="\n".join(lines))
            w.after(1000, refresh)

        refresh()

    def open_helper(self):
        w = self.dialog("helper", "도우미 · 할 일 · 메모 · 타이머", 440, 520)
        if w is None: return
        f = (FONT, 10)
        nb = ttk.Notebook(w)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        t1 = tk.Frame(nb, bg="#fffaf7")
        nb.add(t1, text="할 일")
        row = tk.Frame(t1, bg="#fffaf7")
        row.pack(fill="x", padx=10, pady=10)
        ent = tk.Entry(row, font=f)
        ent.pack(side="left", fill="x", expand=True)
        lb = tk.Listbox(t1, font=f, height=14, activestyle="none")
        lb.pack(fill="both", expand=True, padx=10)

        def draw():
            lb.delete(0, "end")
            for it in self.todos:
                lb.insert("end", ("✔ " if it["done"] else "☐ ") + it["t"])

        def add(*_):
            t = ent.get().strip()
            if t:
                self.todos.append({"t": t, "done": False})
                ent.delete(0, "end")
                draw()
                self.save()

        def toggle():
            for i in lb.curselection():
                self.todos[i]["done"] = not self.todos[i]["done"]
            draw()
            self.save()

        def delete():
            for i in reversed(lb.curselection()):
                del self.todos[i]
            draw()
            self.save()

        ent.bind("<Return>", add)
        tk.Button(row, text="추가", font=f, command=add).pack(side="left", padx=6)
        bt = tk.Frame(t1, bg="#fffaf7")
        bt.pack(pady=8)
        tk.Button(bt, text="완료 표시", font=f, command=toggle).pack(side="left", padx=4)
        tk.Button(bt, text="삭제", font=f, command=delete).pack(side="left", padx=4)
        draw()

        t2 = tk.Frame(nb, bg="#fffaf7")
        nb.add(t2, text="메모")
        txt = tk.Text(t2, font=f, wrap="word", height=18)
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("1.0", self.memo)

        def save_memo(*_):
            self.memo = txt.get("1.0", "end-1c")
            self.save()

        txt.bind("<FocusOut>", save_memo)
        tk.Button(t2, text="저장", font=f, command=save_memo).pack(pady=(0, 8))
        w.protocol("WM_DELETE_WINDOW", lambda: (save_memo(), w.destroy()))

        t3 = tk.Frame(nb, bg="#fffaf7")
        nb.add(t3, text="타이머")
        r3 = tk.Frame(t3, bg="#fffaf7")
        r3.pack(pady=24)
        mv = tk.IntVar(value=5)
        ttk.Spinbox(r3, from_=1, to=600, width=6, textvariable=mv).pack(side="left")
        tk.Label(r3, text="분", font=f, bg="#fffaf7").pack(side="left", padx=6)
        remain = tk.Label(t3, text="", font=(FONT, 22, "bold"), bg="#fffaf7")
        remain.pack(pady=10)

        def start_t():
            try:
                self.timer_end = time.time() + max(1, int(mv.get())) * 60
            except Exception: pass

        def cancel_t():
            self.timer_end = 0

        b3 = tk.Frame(t3, bg="#fffaf7")
        b3.pack()
        tk.Button(b3, text="시작", font=f, command=start_t).pack(side="left", padx=4)
        tk.Button(b3, text="취소", font=f, command=cancel_t).pack(side="left", padx=4)
        tk.Label(t3, text="끝나면 친구가 폴짝 뛰면서 알려줘요.", font=(FONT, 9), bg="#fffaf7", fg="#666").pack(pady=14)

        def tick_t():
            if not w.winfo_exists(): return
            if self.timer_end:
                left = max(0, int(self.timer_end - time.time()))
                remain.config(text=f"{left // 60:02d}:{left % 60:02d}")
            else:
                remain.config(text="--:--")
            w.after(500, tick_t)

        tick_t()


if __name__ == "__main__":
    Game().root.mainloop()
