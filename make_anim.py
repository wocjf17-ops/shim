"""
AI가 만든 GIF / 영상 프레임을 펫용 '투명 배경 애니메이션'으로 바꿔주는 도구

사용법 (명령 프롬프트):
    python make_anim.py 입력 이름 [옵션]

  입력 : .gif / .webp / .apng 파일, 또는 프레임 이미지(png, jpg)가 들어있는 폴더
  이름 : 어떤 동작에 쓸지  → walk, idle, sit, sleep, hop, cry, laugh, eat, slide, dizzy,
                              spin, dance, roll, stretch, wall, ceil, chase ...
  결과 : anim/이름.webp  (이 폴더를 pet.py 옆에 두면 자동으로 쓰여요)

옵션:
  --chroma 00ff00   배경이 초록(또는 지정한 색) 단색일 때 그 색을 투명하게 (기본 허용오차 --tol 70)
  --keep-green      초록 번짐(그린스크린 잔여색) 제거를 끄기
  --rembg           배경이 복잡하면 AI로 배경 제거 (pip install rembg onnxruntime 필요, 첫 실행 때 모델 다운로드)
  --maxh 360        결과 높이 제한(픽셀)
  --fps 12          폴더 입력일 때 초당 프레임 수
  --every 2         프레임이 너무 많을 때 N장마다 1장만 사용

필요한 것:  pip install pillow
"""
import argparse, os, sys
from PIL import Image, ImageChops, ImageSequence


def load_frames(path, fps):
    frames, durs = [], []
    if os.path.isdir(path):
        for fn in sorted(os.listdir(path)):
            if fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                frames.append(Image.open(os.path.join(path, fn)).convert("RGBA"))
                durs.append(int(1000 / fps))
    else:
        im = Image.open(path)
        for fr in ImageSequence.Iterator(im):
            frames.append(fr.convert("RGBA"))
            durs.append(max(30, int(fr.info.get("duration", im.info.get("duration", 80)) or 80)))
    return frames, durs


def chroma_key(im, color, tol):
    rgb = im.convert("RGB")
    solid = Image.new("RGB", rgb.size, color)
    diff = ImageChops.difference(rgb, solid)
    r, g, b = diff.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)       # 색 차이가 가장 큰 채널
    soft = max(1, int(tol * 0.6))
    alpha = mx.point(lambda v: 0 if v < tol else (255 if v >= tol + soft else int((v - tol) * 255 / soft)))
    out = im.copy()
    out.putalpha(ImageChops.multiply(alpha, im.getchannel("A")))
    return out


def despill_green(im):
    """그린스크린 때문에 가장자리에 남는 초록빛을 제거 (초록값을 빨강/파랑 중 큰 값 이하로 제한)"""
    r, g, b, a = im.split()
    g2 = ImageChops.darker(g, ImageChops.lighter(r, b))
    return Image.merge("RGBA", (r, g2, b, a))


def main():
    ap = argparse.ArgumentParser(description="펫용 애니메이션 변환기")
    ap.add_argument("input")
    ap.add_argument("name")
    ap.add_argument("--chroma", help="투명하게 만들 배경색 (예: 00ff00)")
    ap.add_argument("--tol", type=int, default=70)
    ap.add_argument("--rembg", action="store_true")
    ap.add_argument("--keep-green", action="store_true")
    ap.add_argument("--maxh", type=int, default=360)
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--every", type=int, default=1)
    a = ap.parse_args()

    frames, durs = load_frames(a.input, a.fps)
    if not frames:
        sys.exit("프레임을 읽지 못했어요. 입력 경로를 확인하세요.")
    if a.every > 1:
        frames = frames[::a.every]
        durs = [d * a.every for d in durs[::a.every]]
    print(f"프레임 {len(frames)}장 불러옴")

    if a.rembg:
        try:
            from rembg import remove, new_session
        except ImportError:
            sys.exit("rembg 가 없어요:  pip install rembg onnxruntime")
        sess = new_session("u2net")
        frames = [remove(f, session=sess) for f in frames]
    elif a.chroma:
        c = a.chroma.lstrip("#")
        col = tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
        frames = [chroma_key(f, col, a.tol) for f in frames]
        if col[1] > col[0] and col[1] > col[2] and not a.keep_green:
            frames = [despill_green(f) for f in frames]

    boxes = [f.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox() for f in frames]
    boxes = [b for b in boxes if b]
    if not boxes:
        sys.exit("투명하지 않은 부분이 없어요. --chroma 색이나 --tol 값을 바꿔보세요.")
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    frames = [f.crop(box) for f in frames]
    if frames[0].height > a.maxh:
        s = a.maxh / frames[0].height
        frames = [f.resize((max(1, int(f.width * s)), a.maxh), Image.LANCZOS) for f in frames]

    os.makedirs("anim", exist_ok=True)
    out = os.path.join("anim", a.name.lower() + ".webp")
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durs, loop=0,
                   lossless=True, quality=90, method=4)
    print(f"저장 완료: {out}  ({frames[0].width}x{frames[0].height}, {len(frames)}프레임)")
    print("pet.py 를 다시 켜거나, 펫 우클릭 > 놀이·기분 > 애니메이션 다시 불러오기 를 누르세요.")


if __name__ == "__main__":
    main()
