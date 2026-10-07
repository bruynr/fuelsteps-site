"""Builds the site: one page per language from i18n/<lang>.json, plus images (img/web/), icons, manifest, 404,
sitemap.xml, robots.txt, llms.txt, llms-full.txt and the IndexNow key file. `python build.py indexnow` pings IndexNow (after a deploy).

Run: python build.py   (English at the root, the other languages in /<lang>/; needs Pillow)
"""
import json
import html
import re
from datetime import date
from pathlib import Path

BASE = "https://fuelsteps.com/"
DONATE_PAYPAL = "https://paypal.me/rdbruijn"
DONATE_BUNQ = "https://bunq.me/fuelsteps"  # iDEAL/WERO
PLAIN_DONATE = f"{DONATE_PAYPAL} · {DONATE_BUNQ}"  # for plain-text output (JSON-LD, llms.txt)
ORDER = ["en", "nl", "de", "fr", "es", "it"]
ROOT = Path(__file__).parent

T = {code: json.loads((ROOT / "i18n" / f"{code}.json").read_text(encoding="utf-8")) for code in ORDER}

WEB = "img/web/"            # generated from img/ by images()
WIDTHS = [320, 480, 960]    # responsive WebP widths
SHOTS = {"fr970-run": (612, 822), "fr970-alert": (612, 822), "fr970-half": (612, 822), "fr970-quarter": (612, 822),
         "fenix847mm-run": (684, 897), "fenix847mm-almost": (684, 897), "fenix847mm-before": (684, 897)}
LANG_KEY = "fuelsteps-lang"  # localStorage: language picked in the switcher


# cache busting: GitHub Pages serves assets with max-age=600, so a changed style.css or plan.js would show up to
# 10 minutes late (and mixed with new HTML); a content hash in the query makes every change load at once
def v(name):
    import hashlib
    return hashlib.md5((ROOT / name).read_bytes()).hexdigest()[:8]


CSS = f"style.css?v={v('style.css')}"
PLAN_JS = f"plan.js?v={v('plan.js')}"
INDEXNOW_KEY = "1d775e9d727f50ad83cd05991cf82236"  # public by design: served as /<key>.txt (Bing, Yandex, …)

# home page only: on the first visit send the visitor to their browser language; a choice in the switcher wins
REDIRECT = f"""<script>
(function () {{
  try {{
    var langs = {json.dumps(ORDER[1:])}, saved = localStorage.getItem("{LANG_KEY}");
    if (saved) {{ if (langs.indexOf(saved) >= 0) location.replace(saved + "/" + location.hash); return; }}
    var prefs = navigator.languages || [navigator.language || ""];
    for (var i = 0; i < prefs.length; i++) {{
      var l = String(prefs[i]).slice(0, 2).toLowerCase();
      if (l === "en") return;
      if (langs.indexOf(l) >= 0) {{ location.replace(l + "/" + location.hash); return; }}
    }}
  }} catch (e) {{}}
}})();
</script>"""

REMEMBER = f"""<script>
document.querySelectorAll("a[hreflang]").forEach(function (a) {{
  a.addEventListener("click", function () {{ try {{ localStorage.setItem("{LANG_KEY}", a.hreflang); }} catch (e) {{}} }});
}});
</script>"""

# donation links open the overlay with both options; without JS the href (bunq on NL, PayPal elsewhere) still works
DONATE_JS = """<script>
(function () {
  var o = document.getElementById("donate-overlay");
  document.querySelectorAll("a[data-donate]").forEach(function (a) {
    a.addEventListener("click", function (e) { e.preventDefault(); o.hidden = false; });
  });
  o.addEventListener("click", function (e) { if (e.target === o || e.target.closest(".overlay-close")) o.hidden = true; });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") o.hidden = true; });
  // Umami events (no personal data): which donation provider gets clicked, which FAQ gets opened
  var lang = document.documentElement.lang;
  var track = function (name, data) { if (typeof umami !== "undefined") { data.lang = lang; umami.track(name, data); } };
  o.querySelectorAll("a[data-provider]").forEach(function (a) {
    a.addEventListener("click", function () { track("donate_click", { provider: a.dataset.provider }); });
  });
  document.querySelectorAll(".faq details").forEach(function (d, i) {
    d.addEventListener("toggle", function () { if (d.open) track("faq_open", { q: i + 1 }); });
  });
})();
</script>"""

# mobile only: the burger toggles the menu under the header; a tap on a link closes it
MENU_JS = """<script>
(function () {
  var b = document.querySelector(".burger"), m = document.getElementById("menu");
  if (!b || !m) return;
  b.addEventListener("click", function () { m.hidden = !m.hidden; b.setAttribute("aria-expanded", String(!m.hidden)); });
  m.addEventListener("click", function (e) { if (e.target.closest("a")) { m.hidden = true; b.setAttribute("aria-expanded", "false"); } });
})();
</script>"""

# Umami Cloud: page views, referrers, countries and the builder events; cookieless, no personal data, so no consent banner
UMAMI_ID = "458f80aa-006c-4354-9a7b-8bdda8850cbd"
ANALYTICS = f'<script defer src="https://cloud.umami.is/script.js" data-website-id="{UMAMI_ID}" data-domains="fuelsteps.com,www.fuelsteps.com"></script>'


def images():
    from PIL import Image
    out = ROOT / WEB
    out.mkdir(parents=True, exist_ok=True)
    for name in SHOTS:
        im = Image.open(ROOT / "img" / f"{name}.png").convert("RGB")
        for w in WIDTHS:
            im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(out / f"{name}-{w}.webp", "WEBP", quality=82, method=6)
    icon = Image.open(ROOT / "img" / "icon.png").convert("RGBA")
    for n in [32, 180, 192, 512]:
        icon.resize((n, n), Image.LANCZOS).save(out / f"icon-{n}.png")
    Image.open(ROOT / "img" / "og.png").convert("RGB").resize((1200, 600), Image.LANCZOS).save(out / "og.jpg", quality=86)


def pic(up, name, alt, sizes, lazy=True, cls=""):
    w, h = SHOTS[name]
    srcset = ", ".join(f"{up}{WEB}{name}-{x}.webp {x}w" for x in WIDTHS)
    extra = ' loading="lazy"' if lazy else ' fetchpriority="high"'
    c = f' class="{cls}"' if cls else ""
    return f'<img{c} src="{up}{WEB}{name}-480.webp" srcset="{srcset}" sizes="{sizes}" alt="{esc(alt)}" width="{w}" height="{h}"{extra}>'


# Garmin Connect charts as inline SVG, after a real 28 km long run (2026-10-04): 6 moments, 110 g, no caffeine,
# carbs/hour from the first moment on (about 60 g/h, settling around 45). Same data as the summary panel.
DEMO_MOMENTS = [(24, 25), (50, 15), (70, 15), (94, 15), (107, 25), (132, 15)]  # (minute, grams)
DEMO_END = 175
DEMO_TOTAL = sum(g for _, g in DEMO_MOMENTS)
DEMO_CAF = 0
CH_W, CH_H, CH_L, CH_B, CH_T = 560, 112, 34, 20, 6  # width, height, left/bottom/top margins
AMBER, BLUE = "#FFAA00", "#3377DD"  # site palette (style.css --amber / --blue), inline so the SVG never renders black


def chart_frame(y_max, y_ticks, body):
    x = lambda m: CH_L + (CH_W - CH_L - 6) * m / DEMO_END
    y = lambda v: CH_T + (CH_H - CH_T - CH_B) * (1 - v / y_max)
    grid = "".join(f'<line x1="{CH_L}" x2="{CH_W - 6}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>' for v in y_ticks)
    ylab = "".join(f'<text x="{CH_L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>' for v in y_ticks)
    xlab = "".join(f'<text x="{x(m):.1f}" y="{CH_H - 5}" text-anchor="middle">{m // 60}:{m % 60:02d}</text>' for m in range(30, DEMO_END, 30))
    return (f'<svg class="chart" viewBox="0 0 {CH_W} {CH_H}" role="img" aria-hidden="true">'
            f'<g stroke="#e6e6e6" stroke-width="1">{grid}</g>{body(x, y)}'
            f'<g fill="#777" font-size="11" font-family="Segoe UI, system-ui, sans-serif">{ylab}{xlab}</g></svg>')


def chart_carbs():
    def body(x, y):
        pts, total = [], 0
        for m, g in DEMO_MOMENTS:
            if total:
                pts.append(f"{x(m):.1f},{y(total):.1f}")
            total += g
            pts.append(f"{x(m):.1f},{y(total):.1f}")
        pts.append(f"{x(DEMO_END):.1f},{y(total):.1f}")
        first = DEMO_MOMENTS[0][0]
        return f'<polygon fill="{AMBER}" points="{x(first):.1f},{y(0):.1f} {" ".join(pts)} {x(DEMO_END):.1f},{y(0):.1f}"/>'
    return chart_frame(200, [0, 100, 200], body)


def chart_rate():
    def body(x, y):
        first = DEMO_MOMENTS[0][0]
        pts, total, i = [], 0, 0
        for m in range(first, DEMO_END + 1):
            while i < len(DEMO_MOMENTS) and DEMO_MOMENTS[i][0] <= m:
                total += DEMO_MOMENTS[i][1]
                i += 1
            pts.append(f"{x(m):.1f},{y(min(y_max_rate, total * 60 / m)):.1f}")
        return f'<polygon fill="{BLUE}" points="{x(first):.1f},{y(0):.1f} {" ".join(pts)} {x(DEMO_END):.1f},{y(0):.1f}"/>'
    y_max_rate = 100
    return chart_frame(100, [0, 50, 100], body)


def strip(s):
    return re.sub(r"<[^>]+>", "", s.replace("<br>", " "))


def path(code):
    return "" if code == "en" else f"{code}/"


def esc(s):
    return html.escape(s, quote=True)


# "[word]" in a text marks the donation link: an overlay trigger in HTML, the URLs written out in plain text (JSON-LD, llms.txt)
def linked(s, url):
    return re.sub(r"\[(.+?)\]", lambda m: f'<a href="{url}" data-donate>{m.group(1)}</a>', esc(s))


def unlinked(s, urls):
    return re.sub(r"\[(.+?)\]", lambda m: f"{m.group(1)} ({urls})", s)



def page(code):
    t = T[code]
    up = "" if code == "en" else "../"
    url = BASE + path(code)
    donates = [(DONATE_BUNQ, t["donate_bunq"]), (DONATE_PAYPAL, t["donate_paypal"])]
    if code != "nl":
        donates.reverse()  # bunq (iDEAL/WERO) on top only for Dutch visitors
    donate = donates[0][0]  # no-JS fallback for the trigger links
    donate_plain = " · ".join(u for u, _ in donates)
    donate_btns = "".join(f'\n    <a class="btn {cls}" href="{u}" data-provider="{"bunq" if u == DONATE_BUNQ else "paypal"}">{esc(label)}</a>' for (u, label), cls in zip(donates, ("amber", "dark")))
    alternates = "\n".join(f'<link rel="alternate" hreflang="{c}" href="{BASE + path(c)}">' for c in ORDER)
    langs = " ".join(
        f'<a href="{up}{path(c) or "./"}" hreflang="{c}" lang="{c}"{" aria-current=\"page\"" if c == code else ""}>{T[c]["label"]}</a>'
        for c in ORDER)
    app = {
        "@context": "https://schema.org", "@type": "SoftwareApplication", "name": "FuelSteps",
        "description": t["desc"], "url": url, "inLanguage": code,
        "applicationCategory": "SportsApplication", "applicationSubCategory": "Garmin Connect IQ data field",
        "operatingSystem": "Garmin Connect IQ 5.0+", "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
        "image": BASE + WEB + "icon-512.png",
        "screenshot": [BASE + "img/fr970-run.png", BASE + "img/fr970-alert.png", BASE + "img/fenix847mm-before.png"],
    }
    faq = {
        "@context": "https://schema.org", "@type": "FAQPage", "name": f"FuelSteps · {t['faq_kicker']}", "url": url, "inLanguage": code,
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": unlinked(a, donate_plain)}} for q, a in t["faq"]],
    }
    site = {"@context": "https://schema.org", "@type": "WebSite", "name": "FuelSteps", "url": BASE,
            "inLanguage": ORDER, "description": T["en"]["desc"]}
    ld = lambda o: json.dumps(o, ensure_ascii=False, indent=1)
    li = lambda items: "".join(f"<li>{i}</li>" for i in items)
    faqs = "\n".join(f"<details><summary>{esc(q)}</summary><p>{linked(a, donate)}</p></details>" for q, a in t["faq"])
    return f"""<!doctype html>
<html lang="{code}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t["title"])}</title>
<meta name="description" content="{esc(t["desc"])}">
<link rel="canonical" href="{url}">
{alternates}
<link rel="alternate" hreflang="x-default" href="{BASE}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="FuelSteps">
<meta property="og:title" content="{esc(t["og_title"])}">
<meta property="og:description" content="{esc(t["desc"])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}{WEB}og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="600">
<meta property="og:locale" content="{t["locale"]}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#15171a">
<link rel="icon" href="{up}{WEB}icon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{up}{WEB}icon-180.png">
<link rel="manifest" href="{up}manifest.webmanifest">
{REDIRECT if code == "en" else ""}
<link rel="stylesheet" href="{up}{CSS}">
<script type="application/ld+json">
{ld(app)}
</script>
<script type="application/ld+json">
{ld(faq)}
</script>
<script type="application/ld+json">
{ld(site)}
</script>
{ANALYTICS}
</head>
<body>

<header><div class="wrap">
  <a class="brand" href="#" aria-label="FuelSteps"><img src="{up}{WEB}icon-192.png" alt="" width="38" height="38"><b>Fuel<em>Steps</em></b></a>
  <nav class="langs" aria-label="Language">{langs}</nav>
  <a class="btn ghost" href="plan/">{t["plan_nav"]}</a>
  <a class="btn ghost" href="{donate}" data-donate>{t["nav_donate"]}</a>
  <span class="btn soon">{t["nav_soon"]}</span>
  <button class="burger" type="button" aria-label="Menu" aria-expanded="false" aria-controls="menu"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" fill="none"/></svg></button>
</div>
<div class="menu" id="menu" hidden>
  <a href="plan/">{t["plan_nav"]}</a>
  <a href="{donate}" data-donate>{t["nav_donate"]}</a>
  <nav class="langs-menu" aria-label="Language">{langs}</nav>
</div>
</header>

<main>
<section class="alt"><div class="wrap split">
  <div>
    <div class="kicker">{t["hero_kicker"]}</div>
    <h1>{t["hero_h1"]}</h1>
    <p class="lead">{t["hero_lead"]}</p>
    <div class="ctas">
      <a class="btn dark" href="plan/">{t["plan_cta"]}</a>
      <span class="btn soon">{t["hero_soon"]}</span>
      <a class="btn amber" href="{donate}" data-donate>{t["hero_gel"]}</a>
    </div>
  </div>
  {pic(up, "fr970-run", t["alt_hero"], "(max-width: 820px) 90vw, 460px", lazy=False, cls="watch")}
</div></section>

<section><div class="wrap split rev">
  <div>
    <div class="kicker">{t["sched_kicker"]}</div>
    <h2>{t["sched_h2"]}</h2>
    <p class="lead">{t["sched_lead"]}</p>
    <ul class="checks">{li(t["sched_li"])}</ul>
  </div>
  <div class="card">
    <h3>{t["card_title"]}</h3>
    <div class="row"><span class="at">0 km</span><span class="name">Gel</span><span class="g">25 g</span><span class="tag b">{t["tag_before"]}</span></div>
    <div class="row"><span class="at">7 km</span><span class="name">Gel</span><span class="g">25 g</span></div>
    <div class="row"><span class="at">7 km</span><span class="name">Dextro</span><span class="g">15 g</span></div>
    <div class="row"><span class="at">7 km</span><span class="name">Gel CAF</span><span class="g">25 g</span><span class="tag">{t["tag_caf"]}</span></div>
    <div class="row"><span class="at">2× 7 km</span><span class="name">Gel</span><span class="g">25 g</span><span class="tag b">#1 #2</span></div>
  </div>
</div></section>

<section class="alt"><div class="wrap split">
  <div>
    <div class="kicker">{t["alert_kicker"]}</div>
    <h2>{t["alert_h2"]}</h2>
    <p class="lead">{t["alert_lead"]}</p>
  </div>
  {pic(up, "fr970-alert", t["alt_alert"], "(max-width: 820px) 90vw, 460px", cls="watch")}
</div></section>

<section><div class="wrap split rev">
  <div>
    <div class="kicker">{t["glance_kicker"]}</div>
    <h2>{t["glance_h2"]}</h2>
    <p class="lead">{t["glance_lead"]}</p>
  </div>
  <div class="pair">
    {pic(up, "fenix847mm-run", t["alt_run"], "(max-width: 820px) 45vw, 330px")}
    {pic(up, "fenix847mm-almost", t["alt_almost"], "(max-width: 820px) 45vw, 330px")}
  </div>
</div></section>

<section class="alt"><div class="wrap" style="text-align: center;">
  <div class="kicker">{t["layout_kicker"]}</div>
  <h2>{t["layout_h2"]}</h2>
  <p class="lead" style="margin: 18px auto 44px;">{t["layout_lead"]}</p>
  <div class="faces">
    <div class="face"><div>{pic(up, "fr970-run", "", "270px")}</div>{t["full"]}</div>
    <div class="face"><div>{pic(up, "fr970-half", "", "270px")}</div>{t["half"]}</div>
    <div class="face"><div>{pic(up, "fr970-quarter", "", "270px")}</div>{t["quarter"]}</div>
  </div>
</div></section>

<section><div class="wrap start">
  <div class="kicker">{t["start_kicker"]}</div>
  <h2>{t["start_h2"]}</h2>
  <ol class="steps">{li(t["steps"])}</ol>
</div></section>

<section class="alt"><div class="wrap">
  <div class="kicker">{t["after_kicker"]}</div>
  <h2>{t["after_h2"]}</h2>
  <p class="lead">{t["after_lead"]}</p>
  <div class="connect">
    <div class="panel charts">
      <div class="chart-title"><span class="dot amber"></span>{t["fit_carbs"]} <small>IQ</small></div>
      {chart_carbs()}
      <div class="chart-title"><span class="dot blue"></span>{t["fit_rate"]} <small>IQ</small></div>
      {chart_rate()}
    </div>
    <div class="panel summary">
      <div class="sum-h">Connect IQ™</div>
      <div class="stat"><div class="v">{t["fit_card_name"]}</div><div class="l">{t["fit_schedule"]} <small>IQ</small></div></div>
      <div class="stat"><div class="v">{DEMO_TOTAL} g</div><div class="l">{t["fit_total"]} <small>IQ</small></div></div>
      <div class="stat"><div class="v">{len(DEMO_MOMENTS)} x</div><div class="l">{t["fit_count"]} <small>IQ</small></div></div>
      <div class="stat"><div class="v">{DEMO_CAF} x</div><div class="l">{t["fit_caf"]} <small>IQ</small></div></div>
    </div>
  </div>
  <ul class="checks">{li(t["after_li"])}</ul>
</div></section>

<section><div class="wrap">
  <div style="text-align: center;">
    <div class="kicker">{t["faq_kicker"]}</div>
    <h2>{t["faq_h2"]}</h2>
  </div>
  <div class="faq">
{faqs}
  </div>
</div></section>

<section class="donate" id="donate"><div class="wrap">
  <h2>{t["free_h2"]}</h2>
  <p>{t["free_p"]}</p>
  <a class="btn amber" href="{donate}" data-donate>{t["free_btn"]}</a>
</div></section>
</main>

<div class="stripe"></div>
<footer><div class="wrap">
  <span>FuelSteps · {t["footer_watches"]}</span>
  <nav class="langs-foot" aria-label="Language">{langs}</nav>
  <span>{t["not_affiliated"]}</span>
</div></footer>

<div class="overlay" id="donate-overlay" hidden>
  <div class="overlay-box" role="dialog" aria-modal="true" aria-labelledby="donate-title">
    <button class="overlay-close" aria-label="{esc(t["donate_close"])}">✕</button>
    <h3 id="donate-title">{esc(t["donate_title"])}</h3>
    <p class="donate-text">{esc(t["donate_text"])}</p>{donate_btns}
  </div>
</div>

{MENU_JS}
{REMEMBER}
{DONATE_JS}
</body>
</html>
"""


# the plan builder: /plan/ (en) and /<lang>/plan/; UI strings go to plan.js through the #plan-i18n JSON block
def plan(code):
    t = T[code]
    up = "../" if code == "en" else "../../"
    url = f"{BASE}{path(code)}plan/"
    alternates = "\n".join(f'<link rel="alternate" hreflang="{c}" href="{BASE}{path(c)}plan/">' for c in ORDER)
    langs = " ".join(
        f'<a href="{up}{path(c)}plan/" hreflang="{c}" lang="{c}"{" aria-current=\"page\"" if c == code else ""}>{T[c]["label"]}</a>'
        for c in ORDER)
    ui = {k[5:]: v for k, v in t.items() if k.startswith("plan_") and not isinstance(v, list) and k not in ("plan_title", "plan_desc", "plan_h1", "plan_lead")}
    ui["tpl"] = {tid: t[f"plan_tpl_{tid}"] for tid in ("gel5", "marathon7", "time30")}
    webpage = {"@context": "https://schema.org", "@type": "WebPage", "name": t["plan_json_ld_name"], "description": t["plan_desc"],
               "url": url, "inLanguage": code, "isPartOf": {"@type": "WebSite", "name": "FuelSteps", "url": BASE}}
    li = lambda items: "".join(f"<li>{i}</li>" for i in items)
    examples = "".join(f"<tr><td><code>{esc(c)}</code></td><td>{esc(d)}</td></tr>" for c, d in t["plan_format_examples"])
    tpl_opts = "".join(f'<option value="{tid}">{esc(t[f"plan_tpl_{tid}"])}</option>' for tid in ("gel5", "marathon7", "time30"))
    home = f"{up}{path(code) or './'}"
    return f"""<!doctype html>
<html lang="{code}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t["plan_title"])}</title>
<meta name="description" content="{esc(t["plan_desc"])}">
<link rel="canonical" href="{url}">
{alternates}
<link rel="alternate" hreflang="x-default" href="{BASE}plan/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="FuelSteps">
<meta property="og:title" content="{esc(t["plan_json_ld_name"])}">
<meta property="og:description" content="{esc(t["plan_desc"])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}{WEB}og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="600">
<meta property="og:locale" content="{t["locale"]}">
<meta name="theme-color" content="#15171a">
<link rel="icon" href="{up}{WEB}icon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{up}{WEB}icon-180.png">
<link rel="manifest" href="{up}manifest.webmanifest">
<link rel="stylesheet" href="{up}{CSS}">
<script type="application/ld+json">
{json.dumps(webpage, ensure_ascii=False, indent=1)}
</script>
{ANALYTICS}
</head>
<body>

<header><div class="wrap">
  <a class="brand" href="{home}"><img src="{up}{WEB}icon-192.png" alt="" width="38" height="38"><b>Fuel<em>Steps</em></b></a>
  <nav class="langs" aria-label="Language">{langs}</nav>
  <a class="btn ghost" href="{home}#donate">{t["nav_donate"]}</a>
  <button class="burger" type="button" aria-label="Menu" aria-expanded="false" aria-controls="menu"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" fill="none"/></svg></button>
</div>
<div class="menu" id="menu" hidden>
  <a href="{home}#donate">{t["nav_donate"]}</a>
  <nav class="langs-menu" aria-label="Language">{langs}</nav>
</div>
</header>

<main>
<section class="alt plan-hero"><div class="wrap">
  <div class="kicker">{t["plan_kicker"]}</div>
  <h1>{t["plan_h1"]}</h1>
  <p class="lead">{t["plan_lead"]}</p>
  <p class="lead-link"><a href="#ai">{t["plan_lead_ai"]}</a></p>
</div></section>

<section class="builder"><div class="wrap">
  <noscript><p class="lead">JavaScript is needed for the builder. The format reference below works without it.</p></noscript>
  <div class="builder-grid">
    <div class="builder-in">
      <div class="field-row">
        <label>{t["plan_name"]}<input id="plan-name" type="text" maxlength="16" autocomplete="off"></label>
        <fieldset id="plan-unit"><legend>{t["plan_unit"]}</legend>
          <label><input type="radio" name="unit" value="km"> {t["plan_unit_km"]} ({t["plan_km"]})</label>
          <label><input type="radio" name="unit" value="min"> {t["plan_unit_min"]} ({t["plan_min"]})</label>
        </fieldset>
        <label>{t["plan_template"]}<select id="plan-template"><option value="">{t["plan_template_pick"]}</option><option value="empty">{t["plan_template_blank"]}</option>{tpl_opts}</select></label>
      </div>
      <h2 class="h3">{t["plan_steps_h2"]}</h2>
      <table class="steps-table">
        <thead><tr><th></th><th>{t["plan_col_repeat"]}</th><th>{t["plan_col_mode"]}</th><th>{t["plan_col_text"]}</th><th>{t["plan_col_carbs"]}</th><th>{t["plan_col_caf"]}</th><th></th></tr></thead>
        <tbody id="plan-steps"></tbody>
      </table>
      <button id="plan-add" class="btn dark" type="button">{t["plan_add"]}</button>
      <ul id="plan-errors" class="errors"></ul>
    </div>
    <div class="builder-out">
      <h2 class="h3">{t["plan_moments_h2"]}</h2>
      <table class="moments-table">
        <thead><tr><th>{t["plan_col_at"]}</th><th>{t["plan_col_text"]}</th><th>{t["plan_col_carbs"]}</th><th></th></tr></thead>
        <tbody id="plan-moments"></tbody>
      </table>
      <p id="plan-totals" class="totals"></p>
      <h2 class="h3 import-h">{t["plan_import_h2"]}</h2>
      <p class="hint">{t["plan_import_help"]}</p>
      <pre id="plan-import" class="import"></pre>
      <p id="plan-import-warn" class="warn-line"></p>
      <button id="plan-import-copy" class="btn amber" type="button">{t["plan_import_copy"]}</button>
    </div>
  </div>
</div></section>

<section class="alt ai" id="ai"><div class="wrap">
  <div class="kicker">{t["plan_ai_kicker"]}</div>
  <h2>{t["plan_ai_h2"]}</h2>
  <p class="lead">{t["plan_ai_lead"]}</p>
  <div class="ai-grid">
    <div>
      <pre id="plan-ai-prompt" class="import prompt">{esc(t["plan_ai_prompt"])}</pre>
      <button id="plan-ai-copy" class="btn dark" type="button">{t["plan_ai_copy"]}</button>
      <h3 class="h3">{t["plan_ai_examples_h3"]}</h3>
      <ul class="pairs">{"".join(f'<li><span class="in">{esc(a)}</span><span class="arrow" aria-hidden="true">→</span><code>{esc(b)}</code></li>' for a, b in t["plan_ai_examples"])}</ul>
    </div>
    <div>
      <h3 class="h3">{t["plan_ai_paste_h3"]}</h3>
      <p class="hint">{t["plan_ai_paste_help"]}</p>
      <textarea id="plan-ai-paste" class="paste" rows="5" spellcheck="false" placeholder="{esc(t["plan_ai_examples"][2][1])}"></textarea>
      <p id="plan-ai-msg" class="warn-line"></p>
      <button id="plan-ai-load" class="btn amber" type="button">{t["plan_ai_load"]}</button>
    </div>
  </div>
</div></section>

<section class="alt" id="format"><div class="wrap format">
  <div class="kicker">{t["plan_format_kicker"]}</div>
  <h2>{t["plan_format_h2"]}</h2>
  <p class="lead">{t["plan_format_lead"]}</p>
  <ul class="format-list">{li(t["plan_format_li"])}</ul>
  <h3>{t["plan_format_examples_h3"]}</h3>
  <table class="examples"><tbody>{examples}</tbody></table>
  <h3>{t["plan_format_worked_h3"]}</h3>
  <p class="quote">{t["plan_format_worked_q"]}</p>
  <p>{t["plan_format_worked_a"]}</p>
  <pre class="import">{esc(t["plan_format_worked_import"])}</pre>
  <p>{t["plan_format_worked_b"]}</p>
  <h3 class="note-h">{t["plan_note_h3"]}</h3>
  <p class="note">{t["plan_note_p"]}</p>
</div></section>
</main>

<div class="stripe"></div>
<footer><div class="wrap">
  <span>FuelSteps · {t["footer_watches"]}</span>
  <nav class="langs-foot" aria-label="Language">{langs}</nav>
  <span>{t["not_affiliated"]}</span>
</div></footer>

<script type="application/json" id="plan-i18n">{json.dumps(ui, ensure_ascii=False)}</script>
<script type="module" src="{up}{PLAN_JS}"></script>
{MENU_JS}
{REMEMBER}
</body>
</html>
"""


# last commit date (YYYY-MM-DD) of the given source files; today when git or the history is unavailable
# (a shallow checkout gives nothing, so the deploy workflow checks out with fetch-depth: 0)
def lastmod(*files):
    import subprocess
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", *files], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        out = ""
    return out or date.today().isoformat()


# sources per page: the texts and the template; the plan page also changes with its script
def page_lastmod(code, sub):
    files = [f"i18n/{code}.json", "build.py"] + (["plan.js", "plan-core.js"] if sub else [])
    return lastmod(*files)


def sitemap():
    def entry(sub):
        alt = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{BASE}{path(c)}{sub}"/>' for c in ORDER)
        alt += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{BASE}{sub}"/>'
        return "".join(f"\n  <url>\n    <loc>{BASE}{path(c)}{sub}</loc>\n    <lastmod>{page_lastmod(c, sub)}</lastmod>{alt}\n  </url>" for c in ORDER)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
            f"{entry('')}{entry('plan/')}\n</urlset>\n")


def llms():
    t = T["en"]
    faq = "\n".join(f"### {q}\n{unlinked(a, PLAIN_DONATE)}\n" for q, a in t["faq"])
    pages = "\n".join(f"- [{T[c]['language']}]({BASE + path(c)})" for c in ORDER)
    return f"""# FuelSteps

> {t["desc"]}

- Type: Garmin Connect IQ data field (runs inside the native Run activity)
- Price: free, no subscription, no ads, no account; donations: {PLAIN_DONATE}
- Watches: round Garmin watches with Connect IQ 5.0+ (Forerunner 165–970, fēnix 7/8/9/E, epix Gen 2/Pro, Enduro 3, MARQ Gen 2, Venu 2/3/4, vívoactive 5/6)
- Schedules: up to 5, each a chain of steps by distance (km) or time (min) with repeats; per step a name, grams of carbs and a caffeine mark
- Settings format (Garmin Connect: one text field per schedule, 5 schedules, empty = unused, max 1000 characters): `name;km|min;step;step;…`, one step = `[Nx] size [text] [carbsg] [caf]` or `@position [text] [carbsg] [caf]`, e.g. `Long run;km;0 Gel 25g;10 Gel 25g;3x5 Gel 25g caf`; grams always with `g`; full reference in plain text: {BASE}llms-full.txt; plan builder: {BASE}plan/
- Alert: vibration, tone and full screen, 60 s / 150 m before the planned moment by default; afterwards the field keeps showing the last moment ("Gel · now", then "Gel · km 20")
- Converting an existing plan (Maurten planner, coach, book): paste it into an AI assistant with the prompt on {BASE}plan/#ai; the builder can load the resulting import text to check the moments
- Data: planned carbs, carbs per hour, fuel and caffeine moments saved in the activity (Garmin Connect charts)
- Languages: English, Dutch, German, French, Spanish, Italian

## Pages
{pages}
- [Plan builder and settings format]({BASE}plan/)
- [Full text (English)]({BASE}llms-full.txt)

## FAQ
{faq}"""


def manifest():
    return json.dumps({
        "name": "FuelSteps", "short_name": "FuelSteps", "description": T["en"]["desc"],
        "start_url": "./", "display": "browser", "background_color": "#f6f3ec", "theme_color": "#15171a",
        "icons": [{"src": f"{WEB}icon-{n}.png", "sizes": f"{n}x{n}", "type": "image/png"} for n in (192, 512)],
    }, indent=1) + "\n"


# GitHub Pages serves it for every unknown path, so all links are absolute
def not_found():
    langs = " ".join(f'<a href="{BASE + path(c)}" hreflang="{c}" lang="{c}">{T[c]["language"]}</a>' for c in ORDER)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found · FuelSteps</title>
<meta name="robots" content="noindex">
<link rel="icon" href="{BASE}{WEB}icon-32.png" sizes="32x32" type="image/png">
<link rel="stylesheet" href="{BASE}{CSS}">
{ANALYTICS}
</head>
<body>
<main><section class="alt" style="min-height: 100vh; display: flex; align-items: center;"><div class="wrap" style="text-align: center;">
  <img src="{BASE}{WEB}icon-192.png" alt="" width="96" height="96">
  <div class="kicker" style="margin-top: 24px;">404</div>
  <h1>Off <em>course.</em></h1>
  <p class="lead" style="margin: 22px auto 30px;">This page doesn't exist. Head back to the start line:</p>
  <p><a class="btn dark" href="{BASE}">FuelSteps</a></p>
  <p style="margin-top: 26px;">{langs}</p>
</div></section></main>
</body>
</html>
"""


# the settings format reference as markdown (English), for llms-full.txt
def format_section():
    t = T["en"]
    items = "\n".join(f"- {strip(i)}" for i in t["plan_format_li"])
    examples = "\n".join(f"- `{c}`: {d}" for c, d in t["plan_format_examples"])
    return f"""## {t["plan_format_h2"]}
{strip(t["plan_format_lead"])} Plan builder: {BASE}plan/

{items}

### {t["plan_format_examples_h3"]}
{examples}

### {t["plan_format_worked_h3"]}
{t["plan_format_worked_q"]}
{strip(t["plan_format_worked_a"])}

```
{t["plan_format_worked_import"]}
```

{strip(t["plan_format_worked_b"])}
"""


# the whole English page as plain markdown, for AI crawlers
def llms_full():
    t = T["en"]
    bullets = lambda items: "\n".join(f"- {strip(i)}" for i in items)
    faq = "\n".join(f"### {q}\n{unlinked(a, PLAIN_DONATE)}\n" for q, a in t["faq"])
    return f"""# FuelSteps: {strip(t["hero_h1"])}

> {t["desc"]}

{strip(t["hero_lead"])}

Website: {BASE} · Donations: {PLAIN_DONATE}

## {strip(t["sched_h2"])}
{strip(t["sched_lead"])}

{bullets(t["sched_li"])}

Example schedule ({t["card_title"]}):
- 0 km: Gel, 25 g ({t["tag_before"]})
- 7 km: Gel, 25 g
- 7 km: Dextro, 15 g
- 7 km: Gel CAF, 25 g, {t["tag_caf"]}
- 2× 7 km: Gel, 25 g (Gel #1, Gel #2)

{format_section()}
## {strip(t["alert_h2"])}
{strip(t["alert_lead"])}

## {strip(t["glance_h2"])}
{strip(t["glance_lead"])}

## {strip(t["layout_h2"])}
{strip(t["layout_lead"])} ({t["full"]}, {t["half"]}, {t["quarter"]})

## {strip(t["start_h2"])}
{chr(10).join(f"{i + 1}. {strip(s)}" for i, s in enumerate(t["steps"]))}

## {strip(t["after_h2"])}
{strip(t["after_lead"])}

{bullets(t["after_li"])}

## FAQ
{faq}
## {strip(t["free_h2"])}
{strip(t["free_p"])} {PLAIN_DONATE}

Watches: {t["footer_watches"]}. {t["not_affiliated"]}

Other languages: {", ".join(f"{T[c]['language']} {BASE + path(c)}" for c in ORDER[1:])}
"""


def main():
    images()
    for code in ORDER:
        out = ROOT / path(code) / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(code), encoding="utf-8", newline="\n")
    for code in ORDER:
        out = ROOT / path(code) / "plan" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(plan(code), encoding="utf-8", newline="\n")
    (ROOT / "sitemap.xml").write_text(sitemap(), encoding="utf-8", newline="\n")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8", newline="\n")
    (ROOT / "llms.txt").write_text(llms(), encoding="utf-8", newline="\n")
    (ROOT / "llms-full.txt").write_text(llms_full(), encoding="utf-8", newline="\n")
    (ROOT / "manifest.webmanifest").write_text(manifest(), encoding="utf-8", newline="\n")
    (ROOT / "404.html").write_text(not_found(), encoding="utf-8", newline="\n")
    (ROOT / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY, encoding="utf-8", newline="\n")
    print("built:", ", ".join(ORDER))


def indexnow():
    """After a deploy: tell IndexNow search engines that all language pages changed."""
    import urllib.request
    host = BASE.split("/")[2]
    body = {"host": host, "key": INDEXNOW_KEY, "keyLocation": f"{BASE}{INDEXNOW_KEY}.txt",
            "urlList": [BASE + path(c) + sub for sub in ("", "plan/") for c in ORDER]}
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("indexnow:", r.status, len(body["urlList"]), "urls")


if __name__ == "__main__":
    import sys
    indexnow() if sys.argv[1:] == ["indexnow"] else main()
