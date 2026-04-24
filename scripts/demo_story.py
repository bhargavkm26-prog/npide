"""
NPIDE — DEMO SCRIPT
=====================
Exact demo flow to show judges. Run this to generate sample API calls
with timing output. Shows the full story in under 5 minutes.

Usage:
  python scripts/demo_story.py
"""

import sys, os, json, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://localhost:8000/api/v1"
W    = "\033[0m"   # reset
G    = "\033[92m"  # green
B    = "\033[94m"  # blue
Y    = "\033[93m"  # yellow
R    = "\033[91m"  # red
BOLD = "\033[1m"


def say(text: str, color=B) -> None:
    print(f"\n{color}{BOLD}{text}{W}")


def call(method: str, path: str, body=None) -> tuple[dict, float]:
    url  = BASE + path
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"},
                                  method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()), (time.time() - t0) * 1000
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), (time.time() - t0) * 1000


def show(data: dict, keys: list[str] = None) -> None:
    if keys:
        data = {k: data[k] for k in keys if k in data}
    print(f"  {G}{json.dumps(data, indent=2, default=str)[:400]}{W}")


def timing(ms: float) -> str:
    if ms < 10:   return f"{G}⚡ {ms:.1f}ms (CACHE){W}"
    if ms < 100:  return f"{G}🚀 {ms:.1f}ms{W}"
    if ms < 200:  return f"{Y}⚡ {ms:.1f}ms{W}"
    return f"{R}🐢 {ms:.1f}ms{W}"


def main():
    print(f"\n{BOLD}{'='*65}")
    print("  NPIDE — LIVE DEMO STORY")
    print(f"{'='*65}{W}")
    print("""
SCRIPT FOR JUDGES:
  "Our system has two users: citizens who need government help,
   and government officials who need to see where the system is failing.
   Let me walk you through the complete flow in real-time."
""")

    # ── SCENE 1: Citizen logs in ──────────────────────────────
    say("SCENE 1: Citizen logs in — gets scheme matches in milliseconds")
    print("""  'Ramu Gowda is a 45-year-old farmer in Karnataka earning ₹1.2L/year.
  He visits our portal. Our chatbot gathers his profile.
  We run eligibility across ALL active schemes — purely rule-based.
  No ML. No LLM. Because government rules are exact — interpretable,
  auditable, and cannot hallucinate.'
""")
    data, ms = call("POST", "/eligibility", {
        "name": "Ramu Gowda", "age": 45, "income": 120000,
        "gender": "Male", "location": "Karnataka", "occupation": "Farmer"
    })
    print(f"  POST /eligibility → {timing(ms)}")
    print(f"  ✅ Matched {data.get('matched')} schemes | Source: {data.get('source')}")
    schemes = data.get("schemes", [])[:3]
    for s in schemes:
        amt = s.get("benefit_amount")
        print(f"     • {s.get('scheme_name')} — ₹{amt:,}/yr" if amt else
              f"     • {s.get('scheme_name')} — non-monetary")

    # ── Cache demo ────────────────────────────────────────────
    say("  SCENE 1b: Same citizen visits again → Redis cache hit")
    data2, ms2 = call("POST", "/eligibility", {
        "name": "Ramu Gowda", "age": 45, "income": 120000,
        "gender": "Male", "location": "Karnataka", "occupation": "Farmer"
    })
    print(f"  POST /eligibility (second call) → {timing(ms2)}")
    print(f"  Source: {data2.get('source')} — {ms:.0f}ms → {ms2:.0f}ms")
    print(f"\n  WHAT TO SAY: 'First call computes rules in {ms:.0f}ms. Same profile?")
    print(f"  Redis serves it in {ms2:.0f}ms. That's our hot-path caching.'")

    # ── SCENE 2: Gap Detection ────────────────────────────────
    say("SCENE 2: Government logs in — sees which schemes are failing")
    print("""  'Now the district officer logs in. She can see every scheme
  where eligible citizens simply haven't applied.
  We use IsolationForest — an unsupervised ML model.
  Why unsupervised? Because the government doesn't have labeled data
  saying "this district is failing." We discover failures ourselves.'
""")
    data, ms = call("GET", "/gap-detection/db")
    print(f"  GET /gap-detection/db → {timing(ms)}")
    gaps = data.get("gaps", [])[:3]
    for g in gaps:
        missed = g.get("missed_beneficiaries", 0)
        rate   = g.get("application_rate_pct", 0)
        print(f"     • {g.get('scheme_name')}: {missed} missed | {rate}% uptake")

    zero, _ = call("GET", "/gap-detection/zero-schemes")
    z = zero.get("schemes", [])
    if z:
        print(f"\n  🚨 CRITICAL: {len(z)} scheme(s) with ZERO applications:")
        for s in z[:2]:
            print(f"     • {s.get('scheme_name')} — {s.get('total_eligible')} citizens eligible, 0 applied")
    print("\n  WHAT TO SAY: 'This is what policy analytics looks like. Not just reports —")
    print("  anomaly detection that surfaces failures the government couldn't see.'")

    # ── SCENE 3: Grievance ────────────────────────────────────
    say("SCENE 3: Citizen files a complaint — routed in milliseconds")
    print("""  'Ramu's PM Kisan application was rejected. He files a complaint.
  Our NLP pipeline — spaCy + RandomForest — classifies it instantly.
  Why not GPT? 10ms vs 3 seconds. Deterministic. Auditable. CPU-only.
  Same complaint always gives the same routing — critical for govt audit.'
""")
    complaint = "My PM Kisan application was rejected without any reason. I paid the local official ₹500 to process it."
    print(f"  Complaint: '{complaint[:70]}...'")
    data, ms = call("POST", "/grievance/classify", {"text": complaint, "location": "Karnataka"})
    print(f"  POST /grievance/classify → {timing(ms)}")
    print(f"  Category:   {data.get('category')}")
    print(f"  Priority:   {data.get('priority')}/10")
    print(f"  Route to:   {data.get('route_to')}")
    print(f"  Escalate:   {data.get('escalate')}")

    # Full submit
    sub, ms = call("POST", "/grievance/submit", {
        "citizen_id": 4, "scheme_id": 1, "location": "Karnataka",
        "description": complaint, "severity": "high"
    })
    spike = sub.get("spike_alert", {})
    print(f"\n  POST /grievance/submit → {timing(ms)}")
    print(f"  grievance_id: {sub.get('grievance_id')}")
    print(f"  Spike detected: {spike.get('is_spike')} (EWMA baseline: {spike.get('ewma_baseline')})")
    print("\n  WHAT TO SAY: 'The moment this is submitted, three things happen concurrently:")
    print("  1. NLP classifies it (asyncio.to_thread — doesn't block)")
    print("  2. DB insert (asyncpg — truly async)")
    print("  3. Redis Pub/Sub event published — our event bus'")

    # ── SCENE 4: Policy Dashboard ─────────────────────────────
    say("SCENE 4: Policy efficiency dashboard — worst schemes ranked")
    data, ms = call("GET", "/policy-efficiency")
    print(f"  GET /policy-efficiency → {timing(ms)}")
    board = data.get("leaderboard", [])[:4]
    for s in board:
        eff = s.get("efficiency_score", 0)
        print(f"     {s.get('scheme_name', '?')[:40]:40s} {eff}%")
    summary = data.get("summary", {})
    print(f"\n  Average efficiency: {summary.get('avg_efficiency')}%")
    print(f"  Open grievances:   {summary.get('open_grievances')}")

    # ── SCENE 5: Async architecture ───────────────────────────
    say("SCENE 5: Async architecture proof — concurrent dashboard load")
    print("  'Every endpoint is async. DB never blocks the event loop.")
    print("  The admin dashboard runs 3 queries concurrently with asyncio.gather.'")
    data, ms = call("GET", "/admin/dashboard")
    print(f"  GET /admin/dashboard (3 concurrent queries) → {timing(ms)}")
    s = data.get("stats", {})
    print(f"  Schemes: {s.get('active_schemes')} | Citizens: {s.get('total_citizens')} | Applications: {s.get('total_applications')}")

    # ── SCENE 6: Monitoring ───────────────────────────────────
    say("SCENE 6: Prometheus metrics")
    print("  'Every request is tracked. Latency histogram. Cache hit rate.")
    print("  Point Grafana at /api/v1/metrics and get a live dashboard.'")
    print("  GET /api/v1/metrics → (Prometheus text format)")

    # ── Final answer ──────────────────────────────────────────
    say("JUDGE QUESTION PREP", color=Y)
    qa = [
        ("Why rule-based eligibility?",
         "Government rules are exact — income < ₹2.5L, age 18-60, state = Karnataka.\n"
         "     Rules are interpretable, auditable, and cannot hallucinate. A trained\n"
         "     model cannot improve on a hard government criterion."),
        ("Why IsolationForest?",
         "Unsupervised — no labeled 'gap' data exists. Government doesn't label\n"
         "     its own failures. IsolationForest finds anomalies without labels.\n"
         "     O(n log n) train, O(log n) score. Interpretable anomaly score."),
        ("Why not Kafka?",
         "We use Redis Pub/Sub — same contract: async delivery, fan-out, decoupled.\n"
         "     For national scale we'd swap in Kafka. The subscriber interface is identical."),
        ("Is this async?",
         "Yes. asyncpg for DB, redis[asyncio] for cache. CPU-bound AI runs in\n"
         "     asyncio.to_thread. The event loop is never blocked."),
        ("What if the model degrades?",
         "ModelManager tracks prediction distribution (drift detection).\n"
         "     Hot-reload endpoint swaps the model without restarting the server.\n"
         "     Rollback: reload the previous .pkl file."),
    ]
    for q, a in qa:
        print(f"\n  {Y}Q: {q}{W}")
        print(f"  A: {a}")

    print(f"\n{BOLD}{'='*65}")
    print("  Demo complete. System is ready.")
    print(f"{'='*65}{W}\n")


if __name__ == "__main__":
    main()
