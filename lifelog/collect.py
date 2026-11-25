import json, os, re
from datetime import datetime
from pathlib import Path
import requests
from config import TZ, CATEGORIES, ALIASES

TOKEN = os.environ["TELEGRAM_TOKEN"]
TG = f"https://api.telegram.org/bot{TOKEN}"
TG_FILES = f"https://api.telegram.org/file/bot{TOKEN}"
CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
LOG = Path("data/log.json")
TAG_RE = re.compile(r"#(\w+)")

HELP = ("Send photos, videos, voice notes or text with a tag:\n"
        + " ".join(f"#{k}" for k in CATEGORIES)
        + "\n\nA tag sticks until you use another one, so you can send #music once "
          "and then several clips.\n/today - what's logged so far\n/undo - remove the last item")


def load_state():
    if LOG.exists():
        return json.loads(LOG.read_text(encoding="utf-8"))
    return {"offset": 0, "last_tag": None, "day": 0, "items": [], "groups": {}}


def save_state(state):
    LOG.parent.mkdir(exist_ok=True)
    LOG.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")


def send(text):
    requests.post(f"{TG}/sendMessage", json={"chat_id": CHAT_ID, "text": text}, timeout=30)


def react(message_id, emoji):
    try:
        requests.post(f"{TG}/setMessageReaction", json={
            "chat_id": CHAT_ID, "message_id": message_id,
            "reaction": [{"type": "emoji", "emoji": emoji}]}, timeout=30)
    except requests.RequestException:
        pass


def parse_tag(text):
    for t in TAG_RE.findall(text or ""):
        t = ALIASES.get(t.lower(), t.lower())
        if t in CATEGORIES:
            return t
    return None


def extract_media(m):
    if "photo" in m:
        return "photo", m["photo"][-1]["file_id"]          # largest size
    for key, kind in (("video", "video"), ("video_note", "video"), ("animation", "video"),
                      ("voice", "audio"), ("audio", "audio")):
        if key in m:
            return kind, m[key]["file_id"]
    if "document" in m:                                    # photos/videos sent as files
        mime = m["document"].get("mime_type", "")
        for prefix, kind in (("image/", "photo"), ("video/", "video"), ("audio/", "audio")):
            if mime.startswith(prefix):
                return kind, m["document"]["file_id"]
    return "text", None


def handle_command(text, state):
    cmd = text.split()[0].lower()
    pending = [i for i in state["items"] if not i.get("posted")]
    if cmd == "/today":
        got = {i["cat"] for i in pending}
        rows = [("\u2705 " if k in got else "\u2b1c ") + v for k, v in CATEGORIES.items()]
        send("Today so far:\n" + "\n".join(rows) + f"\n\n{len(pending)} item(s) queued.")
    elif cmd == "/undo" and pending:
        state["items"].remove(pending[-1])
        send(f"Removed the last {pending[-1]['cat']} item.")
    elif cmd in ("/start", "/help"):
        send(HELP)


def collect(state):
    res = requests.get(f"{TG}/getUpdates", params={
        "offset": state["offset"], "timeout": 0,
        "allowed_updates": json.dumps(["message"])}, timeout=60).json()
    for u in res.get("result", []):
        state["offset"] = u["update_id"] + 1
        m = u.get("message")
        if not m or m["chat"]["id"] != CHAT_ID:              # ignore strangers
            continue
        text = m.get("caption") or m.get("text") or ""
        if text.startswith("/"):
            handle_command(text, state)
            continue
        tag, group = parse_tag(text), m.get("media_group_id")
        if tag:
            state["last_tag"] = tag
            if group:
                state["groups"][group] = tag
        elif group and group in state["groups"]:            # albums: caption is on 1st item only
            tag = state["groups"][group]
        else:
            tag = state["last_tag"]
        kind, file_id = extract_media(m)
        body = TAG_RE.sub("", text).strip()
        if kind == "text" and not body:                     # a bare "#music" just sets the category
            if tag:
                react(m["message_id"], "\U0001F44C")
            continue
        state["items"].append({
            "id": m["message_id"],
            "ts": datetime.fromtimestamp(m["date"], TZ).isoformat(),
            "cat": tag or "extra", "kind": kind, "file_id": file_id, "text": body,
        })
        react(m["message_id"], "\U0001F44D")
    return state


if __name__ == "__main__":
    s = load_state()
    collect(s)
    save_state(s)
