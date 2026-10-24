"""
바탕화면 펫 프로그램 (업그레이드판)
- Gemini 404 해결: 모델 이름을 고정하지 않고 '지금 쓸 수 있는 모델'을 서버에서 받아 자동 선택
- 인터넷이 막힌 곳에서도 되는 오프라인 기능 (8볼, 포춘 쿠키, 순화어 사전 검수 등)
- OpenPets 참고: 의상 일정, 집중(포모도로), 물 마시기, 빠른 알림, 기분 체크인,
  시스템 리소스 표시, 활동 요약, 컴팩트 질문 바, 아침 인사
- 공문서 순화 및 오타 검수 (Ctrl + Shift + C)
"""
import tkinter as tk
from tkinter import ttk
import json, os, sys, time, random, math, ctypes, threading, re, queue
import urllib.request, urllib.error
import ssl
from PIL import Image, ImageTk, ImageDraw

WIN = sys.platform == "win32"
if WIN:
    import ctypes.wintypes

KEY = "#ff00fe"          # 투명 크로마키 색
FONT = "맑은 고딕"
TOP = 110                # 말풍선 및 점프 공간
MAX_PETS = 5
MILESTONES = [50, 100, 200, 300, 500, 1000, 2000, 3000, 5000, 10000]

# 공공기관 사설 SSL 인증서 오류 우회 컨텍스트
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

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

DEFAULTS = {
    "speed": 3, "activity": 5, "size": 140, "opacity": 100,
    "click_reaction": "폴짝", "hunger_min": 60, "snack": 25,
    "cry_always": False, "hidden_reactions": True,
    "locked": False, "safe_mode": False,
    "show_inti": False, "idle_nap_min": 10, "nap_on": True,

    # 세부 동작 옵션
    "allow_wall": True, "allow_ceil": True, "allow_window": True,
    "allow_sit": True, "short_sit": False,
    "flee_mouse": True, "follow_mouse": False,
    "work_safe_mode": False, "auto_hide_fullscreen": False,
    "spd_walk": 2.0, "spd_spin": 3.0, "spd_slide": 3.0,
    "slide_delay": 0.12,

    # 알림 및 자동 시작
    "autostart": False, "notify_hour_popup": True,
    "work_hour_mute": False, "work_mute_start": 9, "work_mute_end": 18,
    "glow_edge": True, "glow_color": "피치·핑크·보라·하늘",
    "glow_width": "넓게", "glow_intensity": "선명하게",

    "notify_lunch": True, "lunch_time": "12:00", "lunch_msg": "점심 먹으러 가자!",
    "notify_leave": True, "leave_time": "18:00", "leave_msg": "퇴근이다! 오늘도 수고했어",
    "notify_hungry": True, "notify_hour": True, "sound": True,

    # 업그레이드: OpenPets 참고 기능
    "outfit": "auto",            # auto = 일정대로
    "water_on": False, "water_min": 60,
    "mood_daily": False,
    "show_sys": False,
    "focus_min": 25, "break_min": 5, "focus_cycles": 4,

    "ai_provider": "Gemini",
    "ai_persona": "고양이",
    "ai_api_key": "",
    "gemini_model": "",          # 비워두면 자동 선택
}

SECRETS = {
    "spin": ("빙글빙글", "머리 위에서 마우스를 한 바퀴 돌려보기"),
    "dance": ("몰래 하는 군무", "친구가 둘 이상일 때 마우스를 4초 동안 가만히 두기"),
    "tickle": ("간지럼", "친구를 빠르게 5번 클릭하기"),
}

PERSONA_PROMPTS = {
    "고양이": (
        "너는 사용자의 바탕화면에 살고 있는 고양이 데스크톱 펫 비서야.\n"
        "- 모든 문장의 끝을 '~냥', '~다냥', '~냐옹?'으로 끝내줘.\n"
        "- 새침하지만 다정하고 귀엽게 대해줘.\n"
        "- 첫 줄은 바탕화면 말풍선용으로 25자 이내로 짧게 작성하고 줄바꿈해줘.\n"
        "- [도구 실행 규격]:\n"
        "  1) 타이머 요청 시 본문 끝에 [TOOL: {\"action\": \"timer\", \"minutes\": 분, \"msg\": \"알림문구\"}] 추가\n"
        "  2) 할 일 추가 시 본문 끝에 [TOOL: {\"action\": \"todo\", \"text\": \"할일내용\"}] 추가\n"
        "  3) 칭찬받거나 신날 땐 [ACTION: hop] 또는 [ACTION: dance] 추가"
    ),
    "강아지": (
        "너는 사용자의 바탕화면에 살고 있는 밝고 충직한 강아지 데스크톱 펫 비서야!\n"
        "- 모든 문장의 끝을 '~멍!', '~했멍!', '~멍?'으로 끝내줘.\n"
        "- 애교 넘치고 주인을 든든히 지키며 응원해줘.\n"
        "- 첫 줄은 바탕화면 말풍선용으로 25자 이내로 짧게 작성하고 줄바꿈해줘.\n"
        "- [도구 실행 규격]:\n"
        "  1) 타이머 요청 시 본문 끝에 [TOOL: {\"action\": \"timer\", \"minutes\": 분, \"msg\": \"알림문구\"}] 추가\n"
        "  2) 할 일 추가 시 본문 끝에 [TOOL: {\"action\": \"todo\", \"text\": \"할일내용\"}] 추가\n"
        "  3) 칭찬받거나 신날 땐 [ACTION: hop] 또는 [ACTION: dance] 추가"
    )
}

# ------------------------------------------------ 오프라인 콘텐츠
FORTUNES = [
    "오늘은 작은 친절이 큰 행운으로 돌아와요.",
    "미뤄둔 일 하나를 끝내면 마음이 가벼워질 거예요.",
    "점심 메뉴를 새로 골라 보세요. 뜻밖의 맛집을 만날지도 몰라요.",
    "급할수록 천천히, 오늘은 확인 한 번이 실수를 막아줘요.",
    "누군가 오늘 당신 덕분에 웃게 될 거예요.",
    "잠깐 창밖을 바라보세요. 좋은 생각이 떠오를 거예요.",
    "오늘의 수고는 내일 반드시 빛을 내요.",
    "물 한 잔 마시고 시작하면 하루가 부드럽게 풀려요.",
    "생각보다 일이 쉽게 풀리는 날이에요. 자신감을 가지세요.",
    "오래 연락 못 한 사람에게 안부를 보내 보세요.",
    "작은 메모 하나가 오늘의 큰 도움이 돼요.",
    "오늘은 부탁하기에 좋은 날, 용기 내 보세요.",
    "퇴근길에 좋아하는 노래를 들으면 행운이 따라와요.",
    "당신이 하는 일은 생각보다 훨씬 많은 사람에게 도움이 돼요.",
    "깊게 숨을 들이쉬고 천천히 내쉬면, 문제가 반쯤 풀려요.",
    "오늘 만난 첫 번째 좋은 소식이 하루를 이끌어 줄 거예요.",
]

EIGHT_BALL = [
    "확실해요!", "물론이죠.", "내 눈에는 그렇게 보여요.", "아마도 그럴 거예요.",
    "지금은 흐릿해요. 다시 물어봐 줘요.", "조금 더 생각해 보는 게 좋겠어요.",
    "지금은 말하지 않는 게 낫겠어요.", "기대는 너무 하지 마세요.",
    "내 대답은 '아니요'예요.", "가능성이 낮아 보여요.", "일단 해보세요, 손해는 없을 거예요.",
    "한숨 자고 나서 결정해요.",
]

# 행정 순화어 사전 (오프라인 검수용 · 필요하면 자유롭게 추가하세요)
PUREWORD = {
    "시달": "알림", "납기": "납부기한", "잔업": "시간외근무", "가계약": "임시계약",
    "당해": "해당", "익일": "다음 날", "차질없이": "문제없이", "차질 없이": "문제없이",
    "요망됨": "바랍니다", "요망": "바람", "금번": "이번", "상기": "위",
    "제반": "여러", "사료됨": "생각됩니다", "필히": "반드시",
    "수차례": "여러 번", "기제출": "이미 제출한", "금일": "오늘", "명일": "내일",
    "소정의": "정해진", "기히": "이미", "불비": "미비",
}

HELP_TEXT = (
    "이런 걸 할 수 있어요!\n"
    "· 우클릭 → 간식/의상/포춘 쿠키/매직 8볼/기분 체크인\n"
    "· 도우미: 할 일, 메모, 타이머, 집중(포모도로), 빠른 알림\n"
    "· 공문서 순화·오타 검수 (글을 복사하고 Ctrl+Shift+C)\n"
    "· 인터넷이 막혀도 8볼·포춘·순화어 사전은 그대로 써요"
)

# ------------------------------------------------ Win32 API
if WIN:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    try:
        dwm = ctypes.windll.dwmapi
    except Exception:
        dwm = None

    class RECT(ctypes.Structure):
        _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                    ("r", ctypes.c_long), ("b", ctypes.c_long)]

    class MEMSTAT(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    user32.GetForegroundWindow.restype = ctypes.c_void_p

    user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
    user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]

    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    VK_C = 0x43
    VK_CONTROL = 0x11
    KEYEVENTF_KEYUP = 0x0002
    HOTKEY_PROOFREAD_ID = 101

    def simulate_copy():
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_C, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.12)


def get_foreground_window_title():
    if not WIN:
        return ""
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def set_autostart(enable=True):
    if not WIN:
        return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                             winreg.KEY_SET_VALUE)
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
    if not WIN:
        return False
    try:
        fg = user32.GetForegroundWindow()
        if not fg:
            return False
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


# ------------------------------------------------ 시스템 리소스 (CPU / RAM)
_cpu_prev = [None]


def sys_stats():
    """(CPU %, RAM %) 반환. 못 읽으면 (None, None)"""
    cpu = ram = None
    try:
        if WIN:
            m = MEMSTAT()
            m.dwLength = ctypes.sizeof(MEMSTAT)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            ram = int(m.dwMemoryLoad)
            idle, kern, usr = (ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong())
            kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(usr))
            cur = (idle.value, kern.value + usr.value)
        else:
            with open("/proc/meminfo") as f:
                mi = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
            ram = int(100 * (1 - mi["MemAvailable"] / mi["MemTotal"]))
            with open("/proc/stat") as f:
                v = [int(x) for x in f.readline().split()[1:]]
            cur = (v[3] + v[4], sum(v))
        prev = _cpu_prev[0]
        _cpu_prev[0] = cur
        if prev:
            di, dt = cur[0] - prev[0], cur[1] - prev[1]
            if dt > 0:
                cpu = int(max(0, min(100, 100 * (1 - di / dt))))
    except Exception:
        pass
    return cpu, ram


# ------------------------------------------------ Gemini API (모델 자동 선택 · 404 해결)
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
# 서버 목록을 못 받을 때만 쓰는 예비 후보 (최신 → 오래된 순). 1.5 / 2.0 / gemini-pro 는 이미 종료된 모델이에요.
GEMINI_FALLBACKS = ["gemini-flash-latest", "gemini-3.6-flash", "gemini-2.5-flash",
                    "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]
_gemini_state = {"model": "", "last_used": ""}


def _gem_http(url, key, payload=None, timeout=25):
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def _http_err_text(e):
    """HTTPError에서 서버가 보낸 설명을 뽑아냄. 구글이 아닌 중간 장비(프록시)가 준 응답인지도 구분."""
    try:
        raw = e.read().decode("utf-8", "ignore")
    except Exception:
        raw = ""
    try:
        msg = json.loads(raw).get("error", {}).get("message", "")
        return msg or raw[:200], True
    except Exception:
        return raw[:120].replace("\n", " "), False


def discover_gemini_models(key):
    """서버에 '지금 쓸 수 있는 모델 목록'을 물어서 추천 순서대로 이름 반환"""
    data = _gem_http(f"{GEMINI_BASE}/models?pageSize=200", key, timeout=15)
    stable, other = [], []
    for m in data.get("models", []):
        name = m.get("name", "").replace("models/", "")
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if not name.startswith("gemini-"):
            continue
        if any(x in name for x in ("image", "tts", "embedding", "live", "audio", "omni",
                                   "robotics", "computer", "vision", "thinking", "exp")):
            continue
        mt = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash(-lite)?", name)
        if mt:
            # 안정 버전 flash: 새 버전 우선, lite 는 뒤로
            stable.append((1 if mt.group(2) else 0, -float(mt.group(1)), name))
        elif "flash" in name:
            other.append(name)
    stable.sort()
    newer = [t for t in stable if -t[1] >= 2.5]      # 1.x / 2.0 은 이미 종료된 모델이라 뒤로
    older = [t for t in stable if -t[1] < 2.5]
    ordered = [n for _, _, n in (newer or stable)] + other + [n for _, _, n in (older if newer else [])]
    if not ordered:
        ordered = [m.get("name", "").replace("models/", "") for m in data.get("models", [])
                   if "generateContent" in m.get("supportedGenerationMethods", [])
                   and m.get("name", "").startswith("models/gemini-")]
    return ordered


def query_gemini_api(api_key, system_prompt, contents, preferred=""):
    """
    1) 저장된/지정한 모델 → 2) 서버가 알려준 최신 모델 → 3) 예비 후보 순서로 시도.
    404 = '그 모델 없음(종료됨)' 이므로 다음 후보로 넘어가고, 다른 오류는 이유를 설명해서 알려줌.
    """
    key = api_key.strip()
    if not key:
        raise ValueError("API Key가 비어있습니다. 대화창 상단에 Key를 먼저 입력해주세요.")

    payload = {"system_instruction": {"parts": [{"text": system_prompt}]}, "contents": contents}
    tried, notes = [], []

    def attempt(model):
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        d = _gem_http(url, key, payload, timeout=30)
        cands = d.get("candidates") or []
        if not cands:
            fb = d.get("promptFeedback", {})
            raise RuntimeError(f"응답이 비어 있어요 ({fb.get('blockReason', '내용 없음')})")
        parts = cands[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise RuntimeError("모델이 빈 답을 돌려줬어요. 다시 시도해 주세요.")
        _gemini_state["model"] = _gemini_state["last_used"] = model
        return text

    def run(models):
        for model in models:
            if not model or model in tried:
                continue
            tried.append(model)
            try:
                return attempt(model)
            except urllib.error.HTTPError as e:
                msg, is_json = _http_err_text(e)
                if e.code == 404:
                    notes.append(f"{model}: 없는 모델(404)" + ("" if is_json else " · 구글이 아닌 프록시 응답일 수 있음"))
                    continue
                if e.code in (400, 401, 403) and ("API key" in msg or "API_KEY" in msg or e.code in (401, 403)):
                    raise Exception(f"API Key 문제 [{e.code}]: {msg or '키가 올바른지, Generative Language API가 허용돼 있는지 확인하세요.'}")
                if e.code == 429:
                    raise Exception("요청이 너무 많거나 무료 사용량을 넘었어요 [429]. 잠시 후 다시 시도하세요.")
                if e.code >= 500:
                    notes.append(f"{model}: 구글 서버 오류({e.code})")
                    continue
                raise Exception(f"구글 서버 에러 [{e.code}]: {msg or e.reason}")
            except urllib.error.URLError as e:
                raise Exception(f"인터넷에 연결할 수 없어요 (방화벽/프록시 차단 가능): {e.reason}")
            except TimeoutError:
                raise Exception("응답이 너무 늦어요 (30초 초과). 기관망이 느리거나 막혀 있을 수 있어요.")
            except Exception as ex:
                if "timed out" in str(ex):
                    raise Exception("응답이 너무 늦어요 (30초 초과). 기관망이 느리거나 막혀 있을 수 있어요.")
                raise
        return None

    # 1) 지정/기억해 둔 모델
    out = run([preferred.strip(), _gemini_state["model"]])
    if out:
        return out
    # 2) 서버가 알려주는 현재 모델 목록
    try:
        found = discover_gemini_models(key)
    except urllib.error.HTTPError as e:
        msg, _ = _http_err_text(e)
        if e.code in (400, 401, 403):
            raise Exception(f"API Key 문제 [{e.code}]: {msg}")
        found = []
    except urllib.error.URLError as e:
        raise Exception(f"인터넷에 연결할 수 없어요 (방화벽/프록시 차단 가능): {e.reason}")
    except Exception:
        found = []
    out = run(found[:4])
    if out:
        return out
    # 3) 예비 후보
    out = run(GEMINI_FALLBACKS)
    if out:
        return out
    raise Exception("사용할 수 있는 Gemini 모델을 찾지 못했어요.\n" + "\n".join(notes[-6:]) +
                    "\n\n· 키가 'Google AI Studio'에서 만든 키인지 확인하세요."
                    "\n· 기관망이 generativelanguage.googleapis.com 을 막았다면 Ollama(로컬)를 쓰거나 보안팀에 허용을 요청하세요.")


# ------------------------------------------------ 의상 (OpenPets '옷장' 참고)
OUTFITS = {
    "none": "기본", "pajamas": "잠옷", "weekend": "주말", "halloween": "할로윈",
    "winter": "겨울 휴일", "summer": "여름",
}


def scheduled_outfit(lt=None):
    """위에서부터 확인해서 처음 맞는 규칙을 적용 (OpenPets 방식)"""
    lt = lt or time.localtime()
    md = (lt.tm_mon, lt.tm_mday)
    if md >= (12, 15) or md <= (1, 2):
        return "winter"
    if (10, 24) <= md <= (11, 1):
        return "halloween"
    if lt.tm_hour >= 22 or lt.tm_hour < 7:
        return "pajamas"
    if lt.tm_wday >= 5:
        return "weekend"
    if (6, 21) <= md <= (8, 31):
        return "summer"
    return "none"


def make_outfit(base, name):
    """사진 위에 소품(모자 등)을 그려서 새 이미지로 반환. 머리 위에 얹도록 위쪽 여백을 늘려요."""
    if name == "none" or name not in OUTFITS:
        return base
    w, h = base.size
    pad = int(h * (0.34 if name != "weekend" else 0.12))
    S = 3
    cw, chh = w * S, (h + pad) * S
    layer = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = w * S * 0.5
    top = pad * S                    # 머리 꼭대기
    hw = w * S * 0.52                # 모자 폭
    lw = max(3, int(w * 0.012 * S))
    ol = (60, 45, 45, 255)
    yb = top + h * S * 0.09          # 모자 아랫선 (머리와 살짝 겹침)
    hh = pad * S * 0.95              # 모자 높이

    def pom(x, y, r, col=(255, 255, 255, 255)):
        d.ellipse((x - r, y - r, x + r, y + r), fill=col, outline=ol, width=lw)

    if name == "winter":             # 산타 모자
        d.polygon([(cx - hw / 2, yb), (cx + hw / 2, yb), (cx + hw * 0.12, yb - hh)],
                  fill=(214, 48, 49, 255), outline=ol)
        d.line([(cx - hw / 2, yb), (cx + hw * 0.12, yb - hh), (cx + hw / 2, yb)], fill=ol, width=lw)
        d.rounded_rectangle((cx - hw * 0.56, yb - hh * 0.10, cx + hw * 0.56, yb + hh * 0.12),
                            radius=hh * 0.1, fill=(255, 255, 255, 255), outline=ol, width=lw)
        pom(cx + hw * 0.12, yb - hh, hh * 0.10)
    elif name == "halloween":        # 마녀 모자
        d.polygon([(cx - hw * 0.28, yb), (cx + hw * 0.28, yb), (cx + hw * 0.08, yb - hh)],
                  fill=(60, 40, 90, 255), outline=ol)
        d.line([(cx - hw * 0.28, yb), (cx + hw * 0.08, yb - hh), (cx + hw * 0.28, yb)], fill=ol, width=lw)
        d.ellipse((cx - hw * 0.62, yb - hh * 0.07, cx + hw * 0.62, yb + hh * 0.12),
                  fill=(60, 40, 90, 255), outline=ol, width=lw)
        d.rectangle((cx - hw * 0.27, yb - hh * 0.22, cx + hw * 0.27, yb - hh * 0.06),
                    fill=(255, 140, 26, 255), outline=ol, width=lw)
        d.rectangle((cx - hw * 0.05, yb - hh * 0.22, cx + hw * 0.05, yb - hh * 0.06),
                    fill=(255, 226, 100, 255), outline=ol, width=max(2, lw // 2))
    elif name == "pajamas":          # 나이트캡
        d.polygon([(cx - hw * 0.45, yb), (cx + hw * 0.45, yb),
                   (cx + hw * 0.55, yb - hh * 0.7), (cx + hw * 0.25, yb - hh * 0.55)],
                  fill=(120, 160, 230, 255), outline=ol)
        d.line([(cx - hw * 0.45, yb), (cx + hw * 0.25, yb - hh * 0.55), (cx + hw * 0.55, yb - hh * 0.7),
                (cx + hw * 0.45, yb)], fill=ol, width=lw)
        d.rounded_rectangle((cx - hw * 0.5, yb - hh * 0.08, cx + hw * 0.5, yb + hh * 0.1),
                            radius=hh * 0.08, fill=(255, 255, 255, 255), outline=ol, width=lw)
        pom(cx + hw * 0.55, yb - hh * 0.72, hh * 0.09)
    elif name == "summer":           # 밀짚모자
        d.ellipse((cx - hw * 0.75, yb - hh * 0.10, cx + hw * 0.75, yb + hh * 0.16),
                  fill=(240, 205, 120, 255), outline=ol, width=lw)
        d.pieslice((cx - hw * 0.40, yb - hh * 0.75, cx + hw * 0.40, yb + hh * 0.20), 180, 360,
                   fill=(245, 215, 130, 255), outline=ol, width=lw)
        d.rectangle((cx - hw * 0.40, yb - hh * 0.18, cx + hw * 0.40, yb - hh * 0.02),
                    fill=(222, 70, 70, 255), outline=ol, width=lw)
    elif name == "weekend":          # 꽃 머리핀
        fx, fy, r = cx + hw * 0.30, top + h * S * 0.03, hw * 0.085
        for k in range(5):
            a = k * 1.2566
            px, py = fx + math.cos(a) * r * 1.2, fy + math.sin(a) * r * 1.2
            d.ellipse((px - r, py - r, px + r, py + r), fill=(255, 150, 190, 255), outline=ol, width=lw)
        d.ellipse((fx - r * 0.7, fy - r * 0.7, fx + r * 0.7, fy + r * 0.7),
                  fill=(255, 230, 110, 255), outline=ol, width=lw)
    layer = layer.resize((w, h + pad), Image.LANCZOS)
    out = Image.new("RGBA", (w, h + pad), (0, 0, 0, 0))
    out.paste(base, (0, pad), base)
    out.alpha_composite(layer)
    return out


# ------------------------------------------------ 화면 가장자리 빛 효과
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


# ------------------------------------------------ 커스텀 알림창 (미루기 버튼 지원)
class CustomAlertPopup:
    def __init__(self, root, on_close=None):
        self.root = root
        self.on_close = on_close
        self.snooze_cb = None
        self.win = tk.Toplevel(root)
        self.win.title("알림")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.config(bg="#f8f9fa")

        f = tk.Frame(self.win, bg="#ffffff", bd=1, relief="solid")
        f.pack(fill="both", expand=True, padx=4, pady=4)

        top_bar = tk.Frame(f, bg="#ffffff")
        top_bar.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(top_bar, text="알림", font=(FONT, 9, "bold"), bg="#ffffff", fg="#666666").pack(side="left")
        close_btn = tk.Label(top_bar, text="✕", font=(FONT, 11), bg="#ffffff", fg="#999999", cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self.close())

        self.lbl_title = tk.Label(f, text="정각 알림", font=(FONT, 10), bg="#ffffff", fg="#888888")
        self.lbl_title.pack(anchor="w", padx=18, pady=(8, 0))

        self.lbl_time = tk.Label(f, text="11:00", font=(FONT, 34, "bold"), bg="#ffffff", fg="#222222")
        self.lbl_time.pack(anchor="w", padx=14, pady=2)

        self.lbl_sub = tk.Label(f, text="", font=(FONT, 10), bg="#ffffff", fg="#555555",
                                justify="left", wraplength=250)
        self.lbl_sub.pack(anchor="w", padx=18, pady=(0, 12))

        self.btns = tk.Frame(f, bg="#ffffff")
        self.btns.pack(anchor="e", padx=18, pady=(0, 14))
        self.btn_snooze = tk.Button(self.btns, text="5분 미루기", font=(FONT, 10), bg="#e9ecef",
                                    relief="flat", padx=12, pady=6, cursor="hand2",
                                    command=self.snooze)
        tk.Button(self.btns, text="확인했어", font=(FONT, 10, "bold"), bg="#2d3238", fg="#ffffff",
                  activebackground="#454b52", activeforeground="#ffffff", relief="flat",
                  padx=18, pady=6, cursor="hand2", command=self.close).pack(side="right")

    def show(self, time_str, sub_text, title="알림", snooze=None):
        self.lbl_title.config(text=title)
        self.lbl_time.config(text=time_str)
        self.lbl_sub.config(text=sub_text)
        self.snooze_cb = snooze
        if snooze:
            self.btn_snooze.pack(side="right", padx=(0, 8))
        else:
            self.btn_snooze.pack_forget()
        w, h = 300, 230
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+60+{sh // 4}")
        self.win.deiconify()
        self.win.attributes("-topmost", True)

    def snooze(self):
        cb = self.snooze_cb
        self.close()
        if cb:
            cb()

    def close(self):
        self.win.withdraw()
        if self.on_close:
            self.on_close()


# ------------------------------------------------ 펫 객체
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
        self.inspect_until = 0
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
        self.g.stat("bubbles")

    def face(self, dx, dy):
        g = self.g
        return g.W // 2 + dx, g.H - g.ch_h * 0.55 + dy

    def start(self, act, **kw):
        g, s = self.g, self.g.s
        self.act, self.t, self.kw = act, 0, kw
        g.stat_act(act)
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

        work_safe = False
        if s["work_safe_mode"]:
            lt = time.localtime()
            if lt.tm_wday < 5 and (9 <= lt.tm_hour < 18):
                work_safe = True

        if g.focus_phase() == "focus":          # 집중 시간에는 조용히
            ch = [("idle", 50), ("sit", 50)]
        elif s["locked"] or s["safe_mode"] or work_safe:
            ch = [("idle", 50), ("hop", 20)]
            if s["allow_sit"]:
                ch.append(("sit", 30))
        else:
            ch = [("walk", 40), ("idle", 14), ("hop", 8), ("slide", 6), ("dizzy", 3), ("spin", 3)]
            if s["allow_sit"]:
                ch.append(("sit", 12))
            if s["allow_wall"]:
                ch.append(("wall", 5))
            if s["allow_ceil"]:
                ch.append(("ceil", 4))
            if s["allow_window"] and WIN:
                ch.append(("perch", 7))

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
        g.stat("clicks")
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

        m.add_command(label="✨ AI 비서에게 물어보기 (Gemini / Ollama)...", command=lambda: g.open_ai_chat(self))
        m.add_command(label="💬 빠른 질문 바", command=lambda: g.open_quick_bar(self))
        m.add_command(label="📄 공문서 순화·오타 검수 (Ctrl+Shift+C)", command=lambda: g.check_report_spelling(self))
        m.add_separator()

        fun = tk.Menu(m, tearoff=0, font=(FONT, 10))
        fun.add_command(label="🥠 오늘의 포춘 쿠키", command=lambda: g.fortune_cookie(self))
        fun.add_command(label="🎱 매직 8볼에게 물어보기", command=lambda: g.open_eight_ball(self))
        fun.add_command(label="🙂 기분 체크인", command=lambda: g.open_mood(self))
        m.add_cascade(label="놀이 · 기분", menu=fun)

        wear = tk.Menu(m, tearoff=0, font=(FONT, 10))
        wear.add_radiobutton(label=f"일정대로 (지금: {OUTFITS[scheduled_outfit()]})",
                             variable=g.outfit_var, value="auto", command=g.on_outfit_changed)
        for k, v in OUTFITS.items():
            wear.add_radiobutton(label=v, variable=g.outfit_var, value=k, command=g.on_outfit_changed)
        m.add_cascade(label="👕 의상", menu=wear)
        m.add_separator()

        m.add_command(label="친구 한 마리 더 부르기", command=g.add_pet)
        m.add_command(label="이 친구 보내기", command=lambda: g.remove_pet(self))
        m.add_command(label="모두 숨기기", command=g.hide_all)
        m.add_separator()
        m.add_command(label="알림 설정...", command=g.open_notify)
        m.add_command(label="화면 가운데로 모으기", command=g.gather)
        m.add_command(label="움직임 · 반응 설정...", command=g.open_motion)
        m.add_checkbutton(label="위치 고정 (자동 이동 멈추기)", variable=g.lock_var, command=g.sync_flags)
        m.add_checkbutton(label="CPU / RAM 표시", variable=g.sys_var, command=g.sync_flags)
        m.add_command(label="친구 기록 · 활동 요약...", command=g.open_record)
        m.add_command(label="도우미 · 할 일 · 메모 · 타이머 · 집중...", command=g.open_helper)
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

    # ----- 행동별 포즈
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

        if g.s["follow_mouse"]:
            px, _ = self.win.winfo_pointerxy()
            cx = self.x + g.W / 2
            if abs(px - cx) > 40:
                self.dir = 1 if px > cx else -1

        self.x += self.dir * sp
        if self.x < g.L - 25:
            self.dir = 1
        if self.x > g.R - g.W + 25:
            self.dir = -1
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
        if t < 20:
            lift = 4 * t
        elif t < 55:
            lift = 80
        else:
            lift = 80 * (1 - (t - 55) / (d - 55))
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
        if self.x < g.L - 25:
            self.dir = 1
        if self.x > g.R - g.W + 25:
            self.dir = -1
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
        if self.rel < lo:
            self.rel, self.dir = lo, 1
        if self.rel > hi:
            self.rel, self.dir = hi, -1
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

        if hasattr(self, "inspect_until") and now < self.inspect_until:
            self.fxk.add("inspect")

        if g.s["flee_mouse"] and self.act in ("idle", "walk", "sit") and now > self.flee_cooldown \
                and not g.napping:
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
        ch = g.ch_h

        if "inspect" in self.fxk:
            float_y = fy - ch * 0.45 + math.sin(t * 0.25) * 5
            cv.create_text(cx + 18, float_y, text="🔍", font=(FONT, 16), tags="fx")

            pulse_r = (t * 2) % 24 + 6
            alpha_color = "#4fc3f7" if pulse_r < 18 else "#b3e5fc"
            cv.create_oval(cx + 18 - pulse_r, float_y - pulse_r,
                           cx + 18 + pulse_r, float_y + pulse_r,
                           outline=alpha_color, width=2, tags="fx")

            for i in range(2):
                sa = t * 0.15 + i * math.pi
                sx_ = cx + 18 + math.cos(sa) * 16
                sy_ = float_y + math.sin(sa) * 12
                cv.create_text(sx_, sy_, text="✦", fill="#ffd54f", font=(FONT, 9), tags="fx")

        # 머리 위 정보 줄 (친밀도 / CPU·RAM / 집중·타이머)
        lines = []
        if g.s["show_inti"]:
            lines.append(("♥ %d" % g.inti, "#ff4081"))
        if self.idx == 0:
            lines += [(ln, "#37474f") for ln in g.hud_lines()]
        for i, (txt, col) in enumerate(lines):
            tid = cv.create_text(g.W // 2, g.H - g.ih - 10 - i * 15, text=txt, fill=col,
                                 font=(FONT, 9, "bold"), tags="fx")
            x1, y1, x2, y2 = cv.bbox(tid)
            rid = cv.create_rectangle(x1 - 5, y1 - 1, x2 + 5, y2 + 1, fill="white",
                                      outline="#cfd8dc", tags="fx")
            cv.tag_lower(rid, tid)

        if "tears" in self.fxk and abs(ang) < 1:
            for i, s in enumerate((-1, 1)):
                ex = cx + s * ch * 0.14
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
                cv.create_text(cx + math.cos(a) * 34, fy - ch * 0.33 + math.sin(a) * 9,
                               text="★", fill="#ffd23c", font=(FONT, 13), tags="fx")
        if "zzz" in self.fxk:
            for i in range(3):
                zy = fy - 10 - ((t * 0.7 + i * 14) % 42)
                cv.create_text(cx + 26 + i * 7, zy, text="z", fill="#5b6c8f", font=(FONT, 9 + i * 2, "bold"), tags="fx")
        if "cookie" in self.fxk:
            r = max(2, 10 * (1 - self.t / max(1, self.dur)))
            ky = fy + 0.14 * ch
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
        if not text and g.hungry() and g.s["notify_hungry"] and self.act in ("idle", "sit", "cry") \
                and not g.napping:
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


# ------------------------------------------------ 메인 컨트롤러 (Game)
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
        self.reminders = list(d.get("reminders", []))
        self.moods = list(d.get("moods", []))
        self.greet_date = d.get("greet_date", "")
        self.fortune_date = d.get("fortune_date", "")
        self.fortune_text = d.get("fortune_text", "")
        self.stats = d.get("stats", {})
        self.lock_var = tk.BooleanVar(value=self.s["locked"])
        self.safe_var = tk.BooleanVar(value=self.s["safe_mode"])
        self.sys_var = tk.BooleanVar(value=self.s["show_sys"])
        self.outfit_var = tk.StringVar(value=self.s["outfit"])

        self.ai_history = list(d.get("ai_history", []))
        self.ai_persona = str(d.get("ai_persona", self.s.get("ai_persona", "고양이")))

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

        self.outfit_name = self.resolve_outfit()
        self.photo_cur = make_outfit(self.photo_base, self.outfit_name)
        self.cache = {}
        self.set_size(self.s["size"])
        self.pets = []
        self.wins = {}
        self.ui_q = queue.Queue()
        self.acc, self.last, self.tm = 0.0, time.time(), 0.0
        self.bouquet_until = 0
        self.timer_end = 0
        self.timer_custom_msg = ""
        self.last_hour = -1
        self.last_min_check = -1
        self.last_hungry_note = 0
        self.still, self.lastp, self.mouse_moved = 0.0, (0, 0), 0
        self.napping = False
        self.dancing, self.dance_cool = False, 0
        self.circ = {}
        self.restore_win = None
        self.quick = None
        self.focus = {"phase": None, "end": 0, "cycle": 0, "total": 0}
        self.next_water = time.time() + self.s["water_min"] * 60
        self.sysinfo, self.sys_t = (None, None), 0

        self.last_fg_title = ""
        self.fg_context_cooldown = 0

        self.edge_glow = EdgeGlowWindow(r)
        self.alert_popup = CustomAlertPopup(r, on_close=self.on_alert_closed)

        for i in range(max(1, min(MAX_PETS, int(d.get("pets", 1))))):
            self.pets.append(Pet(self, i))

        self.apply_opacity()

        if WIN:
            self.start_global_hotkey()

        r.after(1500, self.greet)
        self.loop()

    # ------------------------------------------------ 이미지 / 의상
    def resolve_outfit(self):
        v = self.s.get("outfit", "auto")
        return scheduled_outfit() if v == "auto" else (v if v in OUTFITS else "none")

    def refresh_outfit(self, force=False):
        name = self.resolve_outfit()
        if force or name != self.outfit_name:
            self.outfit_name = name
            self.photo_cur = make_outfit(self.photo_base, name)
            self.apply_size()

    def on_outfit_changed(self):
        self.s["outfit"] = self.outfit_var.get()
        self.refresh_outfit(force=True)
        self.save()
        nm = OUTFITS.get(self.outfit_name, "")
        self.pets[0].say(f"{nm} 의상으로 갈아입었어요!" if self.outfit_name != "none" else "기본 모습으로 돌아왔어요", 3)
        self.pets[0].start("hop", n=1)

    def set_size(self, size):
        scale = int(size) / max(1, self.photo_base.height)
        self.ch_h = int(size)                         # 캐릭터 본체 높이 (소품 제외)
        self.ih = max(1, int(self.photo_cur.height * scale))
        self.iw = max(1, int(self.photo_cur.width * scale))
        self.W, self.H = self.iw + 50, self.ih + TOP
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
            im = self.photo_cur
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

    # ------------------------------------------------ 상태 / 저장
    def hungry(self):
        return self.s["hunger_min"] <= 0 or self.sat < 20

    def sfx(self):
        return "냥" if getattr(self, "ai_persona", "고양이") == "고양이" else "멍"

    def stat(self, key, n=1):
        today = time.strftime("%Y-%m-%d")
        if self.stats.get("date") != today:
            self.stats = {"date": today, "clicks": 0, "feeds": 0, "bubbles": 0, "acts": {}}
        self.stats[key] = self.stats.get(key, 0) + n

    def stat_act(self, act):
        if act in ("idle", "drag", "fall"):
            return
        self.stat("acts_total", 0)          # 날짜가 바뀌었으면 초기화
        acts = self.stats.setdefault("acts", {})
        acts[act] = acts.get(act, 0) + 1

    def summary_text(self):
        today = time.strftime("%Y-%m-%d")
        st = self.stats if self.stats.get("date") == today else {}
        acts = sorted(st.get("acts", {}).items(), key=lambda kv: -kv[1])[:3]
        names = dict((a, l) for l, a, _ in ACT_MENU)
        names.update({"walk": "걷기", "eat": "간식 먹기", "laugh": "웃기"})
        top = ", ".join(f"{names.get(a, a)} {n}회" for a, n in acts) or "아직 없어요"
        return (f"오늘 클릭 {st.get('clicks', 0)}번 · 간식 {st.get('feeds', 0)}번 · "
                f"말풍선 {st.get('bubbles', 0)}번\n가장 많이 한 동작: {top}")

    def save(self):
        self.s["locked"] = bool(self.lock_var.get())
        self.s["safe_mode"] = bool(self.safe_var.get())
        self.s["show_sys"] = bool(self.sys_var.get())
        try:
            with open(SAVE, "w", encoding="utf-8") as f:
                json.dump({
                    "s": self.s, "sat": self.sat, "inti": self.inti,
                    "mins": self.mins, "secrets": self.secrets,
                    "todos": self.todos, "memo": self.memo,
                    "pets": len(self.pets),
                    "ai_history": self.ai_history,
                    "ai_persona": getattr(self, "ai_persona", "고양이"),
                    "reminders": self.reminders, "moods": self.moods[-60:],
                    "greet_date": self.greet_date, "fortune_date": self.fortune_date,
                    "fortune_text": self.fortune_text, "stats": self.stats,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def sync_flags(self):
        self.s["locked"] = bool(self.lock_var.get())
        self.s["safe_mode"] = bool(self.safe_var.get())
        self.s["show_sys"] = bool(self.sys_var.get())
        if self.s["show_sys"]:
            self.sys_t = 0
        if self.s["safe_mode"]:
            for p in self.pets:
                if p.act in ("wall", "ceil", "perch"):
                    p.start("fall")
        self.save()

    def call_ui(self, fn):
        """다른 스레드에서 화면을 바꿀 때는 큐에 넣어 메인 스레드가 처리"""
        self.ui_q.put(fn)

    def next_milestone(self):
        for m in MILESTONES:
            if m > self.inti:
                return m
        return None

    def trigger_custom_alert(self, title, time_str, msg, snooze=None):
        self.alert_popup.show(time_str, msg, title=title, snooze=snooze)
        if self.s.get("glow_edge", True):
            self.edge_glow.show(self.s.get("glow_color", "피치·핑크·보라·하늘"), self.s.get("glow_width", "넓게"))
        self.beep(880, 200, 1320, 300)

    def beep(self, *seq):
        if WIN and self.s["sound"]:
            try:
                import winsound
                for i in range(0, len(seq), 2):
                    winsound.Beep(seq[i], seq[i + 1])
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
        self.stat("feeds")
        pet.say("냠냠! 간식 최고예요", 2.5)
        pet.start("eat")
        self.save()

    # ------------------------------------------------ 친구 관리
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

    def start_global_hotkey(self):
        """Ctrl + Shift + C 핫키 리스너"""
        def hotkey_worker():
            success = user32.RegisterHotKey(None, HOTKEY_PROOFREAD_ID, MOD_CONTROL | MOD_SHIFT, VK_C)
            if not success:
                return
            msg = ctypes.wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == 0x0312 and msg.wParam == HOTKEY_PROOFREAD_ID:
                    simulate_copy()
                    self.call_ui(lambda: self.check_report_spelling(self.pets[0]))
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        threading.Thread(target=hotkey_worker, daemon=True).start()

    def quit(self):
        if WIN:
            try:
                user32.UnregisterHotKey(None, HOTKEY_PROOFREAD_ID)
            except Exception:
                pass
        self.save()
        self.root.destroy()

    # ------------------------------------------------ 작업 창 감지
    def check_active_context(self, now):
        if not WIN or now < self.fg_context_cooldown:
            return
        self.fg_context_cooldown = now + 4.0

        title = get_foreground_window_title().lower()
        if not title or title == self.last_fg_title:
            return
        self.last_fg_title = title
        p = self.pets[0]
        c = self.sfx()

        if any(k in title for k in ["youtube", "netflix", "치지직", "chzzk", "twitch", "동영상", "영화"]):
            p.start("sit")
            p.say(f"쉿! 영상 같이 보자{c}~", 2.5)
            return
        if any(k in title for k in ["visual studio", "vscode", "pycharm", "intellij", "github", "cmd", "terminal"]):
            p.say(f"코딩 집중 모드! 버그 다 잡아라{c}!", 2.5)
            p.start("hop", n=1)
            return
        if any(k in title for k in ["word", "excel", "powerpoint", "한글", "hwp", "스프레드시트"]):
            p.say(f"열일 모드다{c}! 조금만 더 힘내!", 2.5)

    # ------------------------------------------------ 아침 인사 (OpenPets '아침과 저녁 루틴' 참고)
    def greet(self):
        today = time.strftime("%Y-%m-%d")
        if self.greet_date == today:
            return
        self.greet_date = today
        h = time.localtime().tm_hour
        c = self.sfx()
        hello = (f"좋은 아침이다{c}!" if h < 12 else f"오늘도 왔구나{c}!" if h < 18 else f"수고했어{c}, 저녁이야!")
        left = len([t for t in self.todos if not t["done"]])
        if left:
            hello += f"\n남은 할 일 {left}개"
        p = self.pets[0]
        p.say(hello, 6)
        p.start("hop", n=2)
        self.save()
        if self.s.get("mood_daily") and not any(m.get("d") == today for m in self.moods):
            self.root.after(7000, lambda: self.open_mood(p))

    # ------------------------------------------------ 집중 친구 (포모도로)
    def focus_phase(self):
        return self.focus["phase"]

    def start_focus(self):
        s = self.s
        now = time.time()
        self.focus = {"phase": "focus", "end": now + s["focus_min"] * 60, "cycle": 1,
                      "total": max(1, int(s["focus_cycles"]))}
        p = self.pets[0]
        p.say(f"집중 시작! {s['focus_min']}분 같이 하자{self.sfx()}", 4)
        for q in self.pets:
            q.start("sit")

    def stop_focus(self):
        self.focus = {"phase": None, "end": 0, "cycle": 0, "total": 0}
        self.pets[0].say("집중 모드를 껐어요", 2.5)

    def focus_tick(self, now):
        f = self.focus
        if not f["phase"] or now < f["end"]:
            return
        s, c = self.s, self.sfx()
        if f["phase"] == "focus":
            if f["cycle"] >= f["total"]:
                self.focus = {"phase": None, "end": 0, "cycle": 0, "total": 0}
                self.trigger_custom_alert("집중 완료", "수고했어!", f"{f['total']}번의 집중을 모두 끝냈어요.\n정말 대단해요!")
                for q in self.pets:
                    q.start("dance")
                return
            f["phase"], f["end"] = "break", now + s["break_min"] * 60
            self.pets[0].say(f"{f['cycle']}번째 집중 끝! {s['break_min']}분 쉬자{c}", 5)
            for q in self.pets:
                q.start("hop", n=3)
            self.beep(880, 200, 1100, 250)
        else:
            f["cycle"] += 1
            f["phase"], f["end"] = "focus", now + s["focus_min"] * 60
            self.pets[0].say(f"다시 집중! ({f['cycle']}/{f['total']})", 4)
            for q in self.pets:
                q.start("sit")
            self.beep(660, 200)

    def hud_lines(self):
        out = []
        cpu, ram = self.sysinfo
        if self.s["show_sys"] and ram is not None:
            out.append(f"CPU {cpu if cpu is not None else '-'}% · RAM {ram}%")
        f = self.focus
        if f["phase"]:
            left = max(0, int(f["end"] - time.time()))
            lab = "집중" if f["phase"] == "focus" else "휴식"
            out.append(f"{lab} {left // 60:02d}:{left % 60:02d} ({f['cycle']}/{f['total']})")
        if self.timer_end:
            left = max(0, int(self.timer_end - time.time()))
            out.append(f"타이머 {left // 60:02d}:{left % 60:02d}")
        return out

    # ------------------------------------------------ 빠른 알림 (리마인더)
    def add_reminder(self, text, minutes):
        self.reminders.append({"t": text, "at": time.time() + minutes * 60})
        self.reminders.sort(key=lambda r: r["at"])
        self.save()

    def reminder_tick(self, now):
        for r in list(self.reminders):
            if now >= r["at"]:
                self.reminders.remove(r)
                self.save()
                txt = r["t"]
                self.pets[0].say(txt, 8)
                self.pets[0].start("hop", n=3)
                self.trigger_custom_alert("빠른 알림", time.strftime("%H:%M"), txt,
                                          snooze=lambda t=txt: self.add_reminder(t, 5))

    # ------------------------------------------------ 포춘 쿠키 / 8볼 / 로컬 답변
    def fortune_cookie(self, pet=None):
        pet = pet or self.pets[0]
        today = time.strftime("%Y-%m-%d")
        first = self.fortune_date != today
        if first:
            self.fortune_date = today
            self.fortune_text = random.choice(FORTUNES)
            self.save()
            pet.start("eat")
        self.alert_popup.show("포춘 쿠키", self.fortune_text, title="오늘의 쪽지")
        pet.say("오늘의 쪽지를 열었어요!" if first else "오늘 쪽지는 이미 열어봤어요", 3)

    def local_answer(self, q):
        """인터넷 없이 답할 수 있는 질문 (AI 호출 전에 먼저 확인)"""
        t = q.replace(" ", "").lower()
        lt = time.localtime()
        if any(k in t for k in ("뭘할수", "무엇을할수", "도움말", "기능")):
            return HELP_TEXT
        if any(k in t for k in ("시스템", "cpu", "램", "ram", "메모리상태")):
            sys_stats()
            time.sleep(0.25)                # CPU는 두 번 재서 비교해야 해요
            cpu, ram = sys_stats()
            return f"CPU {cpu if cpu is not None else '-'}% · RAM {ram if ram is not None else '-'}% 사용 중이에요."
        if "활동" in t and "요약" in t:
            return self.summary_text()
        if any(k in t for k in ("몇시", "지금시간", "현재시간")):
            return f"지금은 {lt.tm_hour}시 {lt.tm_min}분이에요."
        if any(k in t for k in ("며칠", "날짜", "무슨요일", "오늘날짜")):
            wd = "월화수목금토일"[lt.tm_wday]
            return f"오늘은 {lt.tm_year}년 {lt.tm_mon}월 {lt.tm_mday}일 {wd}요일이에요."
        if "할일" in t:
            left = [x["t"] for x in self.todos if not x["done"]]
            return ("남은 할 일: " + ", ".join(left[:8])) if left else "남은 할 일이 없어요!"
        return None

    # ------------------------------------------------ 루프
    def loop(self):
        now = time.time()
        dt = min(1.0, now - self.last)
        self.last = now
        self.tm += dt
        s = self.s

        while True:                     # 다른 스레드가 맡긴 화면 작업 처리
            try:
                fn = self.ui_q.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                import traceback
                traceback.print_exc()

        self.check_active_context(now)

        if s["auto_hide_fullscreen"]:
            if is_fullscreen_app_active():
                for p in self.pets:
                    if p.win.winfo_viewable():
                        p.win.withdraw()
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

        if lt.tm_min != self.last_min_check:
            self.last_min_check = lt.tm_min
            if s["outfit"] == "auto":
                self.refresh_outfit()

            if lt.tm_min == 0 and lt.tm_hour != self.last_hour:
                self.last_hour = lt.tm_hour
                mute = s["work_hour_mute"] and (lt.tm_wday < 5) and (s["work_mute_start"] <= lt.tm_hour <= s["work_mute_end"])
                if not mute:
                    ampm = "오전" if lt.tm_hour < 12 else "오후"
                    disp_h = lt.tm_hour if lt.tm_hour <= 12 else lt.tm_hour - 12
                    sub_text = f"{ampm} {disp_h}시야!"
                    if s.get("notify_hour_popup", True):
                        self.trigger_custom_alert("정각 알림", f"{lt.tm_hour:02d}:00", sub_text)
                    elif s.get("notify_hour", True):
                        self.pets[0].say(f"{lt.tm_hour}시 정각이에요!", 4)

            if s.get("notify_lunch", True) and cur_hm == s.get("lunch_time", "12:00"):
                self.trigger_custom_alert("점심 알림", cur_hm, s.get("lunch_msg", "점심 먹으러 가자!"))

            if s.get("notify_leave", True) and cur_hm == s.get("leave_time", "18:00"):
                self.trigger_custom_alert("퇴근 알림", cur_hm, s.get("leave_msg", "퇴근이다! 오늘도 수고했어"))

        if self.hungry() and s["notify_hungry"] and now - self.last_hungry_note > 300 and s["hunger_min"] > 0:
            self.last_hungry_note = now
            self.pets[0].say("배고파요… 간식 주세요", 4)

        if s["water_on"] and now >= self.next_water:
            self.next_water = now + max(5, s["water_min"]) * 60
            self.pets[0].say(f"물 마실 시간이다{self.sfx()}! 한 모금 해요", 6)
            for p in self.pets:
                p.start("hop", n=2)
            self.beep(1000, 150)

        if self.timer_end and now >= self.timer_end:
            self.timer_end = 0
            alert_msg = self.timer_custom_msg or "⏰ 타이머 끝났어요!"
            self.pets[0].say(alert_msg, 5)
            for p in self.pets:
                p.start("hop", n=3)
            self.beep(880, 300, 1175, 400)

        if s["show_sys"] and now - self.sys_t > 2:
            self.sys_t = now
            self.sysinfo = sys_stats()

        self.focus_tick(now)
        self.reminder_tick(now)
        self.track_mouse(now, dt)
        self.mouse_reactions(now, dt)
        for p in list(self.pets):
            p.update()
        self.root.after(33, self.loop)

    def track_mouse(self, now, dt):
        """마우스 움직임 추적 + 낮잠 (입력이 없으면 잠들고, 움직이면 깨요)"""
        s = self.s
        px, py = self.root.winfo_pointerxy()
        moved = abs(px - self.lastp[0]) + abs(py - self.lastp[1])
        self.lastp = (px, py)
        self.mouse_moved = moved
        if moved < 3:
            self.still += dt
        else:
            self.still = 0
        if s.get("nap_on", True) and not self.napping and self.still >= s["idle_nap_min"] * 60:
            self.napping = True
            for p in self.pets:
                p.start("sit")
                p.dur = 10 ** 9
            self.pets[0].say("zzz... 졸려요", 3)
        if self.napping and moved > 3:
            self.napping = False
            for p in self.pets:
                p.start("hop", n=1)
            self.pets[0].say("앗, 깼다!", 2)

    def mouse_reactions(self, now, dt):
        s = self.s
        if not s["hidden_reactions"] or self.napping:
            return
        px, py = self.lastp
        moved = self.mouse_moved
        if moved >= 3 and self.dancing and moved > 20:
            self.dancing = False
            for p in self.pets:
                if p.act == "dance":
                    p.start("idle")

        if len(self.pets) >= 2 and self.still >= 4 and not self.dancing and now > self.dance_cool:
            self.dancing = True
            self.dance_cool = now + 30
            for p in self.pets:
                if p.act in ("walk", "idle", "sit", "hop"):
                    p.start("dance")
            self.found("dance", self.pets[0])

        if self.dancing and not any(p.act == "dance" for p in self.pets):
            self.dancing = False

        for p in self.pets:
            hx = p.x + self.W / 2
            hy = p.y + self.H - self.ch_h * 0.64
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

    # ------------------------------------------------ AI 호출 (채팅창 / 빠른 질문 바 공용)
    def apply_tool_tags(self, text, pet):
        """답변 속 [ACTION:..] / [TOOL:{..}] 를 실행하고, 화면에 보일 글만 돌려줘요"""
        clean = text
        notes = []
        for act in re.findall(r"\[ACTION:\s*([a-zA-Z0-9_]+)\]", clean):
            clean = clean.replace(f"[ACTION: {act}]", "").replace(f"[ACTION:{act}]", "")
            if act in ("hop", "dance", "spin", "dizzy", "slide", "sit"):
                pet.start(act)
        for tm in re.findall(r"\[TOOL:\s*(\{.*?\})\]", clean, re.DOTALL):
            clean = clean.replace(f"[TOOL: {tm}]", "").replace(f"[TOOL:{tm}]", "")
            try:
                tool = json.loads(tm)
                action = tool.get("action")
                if action == "timer":
                    mins = max(1, int(tool.get("minutes", 5)))
                    msg = tool.get("msg", "⏰ 타이머가 끝났어요!")
                    self.timer_end = time.time() + mins * 60
                    self.timer_custom_msg = msg
                    notes.append(f"🔔 {mins}분 타이머가 설정되었습니다. ('{msg}')")
                elif action == "todo":
                    todo_text = tool.get("text", "").strip()
                    if todo_text:
                        self.todos.append({"t": todo_text, "done": False})
                        self.save()
                        notes.append(f"📝 할 일 목록에 추가되었습니다: '{todo_text}'")
            except Exception:
                pass
        return clean.strip(), notes

    def ai_ask(self, query, pet, on_ok, on_err):
        provider = self.s.get("ai_provider", "Gemini")
        persona = self.ai_persona
        self.ai_history.append({"role": "user", "parts": query})
        if len(self.ai_history) > 10:
            self.ai_history = self.ai_history[-10:]
        self.save()
        system_text = PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["고양이"])
        hist = list(self.ai_history)
        key = self.s.get("ai_api_key", "")
        gmodel = self.s.get("gemini_model", "")
        omodel = self.s.get("ollama_model", "llama3.2")

        def worker():
            try:
                if provider == "Ollama":
                    msgs = [{"role": "system", "content": system_text}]
                    for it in hist:
                        msgs.append({"role": "user" if it["role"] == "user" else "assistant",
                                     "content": it["parts"]})
                    payload = {"model": omodel or "llama3.2", "messages": msgs, "stream": False}
                    req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                                 data=json.dumps(payload).encode("utf-8"),
                                                 headers={"Content-Type": "application/json"}, method="POST")
                    # 내 컴퓨터 안의 주소라서 기관 프록시를 거치지 않게 해요
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    try:
                        with opener.open(req, timeout=60) as r:
                            ans = json.loads(r.read().decode("utf-8"))["message"]["content"]
                    except urllib.error.URLError as e:
                        raise Exception(f"Ollama에 연결할 수 없어요 ({e.reason}). Ollama를 먼저 실행했는지 확인하세요.")
                else:
                    contents = [{"role": "user" if it["role"] == "user" else "model",
                                 "parts": [{"text": it["parts"]}]} for it in hist]
                    ans = query_gemini_api(key, system_text, contents, preferred=gmodel)
                self.call_ui(lambda a=ans: _ok(a))
            except Exception as ex:
                msg = str(ex)
                self.call_ui(lambda m=msg: _err(m))

        def _ok(raw):
            clean, notes = self.apply_tool_tags(raw, pet)
            self.ai_history.append({"role": "model", "parts": clean})
            self.save()
            on_ok(clean, notes)

        def _err(msg):
            if self.ai_history and self.ai_history[-1]["role"] == "user":
                self.ai_history.pop()
                self.save()
            on_err(msg)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------ 빠른 질문 바 (OpenPets '컴팩트 채팅 바' 참고)
    def open_quick_bar(self, pet=None):
        pet = pet or self.pets[0]
        if self.quick is not None:
            try:
                self.quick.destroy()
            except Exception:
                pass
            self.quick = None
            return
        w = self.quick = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        x = int(max(self.L, min(self.R - 360, pet.x + self.W / 2 - 180)))
        y = int(pet.y - 6)
        if y < self.T + 4:
            y = int(pet.y + self.H - 10)
        w.geometry(f"360x36+{x}+{y}")
        w.config(bg="#ffb300")
        ent = tk.Entry(w, font=(FONT, 10), relief="flat")
        ent.pack(fill="both", expand=True, padx=2, pady=2)
        ent.focus_force()

        def close(_=None):
            if self.quick is not None:
                try:
                    self.quick.destroy()
                except Exception:
                    pass
                self.quick = None

        def send(_=None):
            q = ent.get().strip()
            close()
            if q:
                self.ask_quick(q, pet)

        ent.bind("<Return>", send)
        ent.bind("<Escape>", close)

    def ask_quick(self, q, pet):
        local = self.local_answer(q)
        if local:
            pet.say(local.split("\n")[0][:60], 5)
            if "\n" in local:
                self.alert_popup.show("펫 답변", local, title="알림")
            return
        c = self.sfx()
        pet.say(f"생각하는 중이다{c}... 🐾", 20)

        def ok(text, notes):
            pet.say((text.strip().split("\n")[0])[:60], 6)
            if len(text) > 40 or notes:
                self.alert_popup.show("펫 답변", text + ("\n\n" + "\n".join(notes) if notes else ""), title="알림")
            pet.start("hop", n=1)

        def err(m):
            pet.say("AI 연결이 안 돼요… 8볼은 어때요?", 4)
            self.alert_popup.show("연결 실패", m, title="AI 오류")

        self.ai_ask(q, pet, ok, err)

    # ------------------------------------------------ 공문서 검수 (온라인 AI + 오프라인 사전)
    @staticmethod
    def _fix_particle(word, p):
        """바꾼 단어의 받침에 맞게 조사(은/는, 이/가, 을/를, 과/와)를 맞춰요"""
        if not p:
            return ""
        last = word[-1]
        has = "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 != 0
        pairs = {"은": ("은", "는"), "는": ("은", "는"), "이": ("이", "가"), "가": ("이", "가"),
                 "을": ("을", "를"), "를": ("을", "를"), "과": ("과", "와"), "와": ("과", "와")}
        return pairs[p][0 if has else 1]

    def local_proofread(self, text):
        hits = []
        out = text
        for bad in sorted(PUREWORD, key=len, reverse=True):
            good = PUREWORD[bad]
            pat = re.compile(r"(?<![가-힣])" + re.escape(bad) + r"([은는이가을를과와])?(?=[^가-힣]|$|[의에도로만])")
            out, n = pat.subn(lambda m, g=good: g + self._fix_particle(g, m.group(1)), out)
            if n:
                hits.append((bad, good, n))
        c = self.sfx()
        total = sum(n for _, _, n in hits)
        head = f"[오프라인 사전 검수] 순화할 표현 {total}곳을 찾았{c}!" if total else f"[오프라인 사전 검수] 걸린 표현이 없{c}!"
        lines = "\n".join(f"- {b} → {g} ({n}곳)" for b, g, n in hits) or "- 해당 없음"
        return (f"{head}\n### 1. 오탈자 및 맞춤법 교정\n- 맞춤법 검사는 AI에 연결되어야 해요 (오프라인에서는 순화어 사전만 확인)\n"
                f"### 2. 행정 순화어 교정 내역\n{lines}\n### 3. 공문서 최종 완성본\n{out}")

    def check_report_spelling(self, pet=None):
        target_pet = pet or self.pets[0]
        try:
            copied_text = self.root.clipboard_get().strip()
        except Exception:
            copied_text = ""

        c = self.sfx()
        if not copied_text:
            target_pet.say(f"복사된 글이 없다{c}! 글을 드래그 후 시도해줘!", secs=3.0)
            return

        target_pet.say(f"공문서·보고서 정독 중이다{c}... 돋보기 장착! 🔍", secs=4.0)
        target_pet.inspect_until = time.time() + 20.0
        target_pet.start("idle")

        w = self.dialog("proofread", "📄 공문서·보고서 표준 순화 및 맞춤법 교정", 580, 620)
        if w is None:
            return
        f = (FONT, 10)

        tk.Label(w, text="📌 행정안전부 공문서 순화 및 오탈자 교정 결과", font=(FONT, 11, "bold"), bg="#fffaf7").pack(anchor="w", padx=16, pady=(12, 4))
        txt_res = tk.Text(w, font=f, bg="#ffffff", wrap="word", padx=10, pady=10)
        txt_res.pack(fill="both", expand=True, padx=16, pady=6)
        txt_res.insert("1.0", "AI가 행정안전부 공문서 순화 규정에 맞추어 검토 중입니다...\n- 맞춤법/띄어쓰기/오탈자\n- 일본어투 표현 및 불필요한 한자어\n- 권위적·관행적 행정 표현")
        txt_res.config(state="disabled")

        btn_bar = tk.Frame(w, bg="#fffaf7")
        btn_bar.pack(fill="x", padx=16, pady=(4, 12))

        def copy_result_to_clipboard():
            raw_content = txt_res.get("1.0", "end-1c").strip()
            if "### 3. 공문서 최종 완성본" in raw_content:
                clean_res = raw_content.split("### 3. 공문서 최종 완성본")[-1].strip()
            else:
                clean_res = raw_content
            self.root.clipboard_clear()
            self.root.clipboard_append(clean_res)
            target_pet.say(f"수정 완성본을 복사했다{c}! 붙여넣기(Ctrl+V)해줘!", secs=2.5)

        tk.Button(btn_bar, text="📋 수정 완성본 바로 복사", font=f, bg="#e9ecef", command=copy_result_to_clipboard).pack(side="left")
        tk.Button(btn_bar, text="닫기", font=f, width=6, command=w.destroy).pack(side="right")

        def show(result, first_line=None):
            if not w.winfo_exists():
                return
            target_pet.inspect_until = 0
            txt_res.config(state="normal")
            txt_res.delete("1.0", "end")
            txt_res.insert("1.0", result)
            txt_res.config(state="disabled")
            target_pet.say((first_line or result.strip().split("\n")[0])[:30], secs=4.5)

        def worker():
            try:
                api_key = self.s.get("ai_api_key", os.environ.get("GEMINI_API_KEY", "")).strip()
                if not api_key:
                    raise ValueError("API Key가 비어있어요.")
                system_prompt = (
                    "너는 대한민국 행정안전부의 '공문서 작성 기술 및 공공언어 순화 규정'을 숙지한 수석 행정 에디터 펫 비서야.\n"
                    "사용자가 작성한 문서를 아래 3원칙에 따라 철저히 교정해줘:\n\n"
                    "1. [맞춤법 및 문맥]: 오탈자, 띄어쓰기, 주어-서술어 불일치 교정\n"
                    "2. [일본어투 순화]: 시달->알림, 납기->납부기한, 잔업->시간외근무, 가계약->임시계약\n"
                    "3. [관행 행정어 순화]: 당해->해당, 익일->다음날, 차질없이->문제없이, 요망됨->바랍니다\n\n"
                    "출력 형식 (반드시 준수):\n"
                    "첫 줄: 오타 및 순화어 발견 개수와 총평을 펫 말투(~냥 또는 ~멍)로 25자 이내 작성\n"
                    "### 1. 오탈자 및 맞춤법 교정\n- 내용\n"
                    "### 2. 행정 순화어 교정 내역\n- 내용\n"
                    "### 3. 공문서 최종 완성본\n(매끄럽게 완성된 본문 전문)"
                )
                contents = [{"role": "user", "parts": [{"text": f"다음 문서를 행안부 공문서 규정에 맞게 검수해줘:\n\n{copied_text}"}]}]
                ans = query_gemini_api(api_key, system_prompt, contents, preferred=self.s.get("gemini_model", ""))
                self.call_ui(lambda: (show(ans), target_pet.start("hop", n=2)))
            except Exception as e:
                err = str(e)
                fallback = self.local_proofread(copied_text)
                msg = f"※ AI 검수를 쓸 수 없어서 오프라인 사전으로 대신 확인했어요.\n(이유: {err})\n\n{fallback}"
                self.call_ui(lambda: show(msg, f"오프라인 사전으로 확인했{c}!"))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------ AI 채팅창
    def open_ai_chat(self, pet=None):
        w = self.dialog("ai_chat", "✨ 펫 AI 에이전트", 540, 640)
        if w is None:
            return
        f = (FONT, 10)
        target_pet = pet or self.pets[0]

        top_f = tk.Frame(w, bg="#fffaf7")
        top_f.pack(fill="x", padx=12, pady=(10, 2))

        tk.Label(top_f, text="엔진:", font=f, bg="#fffaf7").pack(side="left")
        ai_provider = tk.StringVar(value=self.s.get("ai_provider", "Gemini"))
        cb_engine = ttk.Combobox(top_f, textvariable=ai_provider, values=["Gemini", "Ollama"], width=7, state="readonly")
        cb_engine.pack(side="left", padx=2)

        tk.Label(top_f, text="성격:", font=f, bg="#fffaf7").pack(side="left", padx=(6, 2))
        persona_var = tk.StringVar(value=getattr(self, "ai_persona", "고양이"))
        cb_persona = ttk.Combobox(top_f, textvariable=persona_var, values=["고양이", "강아지"], width=6, state="readonly")
        cb_persona.pack(side="left", padx=2)

        lbl_dynamic = tk.Label(top_f, text="Key:", font=f, bg="#fffaf7")
        lbl_dynamic.pack(side="left", padx=(6, 2))
        ent_dynamic = tk.Entry(top_f, font=f)
        ent_dynamic.pack(side="left", fill="x", expand=True)

        row2 = tk.Frame(w, bg="#fffaf7")
        row2.pack(fill="x", padx=12, pady=(0, 4))
        lbl_model = tk.Label(row2, text="Gemini 모델(비우면 자동):", font=(FONT, 9), bg="#fffaf7")
        lbl_model.pack(side="left")
        ent_model = tk.Entry(row2, font=(FONT, 9), width=22)
        ent_model.pack(side="left", padx=4)
        ent_model.insert(0, self.s.get("gemini_model", ""))

        txt_log = tk.Text(w, font=f, bg="#ffffff", wrap="word", state="disabled", padx=8, pady=8)
        txt_log.pack(fill="both", expand=True, padx=12, pady=6)

        def append_log(sender, text):
            txt_log.config(state="normal")
            txt_log.insert("end", f"[{sender}]\n{text}\n\n")
            txt_log.see("end")
            txt_log.config(state="disabled")

        def update_ui_state(e=None):
            eng = ai_provider.get()
            self.s["ai_provider"] = eng
            self.ai_persona = persona_var.get()
            ent_dynamic.delete(0, "end")
            if eng == "Ollama":
                lbl_dynamic.config(text="모델:")
                ent_dynamic.config(show="")
                ent_dynamic.insert(0, self.s.get("ollama_model", "llama3.2"))
                lbl_model.pack_forget()
                ent_model.pack_forget()
            else:
                lbl_dynamic.config(text="Key:")
                ent_dynamic.config(show="*")
                ent_dynamic.insert(0, self.s.get("ai_api_key", ""))
                lbl_model.pack(side="left")
                ent_model.pack(side="left", padx=4)
            self.save()

        cb_engine.bind("<<ComboboxSelected>>", update_ui_state)
        cb_persona.bind("<<ComboboxSelected>>", update_ui_state)
        update_ui_state()

        for item in self.ai_history:
            append_log("나" if item["role"] == "user" else f"{self.ai_persona} 친구", item["parts"])

        def store_settings():
            val = ent_dynamic.get().strip()
            if ai_provider.get() == "Ollama":
                self.s["ollama_model"] = val
            else:
                self.s["ai_api_key"] = val
                self.s["gemini_model"] = ent_model.get().strip()
            self.ai_persona = persona_var.get()
            self.save()

        def test_connection():
            store_settings()
            if ai_provider.get() == "Ollama":
                append_log("연결 테스트", "Ollama는 질문을 보내서 확인해 보세요.")
                return
            key = self.s.get("ai_api_key", "")
            append_log("연결 테스트", "구글 서버에서 사용 가능한 모델 목록을 가져오는 중...")

            def work():
                try:
                    names = discover_gemini_models(key)
                    msg = ("연결 성공! 사용 가능한 모델: " + ", ".join(names[:6])) if names else \
                          "연결은 됐지만 쓸 수 있는 Gemini 모델이 목록에 없어요. 키 권한을 확인하세요."
                except urllib.error.HTTPError as e:
                    m, is_json = _http_err_text(e)
                    msg = f"서버 응답 [{e.code}] {m}" + ("" if is_json else "\n(구글이 아닌 중간 장비의 응답처럼 보여요 → 기관 보안팀에 generativelanguage.googleapis.com 허용 요청)")
                except urllib.error.URLError as e:
                    msg = f"연결 실패: {e.reason}\n(기관 방화벽/프록시가 막고 있을 수 있어요)"
                except Exception as e:
                    msg = f"오류: {e}"
                self.call_ui(lambda: w.winfo_exists() and append_log("연결 테스트", msg))

            threading.Thread(target=work, daemon=True).start()

        bottom_f = tk.Frame(w, bg="#fffaf7")
        bottom_f.pack(fill="x", padx=12, pady=(2, 12))

        chips = tk.Frame(w, bg="#fffaf7")
        chips.pack(fill="x", padx=12, before=bottom_f)

        query_ent = tk.Entry(bottom_f, font=f)
        query_ent.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def clear_history():
            self.ai_history.clear()
            self.save()
            txt_log.config(state="normal")
            txt_log.delete("1.0", "end")
            txt_log.config(state="disabled")
            target_pet.say(f"기억을 지웠다{self.sfx()}! 새 이야기하자!", secs=2.0)

        def run_query(preset=None):
            query = (preset or query_ent.get()).strip()
            if not query:
                return
            store_settings()
            append_log("나", query)
            query_ent.delete(0, "end")
            local = self.local_answer(query)
            if local:                       # 인터넷 없이 답할 수 있는 질문
                append_log(f"{self.ai_persona} 펫", local)
                target_pet.say(local.split("\n")[0][:30], 4)
                return
            append_log("상태", "AI 응답을 기다리는 중... (최대 30초)")
            target_pet.say(f"생각하는 중이다{self.sfx()}... 🐾", secs=20.0)

            def ok(text, notes):
                for n in notes:
                    append_log("시스템", n)
                if w.winfo_exists():
                    append_log(f"{self.ai_persona} 펫", text)
                target_pet.say(text.strip().split("\n")[0][:30], secs=4.0)
                if target_pet.act not in ("dance", "spin"):
                    target_pet.start("hop", n=1)

            def err(m):
                if w.winfo_exists():
                    append_log("오류 안내", m + "\n\n(위의 '연결 테스트' 버튼으로 원인을 확인할 수 있어요)")
                target_pet.say(f"말문이 막혔다{self.sfx()}...", secs=2.5)

            self.ai_ask(query, target_pet, ok, err)

        for label in ("뭘 할 수 있어?", "시스템 상태 확인", "오늘 활동 요약"):
            tk.Button(chips, text=label, font=(FONT, 9), bg="#fff3d6", relief="flat",
                      command=lambda t=label: run_query(t)).pack(side="left", padx=(0, 4))
        tk.Button(chips, text="연결 테스트", font=(FONT, 9), bg="#e3f2fd", relief="flat",
                  command=test_connection).pack(side="right")

        query_ent.bind("<Return>", lambda e: run_query())
        tk.Button(bottom_f, text="대화 리셋", font=(FONT, 9), command=clear_history).pack(side="right", padx=(4, 0))
        tk.Button(bottom_f, text="전송", font=f, bg="#e9ecef", command=run_query).pack(side="right")

    # ------------------------------------------------ 8볼 / 기분 체크인
    def open_eight_ball(self, pet=None):
        pet = pet or self.pets[0]
        w = self.dialog("eight", "🎱 매직 8볼", 380, 300)
        if w is None:
            return
        tk.Label(w, text="마음속으로 질문하고, 예/아니오로 물어보세요", font=(FONT, 10), bg="#fffaf7").pack(pady=(18, 6))
        ent = tk.Entry(w, font=(FONT, 11))
        ent.pack(fill="x", padx=24)
        ans = tk.Label(w, text="?", font=(FONT, 16, "bold"), bg="#fffaf7", fg="#4a3f8f", wraplength=320, height=3)
        ans.pack(pady=14)

        def ask(_=None):
            a = random.choice(EIGHT_BALL)
            ans.config(text=a)
            pet.say(a, 4)
            pet.start("hop", n=1)

        ent.bind("<Return>", ask)
        tk.Button(w, text="물어보기", font=(FONT, 10), command=ask).pack()

    MOODS = [("아주 좋아요", 4), ("좋아요", 3), ("보통이에요", 2), ("별로예요", 1), ("힘들어요", 0)]

    def open_mood(self, pet=None):
        pet = pet or self.pets[0]
        w = self.dialog("mood", "기분 체크인", 340, 340)
        if w is None:
            return
        tk.Label(w, text="지금 기분은 어때요?", font=(FONT, 13, "bold"), bg="#fffaf7").pack(pady=(18, 10))

        def pick(val):
            today = time.strftime("%Y-%m-%d")
            self.moods = [m for m in self.moods if m.get("d") != today] + [{"d": today, "m": val}]
            self.save()
            w.destroy()
            c = self.sfx()
            if val >= 4:
                pet.start("laugh")
                pet.say(f"나도 신난다{c}!", 4)
            elif val == 3:
                pet.start("hop", n=2)
                pet.say(f"좋은 하루다{c}~", 4)
            elif val == 2:
                pet.say(f"오늘도 같이 천천히 가자{c}", 4)
            elif val == 1:
                pet.start("sit")
                pet.say(f"토닥토닥… 간식 먹을래{c}?", 5)
            else:
                pet.start("sit")
                pet.say(f"많이 힘들었구나{c}. 잠깐 쉬어가자. 옆에 있을게", 7)

        for label, val in self.MOODS:
            tk.Button(w, text=label, font=(FONT, 11), width=16, command=lambda v=val: pick(v)).pack(pady=3)

    # ------------------------------------------------ 친구 기록 · 활동 요약
    def open_record(self):
        w = self.dialog("record", "친구 기록 · 활동 요약", 460, 700)
        if w is None:
            return
        f = (FONT, 10)
        big = tk.Label(w, font=(FONT, 16, "bold"), bg="#fffaf7")
        big.pack(anchor="w", padx=20, pady=(18, 4))
        info = tk.Label(w, font=f, bg="#fffaf7", justify="left")
        info.pack(anchor="w", padx=20)
        tk.Button(w, text="간식 주기", font=f, command=lambda: self.feed()).pack(anchor="w", padx=20, pady=8)

        tk.Label(w, text="오늘의 활동 요약", font=(FONT, 10, "bold"), bg="#fffaf7").pack(anchor="w", padx=20)
        summ = tk.Label(w, font=f, bg="#fffaf7", justify="left", wraplength=410)
        summ.pack(anchor="w", padx=20, pady=(2, 8))

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
            except Exception:
                pass
            self.s["cry_always"] = cv_.get()
            self.s["hidden_reactions"] = hr_.get()
            self.save()
            msg.config(text="저장했어요!")

        tk.Button(w, text="생활 설정 저장", font=f, command=apply).pack(anchor="w", padx=20, pady=8)
        msg = tk.Label(w, text="", font=(FONT, 9), bg="#fffaf7", fg="#2a7")
        msg.pack(anchor="w", padx=20)
        sec = tk.Label(w, font=f, bg="#fffaf7", justify="left", wraplength=410)
        sec.pack(anchor="w", padx=20, pady=(10, 0))
        mood = tk.Label(w, font=(FONT, 9), bg="#fffaf7", fg="#555", justify="left", wraplength=410)
        mood.pack(anchor="w", padx=20, pady=(8, 0))

        def refresh():
            if not w.winfo_exists():
                return
            big.config(text=f"♥ 친밀도 {self.inti}   ·   함께 {self.mins}분")
            nm = self.next_milestone()
            info.config(text=f"포만감 {int(self.sat)} / 100\n"
                             f"다음 꽃다발: {'친밀도 %d' % nm if nm else '모두 받았어요!'}\n"
                             f"지금 의상: {OUTFITS.get(self.outfit_name, '기본')}\n"
                             + ("지금 간식을 줄 수 있어요." if self.sat < 100 else "배가 불러요."))
            summ.config(text=self.summary_text())
            lines = [f"발견한 비밀 {len(self.secrets)} / {len(SECRETS)}"]
            for k, (nme, hint) in SECRETS.items():
                lines.append(f"  · {nme}: {hint}" if k in self.secrets else "  · ???")
            sec.config(text="\n".join(lines))
            names = dict((v, l) for l, v in self.MOODS)
            recent = [f"{m['d'][5:].replace('-', '/')} {names.get(m['m'], '')}" for m in self.moods[-7:]]
            mood.config(text="최근 기분: " + (" · ".join(recent) if recent else "아직 기록이 없어요"))
            w.after(1000, refresh)

        refresh()

    # ------------------------------------------------ 움직임 · 반응 설정
    def open_motion(self):
        w = self.dialog("motion", "움직임과 반응", 420, 700)
        if w is None:
            return
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
        v_size = tk.IntVar(value=s.get("size", 140))

        top_f = tk.Frame(w, bg="#fffaf7")
        top_f.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Label(top_f, text="친구가 어떻게 놀지 골라줘", font=(FONT, 9, "bold"), bg="#fffaf7").pack(anchor="w", pady=(0, 4))

        checks = [
            ("화면 양옆 벽 타기", v_wall),
            ("화면 천장 타기", v_ceil),
            ("열린 창 위에서 걷기 · 쉬기", v_win),
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

        f_op = tk.Frame(top_f, bg="#fffaf7")
        f_op.pack(anchor="w", pady=(8, 2))
        tk.Label(f_op, text="캐릭터 진하기", font=f, bg="#fffaf7").pack(side="left")
        ttk.Spinbox(f_op, from_=10, to=100, width=5, textvariable=v_op).pack(side="left", padx=6)
        tk.Label(f_op, text="% · 낮을수록 투명해요", font=(FONT, 8), fg="#777", bg="#fffaf7").pack(side="left")

        f_sz = tk.Frame(top_f, bg="#fffaf7")
        f_sz.pack(anchor="w", pady=2)
        tk.Label(f_sz, text="캐릭터 크기", font=f, bg="#fffaf7").pack(side="left")
        ttk.Spinbox(f_sz, from_=60, to=320, increment=10, width=5, textvariable=v_size).pack(side="left", padx=6)
        tk.Label(f_sz, text="픽셀", font=(FONT, 8), fg="#777", bg="#fffaf7").pack(side="left")

        tk.Label(top_f, text="속도 조절 · 숫자가 클수록 빨라져요", font=(FONT, 9, "bold"), bg="#fffaf7").pack(anchor="w", pady=(10, 2))

        for txt, var in (("걷기 · 기어오르기", v_spd_walk), ("헬리콥터 낙하", v_spd_spin), ("슬라이딩", v_spd_slide)):
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

        f_cr = tk.Frame(top_f, bg="#fffaf7")
        f_cr.pack(anchor="w", pady=(8, 12))
        tk.Label(f_cr, text="클릭했을 때 반응", font=f, bg="#fffaf7").pack(side="left", padx=(0, 6))
        ttk.Combobox(f_cr, textvariable=v_cr, values=["폴짝", "울기", "어질어질", "랜덤"], state="readonly", width=10).pack(side="left")

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
            old_size = s.get("size", 140)
            try:
                s["opacity"] = int(v_op.get())
                s["spd_walk"] = float(v_spd_walk.get())
                s["spd_spin"] = float(v_spd_spin.get())
                s["spd_slide"] = float(v_spd_slide.get())
                s["slide_delay"] = float(v_slide_d.get())
                s["size"] = max(60, min(320, int(v_size.get())))
            except Exception:
                pass
            s["click_reaction"] = v_cr.get()
            self.apply_opacity()
            if s["size"] != old_size:
                self.apply_size()
            self.sync_flags()
            w.destroy()

        tk.Button(btn_bar, text="취소", font=f, width=7, command=w.destroy).pack(side="right", padx=4)
        tk.Button(btn_bar, text="저장", font=f, width=7, bg="#e9ecef", command=save_motion_settings).pack(side="right", padx=4)

    # ------------------------------------------------ 알림 설정
    def open_notify(self):
        w = self.dialog("notify", "자동 시작 / 알림 설정", 470, 780)
        if w is None:
            return
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

        v_nap = tk.BooleanVar(value=s.get("nap_on", True))
        v_nap_m = tk.IntVar(value=s.get("idle_nap_min", 10))
        v_water = tk.BooleanVar(value=s["water_on"])
        v_water_m = tk.IntVar(value=s["water_min"])
        v_mood = tk.BooleanVar(value=s["mood_daily"])

        top_f = tk.Frame(w, bg="#fffaf7")
        top_f.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Checkbutton(top_f, text="정각 알림 (매시간 현재 시각 알려주기)", variable=v_hour,
                       font=(FONT, 9, "bold"), bg="#fffaf7").pack(anchor="w")
        tk.Checkbutton(top_f, text="Windows 로그인 시 자동으로 켜기", variable=v_auto,
                       font=f, bg="#fffaf7").pack(anchor="w", padx=16, pady=(4, 0))
        tk.Checkbutton(top_f, text="별도 정각 알림창 사용 (직접 닫을 때까지 유지)", variable=v_hour_pop,
                       font=f, bg="#fffaf7").pack(anchor="w", padx=16)

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

        f_prev = tk.Frame(top_f, bg="#fffaf7")
        f_prev.pack(fill="x", padx=20, pady=4)
        tk.Button(f_prev, text="정각창 미리보기", font=(FONT, 8),
                  command=lambda: self.trigger_custom_alert("정각 알림", "11:00", "오전 11시야!\n(미리보기)")).pack(side="right")

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

        f_l = tk.Frame(top_f, bg="#fffaf7")
        f_l.pack(fill="x", pady=(10, 2))
        tk.Checkbutton(f_l, text="점심 알림", variable=v_lunch, font=(FONT, 9, "bold"), bg="#fffaf7").pack(side="left")
        tk.Label(f_l, text="시간", font=f, bg="#fffaf7").pack(side="left", padx=(10, 2))
        tk.Entry(f_l, textvariable=v_lunch_t, width=8, font=f).pack(side="left")

        f_lm = tk.Frame(top_f, bg="#fffaf7")
        f_lm.pack(fill="x", padx=24, pady=2)
        tk.Label(f_lm, text="문구", font=f, bg="#fffaf7").pack(side="left")
        tk.Entry(f_lm, textvariable=v_lunch_m, font=f).pack(side="left", fill="x", expand=True, padx=6)

        f_lv = tk.Frame(top_f, bg="#fffaf7")
        f_lv.pack(fill="x", pady=(10, 2))
        tk.Checkbutton(f_lv, text="퇴근 알림", variable=v_leave, font=(FONT, 9, "bold"), bg="#fffaf7").pack(side="left")
        tk.Label(f_lv, text="시간", font=f, bg="#fffaf7").pack(side="left", padx=(10, 2))
        tk.Entry(f_lv, textvariable=v_leave_t, width=8, font=f).pack(side="left")

        f_lvm = tk.Frame(top_f, bg="#fffaf7")
        f_lvm.pack(fill="x", padx=24, pady=2)
        tk.Label(f_lvm, text="문구", font=f, bg="#fffaf7").pack(side="left")
        tk.Entry(f_lvm, textvariable=v_leave_m, font=f).pack(side="left", fill="x", expand=True, padx=6)

        f_water = tk.Frame(top_f, bg="#fffaf7")
        f_water.pack(anchor="w", pady=(10, 2))
        tk.Checkbutton(f_water, text="물 마시기 알림", variable=v_water, font=(FONT, 9, "bold"), bg="#fffaf7").pack(side="left")
        ttk.Spinbox(f_water, from_=5, to=240, width=5, textvariable=v_water_m).pack(side="left", padx=6)
        tk.Label(f_water, text="분마다", font=f, bg="#fffaf7").pack(side="left")

        tk.Checkbutton(top_f, text="하루에 한 번 기분 체크인 물어보기 (아침 인사 후)", variable=v_mood,
                       font=f, bg="#fffaf7").pack(anchor="w", pady=(6, 0))

        f_nap = tk.Frame(top_f, bg="#fffaf7")
        f_nap.pack(anchor="w", pady=(8, 2))
        tk.Checkbutton(f_nap, text="낮잠", variable=v_nap, font=(FONT, 9, "bold"), bg="#fffaf7").pack(side="left")
        ttk.Spinbox(f_nap, from_=1, to=120, width=5, textvariable=v_nap_m).pack(side="left", padx=6)
        tk.Label(f_nap, text="분 동안 마우스를 안 쓰면 잠들어요", font=f, bg="#fffaf7").pack(side="left")

        tk.Label(top_f, text="시간은 12:00처럼 시:분으로 적어 주세요.", font=(FONT, 8), fg="#888", bg="#fffaf7").pack(anchor="w", pady=(4, 8))

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
                s["water_min"] = max(5, int(v_water_m.get()))
                s["idle_nap_min"] = max(1, int(v_nap_m.get()))
            except Exception:
                pass
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
            s["nap_on"] = v_nap.get()
            s["water_on"] = v_water.get()
            s["mood_daily"] = v_mood.get()
            self.next_water = time.time() + s["water_min"] * 60
            self.save()
            w.destroy()

        tk.Button(btn_bar, text="취소", font=f, width=6, command=w.destroy).pack(side="right", padx=3)
        tk.Button(btn_bar, text="저장", font=f, width=6, bg="#e9ecef", command=save_alert_settings).pack(side="right", padx=3)

    # ------------------------------------------------ 도우미 (할 일 · 메모 · 타이머 · 집중 · 빠른 알림)
    def open_helper(self):
        w = self.dialog("helper", "도우미 · 할 일 · 메모 · 타이머 · 집중", 460, 560)
        if w is None:
            return
        f = (FONT, 10)
        nb = ttk.Notebook(w)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # --- 할 일
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

        # --- 메모
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

        # --- 타이머
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
                self.timer_custom_msg = ""
            except Exception:
                pass

        def cancel_t():
            self.timer_end = 0

        b3 = tk.Frame(t3, bg="#fffaf7")
        b3.pack()
        tk.Button(b3, text="시작", font=f, command=start_t).pack(side="left", padx=4)
        tk.Button(b3, text="취소", font=f, command=cancel_t).pack(side="left", padx=4)
        tk.Label(t3, text="끝나면 친구가 폴짝 뛰면서 알려줘요.", font=(FONT, 9), bg="#fffaf7", fg="#666").pack(pady=14)

        # --- 집중 (포모도로)
        t4 = tk.Frame(nb, bg="#fffaf7")
        nb.add(t4, text="집중")
        tk.Label(t4, text="집중 친구 · 포모도로", font=(FONT, 12, "bold"), bg="#fffaf7").pack(pady=(18, 4))
        tk.Label(t4, text="집중하는 동안 친구가 조용히 곁에 있어주고,\n쉬는 시간에는 신나게 알려줘요.",
                 font=(FONT, 9), bg="#fffaf7", fg="#666").pack()
        fr = tk.Frame(t4, bg="#fffaf7")
        fr.pack(pady=14)
        v_fm = tk.IntVar(value=self.s["focus_min"])
        v_bm = tk.IntVar(value=self.s["break_min"])
        v_fc = tk.IntVar(value=self.s["focus_cycles"])
        for i, (lab, var, lo, hi, unit) in enumerate((("집중", v_fm, 1, 120, "분"), ("휴식", v_bm, 1, 60, "분"),
                                                       ("반복", v_fc, 1, 12, "회"))):
            tk.Label(fr, text=lab, font=f, bg="#fffaf7").grid(row=i, column=0, padx=6, pady=3, sticky="e")
            ttk.Spinbox(fr, from_=lo, to=hi, width=6, textvariable=var).grid(row=i, column=1)
            tk.Label(fr, text=unit, font=f, bg="#fffaf7").grid(row=i, column=2, padx=4)
        focus_lbl = tk.Label(t4, text="", font=(FONT, 20, "bold"), bg="#fffaf7")
        focus_lbl.pack(pady=8)

        def start_f():
            try:
                self.s["focus_min"] = max(1, int(v_fm.get()))
                self.s["break_min"] = max(1, int(v_bm.get()))
                self.s["focus_cycles"] = max(1, int(v_fc.get()))
            except Exception:
                pass
            self.save()
            self.start_focus()

        bf = tk.Frame(t4, bg="#fffaf7")
        bf.pack()
        tk.Button(bf, text="집중 시작", font=f, command=start_f).pack(side="left", padx=4)
        tk.Button(bf, text="그만하기", font=f, command=self.stop_focus).pack(side="left", padx=4)

        # --- 빠른 알림
        t5 = tk.Frame(nb, bg="#fffaf7")
        nb.add(t5, text="빠른 알림")
        r5 = tk.Frame(t5, bg="#fffaf7")
        r5.pack(fill="x", padx=10, pady=(12, 4))
        rent = tk.Entry(r5, font=f)
        rent.pack(side="left", fill="x", expand=True)
        rmin = tk.IntVar(value=10)
        ttk.Spinbox(r5, from_=1, to=1440, width=5, textvariable=rmin).pack(side="left", padx=4)
        tk.Label(r5, text="분 뒤", font=f, bg="#fffaf7").pack(side="left")
        rlb = tk.Listbox(t5, font=f, height=12, activestyle="none")
        rlb.pack(fill="both", expand=True, padx=10, pady=6)

        def rdraw():
            rlb.delete(0, "end")
            for r in self.reminders:
                left = max(0, int(r["at"] - time.time()))
                rlb.insert("end", f"{time.strftime('%H:%M', time.localtime(r['at']))}  ({left // 60}분 남음)  {r['t']}")

        def radd(*_):
            t = rent.get().strip()
            if t:
                try:
                    m = max(1, int(rmin.get()))
                except Exception:
                    m = 10
                self.add_reminder(t, m)
                rent.delete(0, "end")
                rdraw()

        def rdel():
            for i in reversed(rlb.curselection()):
                del self.reminders[i]
            self.save()
            rdraw()

        rent.bind("<Return>", radd)
        tk.Button(r5, text="추가", font=f, command=radd).pack(side="left", padx=6)
        tk.Button(t5, text="선택 삭제", font=f, command=rdel).pack(pady=(0, 6))
        tk.Label(t5, text="시간이 되면 알림창이 뜨고, '5분 미루기'를 누를 수 있어요.", font=(FONT, 9),
                 bg="#fffaf7", fg="#666").pack(pady=(0, 8))
        rdraw()

        def tick_t():
            if not w.winfo_exists():
                return
            if self.timer_end:
                left = max(0, int(self.timer_end - time.time()))
                remain.config(text=f"{left // 60:02d}:{left % 60:02d}")
            else:
                remain.config(text="--:--")
            fph = self.focus
            if fph["phase"]:
                left = max(0, int(fph["end"] - time.time()))
                lab = "집중" if fph["phase"] == "focus" else "휴식"
                focus_lbl.config(text=f"{lab} {left // 60:02d}:{left % 60:02d}  ({fph['cycle']}/{fph['total']})")
            else:
                focus_lbl.config(text="--:--")
            rdraw()
            w.after(1000, tick_t)

        tick_t()


if __name__ == "__main__":
    Game().root.mainloop()
