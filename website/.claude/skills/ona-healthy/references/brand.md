# ONA Healthy — visual system

Derived from the farm's actual retail space: white arched shelving, white product
boxes, pale wood floor, tomatoes and green leaves appearing as small points of
colour in all that white. Everything below follows from that photograph. When a
choice is unclear, look at what the shop itself does.

## Colour

| Token | Hex | Use |
|---|---|---|
| ground | `#FAF8F4` | page / sheet background — warm off-white, never pure white |
| card | `#FFFFFF` | cards and panels sitting on the ground, giving a layer of depth |
| tint | `#F7F4EF` | product tiles — one single shade for every tile, no variation |
| band | `#F2EEE8` | alternate section fill |
| ink | `#2E2B28` | headings, body, buttons — soft charcoal, never pure black |
| ink-2 | `#67635C` | secondary text |
| ink-3 | `#6F6960` | captions, small labels |
| tomato | `#B53426` | UI red — badges, small marks, active underlines |
| tomato-img | `#D8402F` | the fruit itself, inside illustration or artwork only |
| tomato-wash | `#F7E7E3` | soft pink behind a red badge |
| vine | `#3F7A4E` | leaves, small marks |
| oak | `#8C6C47` | pale-wood neutral from the shop floor; large decorative numerals |
| line | `#EAE5DD` | hairlines |
| noir | `#2E2B28` | the one dark block on the page — footer, announcement strip |

Darker variants exist for artwork only: `--tomato-d #8E2A1F`, `--vine-d #2F5C3B`.

**The ratio matters more than the hex values.** Roughly 84% white, 10% neutral,
4% red, 2% green. In the shop, red is a handful of tomatoes against an entire wall
of white. On screen and in print, a flat red rectangle has none of the light,
shadow and gloss that makes a real tomato look rich — it just reads as a sale
sticker. So: **buttons are charcoal, not red.** Red is allowed on badges, a price
that has been reduced, a 3px active underline, the dot in the logo, and inside
artwork. It is never the background of a large block.

Avoid entirely: gold, gradients of any kind, and olive green. All three were tried
and all three pulled the brand toward "rustic heritage farm" when the actual brand
is bright, clean and closer to Korean clean-beauty.

## Type

Two pairs, because Playfair Display and Poppins carry no Thai glyphs:

| Role | Thai | English |
|---|---|---|
| Display / headings | Trirong, weight 200–300 | Playfair Display, weight 400 |
| Body | IBM Plex Sans Thai | Poppins, weight 300–400 |
| Wordmark | Playfair Display | Playfair Display |
| Uppercase labels | Poppins, weight 500, tracking `0.24em` | same |
| Figures | IBM Plex Mono, tabular | same |

The wordmark and the uppercase labels are Latin in both languages, so they keep
the Playfair/Poppins pairing regardless of which language is showing.

The uppercase-label treatment is the signature: wide-tracked, small, quiet, the
way `ORGANIC SKINCARE` sits under a serif wordmark on a brand board. Use it for
eyebrows and category kickers, not for anything long.

Thai display type needs care at large sizes. Thai breaks at syllable boundaries,
which splits compound words mid-word — `สกัด|เอง` — and looks broken at 80px. Wrap
words that must stay whole in a nowrap span. Thai also needs more line-height than
Latin for tone marks: 1.2 minimum on display sizes, and avoid negative tracking.

## Form

**The arch.** The shop's shelving is arch-topped. Reusing that silhouette on
product tiles ties any piece back to the physical space, and it is genuinely the
brand's own shape rather than a borrowed trend. On the web:
`border-radius: 999px 999px 14px 14px`.

**Frame, don't bleed.** Tinted blocks sit inset from the edge — 24px on desktop,
12px on a phone — with a 12px radius, so the ground runs continuously down both
sides. Content inside aligns to the same 64px measure as everything else. This is
what stops a layout feeling wall-to-wall.

**Shadow, not stroke.** A 1px border makes white look flat and cheap; a wide, soft,
low-opacity shadow makes it look expensive. Two levels: a barely-there resting
shadow, and a deeper one on hover.

**Light only.** No dark mode. The brand's identity is a white room; a dark palette
would misrepresent it, and half the audience would never see the real thing.

## Voice

Plain and specific. The farm has real evidence, so copy does not need to reach.

- Prefer a fact to an adjective. "10 kcal a bottle" beats "guilt-free".
- Name the proof: FDA, Q mark, OTOP, the Provincial Star year, eight years trading.
- Say what is actually true about process. "Insect netting instead of pesticides"
  is more persuasive than "natural" because it can be checked.
- Do not promise services the farm has not confirmed. Mark proposals as proposals.
- Thai copy is warm but not chatty. English copy is quiet and confident — closer
  to Aesop than to a supplement ad.

### The register: what we make, not what it does

**Decided by the owner, Sep 2026, after a scan of five health brands.** ONA Healthy
speaks in the maker's register — verbs of work, done by us, on this land. Health
outcomes are not the sales argument and mostly should not appear at all.

**What the scan found.** Not one of the five sells a benefit:

| Brand | Their words | Where their authority comes from |
|---|---|---|
| โอ้กะจู๋ | "ปลูกผักเพราะรักแม่" · clean enough to cook for your own mother | a person you love |
| ดอยคำ | "ห่วงใยสุขภาพคุณ" · "กำไรกลับคืนสู่เกษตรกรและสังคม" | the royal project, and farmers' livelihoods |
| Patom | "involved in the entire process" · "small batches" · "honest, responsible and traceable" | owning every step, plus IFOAM |
| อภัยภูเบศร | "trustworthy, meet international production standards" | being a hospital foundation |
| Weleda | "medicinal plants of our own gardens" · "sustainability is part of our roots" | their own gardens, and a century of doing it |

Every one of them answers *why should I trust you*, never *what will this do for
me*. ONA has no king, no hospital and no IFOAM — its answer is **one family, one
piece of land, nothing outsourced**, backed by marks that can be checked.

**The pricing constraint that settles the argument.** Doi Kham sells 100% tomato
juice at 200 ml for 20–85 THB. ONA sells 75 ml for 50. Per millilitre ONA is
roughly four to eight times dearer, so value language is unavailable — there is no
version of "คุ้มค่า" that survives the comparison. Every word has to earn the gap
instead, and craft, provenance and scarcity are the only things that can.

**The brand is meant to read as expensive. That is why the word "premium" is
banned, not despite it.** Weleda, Aesop and Patom all look costly and not one of
them says so; the word itself is a downmarket signal, because a brand that has to
claim the position does not hold it. Expense is read off restraint and specificity
instead — "บ่มสองปี ทำทีละก้อน" prices higher than "คุณภาพพรีเมียม", because the
first is a cost someone actually paid and the second is a word anyone can type.
The admission that the family can only make so much is the strongest premium
signal available here: scarce things are dear.

**Benefits belong on the page. Inflated ones do not.** Stripping every benefit is
its own dishonesty — a reader who cannot tell what a product is for has been
under-served, and this site over-corrected into that once. The line to hold:

> **A benefit the customer can check for themselves is sincere. A benefit only the
> brand can assert is advertising.**

| Inflated — drop | Checkable — use |
|---|---|
| บำรุงล้ำลึก | ซึมเร็ว ไม่เหนียวเหนอะหนะ |
| ผิวขาวกระจ่างใส | ไม่ทิ้งคราบขาว ใช้น้อยก็ทั่วหน้า |
| มหัศจรรย์ | หนึ่งเม็ดเท่ามะเขือเทศ 20 ผล |
| คุณภาพพรีเมียม | ตัดทีละก้อน บ่มสองปี |

A buyer settles "ซึมเร็ว ไม่เหนียว" in five seconds. Nobody can settle "ผิวขาว
กระจ่างใส", which is also where the cosmetic claim starts shading into a medical
one.

**The strongest form of all is a customer's own words.** A real review states the
benefit without the brand claiming anything, which is simultaneously the most
sincere, the most premium and the safest position — `business.md` holds six of
them, attributed and quotable.

**Write the plain label, not the clever line.** A whole pass of headings on the
knowledge page had to be thrown out for being too written. Three failures worth
naming, because each looks fine on the page and lands wrong on a reader:

- **The pharmacy register.** "สารไหนอยู่ในขวด สารไหนอยู่ในเม็ด" and "น้ำกับเม็ด
  ไม่ใช่อย่างเดียวกัน" both read as narcotics — the owner's word was ยาเสพติด.
  Thai talk of a สาร arriving as a น้ำ or a เม็ด is drug talk. This is food. Say
  "ในมะเขือเทศมีอะไรบ้าง" and "เลือกแบบไหนให้เหมาะกับคุณ".
- **Never headline what is being withheld.** "สรรพคุณที่เราเลือกจะไม่พูดถึง" was
  meant to sound principled and instead makes a reader ask what is being hidden.
  The disclaimer is still needed, so lead with the care rather than the omission:
  "ถ้าคุณกำลังดูแลโรคประจำตัวอยู่ … เราปลูกมะเขือเทศ ไม่ได้เป็นหมอ". Same legal
  cover, opposite feeling.
- **Say the necessary thing in the place it belongs.** The family-scale limit was
  headed "สิ่งที่เราทำไม่ได้", which turns a delivery note into a confession.
  It is ordering information. Head it "ก่อนสั่งซื้อ" and write it as service.

### ระดับภาษา — the register, named properly

**Thai copy is written at ระดับกึ่งทางการ, leaning slightly toward ทางการ.**
Decided by the owner, Sep 2026, and it is the setting that reads refined and
costly while staying approachable. ไม่เป็นทางการ reads cheap on this brand; full
ทางการ reads like a government notice.

Thai has five recognised levels — พิธีการ, ทางการ, กึ่งทางการ, ไม่เป็นทางการ,
กันเอง. กึ่งทางการ keeps the complete sentences and the politeness of ทางการ but
uses everyday vocabulary and simpler sentence structure; it is the register of business writing
and of talking to someone you respect but do not know.

**Markers that drop the copy into ไม่เป็นทางการ — none of these belong on the
site:**

| Drop | Use |
|---|---|
| ...ได้เลย · นะครับ · จริง ๆ · ก็เหมือน | complete sentence, no closing particle |
| ทักมา | สอบถาม · ติดต่อ |
| ไหว ("เท่าที่มือเราไหว") | ตามกำลังที่มี |
| หมอ | แพทย์ |
| กิน | รับประทาน |
| คนอื่น | ผู้อื่น |
| ...ไหน (รอบไหน, ขั้นตอนไหน) | ...ใด (รอบใด, ขั้นตอนใด) |
| ถ้า | หาก |
| เอามาล้าง · ทำเอง (in body copy) | การล้าง · ดำเนินการเอง |

Two cautions from the pass that applied this. **Do not overshoot into ทางการ** —
ดำเนินการ, ทั้งนี้, อนึ่ง, มิได้ turn a farm into a ministry. And **ของฝาก,
ของจริง, แบบไหน are ordinary Thai**, not slang; a scanner that flags them is
producing noise. The same scanner will flag จ้า inside จ้าง, so read every hit
before acting on one.

English is a separate decision and does not move with this: it stays quiet and
confident, closer to Aesop than to a corporate report.

**Plain has a floor as well as a ceiling.** Correcting the clever headings
overshot straight into blunt ones, and blunt reads cheap on a brand that is meant
to read expensive. "ของกิน และของทาผิว" is accurate and sounds like a market stall.
"คนที่ตรวจ ไม่ใช่พวกเราเอง" answers an accusation nobody made, so it reads
defensive — a brand that is sure of itself states the fact and offers the evidence:
"ผ่านการตรวจ และมีเลขให้ตรวจซ้ำได้". Money in a headline has the same problem;
"ทุกอย่างที่คุณจ่ายเงินซื้อ" became "ทุกอย่างเกิดขึ้นบนที่ดินผืนนี้", which says the
same thing and keeps its dignity.

The register sits between the two failures: **plain, warm, and sure of itself.**
Not written, not curt, never defensive.

The test to apply: would a shop assistant say this sentence out loud to a customer
standing in front of them? "เลือกแบบไหนให้เหมาะกับคุณ" yes. "น้ำกับเม็ด ไม่ใช่
อย่างเดียวกัน" no.

**Read every line back looking for the opposite meaning.** Thai gives short
headlines two readings more often than English does, and the maker's register runs
straight into it. "ไม่มีขั้นตอนไหนออกจากมือเรา" shipped for a day meaning to say
*no step is handed to anyone else*, and parses just as easily as *no step ever
comes out of our hands* — the exact opposite, and the reading a stranger lands on
first. It became "ทุกขั้นตอน เราทำเอง".

Three traps found in one pass on the knowledge page, all worth checking for again:

- **A verb that faces both ways.** ออกจาก, ผ่าน, ปล่อย. Name the actor instead:
  "เราทำเอง", "ไม่ได้จ้างใครทำ".
- **A negative that sounds like a defect.** "อะไรหายไปตอนไหน" was written about
  fibre lost in pressing and reads as *our product is missing something*. Rewritten
  to "สารไหนอยู่ในขวด สารไหนอยู่ในเม็ด", which steers the choice instead of
  planting doubt.
- **Claiming more than is true, by accident.** The opening said "ทำด้วยมือเราเอง"
  when the press is machinery. Handmade is true of the soap and nothing else; say
  "เราทำเอง" for the process and save "ทำด้วยมือ" for the bar of soap.

**Words to use:** ปลูกเอง · สกัดเอง · บ่ม · ทีละก้อน · บนที่ดินผืนเดียว ·
ตั้งแต่เมล็ดจนถึงฝาขวด · รอบเก็บเกี่ยว · ตรวจสอบย้อนกลับได้ · เท่าที่ทำไหว

**Words to drop:** พรีเมียม · ที่สุด · มหัศจรรย์ · ปลอดภัย 100% · บำรุงล้ำลึก ·
คุ้มค่า · นวัตกรรม (unless something real backs it)

**A benefit heading is usually also a legal problem.** "หัวใจและหลอดเลือด" and
"ควบคุมน้ำหนัก" were section headings on this site until this pass; both are health
claims on a page that sells food. Rewriting them into the maker's register fixed
the voice and the compliance exposure in the same edit. Expect that to keep
happening — if a heading names a body part or an outcome, it is probably both
off-voice and off-side.

**Known and deliberately unused.** The owner has a health qualification and runs
continuous research — tomato varieties, the properties of each, how to make them
easiest to consume. Told to us Sep 2026 and explicitly asked to stay off the site.
Do not put it in a deliverable. It is recorded here only so nobody "discovers" it
later and helpfully writes it up.

### Sincerity, and where it actually comes from

Checked against Ohkajhu (โอ้กะจู๋), the closest Thai comparison — an organic farm
brand built on the same shape of story. Their holding company is literally named
**"ปลูกผักเพราะรักแม่"**: we grow vegetables because we love our mother. The
standard they sell is not a certificate, it is *clean enough that I would cook it
for my own mum*. The brand name itself is a spoonerism of the two founders'
nicknames. Nowhere do they list health benefits.

Three things to take from that, all of which apply here:

1. **Measure the standard against a person, not a document.** ONA Healthy's
   equivalent is already true and was going unsaid: one family does every step on
   one piece of land, and nothing is outsourced. Lead with that rather than with
   what a page contains.
2. **First person.** "เราปลูกเอง" not "ทางสวนปลูก". Writing about the farm in the
   third person on the farm's own site reads like a press release.
3. **The unglamorous specific earns more trust than the polished one.** The press
   runs at night because power is cheaper. Production is family-scale and runs out
   when orders arrive together. A bar of soap cures for weeks and cannot be
   hurried. None of that flatters the business, which is exactly why it is
   believed — and all of it is in `business.md` already.

**Admitting a limit is the strongest move available to this brand.** The knowledge
page ends on a section headed "สิ่งที่เราทำไม่ได้" that says plainly they are not a
factory and orders sometimes have to wait. A brand with certificates and no
admitted limits reads like every supplement ad; a brand that names its ceiling
reads like someone telling the truth. Do not quietly polish these out.
