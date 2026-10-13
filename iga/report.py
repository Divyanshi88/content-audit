"""Step 5: render a single self-contained HTML audit report (open in any browser, send to client)."""
import json
from pathlib import Path

from jinja2 import Environment

STYLE = r"""
/* Layout: one 1040px reading column; sections separated by hairlines, panels only around charts and tables. */
:root{
  --bg:#fafaf9;--surface:#ffffff;--line:#e7e6e3;--line-2:#f0efec;
  --ink:#121314;--ink-2:#55575c;--ink-3:#8a8c91;
  --accent:#2a78d6;--s2:#eb6834;--s3:#1baf7a;
  --good:#1f7a3a;--good-bg:#e8f4ec;--warn:#9a6700;--warn-bg:#fbf1dc;--bad:#b42318;--bad-bg:#fbe9e7;
  --sans:"Geist",ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --mono:"Geist Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0e0f10;--surface:#151618;--line:#26282b;--line-2:#1d1f22;--ink:#f3f3f2;--ink-2:#a8aaaf;--ink-3:#75777c;
  --accent:#3987e5;--s2:#d95926;--s3:#199e70;--good:#5cc77e;--good-bg:#12291a;--warn:#e0b04a;--warn-bg:#2b2310;--bad:#f07a6e;--bad-bg:#2e1614;color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0e0f10;--surface:#151618;--line:#26282b;--line-2:#1d1f22;--ink:#f3f3f2;--ink-2:#a8aaaf;--ink-3:#75777c;
  --accent:#3987e5;--s2:#d95926;--s3:#199e70;--good:#5cc77e;--good-bg:#12291a;--warn:#e0b04a;--warn-bg:#2b2310;--bad:#f07a6e;--bad-bg:#2e1614;color-scheme:dark}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 var(--sans);-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration-color:var(--line);text-underline-offset:3px}a:hover{text-decoration-color:var(--ink-3)}
.wrap{max-width:1040px;margin:0 auto;padding-inline:20px;padding-block:0 72px}
.nav{display:flex;justify-content:space-between;align-items:center;padding-block:18px;border-bottom:1px solid var(--line);font-size:13px;color:var(--ink-2);gap:12px;flex-wrap:wrap}
.mark{font-weight:600;color:var(--ink);letter-spacing:-.01em;text-decoration:none}.mark span{color:var(--ink-3);font-weight:400}
.nav a.btn{border:1px solid var(--line);border-radius:8px;padding:6px 12px;text-decoration:none;color:var(--ink);background:var(--surface)}
.notice{margin-top:20px;padding:10px 14px;border:1px solid var(--line);border-radius:8px;background:var(--surface);font-size:13px;color:var(--ink-2)}
.notice b{color:var(--ink)}
.hero{display:flex;gap:20px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding-block:36px 28px}
.who{display:flex;gap:16px;align-items:center;min-width:0}
.avatar{width:60px;height:60px;border-radius:50%;background:var(--line-2);display:grid;place-items:center;font-weight:600;color:var(--ink-3);overflow:hidden;flex:none;position:relative}
.avatar img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
h1{font-size:28px;line-height:1.15;margin:0;letter-spacing:-.025em;font-weight:600;overflow-wrap:break-word;word-break:break-word}
.who .meta{color:var(--ink-2);font-size:14px;margin-top:4px}
.counts{display:flex;gap:28px}
.counts div{text-align:right}.counts b{display:block;font:500 20px/1.2 var(--mono);letter-spacing:-.02em}
.counts span{font-size:12px;color:var(--ink-3)}
section{border-top:1px solid var(--line);padding-block:32px}
.eyebrow{font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);font-weight:500;margin:0 0 18px}
.lede{font-size:22px;line-height:1.4;letter-spacing:-.015em;margin:0 0 14px;max-width:34em;text-wrap:balance;font-weight:500}
.prose{color:var(--ink-2);max-width:44em;margin:0}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr));gap:20px 32px;margin:24px 0 0}
.facts dt{font-size:12px;color:var(--ink-3);margin-bottom:4px}.facts dd{margin:0;font-size:14px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-radius:12px;background:var(--surface);overflow:hidden}
.kpi{padding:18px 20px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);min-width:0}
.kpi:nth-child(4n){border-right:0}.kpi:nth-last-child(-n+4){border-bottom:0}
.kpi .l{font-size:12.5px;color:var(--ink-2)}
.kpi .v{font:500 26px/1.25 var(--mono);letter-spacing:-.03em;margin-top:6px;font-variant-numeric:tabular-nums;white-space:nowrap}
.kpi .v small{font-size:14px;color:var(--ink-3);letter-spacing:0}
.kpi .n{font-size:12.5px;color:var(--ink-3);margin-top:2px}
.pill{display:inline-block;font:500 11.5px/1 var(--sans);padding:4px 8px;border-radius:99px;vertical-align:4px;margin-left:8px;letter-spacing:.01em}
.pill.strong{color:var(--good);background:var(--good-bg)}.pill.average{color:var(--warn);background:var(--warn-bg)}.pill.weak{color:var(--bad);background:var(--bad-bg)}
.up{color:var(--good)}.down{color:var(--bad)}
.charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px 18px 14px;min-width:0}
.panel h3{font-size:14px;font-weight:500;margin:0}.panel p{font-size:12.5px;color:var(--ink-3);margin:2px 0 12px}
.chart{position:relative;height:220px}
.legend{display:flex;gap:14px;font-size:12px;color:var(--ink-2);margin:-4px 0 8px;flex-wrap:wrap}
.legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.tbl{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{font-weight:500;font-size:12px;color:var(--ink-3);text-align:left;padding:12px 16px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:12px 16px;border-bottom:1px solid var(--line-2);vertical-align:top}tr:last-child td{border-bottom:0}
td.num,th.num{text-align:right;font-family:var(--mono);font-size:13px;white-space:nowrap;font-variant-numeric:tabular-nums}
td.date{font-family:var(--mono);font-size:13px;white-space:nowrap}
td.cap{color:var(--ink-2);min-width:240px}
.type{font-size:12.5px;color:var(--ink-2);white-space:nowrap}.type i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px}
.tags{display:flex;flex-wrap:wrap;gap:8px}
.tag{border:1px solid var(--line);background:var(--surface);border-radius:8px;padding:6px 10px;font-size:13px}
.tag span{font-family:var(--mono);font-size:12px;color:var(--ink-3);margin-left:6px}
.cols{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:40px}
.cols h4,.block h4{font-size:14px;font-weight:500;margin:0 0 10px}
ul.list{list-style:none;margin:0;padding:0}ul.list li{padding:9px 0 9px 22px;border-bottom:1px solid var(--line-2);position:relative;font-size:14px;color:var(--ink-2)}
ul.list li::before{position:absolute;left:0;top:9px;font-family:var(--mono);font-size:13px}
ul.plus li::before{content:"+";color:var(--good)}ul.minus li::before{content:"−";color:var(--bad)}ul.dot li::before{content:"→";color:var(--ink-3)}
.scores{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr));gap:0 40px}
.score{display:grid;grid-template-columns:1fr 90px 40px;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid var(--line-2);font-size:14px}
.score .track{height:4px;background:var(--line);border-radius:4px}.score .track i{display:block;height:100%;border-radius:4px;background:var(--ink)}
.score b{font:500 13px var(--mono);text-align:right}
.score.overall span:first-child{font-weight:600}
.rec{display:grid;grid-template-columns:36px minmax(0,1fr);gap:2px 12px;padding:16px 0;border-bottom:1px solid var(--line-2)}
.rec .no{font:500 13px/1.6 var(--mono);color:var(--ink-3);grid-row:span 3}
.rec b{font-weight:500}.rec .why{color:var(--ink-3);font-size:13.5px}.rec .how{color:var(--ink-2);font-size:14px}
.block{margin-top:32px}
.pitch{border-left:2px solid var(--ink);padding:4px 0 4px 18px;color:var(--ink);max-width:46em;margin:0}
.foot{border-top:1px solid var(--line);padding-top:20px;font-size:12.5px;color:var(--ink-3);max-width:52em;margin:0}
@media (max-width:760px){
  .kpis{grid-template-columns:repeat(2,1fr)}
  .kpi:nth-child(4n){border-right:1px solid var(--line)}.kpi:nth-child(2n){border-right:0}
  .kpi:nth-last-child(-n+4){border-bottom:1px solid var(--line)}.kpi:nth-last-child(-n+2){border-bottom:0}
  .kpi{padding:16px}.kpi .v{font-size:22px}
  .charts,.cols{grid-template-columns:minmax(0,1fr)}.cols{gap:28px}
  .counts{gap:20px}.counts div{text-align:left}.lede{font-size:19px}h1{font-size:23px}.avatar{width:48px;height:48px}
}
"""

TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>@{{ p.username }} · Content Audit</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>{{ style|safe }}</style></head><body><div class="wrap">

<nav class="nav"><a class="mark" href="{{ home_url or '#' }}">Content Audit <span>/ Instagram</span></a>
  <span style="display:flex;gap:14px;align-items:center">Generated {{ generated }}{% if home_url %}<a class="btn" href="{{ home_url }}">New audit</a>{% endif %}</span></nav>

{% if demo %}<div class="notice"><b>Sample report.</b> This account and its numbers are generated demo data showing what an audit looks like.</div>{% endif %}

<header class="hero">
  <div class="who">
    <div class="avatar">{{ p.username[:1]|upper }}{% if p.profile_pic_url %}<img src="{{ p.profile_pic_url }}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">{% endif %}</div>
    <div style="min-width:0"><h1>@{{ p.username }}</h1>
      <div class="meta">{{ p.full_name }}{% if p.business_category %} · {{ p.business_category }}{% endif %}{% if p.is_verified %} · Verified{% endif %}</div></div>
  </div>
  <div class="counts">
    <div><b>{{ compact(p.followers) }}</b><span>Followers</span></div>
    <div><b>{{ compact(p.total_posts) }}</b><span>Posts</span></div>
    <div><b>{{ s.posts_analyzed }}</b><span>Analysed</span></div>
  </div>
</header>

{% if ai %}
<section>
  <p class="eyebrow">Summary</p>
  <p class="lede">{{ ai.one_line_bio }}</p>
  <p class="prose">{{ ai.account_summary }}</p>
  <dl class="facts">
    <div><dt>Niche</dt><dd>{{ ai.niche }}</dd></div>
    <div><dt>Likely audience</dt><dd>{{ ai.target_audience_guess }}</dd></div>
    <div><dt>Brand voice</dt><dd>{{ ai.brand_voice }}</dd></div>
  </dl>
</section>
{% elif p.biography %}
<section><p class="eyebrow">Bio</p><p class="prose">{{ p.biography }}</p></section>
{% endif %}

<section>
  <p class="eyebrow">Key metrics</p>
  <div class="kpis">
    <div class="kpi"><div class="l">Engagement rate</div><div class="v">{{ "%.2f"|format(s.avg_engagement_rate_pct) }}<small>%</small><span class="pill {{ s.benchmark }}">{{ s.benchmark|capitalize }}</span></div>
      <div class="n">Median {{ "%.2f"|format(s.median_engagement_rate_pct) }}%</div></div>
    <div class="kpi"><div class="l">Last 30 days</div><div class="v">{{ "%.2f"|format(s.er_last_30d_pct or 0) }}<small>%</small></div>
      <div class="n">{% if s.er_prev_30d_pct %}{% set d = s.er_last_30d_pct - s.er_prev_30d_pct %}<span class="{{ 'up' if d >= 0 else 'down' }}">{{ "%+.2f"|format(d) }} pts</span> vs previous 30{% else %}No earlier period{% endif %}</div></div>
    <div class="kpi"><div class="l">Avg likes</div><div class="v">{{ compact(s.avg_likes) }}</div><div class="n">Median {{ compact(s.median_likes) }}</div></div>
    <div class="kpi"><div class="l">Avg comments</div><div class="v">{{ s.avg_comments|round(1) }}</div><div class="n">{{ s.comments_per_100_likes }} per 100 likes</div></div>
    <div class="kpi"><div class="l">Posts per week</div><div class="v">{{ s.posts_per_week }}</div><div class="n">{{ s.posts_last_30d }} in the last 30 days</div></div>
    <div class="kpi"><div class="l">Consistency</div><div class="v">{{ s.consistency_score if s.consistency_score is not none else "–" }}<small>/100</small></div><div class="n">Longest gap {{ (s.max_gap_days or 0)|round|int }} days</div></div>
    <div class="kpi"><div class="l">Avg reel views</div><div class="v">{{ compact(s.avg_reel_views) if s.avg_reel_views else "–" }}</div><div class="n">{% if s.avg_reel_view_rate_pct %}{{ s.avg_reel_view_rate_pct|round|int }}% of followers{% else %}No reels{% endif %}</div></div>
    <div class="kpi"><div class="l">Best time to post</div><div class="v">{{ s.best_weekday }} {{ "%02d"|format(s.best_hour) }}:00</div><div class="n">Usually posts at {{ "%02d"|format(s.most_common_post_hour) }}:00 · {{ s.timezone.split('/')[-1] }}</div></div>
  </div>
</section>

<section>
  <p class="eyebrow">Performance</p>
  <div class="charts">
    <div class="panel"><h3>Engagement per post</h3><p>Each dot is one post, coloured by format</p>
      <div class="legend">{% for t in by_type %}<span><i style="background:var({{ type_var.get(t.type, '--ink-3') }})"></i>{{ t.type|capitalize }}</span>{% endfor %}</div>
      <div class="chart"><canvas id="cTimeline" role="img" aria-label="Engagement rate per post over time"></canvas></div></div>
    <div class="panel"><h3>Engagement by format</h3><p>{% for t in by_type %}{{ t.type|capitalize }} {{ t.share_pct|round|int }}%{% if not loop.last %} · {% endif %}{% endfor %} of posts</p>
      <div class="chart"><canvas id="cType" role="img" aria-label="Average engagement rate by format"></canvas></div></div>
    <div class="panel"><h3>Posts per month</h3><p>Posting cadence over the analysed period</p>
      <div class="chart"><canvas id="cMonthPosts" role="img" aria-label="Posts per month"></canvas></div></div>
    <div class="panel"><h3>Engagement rate per month</h3><p>Average of all posts published that month</p>
      <div class="chart"><canvas id="cMonthER" role="img" aria-label="Average engagement rate per month"></canvas></div></div>
    <div class="panel"><h3>By weekday</h3><p>Average engagement rate by day posted</p>
      <div class="chart"><canvas id="cDay" role="img" aria-label="Engagement rate by weekday"></canvas></div></div>
    <div class="panel"><h3>By hour</h3><p>Average engagement rate by hour posted ({{ s.timezone.split('/')[-1] }})</p>
      <div class="chart"><canvas id="cHour" role="img" aria-label="Engagement rate by hour"></canvas></div></div>
  </div>
</section>

<section>
  <p class="eyebrow">Top posts</p>
  <div class="tbl"><table>
    <tr><th>Date</th><th>Format</th><th>Caption</th><th class="num">Likes</th><th class="num">Comments</th><th class="num">Views</th><th class="num">ER</th></tr>
    {% for r in top %}<tr><td class="date"><a href="{{ r.url }}" target="_blank" rel="noopener">{{ r.date_utc[:10] }}</a></td>
      <td class="type"><i style="background:var({{ type_var.get(r.type, '--ink-3') }})"></i>{{ r.type|capitalize }}</td><td class="cap">{{ r.caption or "—" }}</td>
      <td class="num">{{ "{:,}".format(r.likes) }}</td><td class="num">{{ "{:,}".format(r.comments) }}</td>
      <td class="num">{{ "{:,}".format(r.views|int) if r.views else "–" }}</td><td class="num">{{ "%.2f"|format(r.er_pct) }}%</td></tr>{% endfor %}
  </table></div>
  <div class="block"><h4>Lowest performing</h4>
  <div class="tbl"><table>
    <tr><th>Date</th><th>Format</th><th>Caption</th><th class="num">Likes</th><th class="num">Comments</th><th class="num">ER</th></tr>
    {% for r in bottom %}<tr><td class="date"><a href="{{ r.url }}" target="_blank" rel="noopener">{{ r.date_utc[:10] }}</a></td>
      <td class="type"><i style="background:var({{ type_var.get(r.type, '--ink-3') }})"></i>{{ r.type|capitalize }}</td><td class="cap">{{ r.caption or "—" }}</td>
      <td class="num">{{ "{:,}".format(r.likes) }}</td><td class="num">{{ r.comments }}</td><td class="num">{{ "%.2f"|format(r.er_pct) }}%</td></tr>{% endfor %}
  </table></div></div>
</section>

{% if tags %}
<section>
  <p class="eyebrow">Hashtags</p>
  <div class="tags">{% for t in tags %}<span class="tag">#{{ t.tag }}<span>{{ t.uses }}× · {{ "%.2f"|format(t.avg_er_pct) }}%</span></span>{% endfor %}</div>
  <p class="prose" style="font-size:13px;margin-top:14px">Number of uses and average engagement rate of posts with the tag. {{ s.avg_hashtags_per_post }} hashtags and {{ s.avg_caption_len|int }} characters per caption on average.</p>
</section>
{% endif %}

{% if ai %}
<section>
  <p class="eyebrow">Audit</p>
  <div class="scores">{% for k, v in ai.scores.items() %}<div class="score{{ ' overall' if k == 'overall' }}"><span>{{ k.replace("_"," ")|capitalize }}</span><span class="track"><i style="width:{{ v*10 }}%"></i></span><b>{{ v }}/10</b></div>{% endfor %}</div>

  <div class="block"><h4>Content pillars</h4>
  <div class="tbl"><table><tr><th>Pillar</th><th class="num">Share</th><th>Performance</th></tr>
    {% for c in ai.content_pillars %}<tr><td style="min-width:200px"><div>{{ c.pillar }}</div><div style="color:var(--ink-3);font-size:12.5px">{{ c.example }}</div></td>
    <td class="num">{{ c.approx_share_pct|round|int }}%</td><td style="color:var(--ink-2);min-width:200px">{{ c.performance }}</td></tr>{% endfor %}</table></div></div>

  <div class="block cols">
    <div><h4>What works</h4><ul class="list plus">{% for x in ai.what_works %}<li>{{ x }}</li>{% endfor %}</ul></div>
    <div><h4>What doesn't</h4><ul class="list minus">{% for x in ai.what_doesnt_work %}<li>{{ x }}</li>{% endfor %}</ul></div>
  </div>
  <div class="block cols">
    <div><h4>Hooks</h4><p class="prose" style="font-size:14px">{{ ai.hook_analysis }}</p></div>
    <div><h4>Posting behaviour</h4><p class="prose" style="font-size:14px">{{ ai.posting_behaviour }}</p></div>
  </div>
  <div class="block"><h4>Gaps and opportunities</h4><ul class="list dot">{% for x in ai.gaps_and_opportunities %}<li>{{ x }}</li>{% endfor %}</ul></div>
</section>

<section>
  <p class="eyebrow">Recommendations</p>
  <div>{% for r in ai.recommendations %}<div class="rec"><span class="no">{{ "%02d"|format(loop.index) }}</span><b>{{ r.title }}</b><span class="why">{{ r.why }}</span><span class="how">{{ r.how }}</span></div>{% endfor %}</div>
  <div class="block"><h4>Posting plan</h4><p class="prose" style="font-size:14px">{{ ai.posting_plan }}</p></div>
</section>

<section>
  <p class="eyebrow">Reel ideas</p>
  <div class="tbl"><table><tr><th>Idea</th><th>Opening line</th><th>Format</th><th>Why it fits</th></tr>
    {% for r in ai.reel_ideas %}<tr><td style="min-width:160px">{{ r.title }}</td><td style="min-width:200px">“{{ r.hook_line }}”</td><td style="color:var(--ink-2);min-width:120px">{{ r.format }}</td><td style="color:var(--ink-2);min-width:180px">{{ r.why_it_fits }}</td></tr>{% endfor %}
  </table></div>
</section>

<section>
  <p class="eyebrow">In short</p>
  <p class="pitch">{{ ai.sales_pitch_summary }}</p>
</section>
{% endif %}

<p class="foot">Built from publicly visible data: likes, comments, views, post times and captions{% if has_transcripts %}, plus reel audio transcripts{% endif %}.
Engagement rate = (likes + comments) ÷ followers. Shares, saves, reach and audience demographics are visible only to the account owner and are not included.</p>
</div>

<script>
const D = {{ chart_json|safe }};
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const C = {accent:css('--accent'), s2:css('--s2'), s3:css('--s3'), line:css('--line'), ink3:css('--ink-3'), surface:css('--surface'), ink:css('--ink')};
const TC = {reel:C.accent, carousel:C.s2, image:C.s3};
Chart.defaults.color = C.ink3; Chart.defaults.maintainAspectRatio = false; Chart.defaults.animation = false;
Chart.defaults.font = {family:css('--mono') || 'monospace', size:11};
Chart.defaults.plugins.legend.display = false;
Object.assign(Chart.defaults.plugins.tooltip, {backgroundColor:C.ink, titleColor:C.surface, bodyColor:C.surface, padding:10, cornerRadius:6, displayColors:false,
  titleFont:{family:css('--sans'), weight:'500', size:12}, bodyFont:{family:css('--mono'), size:11.5}});
const yAxis = {beginAtZero:true, grid:{color:C.line, drawTicks:false}, border:{display:false}, ticks:{padding:8, maxTicksLimit:5}};
const xAxis = {grid:{display:false}, border:{color:C.line}, ticks:{padding:6, maxRotation:0, autoSkipPadding:12}};
const pct = v => v.toFixed(2) + '%';
function bar(id, labels, data, colors, unit){
  new Chart(document.getElementById(id), {type:'bar',
    data:{labels, datasets:[{data, backgroundColor:colors, borderRadius:{topLeft:4, topRight:4}, borderSkipped:'bottom', maxBarThickness:26, categoryPercentage:.7}]},
    options:{scales:{x:xAxis, y:{...yAxis, ticks:{...yAxis.ticks, callback:v=>unit==='posts'?v:v+'%'}}},
      interaction:{mode:'index', intersect:false},
      plugins:{tooltip:{callbacks:{label:c=>unit==='posts'?c.raw+' posts':pct(c.raw)+' avg ER'+(D.counts[id]?' · '+D.counts[id][c.dataIndex]+' posts':'')}}}}});
}
const mLabel = m => new Date(m+'-01T00:00').toLocaleDateString(undefined,{month:'short', year:'2-digit'});
bar('cMonthPosts', D.monthly.map(m=>mLabel(m.month)), D.monthly.map(m=>m.posts), C.accent, 'posts');
new Chart(document.getElementById('cMonthER'), {type:'line', data:{labels:D.monthly.map(m=>mLabel(m.month)),
  datasets:[{data:D.monthly.map(m=>m.er_pct), borderColor:C.accent, borderWidth:2, tension:.3, fill:true,
    backgroundColor:C.accent+'14', pointRadius:0, pointHoverRadius:5, pointHoverBackgroundColor:C.accent, pointHoverBorderColor:C.surface, pointHoverBorderWidth:2}]},
  options:{scales:{x:xAxis, y:{...yAxis, ticks:{...yAxis.ticks, callback:v=>v+'%'}}}, interaction:{mode:'index', intersect:false},
    plugins:{tooltip:{callbacks:{label:c=>pct(c.raw)+' avg ER'}}}}});
const types = [...new Set(D.timeline.map(t=>t.type))];
new Chart(document.getElementById('cTimeline'), {type:'scatter', data:{datasets:types.map(t=>({label:t,
  data:D.timeline.filter(x=>x.type===t).map(x=>({x:new Date(x.date_utc).getTime(), y:x.er_pct, l:x.likes, c:x.comments})),
  backgroundColor:TC[t]||C.ink3, borderColor:C.surface, borderWidth:1.5, pointRadius:4.5, pointHoverRadius:7}))},
  options:{interaction:{mode:'nearest', intersect:true},
    plugins:{tooltip:{callbacks:{title:c=>new Date(c[0].raw.x).toLocaleDateString(undefined,{day:'numeric', month:'short', year:'numeric'})+' · '+c[0].dataset.label,
      label:c=>`${pct(c.raw.y)} ER · ${c.raw.l.toLocaleString()} likes · ${c.raw.c} comments`}}},
    scales:{x:{...xAxis, type:'linear', ticks:{...xAxis.ticks, maxTicksLimit:6, callback:v=>new Date(v).toLocaleDateString(undefined,{month:'short', year:'2-digit'})}},
            y:{...yAxis, ticks:{...yAxis.ticks, callback:v=>v+'%'}}}}});
bar('cType', D.by_type.map(t=>t.type[0].toUpperCase()+t.type.slice(1)), D.by_type.map(t=>t.avg_er_pct), D.by_type.map(t=>TC[t.type]||C.ink3));
bar('cDay', D.by_weekday.map(d=>d.weekday), D.by_weekday.map(d=>d.avg_er_pct), C.accent);
bar('cHour', D.by_hour.map(h=>String(h.hour).padStart(2,'0')), D.by_hour.map(h=>h.avg_er_pct), C.accent);
</script></body></html>"""

TYPE_VAR = {"reel": "--accent", "carousel": "--s2", "image": "--s3"}


def compact(n):
    if n is None:
        return "–"
    n = float(n)
    for div, suf in ((1e6, "M"), (1e3, "K")):
        if abs(n) >= div:
            return f"{n / div:.1f}".rstrip("0").rstrip(".") + suf
    return f"{n:,.0f}"


_tpl = Environment(autoescape=True).from_string(TEMPLATE)


def render_html(metrics, ai, generated, has_transcripts=False, demo=False, home_url=None):
    chart = {k: metrics[k] for k in ("monthly", "by_type", "by_weekday", "by_hour", "timeline")}
    chart["counts"] = {"cDay": [d["posts"] for d in metrics["by_weekday"]],
                       "cHour": [h["posts"] for h in metrics["by_hour"]],
                       "cType": [t["posts"] for t in metrics["by_type"]]}
    return _tpl.render(p=metrics["profile"], s=metrics["summary"], by_type=metrics["by_type"],
                       top=metrics["top_posts"], bottom=metrics["bottom_posts"], tags=metrics["hashtags"][:18],
                       ai=ai, demo=demo, generated=generated, has_transcripts=has_transcripts, home_url=home_url,
                       style=STYLE, compact=compact, type_var=TYPE_VAR,
                       chart_json=json.dumps(chart, default=str).replace("</", "<\\/"))


def render(metrics, ai, out_path: Path, generated, has_transcripts=False, demo=False, home_url=None):
    out_path.write_text(render_html(metrics, ai, generated, has_transcripts, demo, home_url))
    return out_path
