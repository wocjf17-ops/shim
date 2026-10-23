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

        # 대문자/소문자 파일 자동 탐색
        target_file = None
        for cand in ["pet.png", "PET.PNG", "pet_2.png", "PET_2.PNG"]:
            if os.path.exists(res(cand)):
                target_file = res(cand)
                break
        if not target_file:
            target_file = res("pet.png")

        img = Image.open(target_file).convert("RGBA")
        h = SIZE
        w = int(img.width * h / img.height)
        img = img.resize((w, h), Image.LANCZOS)
        self.W, self.H = w + 40, h + TOP

        # 애니메이션 프레임 준비
        self.frames = {}
        for flip in (False, True):
            base = img.transpose(Image.FLIP_LEFT_RIGHT) if flip else img
            for name, (sx, sy) in {"n": (1, 1), "tall": (.94, 1.08), "squash": (1.1, .9)}.items():
                self.frames[(name, flip, 0)] = self.make(base, sx, sy, 0)
                self.frames[(name, flip, 90)] = self.make(base, sx, sy, 90)
                self.frames[(name, flip, -90)] = self.make(base, sx, sy, -90)
                self.frames[(name, flip, 180)] = self.make(base, sx, sy, 180)

        self.cv = tk.Canvas(r, width=self.W, height=self.H, bg=KEY, highlightthickness=0)
        self.cv.pack()
        self.item = self.cv.create_image(self.W // 2, self.H, anchor="s", image=self.frames[("n", False, 0)])

        # 저장된 데이터 불러오기
        self.sat, self.inti, self.mins = 100.0, 0, 0
        try:
            with open(SAVE_PATH, encoding="utf-8") as f:
                d = json.load(f)
            self.sat = float(d.get("sat", 100))
            self.inti = int(d.get("inti", 0))
            self.mins = int(d.get("mins", 0))
        except Exception:
            pass

        # 초기 좌표 설정 (y 선언 순서 버그 방지)
        self.x = (self.L + self.R - self.W) // 2
        self.y = self.B - self.H + 10
        self.y = self.ground()

        self.dir = random.choice([-1, 1])
        self.state, self.timer = "idle", 60
        self.rotation = 0
        self.vy = self.jt = self.sq = 0
        self.jlen, self.jcount = 22, 0
        self.locked = tk.BooleanVar(value=False)
        self.acc, self.last = 0.0, time.time()
        self.bubble, self.bubble_until, self.drawn = "", 0, None
        self.moved, self.off = False, (0, 0)

        # 알람 상태
        self.alarm_time = None
        self.alarm_msg = ""

        # 마우스 이벤트
        self.cv.bind("<ButtonPress-1>", self.press)
        self.cv.bind("<B1-Motion>", self.motion)
        self.cv.bind("<ButtonRelease-1>", self.release)
        self.cv.bind("<Button-3>", self.menu)
        r.protocol("WM_DELETE_WINDOW", self.quit)

        self.place()
        self.tick()

    def apply_config(self):
        s = self.cfg["Settings"]
        self.opt_walls = s.getboolean("Walls", fallback=True)
        self.opt_ceiling = s.getboolean("Ceiling", fallback=True)
        self.opt_windows = s.getboolean("Windows", fallback=True)
        self.opt_escape = s.getboolean("Escape", fallback=False)
        self.opt_follow = s.getboolean("Follow", fallback=False)
        self.opt_hungercry = s.getboolean("HungerCry", fallback=True)
        self.opt_speed = s.getfloat("Speed", fallback=2.2)
        self.opt_fallspeed = s.getfloat("FallSpeed", fallback=3.0)
        self.opt_hungermins = s.getfloat("HungerMinutes", fallback=60.0)
        opacity = s.getfloat("PetOpacityPercent", fallback=100.0) / 100.0
        try:
            self.root.attributes("-alpha", max(0.2, min(1.0, opacity)))
        except Exception:
            pass

    def make(self, im, sx, sy, angle=0):
        im_s = im.resize((max(1, int(im.width * sx)), max(1, int(im.height * sy))), Image.LANCZOS)
        if angle != 0:
            im_s = im_s.rotate(angle, expand=True)
        mask = im_s.getchannel("A").point(lambda v: 255 if v > 110 else 0)
        bg = Image.new("RGB", im_s.size, KEY)
        bg.paste(im_s.convert("RGB"), mask=mask)
        return ImageTk.PhotoImage(bg)

    def ground(self):
        cur_y = getattr(self, "y", self.B - self.H + 10)
        if getattr(self, "opt_windows", True):
            wrect = get_foreground_window_rect(self.hwnd)
            if wrect:
                wl, wt, wr, wb = wrect
                if wl - 20 <= self.x <= wr - self.W + 20 and (wt - self.H - 30) <= cur_y <= (wt - self.H + 40):
                    return wt - self.H + 10
        return self.B - self.H + 10

    def place(self):
        self.root.geometry(f"{self.W}x{self.H}+{int(self.x)}+{int(self.y)}")

    def save(self):
        try:
            with open(SAVE_PATH, "w", encoding="utf-8") as f:
                json.dump({"sat": self.sat, "inti": self.inti, "mins": self.mins}, f)
        except Exception:
            pass

    def say(self, text, secs=2.0):
        self.bubble, self.bubble_until = text, time.time() + secs

    def jump(self, count=1):
        self.state, self.jt, self.jcount = "jump", 0, count

    def press(self, e):
        self.off = (e.x_root - self.x, e.y_root - self.y)
        self.start = (e.x_root, e.y_root)
        self.moved = False

    def motion(self, e):
        if not self.moved and abs(e.x_root - self.start[0]) + abs(e.y_root - self.start[1]) > 6:
            self.moved = True
            self.state = "drag"
            self.rotation = 0
        if self.moved:
            self.x = e.x_root - self.off[0]
            self.y = e.y_root - self.off[1]
            self.place()

    def release(self, e):
        if self.moved:
            self.state, self.vy = "fall", 0
        else:
            chats = ["골골골~♥", "장난감 물고 왔다냥!", "야옹~ 놀아달라냥!"]
            self.say(random.choice(chats), 1.5)
            self.jump(1)

    def menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=f"♥ 친밀도 {self.inti}  ·  함께 {self.mins}분", state="disabled")
        m.add_separator()
        m.add_command(label=f"츄르 주기  ·  포만감 {int(self.sat)}/100", command=self.feed)
        
        if self.alarm_time:
            rem_sec = max(0, int(self.alarm_time - time.time()))
            rem_m, rem_s = divmod(rem_sec, 60)
            m.add_command(label=f"⏰ 알람 취소 ({rem_m}분 {rem_s}초 남음)", command=self.cancel_alarm)
        else:
            m.add_command(label="⏰ 알람 맞추기 (타이머)", command=self.set_alarm)

        m.add_command(label="화면 가운데로 부르기", command=self.center)
        m.add_checkbutton(label="위치 고정 (자동 이동 멈추기)", variable=self.locked)
        m.add_separator()
        m.add_command(label="설정 파일(settings.ini) 다시 읽기", command=self.reload_settings)
        m.add_command(label="종료", command=self.quit)
        self.root.focus_force()
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def reload_settings(self):
        self.cfg = load_or_create_config()
        self.apply_config()
        self.say("설정을 새로고침했다냥!", 1.5)

    def set_alarm(self):
        self.root.attributes("-topmost", False)
        minutes = simpledialog.askfloat("알람 맞추기", "몇 분 뒤에 알려줄까요? (예: 5 또는 0.5):", minvalue=0.1, maxvalue=1440.0)
        if minutes is not None:
            msg = simpledialog.askstring("알람 내용", "어떤 내용인가요?:", initialvalue="시간 다 됐다냥! 일어나라냥!")
            if not msg:
                msg = "시간 다 됐다냥!"
            self.alarm_time = time.time() + (minutes * 60)
            self.alarm_msg = msg
            self.say(f"{minutes:g}분 뒤에 알려줄게요!", 2.5)
            self.jump(1)
        self.root.attributes("-topmost", True)

    def cancel_alarm(self):
        self.alarm_time = None
        self.alarm_msg = ""
        self.say("알람을 취소했다냥!", 2.0)

    def trigger_alarm(self):
        msg = self.alarm_msg
        self.alarm_time = None
        self.alarm_msg = ""
        self.rotation = 0
        self.center()
        self.jump(5)
        self.say(f"⏰ {msg}", 8.0)
        try:
            for _ in range(3):
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                time.sleep(0.1)
        except Exception:
            pass

    def feed(self):
        if self.sat >= 100:
            self.say("배불러요 냥~", 2)
            return
        self.sat = min(100, self.sat + 25)
        self.say("냠냠! 츄르 맛있다냥", 2.5)
        self.jump(2)
        self.save()

    def center(self):
        self.x = (self.L + self.R - self.W) // 2
        self.y = self.B - self.H + 10
        self.rotation = 0
        self.state, self.timer = "idle", 60
        self.say("여기 왔다냥!", 1.5)

    def quit(self):
        self.save()
        self.root.destroy()

    def tick(self):
        now = time.time()
        dt = now - self.last
        self.last = now

        if self.alarm_time and now >= self.alarm_time:
            self.trigger_alarm()

        # 포만감 계산
        self.sat = max(0.0, self.sat - dt * 100 / (max(1.0, self.opt_hungermins) * 60))
        self.acc += dt
        if self.acc >= 60:
            self.acc -= 60
            self.inti += 1
            self.mins += 1
            self.save()
        hungry = self.sat < 20

        # 마우스 커서 거리 감지
        cursor_x, cursor_y = self.root.winfo_pointerxy()
        dist_x = cursor_x - (self.x + self.W // 2)
        dist_y = cursor_y - (self.y + self.H // 2)
        dist = math.hypot(dist_x, dist_y)

        if not self.locked.get() and self.state not in ("drag", "fall"):
            if self.opt_escape and dist < 120:
                self.dir = -1 if dist_x > 0 else 1
                self.state = "walk"
                self.x += self.dir * (self.opt_speed * 2.2)
                self.say("도망가자냥!", 0.5)
            elif self.opt_follow and dist > 150:
                self.dir = 1 if dist_x > 0 else -1
                self.state = "walk"
                self.x += self.dir * self.opt_speed

        dy, dx, name = 0, 0, "n"
        st = self.state

        target_ground = self.ground()

        if st == "fall":
            self.vy += self.opt_fallspeed
            self.y += self.vy
            if self.y >= target_ground:
                self.y = target_ground
                self.state, self.timer, self.sq = "idle", 40, 6
                self.rotation = 0
            self.place()

        elif st == "jump":
            self.jt += 1
            t = self.jt / self.jlen
            dy = -4 * 45 * t * (1 - t)
            name = "tall" if t < 0.5 else "n"
            if self.jt >= self.jlen:
                self.jcount -= 1
                if self.jcount > 0:
                    self.jt = 0
                else:
                    self.state, self.timer, self.sq = "idle", 25, 5
            self.place()

        elif st == "climb_wall":
            self.y -= self.opt_speed
            if self.y <= self.T:
                if self.opt_ceiling:
                    self.state = "ceiling"
                    self.rotation = 180
                    self.timer = 120
                else:
                    self.state = "fall"
                    self.rotation = 0
            self.place()

        elif st == "ceiling":
            self.x -= self.dir * self.opt_speed
            if self.timer <= 0 or self.x < self.L or self.x > self.R - self.W:
                self.state = "fall"
                self.rotation = 0
            self.timer -= 1
            self.place()

        elif st in ("walk", "idle"):
            if self.y < target_ground - 8:
                self.state = "fall"
                self.vy = 0
            else:
                self.y = target_ground

            self.timer -= 1
            if st == "walk" and not self.locked.get():
                self.x += self.dir * (self.opt_speed * 0.7 if hungry else self.opt_speed)

                if self.opt_walls and (self.x <= self.L or self.x >= self.R - self.W):
                    if random.random() < 0.4:
                        self.state = "climb_wall"
                        self.rotation = 90 if self.x <= self.L else -90
                    else:
                        self.dir *= -1
                else:
                    if self.x < self.L - 20: self.dir = 1
                    if self.x > self.R - self.W + 20: self.dir = -1

                dy = -abs(math.sin(now * 7)) * 4
                if self.timer <= 0:
                    self.state, self.timer = "idle", random.randint(30, 90)

            elif st == "walk":
                self.state = "idle"
            elif self.timer <= 0 and not self.locked.get() and not hungry:
                self.state = "walk"
                self.dir = random.choice([-1, 1])
                self.timer = random.randint(80, 220)

            if hungry and self.state == "idle":
                dx = random.choice([-1, 1])
            self.place()

        if self.sq > 0 and name == "n":
            name = "squash"
            self.sq -= 1

        rot_key = self.rotation if self.rotation in (0, 90, -90, 180) else 0
        self.cv.itemconfig(self.item, image=self.frames.get((name, self.dir > 0, rot_key), self.frames[("n", False, 0)]))
        self.cv.coords(self.item, self.W // 2 + dx, self.H + dy)

        text = self.bubble if now < self.bubble_until else ""
        if not text and hungry and self.opt_hungercry:
            text = "배고파요.. 츄르 줘냥ㅠㅠ"
        if text != self.drawn:
            self.cv.delete("b")
            if text:
                t = self.cv.create_text(self.W // 2, 20, text=text, tags="b",
                                        font=("맑은 고딕", 10, "bold"), fill="#333333")
                x1, y1, x2, y2 = self.cv.bbox(t)
                rect = self.cv.create_rectangle(x1 - 8, y1 - 4, x2 + 8, y2 + 4,
                                                fill="white", outline="#ffb300", width=2, tags="b")
                self.cv.tag_lower(rect, t)
            self.drawn = text

        self.root.after(33, self.tick)

if __name__ == "__main__":
    Pet().root.mainloop()
