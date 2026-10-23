"""
바탕화면 고양이 펫 (실제 사진 전신 버전)
- 장난감 문 고양이 실제 사진 기반 자연스러운 물리 동작
- 걷기 / 앉아서 쉬기 / 폴짝 / 슬라이딩 / 어질어질 / 헬리콥터 돌기
- 벽 타기 / 천장 타기 / 창 타기 (다른 프로그램 창 위에 올라가기)
- 간식 주기, 포만감, 친밀도, 꽃다발, 배고프면 우는 모습
- 숨겨진 반응 3가지, 한 마리 더 부르기 (최대 5마리), 몰래 하는 군무
- 도우미: 할 일 / 메모 / 타이머, 알림 설정, 움직임·반응 설정
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


SAVE = os.path.join(base_dir(), "cat_save.json")

DEFAULTS = {
    "speed": 3, "activity": 5, "size": 140,
    "click_reaction": "폴짝", "hunger_min": 60, "snack": 25,
    "cry_always": False, "hidden_reactions": True,
    "allow_wall": True, "allow_window": True,
    "notify_hungry": True, "notify_hour": False, "sound": True,
    "locked": False, "safe_mode": False,
}

SECRETS = {
    "spin": ("빙글빙글", "고양이 머리 위에서 마우스를 한 바퀴 돌려보기"),
    "dance": ("몰래 하는 군무", "친구가 둘 이상일 때 마우스를 4초 동안 가만히 두기"),
    "tickle": ("간지럼", "고양이를 빠르게 5번 클릭하기"),
}

# ---------------------------------------------------------------- Windows 창 감지 API
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
    if not WIN:
        return out
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
    if not WIN:
        return None
    try:
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return None
        r = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        return (r.l, r.t, r.r, r.b)
    except Exception:
        return None


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
            self.dur = int(random.randint(110, 240) * sc)
        elif act == "hop":
            self.dur = 22 * kw.get("n", random.randint(1, 3))
        elif act == "cry":
            if kw.get("kind") == "hungry":
                self.dur = 140
                self.say("배고파요 ㅠㅠ 츄르 줘냥", 3)
            else:
                self.dur = 100
                self.say("으앙… 놀랐다냥", 2)
        elif act == "laugh":
            self.dur = 70
            self.say("골골골~ 최고다냥!", 2)
        elif act == "eat":
            self.dur = 55
        elif act == "slide":
            self.dir = random.choice([-1, 1])
            self.dur = 34
            self.say("슝~ 달린다냥!", 1.5)
        elif act == "dizzy":
            self.dur = 100
            self.say("어질어질하다냥…", 2.5)
        elif act == "spin":
            self.dur = 75
            self.say("위이이잉! 날아간다냥", 2)
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
            self.say("천장으로 간다냥!", 1.5)
        elif act == "perch":
            wins = list_windows(g.T)
            if not wins:
                self.say("올라갈 창이 없다냥", 2)
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
        if s["locked"]:
            ch = [("idle", 50), ("sit", 30), ("hop", 20)]
        else:
            ch = [("walk", 40), ("idle", 14), ("sit", 12), ("hop", 8),
                  ("slide", 6), ("dizzy", 3), ("spin", 3)]
            if not s["safe_mode"]:
                if s["allow_wall"]:
                    ch += [("wall", 5), ("ceil", 4)]
                if s["allow_window"] and WIN:
                    ch += [("perch", 7)]
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
            self.say(random.choice(["장난감 물었다냥!", "야옹~", "골골골~♥"]), 1.5)
            self.start("hop", n=1)

    def menu(self, e):
        g = self.g
        m = tk.Menu(self.win, tearoff=0, font=(FONT, 10))
        m.add_command(label=f"♥ 친밀도 {g.inti}  ·  함께 {g.mins}분", state="disabled")
        m.add_command(label="고양이 한 마리 더 부르기", command=g.add_pet)
        m.add_command(label="이 친구 보내기", command=lambda: g.remove_pet(self))
        m.add_command(label="모두 숨기기", command=g.hide_all)
        m.add_separator()
        m.add_command(label="알림 설정...", command=g.open_notify)
        m.add_command(label="화면 가운데로 모으기", command=g.gather)
        m.add_command(label="움직임 · 반응 설정...", command=g.open_motion)
        m.add_checkbutton(label="위치 고정 (자동 이동 멈추기)",
                          variable=g.lock_var, command=g.sync_flags)
        m.add_command(label="고양이 기록 · 생활 설정...", command=g.open_record)
        m.add_command(label="도우미 · 할 일 · 메모 · 타이머...", command=g.open_helper)
        m.add_command(label=f"츄르 주기  ·  포만감 {int(g.sat)}/100",
                      command=lambda: g.feed(self))
        sub = tk.Menu(m, tearoff=0, font=(FONT, 10))
        for label, act, kw in ACT_MENU:
            sub.add_command(label=label,
                            command=lambda a=act, k=kw: self.start(a, **k))
        m.add_cascade(label="동작 바로 보기", menu=sub)
        m.add_checkbutton(label="안전 모드 (바닥에서만 놀기)", variable=g.safe_var,
                          command=g.sync_flags)
        m.add_separator()
        m.add_command(label="종료", command=g.quit)
        self.win.focus_force()
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    # ----- 고양이 사진 기반 모션 연출
    def a_idle(self):
        self.y = self.ground()
        k = math.sin(self.t * 0.12)
        if self.t >= self.dur:
            self.next()
        return 0, 0, 0, 1 - 0.015 * k, 1 + 0.02 * k

    def a_walk(self):
        g = self.g
        self.y = self.ground()
        sp = g.s["speed"] * (0.6 if g.hungry() else 1.0)
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
            self.say("맛있다냥 ♥", 2)
            self.start("idle")
        return 0, -abs(math.sin(self.t * 0.5)) * 4, 0, 1, 1

    def a_slide(self):
        g = self.g
        self.y = self.ground()
        sp = 16 * (1 - self.t / self.dur)
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
        return math.sin(t * 0.2) * 8, -lift, (t * 40) % 360, 1, 1

    def a_dance(self):
        self.y = self.ground()
        self.fxk.add("notes")
        u = self.g.tm * 7 + self.idx * math.pi
        if self.t >= self.dur:
            self.start("idle")
        f = math.sin(u)
        return 0, -abs(f) * 12, 10 * f, 1, 1

    def a_drag(self):
        f = math.sin(self.t * 0.5)
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
            self.y -= 2.5
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
        self.x += self.dir * 2
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
        self.rel += self.dir * 1.6
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
        if "tears" in self.fxk and abs(ang) < 1:
            for i, s in enumerate((-1, 1)):
                ex = cx + s * g.ih * 0.14
                ey = fy + ((t * 3 + i * 9) % 32)
                cv.create_oval(ex - 3, ey - 4, ex + 3, ey + 4, fill="#6cc5ff",
                               outline="#3b9be0", tags="fx")
        if "hearts" in self.fxk:
            for i in range(3):
                hx = cx + (i - 1) * 26
                hy = fy - 20 - ((t * 1.5 + i * 12) % 40)
                cv.create_text(hx, hy, text="♥", fill="#ff5c8a",
                               font=(FONT, 14, "bold"), tags="fx")
        if "stars" in self.fxk:
            for i in range(3):
                a = t * 0.2 + i * 2.1
                cv.create_text(cx + math.cos(a) * 34, fy - g.ih * 0.33 + math.sin(a) * 9,
                               text="★", fill="#ffd23c", font=(FONT, 13), tags="fx")
        if "zzz" in self.fxk:
            for i in range(3):
                zy = fy - 10 - ((t * 0.7 + i * 14) % 42)
                cv.create_text(cx + 26 + i * 7, zy, text="z", fill="#5b6c8f",
                               font=(FONT, 9 + i * 2, "bold"), tags="fx")
        if "cookie" in self.fxk:
            r = max(2, 10 * (1 - self.t / max(1, self.dur)))
            ky = fy + 0.14 * g.ih
            cv.create_oval(cx - r, ky - r, cx + r, ky + r, fill="#d9953f",
                           outline="#a8691c", tags="fx")
        if "notes" in self.fxk:
            for i in range(3):
                nx = cx + (i - 1) * 34
                ny = g.H - g.ih - 8 - ((t * 1.2 + i * 15) % 25)
                cv.create_text(nx, ny, text="♪", fill="#7a5cff",
                               font=(FONT, 15, "bold"), tags="fx")
        if "dust" in self.fxk:
            for i in range(4):
                px = cx - self.dir * (g.iw * 0.4 + i * 12)
                py = g.H - 6 - i * 3
                rr = 6 - i
                cv.create_oval(px - rr, py - rr, px + rr, py + rr, fill="#d8d3c8",
                               outline="", tags="fx")
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
            text = "배고파요 ㅠㅠ 츄르 줘냥"
        if text != self.drawn:
            cv.delete("b")
            if text:
                t = cv.create_text(g.W // 2, 24, text=text, tags="b", width=g.W - 24,
                                   justify="center", font=(FONT, 10, "bold"), fill="#333333")
                x1, y1, x2, y2 = cv.bbox(t)
                rc = cv.create_rectangle(x1 - 8, y1 - 4, x2 + 8, y2 + 4,
                                         fill="white", outline="#ffb300", width=2, tags="b")
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

        # 이미지 파일 로드 (대소문자 자동 호환)
        self.photo_base = None
        target_name = None
        for cand in ["pet.png", "PET.PNG", "pet_2.png", "PET_2.PNG"]:
            if os.path.exists(res(cand)):
                target_name = res(cand)
                break
        if not target_name:
            target_name = res("pet.png")

        try:
            self.photo_base = Image.open(target_name).convert("RGBA")
        except Exception:
            self.photo_base = Image.new("RGBA", (140, 140), (255, 180, 0, 255))

        self.cache = {}
        self.set_size(self.s["size"])
        self.pets = []
        self.wins = {}
        self.acc, self.last, self.tm = 0.0, time.time(), 0.0
        self.bouquet_until = 0
        self.timer_end = 0
        self.last_hour = -1
        self.last_hungry_note = 0
        self.still, self.lastp = 0.0, (0, 0)
        self.dancing, self.dance_cool = False, 0
        self.circ = {}
        self.restore_win = None

        for i in range(max(1, min(MAX_PETS, int(d.get("pets", 1))))):
            self.pets.append(Pet(self, i))

        self.loop()

    def set_size(self, size):
        h = int(size)
        self.ih = h
        w = int(self.photo_base.width * h / max(1, self.photo_base.height))
        self.iw = w
        self.W, self.H = w + 50, h + TOP
        self.cache.clear()

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

    def found(self, key, pet):
        if key not in self.secrets:
            self.secrets.append(key)
            pet.say(f"비밀 발견! {SECRETS[key][0]}", 3)
            self.save()

    def feed(self, pet=None):
        pet = pet or self.pets[0]
        if self.sat >= 100:
            pet.say("배불러요~ 냥!", 2)
            return
        self.sat = min(100, self.sat + self.s["snack"])
        pet.say("냠냠! 츄르 최고다냥", 2.5)
        pet.start("eat")
        self.save()

    def add_pet(self):
        if len(self.pets) >= MAX_PETS:
            self.pets[0].say(f"최대 {MAX_PETS}마리예요", 2)
            return
        p = Pet(self, len(self.pets))
        self.pets.append(p)
        p.say("놀자냥!", 2)
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
            p.say("여기 왔다냥!", 1.5)

    def hide_all(self):
        for p in self.pets:
            p.win.withdraw()
        w = self.restore_win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.geometry(f"140x36+{int(self.R - 150)}+{int(self.B - 46)}")
        tk.Button(w, text="고양이 다시 부르기", font=(FONT, 9, "bold"),
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
        if s["notify_hour"] and lt.tm_min == 0 and lt.tm_hour != self.last_hour:
            self.last_hour = lt.tm_hour
            self.pets[0].say(f"{lt.tm_hour}시 정각이다냥!", 4)
        if self.hungry() and s["notify_hungry"] and now - self.last_hungry_note > 300 and s["hunger_min"] > 0:
            self.last_hungry_note = now
            self.pets[0].say("배고파요… 츄르 주세요", 4)
        if self.timer_end and now >= self.timer_end:
            self.timer_end = 0
            self.pets[0].say("⏰ 타이머 끝났다냥!", 5)
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
        # 몰래 하는 군무
        if moved < 3:
            self.still += dt
        else:
            self.still = 0
            if self.dancing and moved > 20:
                self.dancing = False
                for p in self.pets:
                    if p.act == "dance":
                        p.start("idle")
        if len(self.pets) >= 2 and self.still >=
