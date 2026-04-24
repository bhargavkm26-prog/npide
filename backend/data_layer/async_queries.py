"""
NPIDE — Async Query Functions
================================
All DB queries as async functions using SQLAlchemy + asyncpg.
Each function wraps a key_queries.sql query.

Sync versions still exist in queries.py for intelligence layer
(which runs in thread pool via asyncio.to_thread).
"""

import math
from collections import defaultdict
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_layer.database import async_engine, get_db_dialect


async def async_get_eligible_schemes(citizen_id: int) -> list[dict]:
    sql = text("""
        SELECT s.scheme_id, s.scheme_name, s.description,
               s.benefit_amount, s.eligible_location
        FROM schemes s
        JOIN citizens c ON c.citizen_id = :cid
        WHERE
            c.income    BETWEEN s.min_income AND s.max_income AND
            c.age       BETWEEN s.min_age    AND s.max_age    AND
            (s.eligible_gender     = 'All' OR c.gender     = s.eligible_gender)    AND
            (s.eligible_location   = 'All' OR c.location   = s.eligible_location)  AND
            (s.eligible_occupation = 'All' OR c.occupation = s.eligible_occupation) AND
            s.is_active = TRUE
    """)
    async with async_engine.connect() as conn:
        rows = (await conn.execute(sql, {"cid": citizen_id})).mappings().fetchall()
    return [dict(r) for r in rows]


async def async_get_gap_detection() -> list[dict]:
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
    async with async_engine.connect() as conn:
        rows = (await conn.execute(sql)).mappings().fetchall()
    return [dict(r) for r in rows]


async def async_get_grievance_hotspots() -> list[dict]:
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
    async with async_engine.connect() as conn:
        rows = (await conn.execute(sql)).mappings().fetchall()
    return [dict(r) for r in rows]


async def async_get_policy_leaderboard() -> list[dict]:
    sql = text("""
        SELECT s.scheme_id, s.scheme_name,
               pa.total_eligible, pa.total_applied,
               pa.total_approved, pa.efficiency_score,
               (pa.total_eligible - pa.total_applied) AS missed_citizens
        FROM policy_analytics pa
        JOIN schemes s ON s.scheme_id = pa.scheme_id
        ORDER BY efficiency_score ASC
    """)
    async with async_engine.connect() as conn:
        rows = (await conn.execute(sql)).mappings().fetchall()
    return [dict(r) for r in rows]


async def async_get_citizen_applications(citizen_id: int) -> list[dict]:
    sql = text("""
        SELECT s.scheme_name, a.status, a.applied_on, a.resolved_on, a.remarks
        FROM applications a
        JOIN schemes s ON s.scheme_id = a.scheme_id
        WHERE a.citizen_id = :cid
    """)
    async with async_engine.connect() as conn:
        rows = (await conn.execute(sql, {"cid": citizen_id})).mappings().fetchall()
    return [dict(r) for r in rows]


async def async_get_zero_application_schemes() -> list[dict]:
    sql = text("""
        SELECT s.scheme_name, s.eligible_location,
               pa.total_eligible,
               (pa.total_eligible - pa.total_applied) AS gap_count
        FROM policy_analytics pa
        JOIN schemes s ON s.scheme_id = pa.scheme_id
        WHERE pa.total_applied = 0 AND pa.total_eligible > 0
    """)
    async with async_engine.connect() as conn:
        rows = (await conn.execute(sql)).mappings().fetchall()
    return [dict(r) for r in rows]


async def async_get_corruption_cases() -> list[dict]:
    agg = "GROUP_CONCAT(description, ' | ')" if get_db_dialect() == "sqlite" else "STRING_AGG(description, ' | ')"
    sql = text(f"""
        SELECT location, COUNT(*) AS corruption_cases,
               {agg} AS details
        FROM grievances
        WHERE category = 'corruption'
        GROUP BY location
        ORDER BY corruption_cases DESC
    """)
    async with async_engine.connect() as conn:
        rows = (await conn.execute(sql)).mappings().fetchall()
    return [dict(r) for r in rows]


async def async_get_dashboard_stats() -> dict:
    sql = text("""
        SELECT
            (SELECT COUNT(*) FROM schemes WHERE is_active = TRUE)         AS active_schemes,
            (SELECT COUNT(*) FROM citizens)                                AS total_citizens,
            (SELECT COUNT(*) FROM applications)                            AS total_applications,
            (SELECT COUNT(*) FROM applications WHERE status = 'approved')  AS approved_count,
            (SELECT COUNT(*) FROM grievances   WHERE status = 'open')      AS open_grievances,
            (SELECT ROUND(AVG(efficiency_score), 2) FROM policy_analytics) AS avg_efficiency
    """)
    async with async_engine.connect() as conn:
        row = (await conn.execute(sql)).mappings().fetchone()
    return dict(row) if row else {}


async def async_get_scheme_analytics(scheme_id: int) -> Optional[dict]:
    sql = text("""
        SELECT s.scheme_name, pa.total_eligible, pa.total_applied,
               pa.total_approved, pa.efficiency_score,
               (pa.total_eligible - pa.total_applied) AS gap_count,
               pa.computed_at
        FROM policy_analytics pa
        JOIN schemes s ON s.scheme_id = pa.scheme_id
        WHERE pa.scheme_id = :sid LIMIT 1
    """)
    async with async_engine.connect() as conn:
        row = (await conn.execute(sql, {"sid": scheme_id})).mappings().fetchone()
    return dict(row) if row else None


async def async_insert_grievance(data: dict) -> int:
    sql = text("""
        INSERT INTO grievances (citizen_id, scheme_id, location, category, description, severity)
        VALUES (:citizen_id, :scheme_id, :location, :category, :description, :severity)
        RETURNING grievance_id
    """)
    async with async_engine.begin() as conn:
        result = await conn.execute(sql, data)
        return result.scalar()


async def async_list_grievances(limit: int = 50) -> list[dict]:
    sql = text("""
        SELECT
            grievance_id AS id,
            citizen_id,
            scheme_id,
            location,
            category,
            description,
            severity,
            status,
            filed_on,
            resolved_on,
            created_at
        FROM grievances
        ORDER BY created_at DESC, grievance_id DESC
        LIMIT :limit
    """)
    async with async_engine.connect() as conn:
        rows = (await conn.execute(sql, {"limit": limit})).mappings().fetchall()
    return [dict(r) for r in rows]


async def async_get_failure_predictions(state: Optional[str] = None) -> list[dict]:
    where_clause = "WHERE state = :state" if state else ""
    params = {"state": state} if state else {}
    sql = text(f"""
        SELECT district, state, month, expected, actual, population, schemes
        FROM district_monthly
        {where_clause}
        ORDER BY district ASC, month ASC
    """)
    async with async_engine.connect() as conn:
        rows = (await conn.execute(sql, params)).mappings().fetchall()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["district"]].append(dict(row))

    predictions = []
    for district, history in grouped.items():
        history.sort(key=lambda item: item["month"])
        gaps = []
        coverage_values = []
        scheme_density_values = []

        for item in history:
            expected = max(int(item.get("expected") or 0), 1)
            actual = max(int(item.get("actual") or 0), 0)
            population = max(int(item.get("population") or 0), 1)
            schemes = max(int(item.get("schemes") or 0), 0)

            gaps.append((expected - actual) / expected)
            coverage_values.append(actual / population * 1000)
            scheme_density_values.append(schemes / (population / 1_000_000))

        gap_ratio = sum(gaps) / len(gaps)
        coverage_rate = sum(coverage_values) / len(coverage_values)
        scheme_density = sum(scheme_density_values) / len(scheme_density_values)
        trend_value = gaps[-1] - gaps[0] if len(gaps) > 1 else 0.0

        label = 0
        if gap_ratio > 0.30:
            label += 1
        if coverage_rate < 5.0:
            label += 1
        if scheme_density < 10.0:
            label += 1
        if trend_value > 0.05:
            label += 1

        raw_score = (
            (gap_ratio * 2.3)
            + ((5 - min(coverage_rate, 5)) * 0.12)
            + ((10 - min(scheme_density, 10)) * 0.055)
            + (max(trend_value, -0.2) * 1.5)
            + (0.55 if label >= 2 else 0.05)
        )
        failure_probability = 1 / (1 + math.exp(-(raw_score - 1.05)))
        failure_probability = round(max(0.05, min(0.98, failure_probability)), 4)

        risk_level = "HIGH" if failure_probability >= 0.7 else ("MEDIUM" if failure_probability >= 0.4 else "LOW")
        if trend_value > 0.04:
            trend_label = "worsening"
        elif trend_value < -0.04:
            trend_label = "improving"
        else:
            trend_label = "stable"

        predictions.append({
            "district": district,
            "state": history[0].get("state"),
            "failure_probability": failure_probability,
            "risk_level": risk_level,
            "gap_ratio": round(gap_ratio, 4),
            "coverage_rate": round(coverage_rate, 4),
            "scheme_density": round(scheme_density, 4),
            "trend": trend_label,
        })

    predictions.sort(key=lambda item: item["failure_probability"], reverse=True)
    return predictions


async def async_list_schemes(include_inactive: bool = True) -> list[dict]:
    where_clause = "" if include_inactive else "WHERE is_active = TRUE"
    sql = text(f"""
        SELECT
            scheme_id AS id,
            scheme_name AS name,
            COALESCE(description, '') AS description,
            min_income,
            max_income,
            eligible_gender AS gender,
            eligible_location AS location,
            eligible_occupation AS occupation,
            min_age,
            max_age,
            benefit_amount AS benefit,
            is_active AS active,
            created_at
        FROM schemes
        {where_clause}
        ORDER BY is_active DESC, scheme_id ASC
    """)
    async with async_engine.connect() as conn:
        rows = (await conn.execute(sql)).mappings().fetchall()
    return [dict(r) for r in rows]


async def async_create_scheme(data: dict) -> dict:
    sql = text("""
        INSERT INTO schemes (
            scheme_name, description, min_income, max_income,
            eligible_gender, eligible_location, eligible_occupation,
            min_age, max_age, benefit_amount, is_active
        )
        VALUES (
            :name, :description, :min_income, :max_income,
            :gender, :location, :occupation,
            :min_age, :max_age, :benefit, :active
        )
        RETURNING
            scheme_id AS id,
            scheme_name AS name,
            COALESCE(description, '') AS description,
            min_income,
            max_income,
            eligible_gender AS gender,
            eligible_location AS location,
            eligible_occupation AS occupation,
            min_age,
            max_age,
            benefit_amount AS benefit,
            is_active AS active,
            created_at
    """)
    async with async_engine.begin() as conn:
        row = (await conn.execute(sql, data)).mappings().fetchone()
    return dict(row)


async def async_update_scheme(scheme_id: int, data: dict) -> Optional[dict]:
    sql = text("""
        UPDATE schemes
        SET
            scheme_name = :name,
            description = :description,
            min_income = :min_income,
            max_income = :max_income,
            eligible_gender = :gender,
            eligible_location = :location,
            eligible_occupation = :occupation,
            min_age = :min_age,
            max_age = :max_age,
            benefit_amount = :benefit,
            is_active = :active
        WHERE scheme_id = :scheme_id
        RETURNING
            scheme_id AS id,
            scheme_name AS name,
            COALESCE(description, '') AS description,
            min_income,
            max_income,
            eligible_gender AS gender,
            eligible_location AS location,
            eligible_occupation AS occupation,
            min_age,
            max_age,
            benefit_amount AS benefit,
            is_active AS active,
            created_at
    """)
    params = {**data, "scheme_id": scheme_id}
    async with async_engine.begin() as conn:
        row = (await conn.execute(sql, params)).mappings().fetchone()
    return dict(row) if row else None


async def async_deactivate_scheme(scheme_id: int) -> Optional[dict]:
    sql = text("""
        UPDATE schemes
        SET is_active = FALSE
        WHERE scheme_id = :scheme_id
        RETURNING
            scheme_id AS id,
            scheme_name AS name,
            COALESCE(description, '') AS description,
            min_income,
            max_income,
            eligible_gender AS gender,
            eligible_location AS location,
            eligible_occupation AS occupation,
            min_age,
            max_age,
            benefit_amount AS benefit,
            is_active AS active,
            created_at
    """)
    async with async_engine.begin() as conn:
        row = (await conn.execute(sql, {"scheme_id": scheme_id})).mappings().fetchone()
    return dict(row) if row else None
