import re, subprocess
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance, ImageFilter
from config import W, H, CATEGORIES, SCREENSHOT_CATS

# ---------- daily styles ----------
THEMES = [
    dict(name="Midnight Neon", bg="#0B0B12", fg="#F5F5F7", accent="#7CFF6B", muted="#8A8A99",
         title="Anton", body="SpaceMono", layout="fullbleed",
         grade=dict(contrast=1.15, color=1.1, warmth=-10, grain=8, vignette=0.45, mono=False)),
    dict(name="Paper Journal", bg="#F3EDE2", fg="#1E1B16", accent="#D9481C", muted="#7A7062",
         title="DMSerif", body="Lato", layout="framed",
         grade=dict(contrast=1.05, color=0.9, warmth=12, grain=10, vignette=0.2, mono=False)),
    dict(name="Brutalist Mono", bg="#FFFFFF", fg="#000000", accent="#FF2E2E", muted="#555555",
         title="ArchivoBlack", body="SpaceMono", layout="framed",
         grade=dict(contrast=1.3, color=0, warmth=0, grain=14, vignette=0.0, mono=True)),
    dict(name="Sunset Film", bg="#2A1B3D", fg="#FFE8D6", accent="#FF9F68", muted="#C9A7B8",
         title="BebasNeue", body="Poppins", layout="fullbleed",
         grade=dict(contrast=1.1, color=1.2, warmth=18, grain=12, vignette=0.35, mono=False)),
    dict(name="Ice Lab", bg="#E8F1F8", fg="#0D2233", accent="#1F7AE0", muted="#5B7389",
         title="ArchivoBlack", body="Poppins", layout="framed",
         grade=dict(contrast=1.08, color=0.95, warmth=-14, grain=4, vignette=0.15, mono=False)),
    dict(name="Forest Grind", bg="#10201A", fg="#E9F5EC", accent="#C6F432", muted="#8FB3A0",
         title="Anton", body="Lato", layout="fullbleed",
         grade=dict(contrast=1.12, color=1.05, warmth=4, grain=9, vignette=0.4, mono=False)),
    dict(name="Gold Standard", bg="#111111", fg="#F2E6C9", accent="#E8B931", muted="#9C8F74",
         title="AbrilFatface", body="Lato", layout="framed",
         grade=dict(contrast=1.18, color=0.85, warmth=10, grain=6, vignette=0.3, mono=False)),
]


def pick_theme(day):
    return THEMES[(day * 3) % len(THEMES)]   # cycles all 7, never the same twice in a row


# ---------- fonts (downloaded from Google Fonts on first use) ----------
GF = "https://raw.githubusercontent.com/google/fonts/main/"
FONT_FILES = {
    "Anton": "ofl/anton/Anton-Regular.ttf",
    "BebasNeue": "ofl/bebasneue/BebasNeue-Regular.ttf",
    "ArchivoBlack": "ofl/archivoblack/ArchivoBlack-Regular.ttf",
    "DMSerif": "ofl/dmserifdisplay/DMSerifDisplay-Regular.ttf",
    "AbrilFatface": "ofl/abrilfatface/AbrilFatface-Regular.ttf",
    "SpaceMono": "ofl/spacemono/SpaceMono-Bold.ttf",
    "Poppins": "ofl/poppins/Poppins-Medium.ttf",
    "Lato": "ofl/lato/Lato-Bold.ttf",
}
FONT_DIR = Path("fonts")
FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_fonts = {}


def font(name, size):
    if (name, size) in _fonts:
        return _fonts[(name, size)]
    path = FONT_DIR / f"{name}.ttf"
    if not path.exists() and name in FONT_FILES:
        try:
            r = requests.get(GF + FONT_FILES[name], timeout=30)
            r.raise_for_status()
            FONT_DIR.mkdir(exist_ok=True)
            path.write_bytes(r.content)
        except requests.RequestException as e:
            print(f"Font {name} unavailable ({e}), using fallback")
    f = None
    for p in (path, FALLBACK):
        try:
            f = ImageFont.truetype(str(p), size)
            break
        except OSError:
            continue
    f = f or ImageFont.load_default(size)
    _fonts[(name, size)] = f
    return f


# ---------- text helpers ----------
EMOJI = re.compile("[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F\u200D]")


def clean(s):
    return re.sub(r"[ \t]+", " ", EMOJI.sub("", s or "")).strip()


def wrap(d, text, f, max_w):
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            test = f"{line} {word}".strip()
            if d.textlength(test, font=f) <= max_w:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    return [l for l in lines if l] or [""]


def fit_text(d, text, fname, max_w, max_h, start=96, minimum=34, spacing=1.15):
    size = start
    while True:
        f = font(fname, size)
        lines, lh = wrap(d, text, f, max_w), int(size * spacing)
        if lh * len(lines) <= max_h or size <= minimum:
            cap = max(1, max_h // lh)
            if len(lines) > cap:
                lines = lines[:cap]
                lines[-1] = lines[-1].rstrip(" .,") + "..."
            return f, lines, lh
        size -= 4


def draw_lines(d, x, y, lines, f, lh, fill):
    for i, line in enumerate(lines):
        d.text((x, y + i * lh), line, font=f, fill=fill)


def pill(d, xy, text, theme):
    f, t = font(theme["title"], 40), text.upper()
    x, y = xy
    w = d.textlength(t, font=f)
    d.rounded_rectangle((x, y, x + w + 48, y + 66), radius=33, fill=theme["accent"])
    d.text((x + 24, y + 33), t, font=f, fill=theme["bg"], anchor="lm")
    return y + 66


def footer(d, theme, text):
    d.text((70, H - 55), text, font=font(theme["body"], 28), fill=theme["muted"], anchor="ls")


# ---------- photo editing ----------
def open_photo(path):
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def grade(img, g):
    img = ImageOps.autocontrast(img, cutoff=1)
    if g["mono"]:
        img = ImageOps.grayscale(img).convert("RGB")
    else:
        img = ImageEnhance.Color(img).enhance(g["color"])
    img = ImageEnhance.Contrast(img).enhance(g["contrast"])
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    if g["warmth"]:
        r, gr, b = img.split()
        w = g["warmth"]
        r = r.point(lambda v: max(0, min(255, v + w)))
        b = b.point(lambda v: max(0, min(255, v - w)))
        img = Image.merge("RGB", (r, gr, b))
    return img


def vignette(img, strength):
    if strength <= 0:
        return img
    mask = Image.radial_gradient("L").resize(img.size).point(lambda v: int(v * strength))
    return Image.composite(Image.new("RGB", img.size, "black"), img, mask)


def fade_mask(start=0.55, max_alpha=210):
    cut = 255 * start
    return Image.linear_gradient("L").resize((W, H)).point(
        lambda v: 0 if v < cut else int((v - cut) / (255 - cut) * max_alpha))


def grain(img, amount):
    if not amount:
        return img
    noise = Image.effect_noise(img.size, 64).convert("RGB")
    return Image.blend(img, noise, amount / 200)


def paste_rounded(base, img, xy, radius=36, shadow=True):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=radius, fill=255)
    if shadow:
        sh = Image.new("RGBA", (img.width + 80, img.height + 80), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((40, 40, 40 + img.width, 40 + img.height),
                                             radius=radius, fill=(0, 0, 0, 110))
        sh = sh.filter(ImageFilter.GaussianBlur(22))
        base.paste(sh, (xy[0] - 40, xy[1] - 28), sh)
    base.paste(img, xy, mask)


# ---------- slides ----------
def slide_photo(raw, item, theme, out):
    g, label, text = theme["grade"], CATEGORIES.get(item["cat"], "Extra"), clean(item["text"])
    img = open_photo(raw)
    if item["cat"] in SCREENSHOT_CATS:                      # clean card, no grading
        base = Image.new("RGB", (W, H), theme["bg"])
        d = ImageDraw.Draw(base)
        y0 = pill(d, (70, 70), label, theme) + 40
        text_h = 190 if text else 0
        box_h = H - y0 - 70 - (text_h + 30 if text else 0)
        shot = ImageOps.contain(img, (W - 140, box_h))
        paste_rounded(base, shot, ((W - shot.width) // 2, y0 + (box_h - shot.height) // 2))
        if text:
            f, lines, lh = fit_text(d, text, theme["body"], W - 140, text_h, start=56, minimum=30)
            draw_lines(d, 70, H - 70 - lh * len(lines), lines, f, lh, theme["fg"])
        base.save(out, "JPEG", quality=92)
        return
    if theme["layout"] == "fullbleed":
        base = grade(ImageOps.fit(img, (W, H), centering=(0.5, 0.4)), g)
        base = vignette(base, g["vignette"])
        base = Image.composite(Image.new("RGB", (W, H), "black"), base, fade_mask())
        d = ImageDraw.Draw(base)
        pill(d, (60, 60), label, theme)
        if text:
            f, lines, lh = fit_text(d, text, theme["title"], W - 120, 420, start=110, minimum=48, spacing=1.05)
            draw_lines(d, 60, H - 80 - lh * len(lines), lines, f, lh, theme["fg"])
    else:                                                    # framed
        base = Image.new("RGB", (W, H), theme["bg"])
        d = ImageDraw.Draw(base)
        pill(d, (60, 60), label, theme)
        photo_h = 900 if text else 1110
        photo = grade(ImageOps.fit(img, (W - 120, photo_h), centering=(0.5, 0.4)), g)
        paste_rounded(base, vignette(photo, g["vignette"]), (60, 170), shadow=False)
        if text:
            avail = H - (170 + photo_h) - 100
            f, lines, lh = fit_text(d, text, theme["title"], W - 120, avail, start=84, minimum=40, spacing=1.08)
            draw_lines(d, 60, 170 + photo_h + 50, lines, f, lh, theme["fg"])
    grain(base, g["grain"]).save(out, "JPEG", quality=92)


def slide_text(item, theme, out, day):
    base = Image.new("RGB", (W, H), theme["bg"])
    d = ImageDraw.Draw(base)
    pill(d, (70, 70), CATEGORIES.get(item["cat"], "Extra"), theme)
    d.rectangle((70, 220, 84, H - 220), fill=theme["accent"])
    f, lines, lh = fit_text(d, clean(item["text"]), theme["title"], W - 200, H - 500,
                            start=120, minimum=44, spacing=1.08)
    draw_lines(d, 120, (H - lh * len(lines)) // 2, lines, f, lh, theme["fg"])
    footer(d, theme, f"DAY {day}")
    grain(base, theme["grade"]["grain"]).save(out, "JPEG", quality=92)


def make_cover(day, date, done, theme, out, bg_photo=None):
    if bg_photo and theme["layout"] == "fullbleed":
        photo = grade(ImageOps.fit(open_photo(bg_photo), (W, H)), theme["grade"])
        base = Image.blend(photo, Image.new("RGB", (W, H), theme["bg"]), 0.62)
    else:
        base = Image.new("RGB", (W, H), theme["bg"])
    d = ImageDraw.Draw(base)
    d.text((70, 80), "DAY", font=font(theme["title"], 90), fill=theme["accent"])
    d.text((62, 150), str(day), font=font(theme["title"], 380), fill=theme["fg"])
    d.text((76, 600), date.strftime("%A, %d %B %Y").upper(), font=font(theme["body"], 36), fill=theme["muted"])
    y = 700
    for key, label in CATEGORIES.items():
        ok, cx, cy = key in done, 100, y + 40
        if ok:
            d.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), fill=theme["accent"])
            d.line([(cx - 16, cy + 1), (cx - 4, cy + 14), (cx + 18, cy - 12)], fill=theme["bg"], width=8, joint="curve")
        else:
            d.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), outline=theme["muted"], width=5)
            d.line([(cx - 12, cy - 12), (cx + 12, cy + 12)], fill=theme["muted"], width=5)
            d.line([(cx - 12, cy + 12), (cx + 12, cy - 12)], fill=theme["muted"], width=5)
        d.text((165, cy), label.upper(), font=font(theme["title"], 64),
               fill=theme["fg"] if ok else theme["muted"], anchor="lm")
        y += 105
    footer(d, theme, "BUILDING MY LIFE IN PUBLIC")
    grain(base, theme["grade"]["grain"]).save(out, "JPEG", quality=92)
    return out


# ---------- video & audio (ffmpeg) ----------
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart"]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return min(max(float(r.stdout.strip()), 3), 59)     # carousel videos: 3-60 s
    except ValueError:
        return 15


def video_overlay(item, theme, out):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov.putalpha(fade_mask())
    d = ImageDraw.Draw(ov)
    pill(d, (60, 60), CATEGORIES.get(item["cat"], "Extra"), theme)
    text = clean(item["text"])
    if text:
        f, lines, lh = fit_text(d, text, theme["title"], W - 120, 380, start=96, minimum=44, spacing=1.05)
        draw_lines(d, 60, H - 80 - lh * len(lines), lines, f, lh, "#FFFFFF")
    ov.save(out, "PNG")


def slide_video(raw, item, theme, stem):
    g, ov, out = theme["grade"], stem.with_suffix(".png"), stem.with_suffix(".mp4")
    video_overlay(item, theme, ov)
    sat = 0 if g["mono"] else g["color"]
    fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
          f"eq=contrast={g['contrast']}:saturation={sat},tpad=stop_mode=clone:stop_duration=3[b];"
          f"[b][1:v]overlay=0:0,fps=30,format=yuv420p[v]")
    run(["ffmpeg", "-y", "-i", str(raw), "-i", str(ov), "-filter_complex", fc,
         "-map", "[v]", "-map", "0:a?", "-t", f"{duration(raw):.2f}", *ENC, str(out)])
    return out


def audio_bg(item, theme, out, day):
    base = Image.new("RGB", (W, H), theme["bg"])
    d = ImageDraw.Draw(base)
    pill(d, (70, 70), CATEGORIES.get(item["cat"], "Extra"), theme)
    d.text((70, 190), "SOUND IDEA" if item["cat"] == "music" else "VOICE NOTE",
           font=font(theme["title"], 120), fill=theme["fg"])
    text = clean(item["text"])
    if text:
        f, lines, lh = fit_text(d, text, theme["body"], W - 140, 330, start=52, minimum=30)
        draw_lines(d, 70, 360, lines, f, lh, theme["muted"])
    d.line([(70, 900), (W - 70, 900)], fill=theme["muted"], width=2)
    d.text((70, 1150), "TURN SOUND ON", font=font(theme["title"], 48), fill=theme["accent"])
    footer(d, theme, f"DAY {day}")
    base.save(out, "PNG")


def slide_audio(raw, item, theme, stem, day):
    bg, out = stem.with_suffix(".png"), stem.with_suffix(".mp4")
    audio_bg(item, theme, bg, day)
    acc = theme["accent"].lstrip("#")
    fc = (f"[1:a]apad,asplit[a1][a2];"
          f"[a1]aformat=channel_layouts=mono,showwaves=s={W}x360:mode=cline:rate=30:colors=0x{acc}[w];"
          f"[0:v][w]overlay=0:720,format=yuv420p[v]")
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", str(bg), "-i", str(raw),
         "-filter_complex", fc, "-map", "[v]", "-map", "[a2]",
         "-t", f"{duration(raw):.2f}", *ENC, str(out)])
    return out


def make_item(item, theme, stem, day, download):
    """Returns (slide_path, 'image'|'video', raw_photo_or_None)."""
    if item["kind"] == "text":
        out = stem.with_suffix(".jpg")
        slide_text(item, theme, out, day)
        return out, "image", None
    raw = download(item["file_id"], stem.with_name(stem.name + "_raw"))
    if item["kind"] == "photo":
        out = stem.with_suffix(".jpg")
        slide_photo(raw, item, theme, out)
        return out, "image", raw
    if item["kind"] == "video":
        return slide_video(raw, item, theme, stem), "video", None
    return slide_audio(raw, item, theme, stem, day), "video", None
