from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Kolkata")

# Order here = order on the cover checklist
CATEGORIES = {
    "workout": "Workout",
    "meal": "Meal",
    "steps": "Steps",
    "music": "Music Idea",
    "study": "Study",
}
ALIASES = {"gym": "workout", "food": "meal", "walk": "steps",
           "sound": "music", "beat": "music", "notes": "study"}
SCREENSHOT_CATS = {"steps", "study"}   # shown as clean cards, never cropped or graded

MAX_ITEMS = 9            # + cover slide = 10, the API carousel max
POST_EMPTY_DAYS = True   # post an all-missed cover on days you log nothing
SIGN_OFF = "Building my life in public. Day {day}."
HASHTAGS = "#buildinpublic #dailylog #accountability #gymlife #musicproduction #studygram"
W, H = 1080, 1350        # 4:5 portrait
