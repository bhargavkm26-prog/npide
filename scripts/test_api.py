"""
NPIDE - API Test Suite
======================
Runs a lightweight end-to-end check against the running API server.
"""

import sys
import json
import time
import argparse
import urllib.request
import urllib.error

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000/api/v1"

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def request(method: str, path: str, body=None) -> tuple[int, dict, float]:
    url = BASE_URL + path
    data = json.dumps(body).encode("utf-8") if body else None
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed = (time.time() - start) * 1000
            return resp.status, json.loads(resp.read()), elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - start) * 1000
        try:
            return e.code, json.loads(e.read()), elapsed
        except Exception:
            return e.code, {"error": str(e)}, elapsed
    except Exception as e:
        return 0, {"error": str(e)}, 0


def check(name: str, status: int, body: dict, elapsed: float, expected_status: int = 200, check_keys: list | None = None) -> bool:
    ok = status == expected_status
    icon = PASS if ok else FAIL
    perf = "FAST" if elapsed < 50 else ("OK" if elapsed < 200 else "SLOW")
    print(f"  {icon} {name:50s} {status}  {perf} {elapsed:.0f}ms")

    if not ok:
        print(f"     Body: {json.dumps(body)[:160]}")

    if check_keys and ok:
        for key in check_keys:
            if key not in body:
                print(f"     {WARN} Missing key: {key}")

    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/api/v1")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.url

    print("=" * 70)
    print("  NPIDE - API Test Suite")
    print(f"  Target: {BASE_URL}")
    print("=" * 70)

    total = 0
    passed = 0

    tests = [
        ("PREDICTION", "GET", "/prediction/Karnataka", None, ["district", "failure_probability"]),
        ("HEALTH", "GET", "/health", None, ["db", "redis"]),
        ("ELIGIBILITY PROFILE", "POST", "/eligibility", {
            "name": "Ramu Gowda",
            "age": 45,
            "income_range": "Below 1 Lakh",
            "gender": "Male",
            "location": "Karnataka",
            "occupation": "Farmer",
        }, ["matched", "schemes"]),
        ("ELIGIBILITY CITIZEN", "GET", "/eligibility/citizen/1", None, ["matched", "schemes"]),
        ("GAP DETECTION", "GET", "/gap-detection", None, ["top_gaps", "db_gap_report"]),
        ("GRIEVANCE CLASSIFY", "POST", "/grievance/classify", {
            "text": "Officer demanded bribe to approve my application",
            "location": "Karnataka",
        }, ["category", "priority", "route_to"]),
        ("POLICY LEADERBOARD", "GET", "/policy-efficiency", None, ["leaderboard", "summary"]),
        ("ADMIN DASHBOARD", "GET", "/admin/dashboard", None, ["stats", "leaderboard", "top_gaps"]),
        ("SPIKES", "GET", "/spikes", None, ["active_spikes"]),
        ("SCHEME LIST", "GET", "/admin/schemes?include_inactive=true", None, ["schemes"]),
    ]

    for name, method, path, body, keys in tests:
        total += 1
        status, response_body, elapsed = request(method, path, body)
        if check(name, status, response_body, elapsed, check_keys=keys):
            passed += 1

    print("\n" + "=" * 70)
    pct = int((passed / total) * 100) if total else 0
    rating = "EXCELLENT" if pct == 100 else ("GOOD" if pct >= 80 else "CHECK")
    print(f"  {rating}  Results: {passed}/{total} passed ({pct}%)")

    if passed == total:
        print("  All tests passed.")
    elif passed >= total * 0.8:
        print("  Most endpoints are working. Review the failed checks above.")
    else:
        print("  Multiple checks failed. Verify the API server, PostgreSQL, Redis, and models.")

    print("=" * 70)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
