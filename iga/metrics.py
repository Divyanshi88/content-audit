"""Step 2: turn raw posts into the numbers a brand would normally see in Instagram Insights.

Public data only gives likes, comments, views/plays, date, caption. Shares, saves, reach and
follower demographics are private to the account owner, so they are NOT computed here.
"""
from collections import Counter

import pandas as pd

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _r(x, n=2):
    return None if x is None or pd.isna(x) else round(float(x), n)


def compute(data, tz="Asia/Kolkata"):
    profile, posts = data["profile"], data["posts"]
    followers = max(profile.get("followers") or 1, 1)
    if not posts:
        return {"profile": profile, "summary": {"posts_analyzed": 0}}

    df = pd.DataFrame(posts)
    df["date"] = pd.to_datetime(df["date_utc"], utc=True).dt.tz_convert(tz)
    df = df.sort_values("date").reset_index(drop=True)
    df["interactions"] = df["likes"].clip(lower=0) + df["comments"]
    df["er_pct"] = df["interactions"] / followers * 100          # engagement rate by followers
    df["like_rate_pct"] = df["likes"].clip(lower=0) / followers * 100
    df["comment_rate_pct"] = df["comments"] / followers * 100
    df["comment_per_100_likes"] = df["comments"] / df["likes"].clip(lower=1) * 100
    reach_metric = df["plays"].fillna(df["views"])
    df["view_rate_pct"] = reach_metric / followers * 100          # reel views as % of followers
    df["er_by_views_pct"] = df["interactions"] / reach_metric * 100
    df["weekday"] = df["date"].dt.dayofweek.map(lambda d: DAYS[d])
    df["hour"] = df["date"].dt.hour
    df["caption_len"] = df["caption"].fillna("").str.len()
    df["n_hashtags"] = df["hashtags"].apply(len)

    span_days = max((df["date"].max() - df["date"].min()).days, 1)
    gaps = df["date"].diff().dt.total_seconds().dropna() / 86400

    # monthly cadence
    monthly = (df.set_index("date").resample("MS")
               .agg({"shortcode": "count", "er_pct": "mean", "likes": "mean"})
               .rename(columns={"shortcode": "posts"}).reset_index())
    monthly["month"] = monthly["date"].dt.strftime("%Y-%m")

    by_type = (df.groupby("type").agg(posts=("shortcode", "count"), avg_likes=("likes", "mean"),
                                      avg_comments=("comments", "mean"), avg_er_pct=("er_pct", "mean"),
                                      avg_views=("views", "mean")).reset_index())
    by_type["share_pct"] = by_type["posts"] / len(df) * 100

    by_day = df.groupby("weekday").agg(posts=("shortcode", "count"), avg_er_pct=("er_pct", "mean"))
    by_day = by_day.reindex(DAYS).fillna(0).reset_index()
    by_hour = df.groupby("hour").agg(posts=("shortcode", "count"), avg_er_pct=("er_pct", "mean")).reset_index()

    tag_counter = Counter(t.lower() for tags in df["hashtags"] for t in tags)
    tag_perf = []
    for tag, n in tag_counter.most_common(25):
        mask = df["hashtags"].apply(lambda ts: tag in [t.lower() for t in ts])
        tag_perf.append({"tag": tag, "uses": n, "avg_er_pct": _r(df.loc[mask, "er_pct"].mean(), 3)})

    reels = df[df["is_video"]]
    median_er = df["er_pct"].median()
    cols = ["shortcode", "url", "date_utc", "type", "likes", "comments", "views", "er_pct", "caption"]

    def records(frame):
        out = frame[cols].copy()
        out["er_pct"] = out["er_pct"].round(3)
        out["caption"] = out["caption"].fillna("").str.slice(0, 160)
        return out.where(out.notna(), None).to_dict("records")

    last_30 = df[df["date"] >= df["date"].max() - pd.Timedelta(days=30)]
    prev_30 = df[(df["date"] < df["date"].max() - pd.Timedelta(days=30)) &
                 (df["date"] >= df["date"].max() - pd.Timedelta(days=60))]

    summary = {
        "posts_analyzed": len(df),
        "first_post": df["date"].min().isoformat(),
        "last_post": df["date"].max().isoformat(),
        "days_since_last_post": (pd.Timestamp.now(tz=tz) - df["date"].max()).days,
        "posts_per_week": _r(len(df) / span_days * 7),
        "avg_gap_days": _r(gaps.mean()),
        "max_gap_days": _r(gaps.max()),
        "consistency_score": (lambda v: None if v is None else int(v))(_r(max(0, 100 - (gaps.std() / max(gaps.mean(), 0.01)) * 50) if len(gaps) > 2 else None, 0)),
        "avg_likes": _r(df["likes"].mean(), 0),
        "median_likes": _r(df["likes"].median(), 0),
        "avg_comments": _r(df["comments"].mean(), 1),
        "avg_engagement_rate_pct": _r(df["er_pct"].mean(), 3),
        "median_engagement_rate_pct": _r(median_er, 3),
        "like_rate_pct": _r(df["like_rate_pct"].mean(), 3),
        "comment_rate_pct": _r(df["comment_rate_pct"].mean(), 4),
        "comments_per_100_likes": _r(df["comment_per_100_likes"].mean()),
        "reels_share_pct": _r(len(reels) / len(df) * 100, 1),
        "avg_reel_views": _r(reels["views"].mean(), 0) if len(reels) else None,
        "avg_reel_view_rate_pct": _r(reels["view_rate_pct"].mean()) if len(reels) else None,
        "avg_reel_er_by_views_pct": _r(reels["er_by_views_pct"].mean()) if len(reels) else None,
        "avg_reel_duration_s": _r(reels["duration_s"].mean(), 1) if len(reels) else None,
        "avg_caption_len": _r(df["caption_len"].mean(), 0),
        "avg_hashtags_per_post": _r(df["n_hashtags"].mean(), 1),
        "sponsored_posts": int(df["is_sponsored"].sum()),
        "best_weekday": by_day.loc[by_day["avg_er_pct"].idxmax(), "weekday"],
        "best_hour": int(by_hour.loc[by_hour["avg_er_pct"].idxmax(), "hour"]),
        "most_common_post_hour": int(df["hour"].mode().iloc[0]),
        "viral_posts_3x_median": int((df["er_pct"] > 3 * median_er).sum()),
        "er_last_30d_pct": _r(last_30["er_pct"].mean(), 3),
        "er_prev_30d_pct": _r(prev_30["er_pct"].mean(), 3) if len(prev_30) else None,
        "posts_last_30d": len(last_30),
        "timezone": tz,
    }
    summary["benchmark"] = benchmark(summary["avg_engagement_rate_pct"], followers)

    timeline = df[["date_utc", "type", "likes", "comments", "views", "er_pct"]].copy()
    timeline["er_pct"] = timeline["er_pct"].round(3)

    return {
        "profile": profile,
        "summary": summary,
        "monthly": monthly[["month", "posts", "er_pct", "likes"]].round(3).fillna(0).to_dict("records"),
        "by_type": by_type.round(3).where(by_type.notna(), None).to_dict("records"),
        "by_weekday": by_day.round(3).to_dict("records"),
        "by_hour": by_hour.round(3).to_dict("records"),
        "heatmap": df.groupby(["weekday", "hour"]).size().reset_index(name="n").to_dict("records"),
        "hashtags": tag_perf,
        "top_posts": records(df.nlargest(8, "er_pct")),
        "bottom_posts": records(df.nsmallest(5, "er_pct")),
        "timeline": timeline.where(timeline.notna(), None).to_dict("records"),
    }


def benchmark(er, followers):
    """Rough industry ER bands by follower tier (likes+comments / followers)."""
    tiers = [(10_000, 4.0, 1.5), (100_000, 2.5, 1.0), (1_000_000, 1.8, 0.7), (float("inf"), 1.2, 0.4)]
    for cap, good, ok in tiers:
        if followers < cap:
            break
    if er is None:
        return "n/a"
    return "strong" if er >= good else "average" if er >= ok else "weak"
