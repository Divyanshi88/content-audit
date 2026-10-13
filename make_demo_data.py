"""Generate a FAKE account (output/demo_brand/raw.json) to test the pipeline offline:
    python make_demo_data.py && python analyze.py demo_brand --offline --no-ai
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(7)
followers = 48_200
captions = {
    "reel": ["3 ways to style our kurta for office 👗 #ootd #ethnicwear #officewear",
             "POV: your mom sees the price tag 😂 #relatable #fashionreels",
             "Behind the scenes at our Jaipur block-print studio #handmade #jaipur #madeinindia",
             "Festive drop is LIVE 🪔 link in bio #diwali #festivewear"],
    "carousel": ["New arrivals this week — swipe ➡️ #newcollection #ethnicwear",
                 "Customer love 💛 thank you for tagging us! #reviews"],
    "image": ["Sale ends tonight. 30% off sitewide. #sale #shopnow", "Happy Independence Day 🇮🇳"],
}
posts, t = [], datetime.now(timezone.utc) - timedelta(days=2)
for i in range(110):
    typ = random.choices(["reel", "carousel", "image"], [0.5, 0.3, 0.2])[0]
    t -= timedelta(days=random.choice([1, 2, 2, 3, 4, 7, 12]), hours=random.randint(-5, 5))
    t = t.replace(hour=random.choice([4, 6, 7, 12, 13, 14]), minute=random.randint(0, 59))
    base = {"reel": 900, "carousel": 650, "image": 300}[typ]
    viral = random.random() < 0.06
    likes = int(random.lognormvariate(0, 0.5) * base * (6 if viral else 1))
    cap = random.choice(captions[typ])
    posts.append({
        "shortcode": f"DEMO{i:03d}", "url": "https://www.instagram.com/", "date_utc": t.isoformat(),
        "type": typ, "is_video": typ == "reel", "likes": likes, "comments": int(likes * random.uniform(0.01, 0.05)),
        "views": int(likes * random.uniform(12, 30)) if typ == "reel" else None, "plays": None,
        "duration_s": round(random.uniform(7, 45), 1) if typ == "reel" else None, "caption": cap,
        "hashtags": [w[1:] for w in cap.split() if w.startswith("#")], "mentions": [], "tagged_users": [],
        "is_sponsored": False, "is_pinned": False, "location": None, "accessibility_caption": None, "video_file": None,
    })
data = {"profile": {"username": "demo_brand", "full_name": "Demo Ethnic Wear Co. (FAKE DATA)", "biography": "Handmade in Jaipur",
                    "external_url": None, "followers": followers, "following": 310, "total_posts": 412, "is_verified": False,
                    "is_business": True, "business_category": "Clothing (Brand)", "profile_pic_url": None},
        "posts": posts, "fetched_at": "demo"}
out = Path("output/demo_brand"); out.mkdir(parents=True, exist_ok=True)
(out / "raw.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
print("wrote", out / "raw.json")
