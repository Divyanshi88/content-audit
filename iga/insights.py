"""Free, rule-based findings for reports made without a Claude key."""


def quick_insights(m):
    s, out = m["summary"], []
    by_type = {t["type"]: t for t in m["by_type"]}
    er, med = s.get("avg_engagement_rate_pct") or 0, s.get("median_engagement_rate_pct") or 0

    out.append(f"Engagement rate is {er:.2f}% ({s['benchmark']} for an account this size); the median post gets {med:.2f}%.")
    if med and er > 2 * med:
        out.append(f"A few breakout posts carry the average: {s['viral_posts_3x_median']} posts beat 3× the median, "
                   f"while a typical post gets far less.")
    if len(by_type) > 1:
        best = max(by_type.values(), key=lambda t: t["avg_er_pct"] or 0)
        worst = min(by_type.values(), key=lambda t: t["avg_er_pct"] or 0)
        if best is not worst and (worst["avg_er_pct"] or 0) > 0:
            out.append(f"{best['type'].capitalize()}s perform best ({best['avg_er_pct']:.2f}% ER), "
                       f"{best['avg_er_pct'] / worst['avg_er_pct']:.1f}× {worst['type']}s ({worst['avg_er_pct']:.2f}%). "
                       f"{best['type'].capitalize()}s are {best['share_pct']:.0f}% of posts.")
    if s.get("avg_reel_view_rate_pct"):
        out.append(f"Reels average {s['avg_reel_views']:,.0f} views, {s['avg_reel_view_rate_pct']:.0f}% of the follower count"
                   + (", so Instagram is pushing them beyond followers." if s["avg_reel_view_rate_pct"] > 100 else "."))
    hours = sorted(m["by_hour"], key=lambda h: h["posts"], reverse=True)
    if hours and s["best_hour"] != hours[0]["hour"]:
        usual = hours[0]
        best = next(h for h in m["by_hour"] if h["hour"] == s["best_hour"])
        out.append(f"Most posts go out at {usual['hour']:02d}:00 ({usual['avg_er_pct']:.2f}% ER), but {best['hour']:02d}:00 "
                   f"performs best ({best['avg_er_pct']:.2f}%, {best['posts']} posts). Best day: {s['best_weekday']}.")
    if s.get("er_prev_30d_pct"):
        d = s["er_last_30d_pct"] - s["er_prev_30d_pct"]
        out.append(f"Engagement over the last 30 days is {'up' if d >= 0 else 'down'}: {s['er_last_30d_pct']:.2f}% vs "
                   f"{s['er_prev_30d_pct']:.2f}% in the 30 days before.")
    out.append(f"Posting cadence: {s['posts_per_week']} posts a week, longest gap {s['max_gap_days']:.0f} days "
               f"(consistency {s['consistency_score']}/100).")
    if s["comments_per_100_likes"] < 3:
        out.append(f"Comments are low ({s['comments_per_100_likes']} per 100 likes). Captions could ask a question to start conversation.")
    return out
