import os, time
from datetime import datetime
from pathlib import Path
import requests
import cloudinary, cloudinary.uploader
import render
from collect import load_state, save_state, collect, send, TG, TG_FILES
from config import TZ, CATEGORIES, SCREENSHOT_CATS, MAX_ITEMS, POST_EMPTY_DAYS, SIGN_OFF, HASHTAGS

IG = "https://graph.instagram.com/v26.0"
IG_TOKEN = os.environ["IG_TOKEN"]
OUT = Path("out")
OUT.mkdir(exist_ok=True)
cloudinary.config(secure=True)        # reads CLOUDINARY_URL from env


def tg_download(file_id, dest):
    info = requests.get(f"{TG}/getFile", params={"file_id": file_id}, timeout=30).json()
    if not info.get("ok"):
        raise RuntimeError(info.get("description", "getFile failed"))   # e.g. file over 20 MB
    r = requests.get(f"{TG_FILES}/{info['result']['file_path']}", timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def ig(method, path, **params):
    params["access_token"] = IG_TOKEN
    kw = {"data": params} if method == "POST" else {"params": params}
    j = requests.request(method, f"{IG}/{path}", timeout=120, **kw).json()
    if "error" in j:
        raise RuntimeError(j["error"].get("message", j["error"]))
    return j


def wait_ready(cid):
    for _ in range(60):
        status = ig("GET", cid, fields="status_code").get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram rejected media {cid}: {status}")
        time.sleep(10)
    raise TimeoutError(f"Media {cid} never finished processing")


def publish(slides, caption):
    uid = ig("GET", "me", fields="user_id,username")["user_id"]
    urls = []
    for path, kind in slides:
        res = cloudinary.uploader.upload(str(path), folder="lifelog",
                                         resource_type="video" if kind == "video" else "image")
        urls.append((res["secure_url"], kind))
    if len(urls) == 1:
        cid = ig("POST", f"{uid}/media", image_url=urls[0][0], caption=caption)["id"]
    else:
        kids = []
        for url, kind in urls:
            p = {"is_carousel_item": "true"}
            if kind == "video":
                p.update(media_type="VIDEO", video_url=url)
            else:
                p["image_url"] = url
            kids.append(ig("POST", f"{uid}/media", **p)["id"])
        for k in kids:
            wait_ready(k)
        cid = ig("POST", f"{uid}/media", media_type="CAROUSEL",
                 children=",".join(kids), caption=caption)["id"]
    wait_ready(cid)
    media_id = ig("POST", f"{uid}/media_publish", creation_id=cid)["id"]
    try:
        return ig("GET", media_id, fields="permalink").get("permalink", "")
    except Exception:
        return ""


def select(items):
    order = list(CATEGORIES) + ["extra"]
    buckets = {c: [i for i in items if i["cat"] == c] for c in order}
    chosen = []
    while len(chosen) < MAX_ITEMS and any(buckets.values()):   # round-robin so every category shows
        for c in order:
            if buckets[c] and len(chosen) < MAX_ITEMS:
                chosen.append(buckets[c].pop(0))
    chosen.sort(key=lambda i: (order.index(i["cat"]), i["ts"]))
    return chosen, len(items) - len(chosen)


def build_caption(day, now, pending, extra):
    lines = [f"Day {day} \u00b7 {now:%d %b %Y}", ""]
    for key, label in CATEGORIES.items():
        its = [i for i in pending if i["cat"] == key]
        note = next((i["text"] for i in its if i["text"]), "")
        mark = "\u2705" if its else "\u274c"
        lines.append(f"{mark} {label}" + (f" - {note[:80]}" if note else ""))
    if extra:
        lines.append(f"\n+{extra} more logged today")
    lines += ["", SIGN_OFF.format(day=day), "", HASHTAGS]
    return "\n".join(lines)[:2200]


def main():
    state = load_state()
    try:
        collect(state)                                   # grab last-minute messages
        pending = [i for i in state["items"] if not i.get("posted")]
        if not pending and not POST_EMPTY_DAYS:
            return
        day, now = state["day"] + 1, datetime.now(TZ)
        theme = render.pick_theme(day)
        chosen, extra = select(pending)
        slides, cover_photo = [], None
        for n, it in enumerate(chosen):
            try:
                path, kind, raw = render.make_item(it, theme, OUT / f"{n:02d}", day, tg_download)
                slides.append((path, kind))
                if raw and not cover_photo and it["cat"] not in SCREENSHOT_CATS:
                    cover_photo = raw
            except Exception as e:
                print(f"Skipped {it['cat']} item {it['id']}: {e}")
        cover = render.make_cover(day, now, {i["cat"] for i in pending}, theme, OUT / "cover.jpg", cover_photo)
        link = publish([(cover, "image")] + slides, build_caption(day, now, pending, extra))
        for i in pending:
            i["posted"] = now.isoformat()
        state["day"], state["groups"] = day, {}
        state["items"] = state["items"][-400:]
        send(f"\u2705 Day {day} is live ({theme['name']} style)\n{link}")
    except Exception as e:
        send(f"\u26a0\ufe0f Today's post failed: {str(e)[:300]}")
        raise
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
