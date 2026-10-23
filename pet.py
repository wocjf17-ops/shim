import tkinter as tk
import json, os, sys, time, random, math, ctypes
from PIL import Image, ImageTk

# ===== 설정 (마음대로 바꿔도 돼요) =====
SIZE = 130          # 펫 키(픽셀)
HUNGER_MIN = 60     # 간식 없이 배고파지기까지 걸리는 시간(분)
SNACK = 25          # 간식 1개당 포만감
JUMP_H = 50         # 폴짝 높이
# ======================================

KEY = "#ff00fe"     # 투명 처리용 색
TOP = 90            # 말풍선 + 점프 공간

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


def work_area(root):
    """작업표시줄을 뺀 화면 영역"""
    try:
        class RECT(ctypes.Structure):
            _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                        ("r", ctypes.c_long), ("b", ctypes.c_long)]
        r = RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0)
        return r.l, r.t, r.r, r.b
    except Exception:
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


class Pet:
    def __init__(self):
        r = self.root = tk.Tk()
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-transparentcolor", KEY)
        r.config(bg=KEY)
        self.L, self.T, self.R, self.B = work_area(r)

        # 이미지 준비
        img = Image.open(res("pet.png")).convert("RGBA")
        h = SIZE
        w = int(img.width * h / img.height)
        img = img.resize((w, h), Image.LANCZOS)
        self.W, self.H = w + 40, h + TOP
        self.frames = {}
        for flip in (False, True):
            base = img.transpose(Image.FLIP_LEFT_RIGHT) if flip else img
            for name, (sx, sy) in {"n": (1, 1), "tall": (.92, 1.1),
                                   "squash": (1.12, .88)}.items():
                self.frames[(name, flip)] = self.make(base, sx, sy)

        self.cv = tk.Canvas(r, width=self.W, height=self.H, bg=KEY,
                            highlightthickness=0)
        self.cv.pack()
        self.item = self.cv.create_image(self.W // 2, self.H, anchor="s",
                                         image=self.frames[("n", False)])

        # 저장된 상태
        self.sat, self.inti, self.mins = 100.0, 0, 0
        try:
            with open(SAVE, encoding="utf-8") as f:
                d = json.load(f)
            self.sat = float(d.get("sat", 100))
            self.inti = int(d.get("inti", 0))
            self.mins = int(d.get("mins", 0))
        except Exception:
            pass

        # 상태
        self.x = random.randint(self.L, max(self.L, self.R - self.W))
        self.y = self.ground()
        self.dir = random.choice([-1, 1])
        self.state, self.timer = "walk", 120
        self.vy = self.jt = self.sq = 0
        self.jlen, self.jcount = 22, 0
        self.locked = tk.BooleanVar(value=False)
        self.acc, self.last = 0.0, time.time()
        self.bubble, self.bubble_until, self.drawn = "", 0, None
        self.moved, self.off = False, (0, 0)

        self.cv.bind("<ButtonPress-1>", self.press)
        self.cv.bind("<B1-Motion>", self.motion)
        self.cv.bind("<ButtonRelease-1>", self.release)
        self.cv.bind("<Button-3>", self.menu)
        r.protocol("WM_DELETE_WINDOW", self.quit)

        self.place()
        self.tick()

    # ---------- 도우미 ----------
    def make(self, im, sx, sy):
        im = im.resize((max(1, int(im.width * sx)), max(1, int(im.height * sy))),
                       Image.LANCZOS)
        mask = im.getchannel("A").point(lambda v: 255 if v > 110 else 0)
        bg = Image.new("RGB", im.size, KEY)
        bg.paste(im.convert("RGB"), mask=mask)
        return ImageTk.PhotoImage(bg)

    def ground(self):
        return self.B - self.H

    def place(self):
        self.root.geometry(f"{self.W}x{self.H}+{int(self.x)}+{int(self.y)}")

    def save(self):
        try:
            with open(SAVE, "w", encoding="utf-8") as f:
                json.dump({"sat": self.sat, "inti": self.inti,
                           "mins": self.mins}, f)
        except Exception:
            pass

    def say(self, text, secs=2.0):
        self.bubble, self.bubble_until = text, time.time() + secs

    def jump(self, count=1):
        self.state, self.jt, self.jcount = "jump", 0, count

    # ---------- 마우스 ----------
    def press(self, e):
        self.off = (e.x_root - self.x, e.y_root - self.y)
        self.start = (e.x_root, e.y_root)
        self.moved = False

    def motion(self, e):
        if not self.moved and abs(e.x_root - self.start[0]) + \
                abs(e.y_root - self.start[1]) > 6:
            self.moved = True
            self.state = "drag"
        if self.moved:
            self.x = e.x_root - self.off[0]
            self.y = e.y_root - self.off[1]
            self.place()

    def release(self, e):
        if self.moved:
            self.state, self.vy = "fall", 0
        else:
            self.say("두근!", 1.2)
            self.jump(1)

    def menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=f"♥ 친밀도 {self.inti}  ·  함께 {self.mins}분",
                      state="disabled")
        m.add_separator()
        m.add_command(label=f"간식 주기  ·  포만감 {int(self.sat)}/100",
                      command=self.feed)
        m.add_command(label="화면 가운데로 부르기", command=self.center)
        m.add_checkbutton(label="위치 고정 (자동 이동 멈추기)",
                          variable=self.locked)
        m.add_separator()
        m.add_command(label="종료", command=self.quit)
        self.root.focus_force()
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def feed(self):
        if self.sat >= 100:
            self.say("배불러요~", 2)
            return
        self.sat = min(100, self.sat + SNACK)
        self.say("냠냠! 맛있다", 2.5)
        self.jump(2)
        self.save()

    def center(self):
        self.x = (self.L + self.R - self.W) / 2
        self.y = self.ground()
        self.state, self.timer = "idle", 60
        self.say("여기요!", 1.5)

    def quit(self):
        self.save()
        self.root.destroy()

    # ---------- 메인 루프 ----------
    def tick(self):
        now = time.time()
        dt = now - self.last
        self.last = now

        self.sat = max(0.0, self.sat - dt * 100 / (HUNGER_MIN * 60))
        self.acc += dt
        if self.acc >= 60:
            self.acc -= 60
            self.inti += 1
            self.mins += 1
            self.save()
        hungry = self.sat < 20

        dy, dx, name = 0, 0, "n"
        st = self.state
        if st == "fall":
            self.vy += 2
            self.y += self.vy
            if self.y >= self.ground():
                self.y = self.ground()
                self.state, self.timer, self.sq = "idle", 40, 6
            self.place()
        elif st == "jump":
            self.jt += 1
            t = self.jt / self.jlen
            dy = -4 * JUMP_H * t * (1 - t)
            name = "tall" if t < 0.5 else "n"
            if self.jt >= self.jlen:
                self.jcount -= 1
                if self.jcount > 0:
                    self.jt = 0
                else:
                    self.state, self.timer, self.sq = "idle", 25, 5
        elif st in ("walk", "idle"):
            self.y = self.ground()
            self.timer -= 1
            if st == "walk" and not self.locked.get():
                self.x += self.dir * (1.5 if hungry else 3)
                if self.x < self.L - 20:
                    self.dir = 1
                if self.x > self.R - self.W + 20:
                    self.dir = -1
                dy = -abs(math.sin(now * 9)) * 5
                if self.timer <= 0:
                    self.state, self.timer = "idle", random.randint(30, 100)
            elif st == "walk":
                self.state = "idle"
            elif self.timer <= 0 and not self.locked.get() and not hungry:
                self.state = "walk"
                self.dir = random.choice([-1, 1])
                self.timer = random.randint(90, 250)
            if hungry and self.state == "idle":
                dx = random.choice([-2, 2])  # 배고파서 떨기
            self.place()

        if self.sq > 0 and name == "n":
            name = "squash"
            self.sq -= 1

        self.cv.itemconfig(self.item, image=self.frames[(name, self.dir > 0)])
        self.cv.coords(self.item, self.W // 2 + dx, self.H + dy)

        # 말풍선
        text = self.bubble if now < self.bubble_until else ""
        if not text and hungry:
            text = "배고파요 ㅠㅠ"
        if text != self.drawn:
            self.cv.delete("b")
            if text:
                t = self.cv.create_text(self.W // 2, 20, text=text, tags="b",
                                        font=("맑은 고딕", 10, "bold"),
                                        fill="#333333")
                x1, y1, x2, y2 = self.cv.bbox(t)
                rect = self.cv.create_rectangle(x1 - 8, y1 - 4, x2 + 8, y2 + 4,
                                                fill="white", outline="#999999",
                                                tags="b")
                self.cv.tag_lower(rect, t)
            self.drawn = text

        self.root.after(33, self.tick)


if __name__ == "__main__":
    Pet().root.mainloop()
