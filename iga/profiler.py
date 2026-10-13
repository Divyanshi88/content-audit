"""Step 4: Claude reads the metrics + captions + transcripts + reel frames and writes the
account "bio" / content audit that we hand to the client."""
import base64
import json
import os
from pathlib import Path

MODEL = "claude-opus-5-5"

SYSTEM = """You are a senior Instagram content strategist auditing a brand's account for an agency pitch.
You get computed metrics (public data only: likes, comments, views, timing, captions, transcripts,
a few frames from reels). You do NOT have shares, saves, reach or audience demographics - never invent them.
Ground every claim in the data provided; cite numbers. Be direct and specific, not generic.
The client is often an Indian brand; Hinglish content is normal. Write in clear English."""

S = {"type": "string"}
SA = {"type": "array", "items": S}


def _obj(props, req=None):
    return {"type": "object", "properties": props, "required": req or list(props), "additionalProperties": False}


SCHEMA = _obj({
    "one_line_bio": S,
    "account_summary": S,
    "niche": S,
    "target_audience_guess": S,
    "brand_voice": S,
    "content_pillars": {"type": "array", "items": _obj({"pillar": S, "approx_share_pct": {"type": "number"},
                                                         "example": S, "performance": S})},
    "formats_used": SA,
    "hook_analysis": S,
    "posting_behaviour": S,
    "what_works": SA,
    "what_doesnt_work": SA,
    "gaps_and_opportunities": SA,
    "scores": _obj({k: {"type": "integer"} for k in
                    ["consistency", "engagement", "content_quality", "hooks", "variety", "branding", "overall"]}),
    "recommendations": {"type": "array", "items": _obj({"title": S, "why": S, "how": S})},
    "reel_ideas": {"type": "array", "items": _obj({"title": S, "hook_line": S, "format": S, "why_it_fits": S})},
    "posting_plan": S,
    "sales_pitch_summary": S,
})


def _img_block(path):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(Path(path).read_bytes()).decode()}}


def build_prompt(data, metrics, max_posts=60, max_frame_reels=8):
    posts = sorted(data["posts"], key=lambda p: p["date_utc"], reverse=True)[:max_posts]
    followers = max(data["profile"].get("followers") or 1, 1)
    compact = []
    for p in posts:
        compact.append({
            "date": p["date_utc"][:16], "type": p["type"], "likes": p["likes"], "comments": p["comments"],
            "views": p.get("views"), "er_pct": round((max(p["likes"], 0) + p["comments"]) / followers * 100, 3),
            "duration_s": p.get("duration_s"), "caption": (p.get("caption") or "")[:400],
            "transcript": (p.get("transcript") or "")[:600] or None,
        })
    lean_metrics = {k: v for k, v in metrics.items() if k not in ("timeline", "heatmap")}
    content = [{"type": "text", "text":
                f"PROFILE + METRICS:\n{json.dumps(lean_metrics, ensure_ascii=False, default=str)}\n\n"
                f"POSTS (newest first):\n{json.dumps(compact, ensure_ascii=False, default=str)}"}]

    # frames from the best and worst reels so Claude can compare visuals
    reels = [p for p in data["posts"] if p.get("frames")]
    reels.sort(key=lambda p: p["likes"] + p["comments"], reverse=True)
    picked = reels[: max_frame_reels // 2] + reels[-(max_frame_reels // 2):] if len(reels) > max_frame_reels else reels
    for p in picked:
        content.append({"type": "text", "text": f"Frames (hook/mid/end) of reel {p['shortcode']} "
                                                f"- likes {p['likes']}, comments {p['comments']}, views {p.get('views')}:"})
        content += [_img_block(f) for f in p["frames"]]

    content.append({"type": "text", "text":
                    "Write the full audit. 5-8 recommendations, 10 reel ideas tailored to this brand, "
                    "scores 1-10. sales_pitch_summary = 4-6 sentences an agency could send the brand."})
    return content


def generate_profile(data, metrics):
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("  ! no ANTHROPIC_API_KEY set - skipping AI bio (metrics report still generated)")
        return None
    import anthropic

    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": build_prompt(data, metrics)}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        print("  ! model declined the request")
        return None
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text)
