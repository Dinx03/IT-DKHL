# ONA Healthy — the website

`README.md` in the repo root covers the same ground in Thai, for the owner. If you
change how the build or a convention works, change both — they drift otherwise.

## Layout

```
website/
├── src/                    ← edit here
│   ├── sprite.html         every illustration, shared by all pages
│   ├── header.html         topbar + mega menus + mobile nav, shared
│   ├── footer.html         footer + toast, shared
│   ├── page-home.html      the home <main>
│   ├── page-products.html  the catalogue <main>
│   └── page-knowledge.html the reference page <main>
├── assets/css/style.css    ← and here
├── assets/js/main.js       ← and here
├── assets/video/           the hero cover film
├── index.html              generated — never edit
├── products.html           generated — never edit
├── knowledge.html          generated — never edit
├── dist/*.html             single-file bundles, generated
├── build.py                stitches src/ into the pages and the bundles
└── data/                   the owner's source documents (.docx)
```

Edit `src/` and the two asset files, then `py build.py`. Header, footer and sprite
exist once and are stitched into every page at build time — copying them per page
is exactly how two versions quietly drift apart.

The bundles exist because Claude Artifacts must be one self-contained file with no
`<!doctype>`/`<html>`/`<head>`/`<body>` of its own. Publish `dist/ona-healthy.html`
(home) or `dist/products.html`, never the root pages. **Links between pages do not
resolve inside an Artifact** — each artifact is a single file — so the catalogue
link works locally and on a real host but is dead in the published preview.

**The bundles cannot carry the hero film.** An Artifact is one self-contained file
on its own origin, and its CSP blocks external media outright, so the relative
`assets/video/animation.mp4` resolves to nothing and the hero renders as an empty
cream panel — no error, just a blank cover. A published Artifact is therefore no
longer a faithful preview of the home page. Share a real host for that, or upload
the film as an artifact asset and point the bundle at the URL that comes back.

Images in `assets/img/` (the certification logos) are linked normally in the real
pages; `build.py` swaps every `src="assets/img/…"` for a data URI in the bundles,
for the same reason the film cannot ride along. The Q logo is cropped to the
symbol only — the source file carries a sample certificate number that is not
the farm's, and the real one (มกษ. 03-9001-53-393-000041) is set as text beside it.

The sprite is inlined into each page rather than referenced as a separate file:
`<use href="#id">` only resolves within the same document, so a shared external
sprite would break every illustration when a page is opened straight from disk.

Adding a page: drop `src/page-<name>.html` in and add a row to `PAGES` in
`build.py`. A page that opens straight onto content (no hero) should carry
`class="page--plain"` on its `<main>` for the top spacing.

To preview: open `index.html`, or `py -m http.server 8899` for something closer to
a real host.

Header and footer link to home-page sections with a bare hash. On any page that
does not contain the section, `main.js` rewrites the link to `index.html#…` at
load, so shared markup does not need to know which page it is on.

## The three pages

`index.html` sells, `products.html` is the catalogue you scan, and
`knowledge.html` is the long-form reference — what is in the fruit, and eleven
products explained by what they are made of and how they are used.

**The knowledge page carries no prices and no order buttons, on purpose.** It is
where someone works out what a thing is; each group ends with one quiet link to
the catalogue and that is where the selling happens. Three bundles — box set,
monthly pack, gift set — are deliberately absent from it too: they are quantities
of the juice, not products with properties of their own, so they belong in the
catalogue and nowhere else.

Sizes still appear on both pages, so **a size changed in one has to be changed in
the other.** There is no shared data file behind them.

Each group is built as one feature entry plus a two-across grid rather than a run
of identical rows. The lead is the product the group is genuinely known for — the
juice, and the soap the reviews keep returning to — so the hierarchy states
something true instead of just breaking up the monotony. An earlier revision ran
all fourteen as one uniform row list and read as a spreadsheet; it was also
29,766px tall against 7,671px now.

The knowledge page is reached from the button at the foot of the "why ONA Healthy"
rail on the home page. It is not in the header nav yet.

**Its contents bar is a direct child of `<main>`, not of a section.** `position:
sticky` only holds while the element's own containing block is on screen, so a
sticky bar placed inside the intro section stops following after the first scroll —
which on a thirty-thousand-pixel page is the moment it starts being useful. It also
pins to `var(--topbar-h)`, not to 78px, because the announcement strip opens on
scroll and changes the height of the stack above it. Anything that has to clear
both bars uses `scroll-margin-top: calc(var(--topbar-h) + 84px)`, which is set on
every `[id]` so in-page links do not land under them.

## Bilingual

Thai lives in the markup, English lives beside it in attributes, so the page still
reads correctly in Thai with JavaScript off.

| Attribute | For |
|---|---|
| `data-en` | plain-text elements — most things |
| `data-en-html` | content containing tags, e.g. a `<br>` |
| `data-en-text` | elements mixing text with child elements, e.g. a button with an icon |
| `data-en-aria` | screen-reader labels |
| `data-en-placeholder` | form fields |

Any new string needs its translation at the same time, or switching to English
leaves Thai stranded on the page. Quickest check: switch to English and scan for
Thai characters. Choice persists in `localStorage` under `ona-lang`.

## Setting Thai

Thai and English share every size in the stylesheet, which quietly penalises Thai.
A Thai syllable stacks up to four levels — a vowel under the letter, a vowel over
it, a tone mark over that — where Latin puts nothing above the cap line. Two
consequences, both handled in the `READING IN THAI` block at the foot of the
stylesheet, and both scoped to `:root[data-lang="th"]` so the English page is
untouched:

- **Small labels get a floor.** Below about 12px the upper marks merge into a
  smudge and Thai stops being readable as words, while the same Latin string is
  merely small. Raised: `.jrail__i span` 10 → 12, `.badge` and `.cert__s`
  10.5 → 12, `.ft__cols h4` 11 → 12, `.ft__bot` 11.5 → 12.5.
- **Tracking comes off.** Wide letter-spacing is a Latin device; in Thai it prises
  the tone mark away from the consonant it belongs to, so the reader reassembles
  each syllable. `.eyebrow` drops from .24em to .06em in Thai, and the other label
  styles similarly. Latin keeps the brand board's tracking.

**Add to that list from a measurement, not from the source.** Three selectors went
in on the first pass because the stylesheet said 11px — measured, they were
already 12px or larger, and the `.scard__t` rule made Thai *smaller* than English.
`.scard__t` computes to 14px on the page against 11px in the rule; the computed
value is not always the one written down.

## Traps that have already cost time here

Each of these produced a real, hard-to-diagnose failure in this project. They look
like preferences; they are not.

**The hero film fills the opening screen at every size and is simply cropped to
fit; the copy sits straight on it with nothing in between.** This is the owner's
call, made after three passes that each tried to protect the text — a full cream
veil, a graded film under a light veil, and a two-band dissolve — and each was
rejected for burying the footage.

What it costs, measured over the whole clip against the exact boxes the text
occupies: the headline averages 6.3:1 but **27.5% of the area behind it is under
4.5:1**, bottoming out at 1.0:1; the standfirst averages 5.8:1 with 27.7% under.
Those patches move as the clip plays, so words drop out and come back rather than
being reliably unreadable — which is harder to notice in a screenshot than in use.
The fix is upstream, not in CSS: a paler grade on the clip itself, the way the
reference site's own footage is shot and graded. Anything added here to rescue it
is a veil by another name, and has already been asked for and removed once.

**Portrait shows about a quarter of the frame.** Cropping a 16:9 clip into a phone
screen leaves roughly 27% of the clip's width — the jar, and none of the
greenhouse. That is accepted, not an oversight.

**`width:100%` on `.hero__in` is load-bearing.** `.g` carries `margin-inline:auto`,
an auto cross-axis margin switches off stretch for a flex item, and `.hero` is a
column flex container — so without it the grid shrinks to its content, the 22 `1fr`
columns collapse and the copy renders a few pixels wide against the left edge. It
looked like the copy had vanished entirely. The same trap bit the earlier banded
layout.

**Anything in the hero that must sit above the film needs `position` and a
z-index.** `.hero__panel` is absolutely positioned with `z-index:0`, and positioned
elements paint above the inline content of static ones — so static copy disappears
behind the video with no warning and no error.

**The hero film plays once; do not put `loop` back on it.** Measured frame by
frame, the cut from the last frame to the first is a bigger jump (38 mean RGB
delta) than any movement inside the clip (31), so looping it snaps visibly every
eight seconds. It plays through and settles on its final frame, which is the
strongest still in the clip — the jar with a tomato beside it.

**It plays for everyone, including `prefers-reduced-motion`.** That is a
deliberate instruction from the owner, not an oversight; the guard is gone from
`main.js` and the spot where it belongs is commented. Note that this repo's
preview pane reports `reduce`, so anything keyed to it silently changes behaviour
in testing only.

**A resolved `play()` is not proof of playback.** The preview pane hands back a
promise that settles cleanly and then holds the clock at zero until the page gets
a real click — a scroll will not do it, because scrolling is not user activation
for media. So the retry is armed by checking `film.paused` on a timer rather than
by catching a rejection that never comes. Autoplay failing in the pane says
nothing about a real browser, where `autoplay muted playsinline` is permitted.

**`body { overflow-x: clip }` — never `hidden`.** `hidden` silently forces
`overflow-y` to `auto`, which makes `body` the scroll container. Window scroll
events then stop firing entirely, and the scroll-driven "field to bottle" section
freezes on step one with no error anywhere.

**`setLang()` runs at the very bottom of `main.js`.** It was once called near the
top, where it touched variables that had not been assigned yet. The resulting
throw killed the rest of the file — product filter, tabs, both carousels and the
newsletter all stopped working, with nothing visible on screen to say so.

**The card rail uses `scroll-snap-type: x proximity`, not `mandatory`.** Mandatory
snap overrides programmatic scrolling, so the arrow buttons bounce back and the
counter jumps in the wrong direction. It also needs `scroll-padding-left` equal to
the gutter, or the rail rests at a non-zero `scrollLeft` and every index
calculation is off by one gutter.

**The rail arrows tween `scrollLeft` by hand, with a `setTimeout` fallback.**
`scrollTo({behavior:'smooth'})` on a snapping overflow container is unreliable, and
`requestAnimationFrame` stops entirely when the tab is backgrounded or the host
pauses compositing. The timeout lands the scroll regardless.

**Sticky offsets are variables, not the number 78.** The announcement strip opens
on scroll and changes the height of the sticky stack. `--hdr-h` is the header
alone and stays fixed so the hero never reflows; `--topbar-h` is measured in JS and
is what the pinned section aligns to.

**The pinned section has three fallbacks** — rAF, `scroll`, `scrollend` — because
mobile browsers coalesce or drop scroll events during momentum scrolling.

## Verifying changes

The preview pane in this environment intermittently stops compositing, which
starves `requestAnimationFrame` and suppresses scroll events. When that happens,
anything animation-driven appears broken and is not. Check `requestAnimationFrame`
is actually ticking before concluding a scroll behaviour is faulty — and prefer
verifying by computing what the driver *should* pick and comparing it to the DOM,
which isolates logic errors from a starved environment.
