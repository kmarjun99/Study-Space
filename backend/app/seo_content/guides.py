"""Seed long-form guides — citation-grade content for AEO / GEO.

These are deliberately structured for AI extraction:
  - TL;DR in the first 50 words (Answer Overviews quote this verbatim).
  - Quick-facts callout with numbers AI loves to cite.
  - H2 sections, each with a one-sentence answer up front.
  - Comparison tables where applicable.
  - 12–20 FAQs at the bottom, each ≤ 2 sentences.

Pure Python data so the same content powers both the Jinja2 server-rendered
page AND, eventually, a JSON API consumed by the React app. No DB
dependency — guides are part of the editorial pipeline, not user data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GuideSection:
    heading: str
    paragraphs: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    lead: Optional[str] = None
    table: Optional[dict] = None  # {"headers": [...], "rows": [[...], [...]]}


@dataclass
class GuideFAQ:
    question: str
    answer: str


@dataclass
class Guide:
    slug: str
    title: str
    description: str            # meta description, ≤ 160 chars
    tldr: str                    # one-paragraph summary (this becomes the AI overview citation)
    category: str               # editorial category, drives /guides hub grouping
    keywords: list[str]
    date_published: str
    date_modified: str
    read_time: int
    quick_stats: list[str] = field(default_factory=list)
    sections: list[GuideSection] = field(default_factory=list)
    faqs: list[GuideFAQ] = field(default_factory=list)


# ---------------------------------------------------------------- 10 seeds

GUIDES: dict[str, Guide] = {}


def _add(g: Guide) -> None:
    GUIDES[g.slug] = g


# --- 1. Best reading rooms in Kerala -------------------------------------
_add(Guide(
    slug="best-reading-rooms-in-kerala",
    title="Best Reading Rooms in Kerala — A 2026 Guide",
    description="A complete 2026 guide to reading rooms in Kerala — prices, top areas, what to look for, and how to book online across 14 districts.",
    tldr=(
        "Kerala has the strongest reading-room culture in India. A typical "
        "reading room in Trivandrum or Kochi costs ₹1,500–₹3,000 per month "
        "for a shared seat, ₹2,500–₹5,000 for a private cabin. The best "
        "options cluster around Technopark, Kakkanad, and Medical College "
        "areas. This guide covers every district, what to look for, and "
        "how to book on mySpace."
    ),
    category="reading-rooms",
    keywords=["reading rooms kerala", "best reading room kerala", "study cabin kerala",
              "UPSC reading room kerala", "library kerala"],
    date_published="2026-01-15",
    date_modified="2026-05-29",
    read_time=8,
    quick_stats=[
        "Districts covered on mySpace: 14 of 14",
        "Typical shared-seat price: ₹1,500–₹3,000/month",
        "Typical private cabin price: ₹2,500–₹5,000/month",
        "24-hour reading rooms available in: Trivandrum, Kochi, Kozhikode",
    ],
    sections=[
        GuideSection(
            heading="Why reading rooms matter in Kerala",
            paragraphs=[
                "Kerala has the highest density of competitive-exam aspirants in India per capita. PSC, UPSC, banking, SSC, and university aspirants all rely on dedicated reading rooms as their default study environment.",
                "Most reading rooms offer dedicated seats (allotted to one person for the month), lockers, AC or fan, Wi-Fi, and 12-to-16 hour access. Premium spaces extend to 24-hour access and provide private cabins.",
            ],
        ),
        GuideSection(
            heading="Trivandrum — the PSC capital",
            lead="Trivandrum has the deepest reading-room market in Kerala, with major clusters at Pattom, Vazhuthacaud, and Statue.",
            paragraphs=[
                "If you're preparing for Kerala PSC, Trivandrum is the obvious choice. The Pattom area alone has more than 30 reading rooms, many within walking distance of coaching institutes.",
                "Technopark Phase 1 and Kazhakkoottam have an emerging working-professional reading-room market — open-plan study spaces with high-speed Wi-Fi, suitable for remote-work or hybrid prep.",
            ],
            bullets=[
                '<a href="/reading-rooms/trivandrum/pattom">Pattom</a> — PSC heartland, ₹1,500–₹2,500/mo',
                '<a href="/reading-rooms/trivandrum/vazhuthacaud">Vazhuthacaud</a> — coaching cluster, ₹2,000–₹3,000/mo',
                '<a href="/reading-rooms/trivandrum/technopark">Technopark</a> — working pros, ₹2,500–₹4,500/mo',
                '<a href="/reading-rooms/trivandrum/medical-college">Medical College</a> — long hours, ₹1,800–₹2,800/mo',
            ],
        ),
        GuideSection(
            heading="Kochi — the all-rounder",
            lead="Kochi covers everyone from UPSC aspirants to working professionals to MBA candidates.",
            paragraphs=[
                "Kakkanad has emerged as Kochi's primary reading-room hub. Infopark proximity attracts a mix of IT professionals and bank-exam aspirants. Edappally is the second cluster, denser and closer to the city centre.",
                "Marine Drive and Fort Kochi are pricier (₹3,000+) but offer quieter, more boutique reading rooms suited to long-form study.",
            ],
            bullets=[
                '<a href="/reading-rooms/kochi/kakkanad">Kakkanad</a> — Infopark adjacency, ₹2,000–₹3,500/mo',
                '<a href="/reading-rooms/kochi/edappally">Edappally</a> — densest cluster, ₹1,800–₹3,000/mo',
                '<a href="/reading-rooms/kochi/marine-drive">Marine Drive</a> — premium boutique, ₹3,000+/mo',
                '<a href="/reading-rooms/kochi/aluva">Aluva</a> — affordable, ₹1,500–₹2,500/mo',
            ],
        ),
        GuideSection(
            heading="District-by-district price snapshot",
            table={
                "headers": ["District", "Shared seat (₹/mo)", "Private cabin (₹/mo)", "Notes"],
                "rows": [
                    ["Trivandrum", "1,500–3,000", "2,500–5,000", "PSC capital; deepest supply"],
                    ["Kochi (Ernakulam)", "1,800–3,500", "3,000–5,500", "Best for working pros + students"],
                    ["Kollam", "1,200–2,200", "2,000–3,500", "Affordable, smaller market"],
                    ["Kottayam", "1,500–2,500", "2,200–3,800", "MBA + medical aspirants"],
                    ["Thrissur", "1,400–2,800", "2,300–4,000", "Coaching-led market"],
                    ["Kozhikode", "1,500–2,800", "2,500–4,200", "Growing IT cluster"],
                    ["Malappuram", "1,200–2,200", "2,000–3,500", "Gulf-returnee demand"],
                    ["Palakkad", "1,200–2,000", "1,800–3,200", "Engineering colleges"],
                ],
            },
        ),
        GuideSection(
            heading="What to look for when picking a reading room",
            bullets=[
                "<strong>Dedicated vs. shared seat:</strong> dedicated lets you leave books overnight; shared rotates.",
                "<strong>Hours:</strong> 12-hour, 16-hour, and 24-hour options exist. UPSC prep usually needs 16h+.",
                "<strong>AC vs. fan:</strong> AC adds ₹500–₹1,000/mo. Worth it in Trivandrum/Kochi summer.",
                "<strong>Locker:</strong> non-negotiable for serious prep. Confirm before paying.",
                "<strong>Wi-Fi:</strong> required for online classes and PDF resources.",
                "<strong>Distance:</strong> ≤ 15 minutes from home is the realistic upper bound for daily commute.",
            ],
        ),
        GuideSection(
            heading="How to book on mySpace",
            paragraphs=[
                "Open the city page (e.g. <a href='/reading-rooms/trivandrum'>Trivandrum</a>), filter by locality, price, and amenities, then book online with instant confirmation. Most listings allow a visit first if you prefer.",
                "Owners are verified for identity and address. Prices on mySpace are GST-inclusive — no hidden fees at checkout.",
            ],
        ),
    ],
    faqs=[
        GuideFAQ(
            question="What is the cheapest reading room in Kerala?",
            answer="Cheap shared seats start around ₹1,200/month in Kollam, Palakkad, and Malappuram. Trivandrum and Kochi entry prices begin at ₹1,500/month.",
        ),
        GuideFAQ(
            question="Are 24-hour reading rooms common in Kerala?",
            answer="They're available but not the default. Trivandrum (Pattom, Statue), Kochi (Kakkanad, Edappally), and Kozhikode have the most options. Expect to pay ₹500–₹1,000 more per month for 24h access.",
        ),
        GuideFAQ(
            question="Do reading rooms in Kerala have AC?",
            answer="Mid-range and premium rooms do. Budget rooms typically have fans only. AC adds ₹500–₹1,000 to the monthly fee.",
        ),
        GuideFAQ(
            question="Which area is best for UPSC preparation in Kerala?",
            answer="Trivandrum (Pattom, Vazhuthacaud) and Kochi (Kakkanad, Edappally) have the densest UPSC ecosystems with coaching, libraries, and reading rooms together.",
        ),
        GuideFAQ(
            question="Can I book a reading room online without visiting first?",
            answer="Yes. Most mySpace listings accept online booking with instant confirmation. If you prefer to visit, use the 'Contact owner' button to schedule a tour.",
        ),
        GuideFAQ(
            question="Are reading rooms different from libraries?",
            answer="Yes. Libraries lend books; reading rooms rent you a seat. Reading rooms are commercial, monthly-paid spaces designed for long study sessions with lockers, Wi-Fi, and amenities.",
        ),
    ],
))


# --- 2. Cost of PGs in Bangalore -----------------------------------------
_add(Guide(
    slug="cost-of-pgs-in-bangalore",
    title="Cost of PGs in Bangalore — 2026 Price Guide by Area",
    description="What does a PG in Bangalore cost in 2026? Area-by-area pricing for Whitefield, Koramangala, HSR, Electronic City and 12 more — with what's included.",
    tldr=(
        "A PG room in Bangalore costs between ₹6,000 and ₹25,000 per month "
        "in 2026, depending on area, sharing type, and food inclusion. "
        "Whitefield, Koramangala, and HSR Layout are the priciest. "
        "Electronic City and Marathahalli are the value picks. AC, food, "
        "and laundry typically add ₹1,500–₹4,000."
    ),
    category="pgs",
    keywords=["pg bangalore cost", "pg price bangalore", "cheap pg bangalore",
              "pg koramangala price", "pg whitefield price"],
    date_published="2026-02-01",
    date_modified="2026-05-29",
    read_time=6,
    quick_stats=[
        "Entry-level shared PG: ₹6,000–₹9,000/month",
        "Mid-range PG with food: ₹10,000–₹14,000/month",
        "Premium PG (single + AC + food): ₹18,000–₹25,000/month",
        "Cheapest areas: Electronic City, Marathahalli, BTM Layout",
        "Priciest areas: Koramangala, Indiranagar, HSR Layout",
    ],
    sections=[
        GuideSection(
            heading="What goes into a PG price?",
            bullets=[
                "<strong>Area</strong> — proximity to tech parks adds 30–50%",
                "<strong>Sharing</strong> — single is 1.6–2× the price of triple-sharing",
                "<strong>AC</strong> — adds ₹1,500–₹3,000/month",
                "<strong>Food</strong> — typically adds ₹2,500–₹4,000/month",
                "<strong>Gender</strong> — girls' PGs are usually 5–10% pricier",
            ],
        ),
        GuideSection(
            heading="Bangalore PG price map (2026)",
            table={
                "headers": ["Area", "Triple-sharing (₹/mo)", "Single room (₹/mo)", "Best for"],
                "rows": [
                    ["Koramangala", "10,000–14,000", "20,000–28,000", "Startups, foodies"],
                    ["Indiranagar", "9,000–13,000", "18,000–25,000", "Working pros"],
                    ["HSR Layout", "9,000–13,000", "17,000–24,000", "Engineering crowd"],
                    ["BTM Layout", "7,000–10,000", "14,000–20,000", "Students + early-career"],
                    ["Whitefield", "9,000–12,000", "16,000–22,000", "IT corridor workers"],
                    ["Marathahalli", "7,500–11,000", "14,000–20,000", "Outer Ring Road IT"],
                    ["Electronic City", "6,000–9,000", "12,000–18,000", "Affordable IT proximity"],
                    ["KR Puram", "6,500–9,500", "12,500–18,000", "Whitefield commute"],
                    ["Bellandur", "8,500–12,000", "15,000–22,000", "OR R hubs"],
                ],
            },
        ),
        GuideSection(
            heading="What's typically included",
            bullets=[
                "Bed + mattress + locker",
                "Wi-Fi, hot water, attached/common bathroom",
                "Power backup (most mid-range and above)",
                "Housekeeping 2–3× per week",
                "Optional: 2 meals/day, AC, laundry (each adds to monthly cost)",
            ],
        ),
        GuideSection(
            heading="Hidden costs to watch for",
            paragraphs=[
                "Deposit: 1–2 months' rent. Refundable on smooth exit; partial deductions for damage.",
                "Maintenance: some PGs add ₹500–₹1,000/mo for upkeep. Confirm before paying.",
                "Move-out notice: typically 30 days. Failing to give notice = lost deposit.",
            ],
        ),
        GuideSection(
            heading="How to find the right PG quickly",
            paragraphs=[
                "Decide your sharing type and budget first. Then filter by area on <a href='/pgs/bangalore'>mySpace Bangalore PGs</a>. Visit two before paying — photos lie.",
            ],
        ),
    ],
    faqs=[
        GuideFAQ(
            question="What is the cheapest PG in Bangalore?",
            answer="Triple-sharing PGs in Electronic City, Marathahalli, and KR Puram start around ₹6,000/month. Adding meals brings the total to ~₹9,500.",
        ),
        GuideFAQ(
            question="Is food included in Bangalore PG rent?",
            answer="Not by default. Food is usually an optional add-on costing ₹2,500–₹4,000/month for 2 meals/day.",
        ),
        GuideFAQ(
            question="Do PGs in Bangalore charge GST?",
            answer="Residential PGs charging ≤ ₹20,000/month/person are GST-exempt. Premium PGs above that, or hotel-style stays, attract 12–18% GST.",
        ),
        GuideFAQ(
            question="How much deposit do Bangalore PGs ask for?",
            answer="1–2 months' rent is standard. Premium PGs sometimes ask 3 months. The deposit is refundable on smooth exit.",
        ),
        GuideFAQ(
            question="Are girls' PGs more expensive than boys' PGs in Bangalore?",
            answer="Typically 5–10% more, due to additional security and segregated facilities. The price range tracks the area more than the gender.",
        ),
    ],
))


# --- 3. PG vs Hostel comparison ------------------------------------------
_add(Guide(
    slug="pg-vs-hostel",
    title="PG vs Hostel — Which is Better for Students and Young Professionals?",
    description="PGs vs hostels: pricing, privacy, food, rules, deposits, and which is better for students vs working professionals. A practical 2026 comparison.",
    tldr=(
        "A PG (Paying Guest) is a small, home-like rental with 2–4 rooms; "
        "a hostel is a larger commercial property with 20+ beds. PGs are "
        "quieter and more flexible. Hostels are cheaper and more social. "
        "Students typically prefer hostels; working professionals usually "
        "go for PGs."
    ),
    category="comparisons",
    keywords=["pg vs hostel", "difference between pg and hostel",
              "hostel or pg which is better", "pg or hostel"],
    date_published="2026-02-15",
    date_modified="2026-05-29",
    read_time=5,
    sections=[
        GuideSection(
            heading="The core difference",
            paragraphs=[
                "A PG is essentially a residential house converted into a rental. A hostel is built as a hostel — larger, more rooms, more residents, more rules.",
                "PGs feel like living in someone's home (often the owner lives downstairs). Hostels feel like a hotel or college dorm.",
            ],
        ),
        GuideSection(
            heading="Side-by-side",
            table={
                "headers": ["Aspect", "PG", "Hostel"],
                "rows": [
                    ["Typical size", "2–8 rooms", "20+ beds"],
                    ["Privacy", "Higher", "Lower"],
                    ["Rules", "Owner-set, flexible", "Standardised, strict"],
                    ["Food", "Home-style, often included", "Mess-style, often included"],
                    ["Price (Bangalore)", "₹8,000–₹20,000", "₹6,000–₹12,000"],
                    ["Best for", "Working professionals, postgrad", "Undergrads, exam aspirants"],
                    ["Deposit", "1–2 months", "1 month"],
                    ["Notice period", "30 days", "15–30 days"],
                ],
            },
        ),
        GuideSection(
            heading="When to pick a PG",
            bullets=[
                "You're a working professional with a steady income",
                "You want home-style food",
                "You value quiet and privacy",
                "You're staying 6+ months",
            ],
        ),
        GuideSection(
            heading="When to pick a hostel",
            bullets=[
                "You're a student, esp. exam aspirant or undergrad",
                "You want the lowest possible monthly cost",
                "You prefer a social environment",
                "You're staying short-term (≤ 6 months)",
            ],
        ),
    ],
    faqs=[
        GuideFAQ(question="Is a PG cheaper than a hostel?",
                 answer="No. Hostels are typically 20–30% cheaper per bed because they spread fixed costs across more residents."),
        GuideFAQ(question="Can working professionals stay in hostels?",
                 answer="Yes — many hostels now have working-professional floors with stricter quiet hours and faster Wi-Fi."),
        GuideFAQ(question="Do PGs allow couples?",
                 answer="Most don't, especially in conservative neighborhoods. Co-living spaces and rental houses are better for couples."),
        GuideFAQ(question="Are PG owners obligated to give a rent receipt?",
                 answer="Yes, on request, especially if rent ≥ ₹3,000/month (required for HRA tax claims)."),
    ],
))


# --- 4. Reading Room vs Library ------------------------------------------
_add(Guide(
    slug="reading-room-vs-library",
    title="Reading Room vs Library — Which Should You Choose?",
    description="The practical difference between a reading room and a library — purpose, cost, hours, environment, and what each is better for.",
    tldr=(
        "Libraries lend you books; reading rooms rent you a seat. Libraries "
        "are free or near-free, public, and have limited hours. Reading "
        "rooms are paid, private, and built for long focused study with "
        "lockers, Wi-Fi, and AC. For exam prep, a reading room almost "
        "always wins."
    ),
    category="comparisons",
    keywords=["reading room vs library", "library or reading room",
              "difference between library and reading room"],
    date_published="2026-02-20",
    date_modified="2026-05-29",
    read_time=4,
    sections=[
        GuideSection(
            heading="What each is for",
            paragraphs=[
                "Libraries exist to lend books and other materials. Their seating is incidental — a place to read books before borrowing them.",
                "Reading rooms exist to rent you a study seat. Books are usually your own; the room provides the environment.",
            ],
        ),
        GuideSection(
            heading="Side-by-side",
            table={
                "headers": ["Aspect", "Library", "Reading Room"],
                "rows": [
                    ["Cost", "₹0–₹100/year (public) or ₹200–₹500/year (subscription)", "₹1,500–₹5,000/month"],
                    ["Hours", "Usually 9 AM–8 PM", "12–24 hours (often 24)"],
                    ["Personal locker", "No", "Yes"],
                    ["Wi-Fi", "Sometimes", "Always"],
                    ["AC", "Sometimes", "Common"],
                    ["Crowd", "Variable", "Curated (aspirants only)"],
                    ["Best for", "Borrowing books, casual reading", "Long, focused study"],
                ],
            },
        ),
        GuideSection(
            heading="When a library is enough",
            bullets=[
                "You just need to borrow books",
                "Your study session is ≤ 3 hours/day",
                "You don't need a dedicated seat",
                "You're not preparing for a long exam (UPSC/PSC/CAT)",
            ],
        ),
        GuideSection(
            heading="When a reading room is worth the cost",
            bullets=[
                "You study 6+ hours daily",
                "You want a fixed seat with your books left behind",
                "You need 24-hour or late-night access",
                "You're preparing for a competitive exam over 6–12 months",
            ],
        ),
    ],
    faqs=[
        GuideFAQ(question="Are reading rooms in India free?",
                 answer="No. They're commercial monthly subscriptions. Public libraries are free or near-free but offer different services."),
        GuideFAQ(question="Can I bring my own books to a reading room?",
                 answer="Yes — that's the default expectation. Most aspirants bring their own materials."),
        GuideFAQ(question="Do libraries have 24-hour access?",
                 answer="Very rare in India. Reading rooms are the better choice for late-night or 24-hour study."),
    ],
))


# --- 5. Best areas for UPSC aspirants in Trivandrum ----------------------
_add(Guide(
    slug="best-areas-for-upsc-aspirants-trivandrum",
    title="Best Areas in Trivandrum for UPSC Aspirants — 2026 Guide",
    description="The top localities in Trivandrum for UPSC preparation — coaching clusters, reading rooms, hostel access, and what each area costs.",
    tldr=(
        "Pattom, Vazhuthacaud, and Statue are Trivandrum's three best "
        "UPSC areas. Pattom has the deepest reading-room market. "
        "Vazhuthacaud is the coaching cluster. Statue offers central "
        "access. Expect to spend ₹15,000–₹22,000/month all-in (PG + "
        "reading room + coaching)."
    ),
    category="upsc",
    keywords=["upsc trivandrum", "best area upsc trivandrum",
              "upsc preparation trivandrum kerala", "trivandrum civil service"],
    date_published="2026-03-01",
    date_modified="2026-05-29",
    read_time=6,
    quick_stats=[
        "Coaching clusters: Vazhuthacaud, Statue, Pattom",
        "Reading rooms per cluster: 25–50",
        "Typical PG cost: ₹7,000–₹12,000/month",
        "All-in monthly budget (PG + reading + coaching): ₹15,000–₹22,000",
    ],
    sections=[
        GuideSection(
            heading="Pattom — the reading-room heartland",
            paragraphs=[
                "Pattom is where most serious aspirants base themselves. The combination of <a href='/reading-rooms/trivandrum/pattom'>reading rooms</a> and proximity to Vazhuthacaud coaching makes it the default first choice.",
            ],
        ),
        GuideSection(
            heading="Vazhuthacaud — the coaching cluster",
            paragraphs=[
                "Vazhuthacaud is dense with coaching institutes (Civil Service Academy, Kerala State Civil Service Academy, etc). Reading rooms here are often run by the coaching institutes themselves.",
            ],
        ),
        GuideSection(
            heading="Statue — central access",
            paragraphs=[
                "Statue is closer to the Secretariat and central Trivandrum. Slightly pricier but convenient if you want access to KSL or the central library.",
            ],
        ),
        GuideSection(
            heading="Sample monthly budget",
            table={
                "headers": ["Item", "Cost (₹/mo)"],
                "rows": [
                    ["PG single-sharing with food", "10,000–12,000"],
                    ["Dedicated reading-room seat", "2,000–3,000"],
                    ["Coaching (varies)", "3,000–7,000"],
                    ["Internet + misc.", "500–1,000"],
                    ["Total", "15,500–23,000"],
                ],
            },
        ),
    ],
    faqs=[
        GuideFAQ(question="Where do most UPSC aspirants stay in Trivandrum?",
                 answer="Pattom and Vazhuthacaud account for the majority. Both have walking-distance access to coaching and reading rooms."),
        GuideFAQ(question="Is Trivandrum cheaper than Delhi for UPSC prep?",
                 answer="Significantly. A full all-in budget in Trivandrum is ₹15,000–₹22,000/month vs ₹25,000–₹40,000 in Delhi (Mukherjee Nagar / Old Rajinder Nagar)."),
        GuideFAQ(question="Do Trivandrum reading rooms offer test series space?",
                 answer="Most do; some run their own mock-test series on weekends."),
    ],
))


# --- 6. PG near Technopark ----------------------------------------------
_add(Guide(
    slug="pg-near-technopark",
    title="PG Near Technopark — Best Areas, Prices & What to Look For",
    description="Best PGs near Technopark Trivandrum — Kazhakkoottam, Sreekaryam, and Kariavattom prices, distance, and what's included.",
    tldr=(
        "If you work at Technopark, the closest PG clusters are "
        "Kazhakkoottam (5–10 min), Sreekaryam (10–15 min), and "
        "Kariavattom (15 min). Triple-sharing PGs start at ₹7,000/month; "
        "single-sharing with food runs ₹12,000–₹16,000."
    ),
    category="pgs",
    keywords=["pg near technopark", "pg technopark trivandrum",
              "kazhakkoottam pg", "sreekaryam pg"],
    date_published="2026-03-10",
    date_modified="2026-05-29",
    read_time=5,
    sections=[
        GuideSection(
            heading="The three commuter belts",
            bullets=[
                '<strong><a href="/pgs/trivandrum/kazhakkoottam">Kazhakkoottam</a></strong> — 5–10 min commute. Densest supply. ₹8,000–₹14,000 with food.',
                '<strong><a href="/pgs/trivandrum/sreekaryam">Sreekaryam</a></strong> — 10–15 min commute. Quieter, slightly cheaper. ₹7,500–₹13,000.',
                '<strong><a href="/pgs/trivandrum/kariavattom">Kariavattom</a></strong> — 15 min. University area, mixed crowd. ₹7,000–₹12,000.',
            ],
        ),
        GuideSection(
            heading="What to confirm before booking",
            bullets=[
                "Distance and commute time during Technopark rush hours (8:30–9:30 AM, 5:30–7 PM)",
                "Wi-Fi speed — confirm a 50+ Mbps test result, especially for hybrid work",
                "Food timing — early breakfast for 9 AM shift is critical",
                "Backup power — Trivandrum has fewer outages than 2010s but still common",
            ],
        ),
    ],
    faqs=[
        GuideFAQ(question="What's the cheapest PG near Technopark?",
                 answer="Triple-sharing in Kariavattom starts around ₹7,000/month. With food, ₹9,500–₹11,000."),
        GuideFAQ(question="Are there PGs inside Technopark itself?",
                 answer="No on-campus PGs. The closest options are in Kazhakkoottam, ~5 min by autorickshaw."),
    ],
))


# --- 7. Co-working vs Co-learning spaces ---------------------------------
_add(Guide(
    slug="coworking-vs-colearning",
    title="Co-working vs Co-learning Spaces — When to Choose Each",
    description="The difference between co-working spaces (for working professionals) and co-learning spaces (for students) — pricing, environment, and amenities.",
    tldr=(
        "Co-working spaces are built for working professionals — meeting "
        "rooms, video-call booths, printers, networking events. "
        "Co-learning spaces are built for students and aspirants — quiet "
        "study areas, lockers, long hours, mock-test space. Pricing is "
        "similar; the environment is the key difference."
    ),
    category="comparisons",
    keywords=["coworking vs colearning", "co-working space difference",
              "study space co-working", "co-learning vs coworking"],
    date_published="2026-03-15",
    date_modified="2026-05-29",
    read_time=5,
    sections=[
        GuideSection(
            heading="The core difference",
            paragraphs=[
                "Co-working = built around video calls, meetings, and collaboration.",
                "Co-learning = built around quiet, single-task focus.",
            ],
        ),
        GuideSection(
            heading="Side-by-side",
            table={
                "headers": ["Aspect", "Co-working", "Co-learning"],
                "rows": [
                    ["Primary user", "Working professionals", "Students, aspirants"],
                    ["Noise level", "Moderate (calls allowed)", "Library quiet"],
                    ["Meeting rooms", "Yes", "No (or quiet pods)"],
                    ["Locker", "Optional", "Standard"],
                    ["Hours", "9 AM–9 PM (some 24h)", "12–24 hours"],
                    ["Monthly pass", "₹4,000–₹12,000", "₹2,500–₹6,000"],
                    ["Day pass", "₹500–₹1,500", "₹150–₹400"],
                ],
            },
        ),
    ],
    faqs=[
        GuideFAQ(question="Can students use co-working spaces?",
                 answer="Yes, but the environment may be too noisy for sustained study. Co-learning is purpose-built for focus."),
        GuideFAQ(question="Are co-learning spaces the same as reading rooms?",
                 answer="Reading rooms are smaller, more residential-style spaces. Co-learning is the newer, scaled-up format with shared resources."),
    ],
))


# --- 8. Cost of living in Kochi for students ----------------------------
_add(Guide(
    slug="cost-of-living-kochi-students",
    title="Cost of Living in Kochi for Students — 2026 Budget Guide",
    description="What does student life in Kochi cost in 2026 — PG, food, transport, internet, and a realistic ₹15,000 monthly budget breakdown.",
    tldr=(
        "A student in Kochi can live comfortably on ₹15,000/month: "
        "₹9,000 for a PG with food, ₹1,500 transport, ₹500 internet, "
        "₹2,000 personal, ₹2,000 buffer. Triple-sharing PG users with "
        "self-cooking can get to ₹11,000/month total."
    ),
    category="city-guides",
    keywords=["cost of living kochi", "student budget kochi", "kochi expenses",
              "monthly cost kochi student"],
    date_published="2026-04-01",
    date_modified="2026-05-29",
    read_time=6,
    quick_stats=[
        "Frugal budget: ₹11,000/month",
        "Comfortable budget: ₹15,000/month",
        "Premium budget: ₹22,000/month",
        "PG share of budget: 55–65%",
    ],
    sections=[
        GuideSection(
            heading="The ₹15,000 baseline budget",
            table={
                "headers": ["Item", "Cost (₹/mo)"],
                "rows": [
                    ["Triple-sharing PG (food incl.)", "9,000"],
                    ["Transport (bus + autorickshaw)", "1,500"],
                    ["Internet + phone", "500"],
                    ["Personal + entertainment", "2,000"],
                    ["Buffer", "2,000"],
                    ["Total", "15,000"],
                ],
            },
        ),
        GuideSection(
            heading="Cheaper if",
            bullets=[
                "You stay in Aluva or Kalamassery (₹7,000 PG instead of ₹9,000)",
                "You self-cook (₹4,000 instead of ₹6,000 for food)",
                "You take only KSRTC buses (₹800 instead of ₹1,500)",
            ],
        ),
        GuideSection(
            heading="Pricier if",
            bullets=[
                "Single-sharing PG with AC (₹14,000–₹18,000)",
                "Eating out 2+ meals/day (₹8,000 food)",
                "Cab/scooter (₹3,000–₹5,000 transport)",
            ],
        ),
    ],
    faqs=[
        GuideFAQ(question="Is Kochi cheap for students?",
                 answer="Mid-range. Cheaper than Bangalore/Hyderabad, pricier than smaller Kerala cities (Kollam, Palakkad)."),
        GuideFAQ(question="What's the cheapest neighborhood in Kochi for students?",
                 answer="Aluva and Kalamassery are 20–30% cheaper than Kakkanad or central Kochi while still being within reach of metro stations."),
    ],
))


# --- 9. Hostels Near Infopark Kochi --------------------------------------
_add(Guide(
    slug="hostels-near-infopark-kochi",
    title="Hostels &amp; Co-Living Near Infopark Kochi — 2026 Guide",
    description="Best hostels and co-living near Infopark Kochi — Kakkanad, SmartCity, and Thrikkakara — with pricing, distance, and what to expect.",
    tldr=(
        "Infopark Kochi is best served by hostels in Kakkanad (2–5 min), "
        "Thrikkakara (5–10 min), and SmartCity (10 min). Triple-sharing "
        "starts at ₹6,500; single rooms run ₹14,000–₹20,000."
    ),
    category="hostels",
    keywords=["hostel infopark kochi", "kakkanad hostel", "infopark accommodation",
              "smartcity hostel kochi"],
    date_published="2026-04-10",
    date_modified="2026-05-29",
    read_time=5,
    sections=[
        GuideSection(
            heading="The three commuter belts",
            bullets=[
                '<strong><a href="/hostels/kochi/kakkanad">Kakkanad</a></strong> — 2–5 min commute. Most options. ₹6,500–₹16,000.',
                '<strong><a href="/hostels/kochi/thrikkakara">Thrikkakara</a></strong> — 5–10 min. Quieter residential area. ₹6,000–₹14,000.',
                '<strong><a href="/hostels/kochi/smartcity">SmartCity</a></strong> — 10 min. Built around SmartCity, newer construction. ₹7,500–₹18,000.',
            ],
        ),
        GuideSection(
            heading="Working-professional features to look for",
            bullets=[
                "100+ Mbps Wi-Fi — non-negotiable for hybrid work",
                "Power backup — full coverage, not just lights",
                "Quiet hours after 10 PM (some hostels are stricter)",
                "Co-working / common-area for video calls",
            ],
        ),
    ],
    faqs=[
        GuideFAQ(question="Are there working-professional-only hostels near Infopark?",
                 answer="Yes — several Kakkanad hostels are working-pro-only. Ages typically 22–32."),
        GuideFAQ(question="Is there metro access from Infopark hostels?",
                 answer="The metro extension to Infopark is in progress. For now, autorickshaw and bus are the main options."),
    ],
))


# --- 10. How to find a reading room near you ---------------------------
_add(Guide(
    slug="how-to-find-a-reading-room",
    title="How to Find a Reading Room Near You — A Practical 2026 Guide",
    description="Step-by-step practical guide to finding the right reading room near you — what to filter for, what to check on visit, and how to lock in a deal.",
    tldr=(
        "Search on mySpace by city and locality, filter by price and "
        "amenities (AC, 24-hour, Wi-Fi, locker), shortlist 3, visit each, "
        "then pay only after confirming the seat is dedicated and the "
        "locker key works."
    ),
    category="reading-rooms",
    keywords=["how to find reading room", "reading room near me",
              "find study cabin near me", "how to book reading room"],
    date_published="2026-04-20",
    date_modified="2026-05-29",
    read_time=4,
    sections=[
        GuideSection(
            heading="Step 1 — Define your search",
            bullets=[
                "Your daily commute tolerance (≤15 min works)",
                "Your budget band (₹1,500/₹2,500/₹4,000)",
                "Hours you need (12h / 16h / 24h)",
                "Must-haves: AC, Wi-Fi, locker, dedicated seat",
            ],
        ),
        GuideSection(
            heading="Step 2 — Search on mySpace",
            paragraphs=[
                "Pick your city page (e.g. <a href='/reading-rooms/trivandrum'>Trivandrum</a> or <a href='/reading-rooms/kochi'>Kochi</a>) and use the locality + price filters.",
            ],
        ),
        GuideSection(
            heading="Step 3 — Visit before paying",
            bullets=[
                "Check the seat you'd be assigned (not the demo seat)",
                "Test the locker key personally",
                "Run a 60-second Wi-Fi speed test on your phone",
                "Note bathroom cleanliness — non-negotiable for daily use",
            ],
        ),
        GuideSection(
            heading="Step 4 — Lock in",
            paragraphs=[
                "Most mySpace listings let you pay online for instant confirmation. Always pay through mySpace — not cash to the owner — so you have a receipt and GST invoice.",
            ],
        ),
    ],
    faqs=[
        GuideFAQ(question="How long does it take to find a reading room?",
                 answer="A focused search on mySpace + 2 visits = under 4 hours of effort. Most aspirants book within 48 hours."),
        GuideFAQ(question="Can I trial a reading room for a day before paying for the month?",
                 answer="Many owners offer a free trial visit. Some allow a 1-day paid pass."),
        GuideFAQ(question="What's the right notice period to leave a reading room?",
                 answer="15–30 days is standard. Confirm before paying — verbal agreements rarely hold up."),
    ],
))


def list_guides() -> list[Guide]:
    """All seeded guides, ordered by category then date."""
    return sorted(
        GUIDES.values(),
        key=lambda g: (g.category, g.date_published),
        reverse=False,
    )
