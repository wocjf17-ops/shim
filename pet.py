import tkinter as tk
import json, os, sys, time, random, math, ctypes
from PIL import Image, ImageTk, ImageDraw

SIZE = 135          # 고양이 크기 (픽셀)
HUNGER_MIN = 60     # 배고파지는 시간 (분)
SNACK = 25          # 츄르/간식 포만감
JUMP_H = 50         # 점프 높이
KEY = "#ff00fe"     # 투명 배경색 키
TOP = 100           # 프로펠러 및 말풍선용 여백 높이

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

SAVE = os.path.join(base_dir(), "cat_save.json")

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

class CatCanvasRenderer:
    """IMG_2927.jpg 특징을 살린 절차적 픽셀 아트 렌더러"""
    C_CREAM = (235, 222, 205)
    C_DARK = (48, 35, 30)
    C_POINT = (32, 22, 18)
    C_WHITE = (252, 252, 252)
    C_EYE_BLUE = (85, 160, 225)
    C_PUPIL = (15, 20, 30)
    C_HOOD = (248, 220, 78)
    C_HOOD_SHADOW = (220, 190, 55)
    C_APPLE = (230, 60, 60)
    C_PROP = (70, 130, 240)

    @classmethod
    def draw_cat(cls, state, frame=0, eye_closed=False, hungry=False):
        w, h = 180, 200
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        cx, cy = 90, 135

        # 1. 꼬리
        tail_angle = math.sin(frame * 0.2) * 20
        tx = cx + 45
        ty = cy + 20
        d.line([(tx, ty), (tx + 18 + tail_angle * 0.4, ty - 22), (tx + 28 + tail_angle, ty - 40)],
               fill=cls.C_POINT, width=9)

        # 2. 뒷다리 / 앉기 / 걷기 다리
        if state == "sit_edge":
            # 모서리에 걸터앉아 다리 흔들흔들
            leg_swing = math.sin(frame * 0.25) * 8
            d.rounded_rectangle([cx - 24, cy + 20, cx - 8, cy + 45 + leg_swing], radius=6, fill=cls.C_POINT)
            d.rounded_rectangle([cx - 24, cy + 38 + leg_swing, cx - 8, cy + 47 + leg_swing], radius=4, fill=cls.C_WHITE)
            d.rounded_rectangle([cx + 8, cy + 20, cx + 24, cy + 45 - leg_swing], radius=6, fill=cls.C_POINT)
            d.rounded_rectangle([cx + 8, cy + 38 - leg_swing, cx + 24, cy + 47 - leg_swing], radius=4, fill=cls.C_WHITE)
        elif state == "walk":
            leg_step = math.sin(frame * 0.4) * 9
            d.rounded_rectangle([cx - 22 + leg_step, cy + 20, cx - 6 + leg_step, cy + 40], radius=6, fill=cls.C_POINT)
            d.rounded_rectangle([cx - 22 + leg_step, cy + 34, cx - 6 + leg_step, cy + 42], radius=4, fill=cls.C_WHITE)
            d.rounded_rectangle([cx + 6 - leg_step, cy + 20, cx + 22 - leg_step, cy + 40], radius=6, fill=cls.C_POINT)
            d.rounded_rectangle([cx + 6 - leg_step, cy + 34, cx + 22 - leg_step, cy + 42], radius=4, fill=cls.C_WHITE)
        elif state == "fly":
            # 허공에서 다리 가지런히
            d.rounded_rectangle([cx - 18, cy + 22, cx - 4, cy + 38], radius=5, fill=cls.C_POINT)
            d.rounded_rectangle([cx - 18, cy + 33, cx - 4, cy + 40], radius=4, fill=cls.C_WHITE)
            d.rounded_rectangle([cx + 4, cy + 22, cx + 18, cy + 38], radius=5, fill=cls.C_POINT)
            d.rounded_rectangle([cx + 4, cy + 33, cx + 18, cy + 40], radius=4, fill=cls.C_WHITE)
        elif state == "drag":
            # 마우스로 끌려갈 때 버둥버둥
            kick = math.sin(frame * 0.8) * 12
            d.rounded_rectangle([cx - 25 - kick, cy + 18, cx - 8 - kick, cy + 38], radius=5, fill=cls.C_POINT)
            d.rounded_rectangle([cx - 25 - kick, cy + 32, cx - 8 - kick, cy + 40], radius=4, fill=cls.C_WHITE)
            d.rounded_rectangle([cx + 8 + kick, cy + 18, cx + 25 + kick, cy + 38], radius=5, fill=cls.C_POINT)
            d.rounded_rectangle([cx + 8 + kick, cy + 32, cx + 25 + kick, cy + 40], radius=4, fill=cls.C_WHITE)
        else:
            # 기본 식빵/앉은 자세 (앞에 흰 양말 발 두 개 가지런히)
            d.ellipse([cx - 40, cy + 5, cx + 40, cy + 40], fill=cls.C_CREAM)
            d.rounded_rectangle([cx - 22, cy + 24, cx - 6, cy + 38], radius=6, fill=cls.C_WHITE)
            d.rounded_rectangle([cx + 6, cy + 24, cx + 22, cy + 38], radius=6, fill=cls.C_WHITE)

        # 3. 푹신한 몸통
        d.ellipse([cx - 36, cy - 8, cx + 36, cy + 34], fill=cls.C_CREAM)
        # 하얀 가슴털
        d.ellipse([cx - 22, cy + 2, cx + 22, cy + 30], fill=cls.C_WHITE)

        # 4. 노란 사과 두건 (머리 뒤쪽 배색)
        d.ellipse([cx - 48, cy - 65, cx + 48, cy + 15], fill=cls.C_HOOD)
        # 두건 위 사과 패턴 장식
        for ax, ay in [(cx - 28, cy - 40), (cx + 25, cy - 42), (cx - 15, cy - 54), (cx + 12, cy - 55)]:
            d.ellipse([ax - 4, ay - 4, ax + 4, ay + 4], fill=cls.C_APPLE)
            d.line([(ax, ay - 4), (ax + 2, ay - 7)], fill=(50, 120, 40), width=1)

        # 5. 귀 (두건 밖/위로 살짝 비치는 뾰족귀)
        d.polygon([(cx - 42, cy - 40), (cx - 32, cy - 72), (cx - 12, cy - 50)], fill=cls.C_POINT)
        d.polygon([(cx - 38, cy - 42), (cx - 32, cy - 66), (cx - 18, cy - 50)], fill=(80, 50, 50))
        d.polygon([(cx + 42, cy - 40), (cx + 32, cy - 72), (cx + 12, cy - 50)], fill=cls.C_POINT)
        d.polygon([(cx + 38, cy - 42), (cx + 32, cy - 66), (cx + 18, cy - 50)], fill=(80, 50, 50))

        # 6. 얼굴 기본 털 & 짙은 샴/래그돌 마스크
        d.ellipse([cx - 38, cy - 54, cx + 38, cy + 8], fill=cls.C_CREAM)
        # 짙은 갈색 얼굴 마스크
        d.ellipse([cx - 28, cy - 45, cx + 28, cy + 4], fill=cls.C_DARK)

        # 7. 흰색 주둥이 & 볼털 (턱 아래)
        d.ellipse([cx - 18, cy - 12, cx + 18, cy + 7], fill=cls.C_WHITE)

        # 8. 눈 (사파이어 블루)
        if eye_closed or state == "sleep":
            d.line([(cx - 22, cy - 20), (cx - 10, cy - 20)], fill=cls.C_WHITE, width=2)
            d.line([(cx + 10, cy - 20), (cx + 22, cy - 20)], fill=cls.C_WHITE, width=2)
        elif hungry:
            # 배고플 때 그렁그렁한 눈
            d.ellipse([cx - 24, cy - 28, cx - 8, cy - 12], fill=cls.C_EYE_BLUE)
            d.ellipse([cx + 8, cy - 28, cx + 24, cy - 12], fill=cls.C_EYE_BLUE)
            d.ellipse([cx - 18, cy - 24, cx - 12, cy - 18], fill=cls.C_WHITE)
            d.ellipse([cx + 12, cy - 24, cx + 18, cy - 18], fill=cls.C_WHITE)
        else:
            d.ellipse([cx - 23, cy - 27, cx - 9, cy - 13], fill=cls.C_EYE_BLUE)
            d.ellipse([cx + 9, cy - 27, cx + 23, cy - 13], fill=cls.C_EYE_BLUE)
            # 동공
            d.ellipse([cx - 18, cy - 24, cx - 14, cy - 16], fill=cls.C_PUPIL)
            d.ellipse([cx + 14, cy - 24, cx + 18, cy - 16], fill=cls.C_PUPIL)
            # 하이라이트
            d.ellipse([cx - 21, cy - 26, cx - 17, cy - 22], fill=cls.C_WHITE)
            d.ellipse([cx + 11, cy - 26, cx + 15, cy - 22], fill=cls.C_WHITE)

        # 9. 코 & 입 & 수염
        d.polygon([(cx - 3, cy - 12), (cx + 3, cy - 12), (cx, cy - 8)], fill=(40, 20, 20))
        d.arc([cx - 8, cy - 10, cx, cy - 4], 0, 180, fill=cls.C_DARK, width=2)
        d.arc([cx, cy - 10, cx + 8, cy - 4], 0, 180, fill=cls.C_DARK, width=2)

        # 새하얀 수염
        for dy_w in [-3, 0, 3]:
            d.line([(cx - 16, cy - 9 + dy_w), (cx - 44, cy - 13 + dy_w * 2)], fill=cls.C_WHITE, width=1)
            d.line([(cx + 16, cy - 9 + dy_w), (cx + 44, cy - 13 + dy_w * 2)], fill=cls.C_WHITE, width=1)

        # 10. 두건 앞쪽 리본 묶음 (목 부근)
        d.polygon([(cx - 12, cy + 6), (cx + 12, cy + 6), (cx, cy + 18)], fill=cls.C_HOOD_SHADOW)
        d.ellipse([cx - 8, cy + 8, cx + 8, cy + 18], fill=cls.C_HOOD)

        # 11. 머리 위 프로펠러 (비행 모드일 때 맹렬히 회전)
        if state == "fly":
            # 프로펠러 기둥
            d.rectangle([cx - 2, cy - 78, cx + 2, cy - 64], fill=(80, 80, 80))
            d.ellipse([cx - 5, cy - 81, cx + 5, cy - 74], fill=cls.C_DARK)
            # 날개 회전
            pw = abs(math.cos(frame * 0.7)) * 42 + 6
            d.ellipse([cx - pw, cy - 83, cx + pw, cy - 77], fill=cls.C_PROP)

        # 12. 간식 먹기 모드 시 츄르/과자 연출
        if state == "snack":
            d.rounded_rectangle([cx - 14, cy - 4, cx - 2, cy + 24], radius=3, fill=(240, 80, 120))
            d.ellipse([cx - 10, cy - 8, cx - 4, cy - 2], fill=(220, 160, 100))

        return im

class DesktopPetApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", KEY)
        self.root.config(bg=KEY)

        self.L, self.T, self.R, self.B = work_area(self.root)
        self.W, self.H = 180, 200

        self.cv = tk.Canvas(self.root, width=self.W, height=self.H, bg=KEY, highlightthickness=0)
        self.cv.pack()

        # 데이터 로드
        self.sat, self.inti, self.mins = 100.0, 0, 0
        try:
            with open(SAVE, encoding="utf-8") as f:
                d = json.load(f)
                self.sat = float(d.get("sat", 100))
                self.inti = int(d.get("inti", 0))
                self.mins = int(d.get("mins", 0))
        except Exception:
            pass

        # 물리 및 애니메이션 상태
        self.x = (self.L + self.R - self.W) // 2
        self.y = self.ground()
        self.dir = 1
        self.state = "idle"
        self.timer = 120
        self.anim_frame = 0
        self.blink_timer = 40
        self.eye_closed = False
        self.vy = 0
        self.locked = tk.BooleanVar(value=False)
        self.acc, self.last = 0.0, time.time()
        self.bubble, self.bubble_until, self.drawn = "", 0, None
        self.moved = False
        self.off = (0, 0)

        # 캔버스 객체
        self.tk_img = None
        self.item = self.cv.create_image(self.W // 2, self.H // 2, anchor="center")

        # 이벤트 바인딩
        self.cv.bind("<ButtonPress-1>", self.on_press)
        self.cv.bind("<B1-Motion>", self.on_motion)
        self.cv.bind("<ButtonRelease-1>", self.on_release)
        self.cv.bind("<Button-3>", self.on_menu)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        self.place()
        self.tick()

    def ground(self):
        return self.B - self.H + 18

    def place(self):
        self.root.geometry(f"{self.W}x{self.H}+{int(self.x)}+{int(self.y)}")

    def save(self):
        try:
            with open(SAVE, "w", encoding="utf-8") as f:
                json.dump({"sat": self.sat, "inti": self.inti, "mins": self.mins}, f)
        except Exception:
            pass

    def say(self, text, secs=2.0):
        self.bubble, self.bubble_until = text, time.time() + secs

    def on_press(self, e):
        self.off = (e.x_root - self.x, e.y_root - self.y)
        self.start = (e.x_root, e.y_root)
        self.moved = False

    def on_motion(self, e):
        if not self.moved and abs(e.x_root - self.start[0]) + abs(e.y_root - self.start[1]) > 6:
            self.moved = True
            self.state = "drag"
        if self.moved:
            self.x = e.x_root - self.off[0]
            self.y = e.y_root - self.off[1]
            self.place()

    def on_release(self, e):
        if self.moved:
            self.state = "fall"
            self.vy = 0
        else:
            # 클릭 시 상호작용
            actions = ["골골송~♥", "야옹~", "냥!"]
            self.say(random.choice(actions), 1.5)
            self.state = "jump"
            self.jt = 0

    def on_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=f"♥ 친밀도 {self.inti}  ·  함께 {self.mins}분", state="disabled")
        m.add_separator()
        m.add_command(label=f"츄르 주기  ·  포만감 {int(self.sat)}/100", command=self.feed)
        m.add_command(label="프로펠러 비행 띄우기", command=self.start_fly)
        m.add_command(label="화면 구석에 걸터앉기", command=self.sit_edge)
        m.add_command(label="화면 가운데로 부르기", command=self.center)
        m.add_checkbutton(label="위치 고정 (자동 이동 멈추기)", variable=self.locked)
        m.add_separator()
        m.add_command(label="종료", command=self.quit)
        self.root.focus_force()
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def feed(self):
        if self.sat >= 100:
            self.say("배불러요 냥~", 2)
            return
        self.sat = min(100, self.sat + SNACK)
        self.say("냠냠! 츄르 최고다냥", 2.5)
        self.state = "snack"
        self.timer = 50
        self.save()

    def start_fly(self):
        self.state = "fly"
        self.timer = 150
        self.say("두두두두! 날아간다냥", 2.0)

    def sit_edge(self):
        self.state = "sit_edge"
        self.timer = 200
        self.x = self.R - self.W + 10
        self.y = self.ground()
        self.say("살랑살랑~ 휴식 중", 2.0)

    def center(self):
        self.x = (self.L + self.R - self.W) / 2
        self.y = self.ground()
        self.state = "idle"
        self.timer = 60
        self.say("왔다냥!", 1.5)

    def quit(self):
        self.save()
        self.root.destroy()

    def tick(self):
        now = time.time()
        dt = now - self.last
        self.last = now
        self.anim_frame += 1

        # 포만감 및 시간 카운트
        self.sat = max(0.0, self.sat - dt * 100 / (HUNGER_MIN * 60))
        self.acc += dt
        if self.acc >= 60:
            self.acc -= 60
            self.inti += 1
            self.mins += 1
            self.save()
        hungry = self.sat < 20

        # 눈 깜빡임 타이머
        self.blink_timer -= 1
        if self.blink_timer <= 0:
            self.eye_closed = not self.eye_closed
            self.blink_timer = 5 if self.eye_closed else random.randint(40, 100)

        # 상태별 물리 엔진
        st = self.state
        if st == "fall":
            self.vy += 2
            self.y += self.vy
            if self.y >= self.ground():
                self.y = self.ground()
                self.state = "idle"
                self.timer = 40
            self.place()

        elif st == "jump":
            self.jt += 1
            t = self.jt / 20
            self.y = self.ground() - math.sin(t * math.pi) * JUMP_H
            if self.jt >= 20:
                self.y = self.ground()
                self.state = "idle"
                self.timer = 30
            self.place()

        elif st == "fly":
            # 프로펠러 회전하며 부드럽게 위아래로 둥실거리며 비행
            self.y = max(self.T + 50, self.y - 1.8 + math.sin(self.anim_frame * 0.15) * 1.5)
            self.x += self.dir * 1.2
            if self.x < self.L: self.dir = 1
            if self.x > self.R - self.W: self.dir = -1
            self.place()
            self.timer -= 1
            if self.timer <= 0:
                self.state = "fall"
                self.say("착륙한다냥~", 1.5)

        elif st == "sit_edge":
            self.timer -= 1
            if self.timer <= 0 and not self.locked.get():
                self.state = "idle"
                self.timer = 60

        elif st in ("walk", "idle", "snack"):
            self.y = self.ground()
            self.timer -= 1
            if st == "walk" and not self.locked.get():
                self.x += self.dir * (1.5 if hungry else 2.5)
                if self.x < self.L - 10: self.dir = 1
                if self.x > self.R - self.W + 10: self.dir = -1
                if self.timer <= 0:
                    self.state = "idle"
                    self.timer = random.randint(40, 120)
            elif st == "idle":
                if self.timer <= 0 and not self.locked.get() and not hungry:
                    # 일정 확률로 걷기, 프로펠러 비행 또는 걸터앉기 발동
                    pick = random.random()
                    if pick < 0.6:
                        self.state = "walk"
                        self.dir = random.choice([-1, 1])
                        self.timer = random.randint(80, 200)
                    elif pick < 0.8:
                        self.start_fly()
                    else:
                        self.sit_edge()
            elif st == "snack" and self.timer <= 0:
                self.state = "idle"
                self.timer = 40
            self.place()

        # 이미지 렌더링
        raw_pil = CatCanvasRenderer.draw_cat(
            state=self.state,
            frame=self.anim_frame,
            eye_closed=self.eye_closed,
            hungry=hungry
        )
        if self.dir < 0 and self.state != "sit_edge":
            raw_pil = raw_pil.transpose(Image.FLIP_LEFT_RIGHT)

        bg = Image.new("RGB", raw_pil.size, KEY)
        bg.paste(raw_pil.convert("RGB"), mask=raw_pil.getchannel("A"))
        self.tk_img = ImageTk.PhotoImage(bg)
        self.cv.itemconfig(self.item, image=self.tk_img)

        # 말풍선
        text = self.bubble if now < self.bubble_until else ""
        if not text and hungry:
            text = "배고파요.. 츄르 줘냥ㅠㅠ"
        if text != self.drawn:
            self.cv.delete("b")
            if text:
                t = self.cv.create_text(self.W // 2, 22, text=text, tags="b",
                                        font=("맑은 고딕", 10, "bold"), fill="#2b2b2b")
                x1, y1, x2, y2 = self.cv.bbox(t)
                rect = self.cv.create_rectangle(x1 - 8, y1 - 4, x2 + 8, y2 + 4,
                                                fill="#ffffff", outline="#f0c040", width=2, tags="b")
                self.cv.tag_lower(rect, t)
            self.drawn = text

        self.root.after(33, self.tick)

if __name__ == "__main__":
    DesktopPetApp().root.mainloop()
