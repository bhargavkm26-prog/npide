-- ============================================================
--  NPIDE — National Policy Intelligence & Delivery Engine
--  DATABASE SCHEMA
-- ============================================================

-- Drop tables if they exist (safe re-run)
DROP TABLE IF EXISTS policy_analytics CASCADE;
DROP TABLE IF EXISTS grievances CASCADE;
DROP TABLE IF EXISTS applications CASCADE;
DROP TABLE IF EXISTS schemes CASCADE;
DROP TABLE IF EXISTS citizens CASCADE;

-- ============================================================
-- TABLE 1: citizens
-- ============================================================
CREATE TABLE citizens (
    citizen_id    SERIAL PRIMARY KEY,
    full_name     VARCHAR(100)  NOT NULL,
    age           INTEGER       NOT NULL CHECK (age >= 0 AND age <= 120),
    income        INTEGER       NOT NULL CHECK (income >= 0),
    location      VARCHAR(100)  NOT NULL,
    occupation    VARCHAR(100)  NOT NULL,
    gender        VARCHAR(20),
    phone         VARCHAR(15),
    created_at    TIMESTAMP     DEFAULT NOW()
);

CREATE INDEX idx_citizens_location   ON citizens(location);
CREATE INDEX idx_citizens_occupation ON citizens(occupation);
CREATE INDEX idx_citizens_income     ON citizens(income);

-- ============================================================
-- TABLE 2: schemes
-- ============================================================
CREATE TABLE schemes (
    scheme_id           SERIAL PRIMARY KEY,
    scheme_name         VARCHAR(200)  NOT NULL,
    description         TEXT,
    min_income          INTEGER       DEFAULT 0,
    max_income          INTEGER       DEFAULT 999999999,
    eligible_gender     VARCHAR(20)   DEFAULT 'All',
    eligible_location   VARCHAR(100)  DEFAULT 'All',
    eligible_occupation VARCHAR(100)  DEFAULT 'All',
    min_age             INTEGER       DEFAULT 0,
    max_age             INTEGER       DEFAULT 120,
    benefit_amount      INTEGER,
    is_active           BOOLEAN       DEFAULT TRUE,
    created_at          TIMESTAMP     DEFAULT NOW()
);

CREATE INDEX idx_schemes_location   ON schemes(eligible_location);
CREATE INDEX idx_schemes_occupation ON schemes(eligible_occupation);

-- ============================================================
-- TABLE 3: applications
-- ============================================================
CREATE TABLE applications (
    app_id       SERIAL PRIMARY KEY,
    citizen_id   INTEGER NOT NULL REFERENCES citizens(citizen_id) ON DELETE CASCADE,
    scheme_id    INTEGER NOT NULL REFERENCES schemes(scheme_id)   ON DELETE CASCADE,
    status       VARCHAR(50)  DEFAULT 'pending',
    applied_on   DATE         DEFAULT CURRENT_DATE,
    resolved_on  DATE,
    remarks      TEXT,
    created_at   TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX idx_applications_citizen ON applications(citizen_id);
CREATE INDEX idx_applications_scheme  ON applications(scheme_id);
CREATE INDEX idx_applications_status  ON applications(status);

-- ============================================================
-- TABLE 4: grievances
-- ============================================================
CREATE TABLE grievances (
    grievance_id   SERIAL PRIMARY KEY,
    citizen_id     INTEGER      REFERENCES citizens(citizen_id) ON DELETE SET NULL,
    scheme_id      INTEGER      REFERENCES schemes(scheme_id)   ON DELETE SET NULL,
    location       VARCHAR(100) NOT NULL,
    category       VARCHAR(100),
    description    TEXT,
    severity       VARCHAR(20)  DEFAULT 'medium',
    status         VARCHAR(50)  DEFAULT 'open',
    filed_on       DATE         DEFAULT CURRENT_DATE,
    resolved_on    DATE,
    created_at     TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX idx_grievances_location ON grievances(location);
CREATE INDEX idx_grievances_category ON grievances(category);
CREATE INDEX idx_grievances_status   ON grievances(status);

-- ============================================================
-- TABLE 5: policy_analytics
-- ============================================================
CREATE TABLE policy_analytics (
    analytics_id         SERIAL PRIMARY KEY,
    scheme_id            INTEGER NOT NULL REFERENCES schemes(scheme_id) ON DELETE CASCADE,
    total_eligible       INTEGER DEFAULT 0,
    total_applied        INTEGER DEFAULT 0,
    total_approved       INTEGER DEFAULT 0,
    efficiency_score     NUMERIC(5,2),
    gap_count            INTEGER GENERATED ALWAYS AS (total_eligible - total_applied) STORED,
    computed_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_analytics_scheme ON policy_analytics(scheme_id);

-- ============================================================
-- VIEW: Gap Detection
-- ============================================================
CREATE VIEW vw_gap_detection AS
SELECT
    s.scheme_id,
    s.scheme_name,
    s.eligible_location,
    COUNT(DISTINCT c.citizen_id)                          AS expected_eligible,
    COUNT(DISTINCT a.app_id)                              AS actually_applied,
    COUNT(DISTINCT CASE WHEN a.status = 'approved'
                        THEN a.app_id END)                AS actually_approved,
    ROUND(
        COUNT(DISTINCT a.app_id)::DECIMAL /
        NULLIF(COUNT(DISTINCT c.citizen_id), 0) * 100
    , 2)                                                  AS application_rate_pct,
    COUNT(DISTINCT c.citizen_id) - COUNT(DISTINCT a.app_id) AS missed_beneficiaries
FROM schemes s
JOIN citizens c ON (
    c.income    BETWEEN s.min_income    AND s.max_income  AND
    c.age       BETWEEN s.min_age       AND s.max_age     AND
    (s.eligible_gender    = 'All' OR c.gender    = s.eligible_gender)    AND
    (s.eligible_location  = 'All' OR c.location  = s.eligible_location)  AND
    (s.eligible_occupation = 'All' OR c.occupation = s.eligible_occupation)
)
LEFT JOIN applications a ON a.scheme_id = s.scheme_id
                         AND a.citizen_id = c.citizen_id
WHERE s.is_active = TRUE
GROUP BY s.scheme_id, s.scheme_name, s.eligible_location;

-- ============================================================
-- VIEW: Grievance Hotspots
-- ============================================================
CREATE VIEW vw_grievance_hotspots AS
SELECT
    location,
    category,
    COUNT(*)                                         AS total_complaints,
    COUNT(CASE WHEN status = 'open' THEN 1 END)      AS open_complaints,
    COUNT(CASE WHEN severity = 'high' THEN 1 END)    AS high_severity_count,
    ROUND(AVG(
        CASE WHEN resolved_on IS NOT NULL
             THEN resolved_on - filed_on END
    ), 1)                                            AS avg_resolution_days
FROM grievances
GROUP BY location, category
ORDER BY total_complaints DESC;

-- ============================================================
-- TABLE 6: district_monthly (FOR AI PREDICTION)
-- ============================================================

CREATE TABLE district_monthly (
    id SERIAL PRIMARY KEY,
    district VARCHAR(100),
    state VARCHAR(100),
    month INT,
    expected INT,
    actual INT,
    population INT,
    schemes INT
);

CREATE INDEX idx_district_monthly_state ON district_monthly(state);
CREATE INDEX idx_district_monthly_district ON district_monthly(district);
