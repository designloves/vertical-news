#!/usr/bin/env python3
"""Build a shareable page and a preview image for every story, so a link to one story unfurls with its own
headline and picture in Messages, Slack, LinkedIn, Teams and the like.

  s/<date>/<slug>/index.html   small static page with Open Graph / Twitter tags; sends people on to the story
  og/<date>/<slug>.png         1200x630 preview card in the paper's style
  og/site.png                  preview card for the front page

Runs in GitHub Actions (.github/workflows/story-pages.yml) after an edition is pushed. Link-preview bots do not
run JavaScript, which is why each story needs a real page of its own.
The slug rule must match slugify() in index.html.
"""
import datetime, glob, html, json, os, re, shutil, unicodedata
from PIL import Image, ImageDraw, ImageFont

SITE = os.environ.get("SITE_URL", "https://designloves.github.io/vertical-news/").rstrip("/") + "/"
FONTS = os.environ.get("FONT_DIR", "fonts")
PAPER, INK, INK2, RULE = (238, 234, 223), (47, 45, 40), (98, 94, 85), (205, 198, 182)
W, H, M = 1200, 630, 72
CAT = {"gen": "AI", "ux": "Product & UX", "pm": "Strategy & PM", "eng": "Engineering AI",
       "vv": "Virtual validation", "bear": "Bearings", "auto": "Automotive"}


def slugify(text):
    t = unicodedata.normalize("NFD", str(text or "")).lower()
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:60].rstrip("-") or "story"


def slugs_for(stories):
    seen, out = {}, []
    for s in stories:
        base = slugify(s.get("headline"))
        n = seen.get(base, 0) + 1
        seen[base] = n
        out.append(base if n == 1 else f"{base}-{n}")
    return out


def font(names, size):
    for n in names:
        p = os.path.join(FONTS, n)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def wrap(draw, text, f, width, max_lines):
    words, lines, cur = str(text or "").split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=f) <= width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textlength(last + "…", font=f) > width:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        lines[-1] = last.rstrip(",;:") + "…"
    return lines


def long_date(date):
    d = datetime.date.fromisoformat(date)
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')} {d.year}"


def masthead(draw, date_text):
    np = font(["UnifrakturMaguntia.ttf"], 64)
    draw.text((M, 44), "vertical news", font=np, fill=INK)
    if date_text:
        lab = font(["ArchivoNarrow-SemiBold.ttf"], 26)
        t = date_text.upper()
        draw.text((W - M - draw.textlength(t, font=lab), 70), t, font=lab, fill=INK)
    draw.rectangle((M, 136, W - M, 142), fill=INK)


def card(story, date, path):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    masthead(d, long_date(date))
    y = 176
    kick = " · ".join(x for x in (CAT.get(story.get("cat"), ""), str(story.get("date") or "")) if x).upper()
    if kick:
        d.text((M, y), kick, font=font(["ArchivoNarrow-SemiBold.ttf"], 26), fill=INK2)
        y += 48
    # Largest headline size that fits in four lines; the "why" line takes what is left.
    for size in (66, 60, 54, 50, 46):
        hf = font(["Newsreader-Bold.ttf"], size)
        lines = wrap(d, story.get("headline"), hf, W - 2 * M, 4)
        if not lines[-1].endswith("…") or size == 46:
            break
    lh = int(size * 1.14)
    for ln in lines:
        d.text((M, y), ln, font=hf, fill=INK)
        y += lh
    y += 18
    why = str(story.get("why") or "")
    if why:
        wf = font(["Newsreader-Italic.ttf"], 32)
        room = max(0, (H - 56 - y) // 42)
        for ln in wrap(d, why, wf, W - 2 * M, min(3, room)) if room else []:
            d.text((M, y), ln, font=wf, fill=INK)
            y += 42
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.quantize(colors=48, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)  # flat paper and ink: small files


def site_card(path):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    np = font(["UnifrakturMaguntia.ttf"], 150)
    t = "vertical news"
    d.text(((W - d.textlength(t, font=np)) / 2, 170), t, font=np, fill=INK)
    d.rectangle((M + 120, 380, W - M - 120, 386), fill=INK)
    sub = font(["Newsreader-Italic.ttf"], 38)
    s = "AI, bearing and automotive news, every morning"
    d.text(((W - d.textlength(s, font=sub)) / 2, 412), s, font=sub, fill=INK)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.quantize(colors=48, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)  # flat paper and ink: small files


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Vertical News</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Vertical News">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{title}">
<meta property="article:published_time" content="{date}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{img}">
<link rel="icon" href="{site}icons/favicon-32.png?v=3" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{site}apple-touch-icon.png?v=3">
<style>
:root{{color-scheme:light}}
body{{margin:0;padding:24px 16px 48px;background:#eeeadf;color:#2f2d28;font:18px/1.55 Georgia,"Times New Roman",serif}}
main{{max-width:640px;margin:0 auto}}
.np{{font:400 34px/1 "UnifrakturMaguntia","Old English Text MT",serif;text-decoration:none;color:inherit}}
.k{{margin:28px 0 6px;font:600 13px/1.3 "Arial Narrow",Arial,sans-serif;letter-spacing:.07em;text-transform:uppercase;color:#625e55}}
h1{{margin:0 0 10px;font-size:30px;line-height:1.2}}
.why{{font-style:italic}}
a{{color:#3f5a70}}
</style>
<script>location.replace({target});</script>
</head>
<body>
<main>
<a class="np" href="{site}">vertical news</a>
<p class="k">{kicker}</p>
<h1>{title_h}</h1>
<p class="why">{why_h}</p>
{body}
<p><a href="{site}#{date}/{slug}">Read it in Vertical News, {long}</a></p>
</main>
</body>
</html>
"""


def page(date, slug, s, path):
    url = f"{SITE}s/{date}/{slug}/"
    e = lambda x: html.escape(str(x or ""), quote=True)
    body = "\n".join(f"<p>{e(p)}</p>" for p in s.get("body", []) if str(p).strip())
    kicker = " · ".join(x for x in (CAT.get(s.get("cat"), ""), long_date(date)) if x)
    out = PAGE.format(title=e(s.get("headline")), desc=e(s.get("why")), url=e(url),
                      img=e(f"{SITE}og/{date}/{slug}.png"), date=e(date), site=e(SITE), slug=e(slug),
                      target=json.dumps(f"{SITE}#{date}/{slug}"), kicker=e(kicker),
                      title_h=e(s.get("headline")), why_h=e(s.get("why")), body=body, long=e(long_date(date)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(out)


def main():
    for d in ("s", "og"):
        shutil.rmtree(d, ignore_errors=True)
    count = 0
    for path in sorted(glob.glob("editions/????-??-??.json")):
        date = os.path.basename(path)[:-5]
        with open(path) as f:
            ed = json.load(f)
        stories = [s for s in ed.get("stories", []) if isinstance(s, dict)]
        for s, slug in zip(stories, slugs_for(stories)):
            page(date, slug, s, f"s/{date}/{slug}/index.html")
            card(s, date, f"og/{date}/{slug}.png")
            count += 1
    site_card("og/site.png")
    print(f"built {count} story pages")


if __name__ == "__main__":
    main()
