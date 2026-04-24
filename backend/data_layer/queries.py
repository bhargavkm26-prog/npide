"""
NPIDE — Data Layer: Key Queries
=================================
All DB queries in one place. Functions return plain dicts/lists
so the intelligence layer stays decoupled from SQLAlchemy Row types.

These implement every query from key_queries.sql plus streaming helpers
needed by the AI engine.
"""

from typing import Optional, Generator
from sqlalchemy import text
from backend.data_layer.database import engine, get_db_dialect


# ─────────────────────────────────────────────────────────────
# QUERY 1: Citizen Eligibility Check
# ─────────────────────────────────────────────────────────────

def get_eligible_schemes(citizen_id: int) -> list[dict]:
    """
    Returns all active schemes the citizen qualifies for.
    Mirrors key_queries.sql Query 1.
    """
    sql = text("""
        SELECT s.scheme_id, s.scheme_name, s.description, s.benefit_amount,
               s.eligible_gender, s.eligible_location, s.eligible_occupation,
               s.min_income, s.max_income, s.min_age, s.max_age
        FROM schemes s
        JOIN citizens c ON c.citizen_id = :cid
        WHERE
            c.income    BETWEEN s.min_income    AND s.max_income  AND
            c.age       BETWEEN s.min_age       AND s.max_age     AND
            (s.eligible_gender     = 'All' OR c.gender     = s.eligible_gender)    AND
            (s.eligible_location   = 'All' OR c.location   = s.eligible_location)  AND
            (s.eligible_occupation = 'All' OR c.occupation = s.eligible_occupation) AND
            s.is_active = TRUE
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"cid": citizen_id}).mappings().fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# QUERY 2: Gap Detection View
# ─────────────────────────────────────────────────────────────

def get_gap_detection() -> list[dict]:
    """Returns gap detection report sorted by missed_beneficiaries DESC."""
    sql = text("""
        SELECT
            s.scheme_id,
            s.scheme_name,
            s.eligible_location,
            COUNT(DISTINCT c.citizen_id) AS expected_eligible,
            COUNT(DISTINCT a.app_id) AS actually_applied,
            COUNT(DISTINCT CASE WHEN a.status = 'approved' THEN a.app_id END) AS actually_approved,
            ROUND(
                COUNT(DISTINCT a.app_id) * 100.0 /
                NULLIF(COUNT(DISTINCT c.citizen_id), 0),
            2) AS application_rate_pct,
            COUNT(DISTINCT c.citizen_id) - COUNT(DISTINCT a.app_id) AS missed_beneficiaries
        FROM schemes s
        JOIN citizens c ON (
            c.income BETWEEN s.min_income AND s.max_income AND
            c.age BETWEEN s.min_age AND s.max_age AND
            (s.eligible_gender = 'All' OR c.gender = s.eligible_gender) AND
            (s.eligible_location = 'All' OR c.location = s.eligible_location) AND
            (s.eligible_occupation = 'All' OR c.occupation = s.eligible_occupation)
        )
        LEFT JOIN applications a ON a.scheme_id = s.scheme_id
            AND a.citizen_id = c.citizen_id
        WHERE s.is_active = TRUE
        GROUP BY s.scheme_id, s.scheme_name, s.eligible_location
        ORDER BY missed_beneficiaries DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# QUERY 3: Grievance Hotspots
# ─────────────────────────────────────────────────────────────

def get_grievance_hotspots() -> list[dict]:
    """Returns regions with open complaints, sorted by count DESC."""
    avg_expr = (
        "ROUND(AVG(CASE WHEN resolved_on IS NOT NULL THEN julianday(resolved_on) - julianday(filed_on) END), 1)"
        if get_db_dialect() == "sqlite"
        else
        "ROUND(AVG(CASE WHEN resolved_on IS NOT NULL THEN resolved_on - filed_on END), 1)"
    )
    sql = text(f"""
        SELECT
            location,
            category,
            COUNT(*) AS total_complaints,
            COUNT(CASE WHEN status = 'open' THEN 1 END) AS open_complaints,
            COUNT(CASE WHEN severity = 'high' THEN 1 END) AS high_severity_count,
            {avg_expr} AS avg_resolution_days
        FROM grievances
        GROUP BY location, category
        HAVING COUNT(CASE WHEN status = 'open' THEN 1 END) > 0
        ORDER BY open_complaints DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# QUERY 4: Policy Efficiency Leaderboard
# ─────────────────────────────────────────────────────────────

def get_policy_leaderboard() -> list[dict]:
    """Returns schemes sorted by efficiency ASC (worst first)."""
    sql = text("""
        SELECT
            s.scheme_id,
            s.scheme_name,
            pa.total_eligible,
            pa.total_applied,
            pa.total_approved,
            pa.efficiency_score,
            (pa.total_eligible - pa.total_applied) AS missed_citizens
        FROM policy_analytics pa
        JOIN schemes s ON s.scheme_id = pa.scheme_id
        ORDER BY efficiency_score ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# QUERY 5: Citizen Application Status
# ─────────────────────────────────────────────────────────────

def get_citizen_applications(citizen_id: int) -> list[dict]:
    """Returns all applications + status for a given citizen."""
    sql = text("""
        SELECT
            s.scheme_name,
            a.status,
            a.applied_on,
            a.resolved_on,
            a.remarks
        FROM applications a
        JOIN schemes s ON s.scheme_id = a.scheme_id
        WHERE a.citizen_id = :cid
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"cid": citizen_id}).mappings().fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# QUERY 6: Zero-Application Schemes (Critical Gap)
# ─────────────────────────────────────────────────────────────

def get_zero_application_schemes() -> list[dict]:
    """Schemes with eligible citizens but ZERO applications — biggest gap."""
    sql = text("""
        SELECT
            s.scheme_name,
            s.eligible_location,
            pa.total_eligible,
            (pa.total_eligible - pa.total_applied) AS gap_count
        FROM policy_analytics pa
        JOIN schemes s ON s.scheme_id = pa.scheme_id
        WHERE pa.total_applied = 0 AND pa.total_eligible > 0
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# QUERY 7: Corruption / Bribe Complaints
# ─────────────────────────────────────────────────────────────

def get_corruption_cases() -> list[dict]:
    """Groups corruption grievances by location for anti-corruption panel."""
    agg = "GROUP_CONCAT(description, ' | ')" if get_db_dialect() == "sqlite" else "STRING_AGG(description, ' | ')"
    sql = text(f"""
        SELECT
            location,
            COUNT(*) AS corruption_cases,
            {agg} AS details
        FROM grievances
        WHERE category = 'corruption'
        GROUP BY location
        ORDER BY corruption_cases DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# HELPER: Load ALL active schemes into memory (for AI engine)
# ─────────────────────────────────────────────────────────────

def load_all_active_schemes() -> list[dict]:
    """
    Fetches all active schemes with their eligibility rules.
    Called once at startup by the AI engine.
    """
    sql = text("""
        SELECT scheme_id, scheme_name, description,
               min_income, max_income, eligible_gender,
               eligible_location, eligible_occupation,
               min_age, max_age, benefit_amount
        FROM schemes
        WHERE is_active = TRUE
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# HELPER: Stream district-like stats for gap detection
# Returns Polars DataFrames (chunked) for streaming processing
# ─────────────────────────────────────────────────────────────

def stream_district_stats(location: Optional[str] = None) -> Generator[list[dict], None, None]:
    """
    Streams gap stats grouped by scheme+location in 50-row chunks.
    Used by the IsolationForest gap detector.
    Yields Polars DataFrames — O(chunk) RAM, not O(total).
    """
    location_filter = "AND s.eligible_location = :loc" if location else ""
    params: dict = {}
    if location:
        params["loc"] = location

    sql = text(f"""
        SELECT
            s.scheme_id,
            s.scheme_name,
            COALESCE(s.eligible_location, 'All')          AS location,
            COUNT(DISTINCT c.citizen_id)                   AS expected,
            COUNT(DISTINCT a.app_id)                       AS actual,
            COUNT(DISTINCT c.citizen_id)                   AS population
        FROM schemes s
        JOIN citizens c ON (
            c.income  BETWEEN s.min_income AND s.max_income AND
            c.age     BETWEEN s.min_age    AND s.max_age    AND
            (s.eligible_gender    = 'All' OR c.gender    = s.eligible_gender)    AND
            (s.eligible_location  = 'All' OR c.location  = s.eligible_location)  AND
            (s.eligible_occupation= 'All' OR c.occupation= s.eligible_occupation)
        )
        LEFT JOIN applications a ON a.scheme_id = s.scheme_id AND a.citizen_id = c.citizen_id
        WHERE s.is_active = TRUE {location_filter}
        GROUP BY s.scheme_id, s.scheme_name, s.eligible_location
        ORDER BY s.scheme_id
    """)

    CHUNK_SIZE = 50
    with engine.connect() as conn:
        total_schemes_sql = text(f"SELECT COUNT(*) FROM schemes s WHERE s.is_active = TRUE {'AND s.eligible_location = :loc' if location else ''}")
        total_schemes = conn.execute(total_schemes_sql, params).scalar() or 0
        result = conn.execute(sql, params)
        while True:
            batch = result.fetchmany(CHUNK_SIZE)
            if not batch:
                break
            records = []
            for row in batch:
                record = dict(row._mapping)
                record["schemes_available"] = total_schemes
                records.append(record)
            yield records


# ─────────────────────────────────────────────────────────────
# HELPER: Get citizen profile dict (for in-memory eligibility)
# ─────────────────────────────────────────────────────────────

def get_citizen_profile(citizen_id: int) -> Optional[dict]:
    sql = text("""
        SELECT citizen_id, full_name, age, income, location, occupation, gender
        FROM citizens WHERE citizen_id = :cid
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"cid": citizen_id}).mappings().fetchone()
    return dict(row) if row else None


# ─────────────────────────────────────────────────────────────
# HELPER: Insert a new grievance
# ─────────────────────────────────────────────────────────────

def insert_grievance(data: dict) -> int:
    """Inserts a grievance and returns the new grievance_id."""
    sql = text("""
        INSERT INTO grievances (citizen_id, scheme_id, location, category, description, severity)
        VALUES (:citizen_id, :scheme_id, :location, :category, :description, :severity)
        RETURNING grievance_id
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, data)
        conn.commit()
        return result.scalar()


# ─────────────────────────────────────────────────────────────
# HELPER: Dashboard summary stats
# ─────────────────────────────────────────────────────────────

def get_dashboard_stats() -> dict:
    """Returns top-level stats for the admin overview panel."""
    sql = text("""
        SELECT
            (SELECT COUNT(*) FROM schemes  WHERE is_active = TRUE)      AS active_schemes,
            (SELECT COUNT(*) FROM citizens)                              AS total_citizens,
            (SELECT COUNT(*) FROM applications)                          AS total_applications,
            (SELECT COUNT(*) FROM applications WHERE status = 'approved') AS approved_count,
            (SELECT COUNT(*) FROM grievances   WHERE status = 'open')    AS open_grievances,
            (SELECT ROUND(AVG(efficiency_score), 2) FROM policy_analytics) AS avg_efficiency
    """)
    with engine.connect() as conn:
        row = conn.execute(sql).mappings().fetchone()
    return dict(row) if row else {}
