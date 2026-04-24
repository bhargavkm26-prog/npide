-- ============================================================
--  NPIDE — Sample Data (seed.sql)
--  Use this to demo the project to judges
-- ============================================================

-- ============================================================
-- SCHEMES (10 realistic Indian govt schemes)
-- ============================================================
INSERT INTO schemes (scheme_name, description, min_income, max_income, eligible_gender, eligible_location, eligible_occupation, min_age, max_age, benefit_amount, is_active) VALUES
('PM Kisan Samman Nidhi',       'Direct income support to farmers',               0,      200000, 'All',    'All',        'Farmer',       18,  80,  6000),
('Ujjwala Yojana',              'Free LPG connection for BPL families',            0,      150000, 'Female', 'All',        'All',          18, 120, 1600),
('Pradhan Mantri Awas Yojana',  'Housing subsidy for homeless families',           0,      300000, 'All',    'All',        'All',          21, 120, 250000),
('Atal Pension Yojana',         'Pension scheme for unorganised sector',           0,      500000, 'All',    'All',        'All',          18,  40, NULL),
('Sukanya Samriddhi Yojana',    'Savings scheme for girl child education',         0,      999999999,'Female','All',       'All',           0,  10, NULL),
('National Health Mission',     'Free healthcare for rural BPL families',          0,      250000, 'All',    'Karnataka',  'All',          0,  120, 50000),
('Karnataka Rajiv Gandhi Scheme','State scheme for SC/ST farmers in Karnataka',   0,      180000, 'All',    'Karnataka',  'Farmer',       18,  65, 10000),
('Mudra Loan Yojana',           'Business loans for micro entrepreneurs',          0,      600000, 'All',    'All',        'Self-employed',18, 65, 500000),
('MGNREGA',                     'Guaranteed 100 days rural employment',            0,      200000, 'All',    'All',        'Daily Wage',   18, 120, 24000),
('Beti Bachao Beti Padhao',     'Girl child welfare and education scheme',         0,      500000, 'Female', 'All',        'All',           0,  18, 5000);


-- ============================================================
-- CITIZENS (20 realistic profiles across India)
-- ============================================================
INSERT INTO citizens (full_name, age, income, location, occupation, gender, phone) VALUES
('Ramu Gowda',        45, 120000, 'Karnataka', 'Farmer',        'Male',   '9845001001'),
('Savitha Devi',      35, 90000,  'Karnataka', 'Daily Wage',    'Female', '9845001002'),
('Arjun Patil',       28, 250000, 'Karnataka', 'Self-employed', 'Male',   '9845001003'),
('Lakshmi Bai',       52, 80000,  'Karnataka', 'Farmer',        'Female', '9845001004'),
('Suresh Kumar',      60, 110000, 'Karnataka', 'Daily Wage',    'Male',   '9845001005'),
('Priya Nair',        22, 140000, 'Kerala',    'Self-employed', 'Female', '9744001001'),
('Mohammed Rafiq',    38, 175000, 'Kerala',    'Daily Wage',    'Male',   '9744001002'),
('Ananya Das',        19, 95000,  'West Bengal','All',          'Female', '9333001001'),
('Biplab Roy',        44, 160000, 'West Bengal','Farmer',       'Male',   '9333001002'),
('Sunita Sharma',     31, 130000, 'Rajasthan', 'Daily Wage',    'Female', '9414001001'),
('Deepak Verma',      55, 200000, 'Rajasthan', 'Farmer',        'Male',   '9414001002'),
('Geeta Devi',        40, 75000,  'Bihar',     'Daily Wage',    'Female', '9431001001'),
('Ramesh Yadav',      48, 135000, 'Bihar',     'Farmer',        'Male',   '9431001002'),
('Pooja Singh',        8, 200000, 'Uttar Pradesh','All',        'Female', NULL),
('Kavya Reddy',       15, 300000, 'Telangana', 'All',           'Female', NULL),
('Harish Naidu',      33, 420000, 'Telangana', 'Self-employed', 'Male',   '9848001001'),
('Fatima Begum',      27, 88000,  'Karnataka', 'Daily Wage',    'Female', '9845001006'),
('Chandra Babu',      50, 145000, 'Karnataka', 'Farmer',        'Male',   '9845001007'),
('Nirmala Devi',      36, 92000,  'Karnataka', 'Daily Wage',    'Female', '9845001008'),
('Srinivas Rao',      41, 195000, 'Karnataka', 'Self-employed', 'Male',   '9845001009');


-- ============================================================
-- APPLICATIONS (realistic mix of statuses)
-- ============================================================
INSERT INTO applications (citizen_id, scheme_id, status, applied_on, resolved_on) VALUES
(1,  1, 'approved',  '2024-06-10', '2024-06-25'),  -- Ramu Gowda → PM Kisan ✅
(1,  9, 'approved',  '2024-07-01', '2024-07-15'),  -- Ramu Gowda → MGNREGA ✅
(2,  2, 'approved',  '2024-05-15', '2024-05-30'),  -- Savitha Devi → Ujjwala ✅
(2,  9, 'pending',   '2024-08-01', NULL),          -- Savitha Devi → MGNREGA ⏳
(3,  8, 'approved',  '2024-04-20', '2024-05-05'),  -- Arjun Patil → Mudra ✅
(4,  1, 'rejected',  '2024-06-12', '2024-06-20'),  -- Lakshmi Bai → PM Kisan ❌ (wrong docs)
(4,  7, 'pending',   '2024-09-01', NULL),          -- Lakshmi Bai → Karnataka scheme ⏳
(5,  9, 'approved',  '2024-07-10', '2024-07-20'),  -- Suresh Kumar → MGNREGA ✅
(8,  5, 'approved',  '2024-03-01', '2024-03-15'),  -- Ananya Das → Sukanya ✅
(9,  1, 'approved',  '2024-06-18', '2024-07-02'),  -- Biplab Roy → PM Kisan ✅
(12, 9, 'approved',  '2024-08-05', '2024-08-20'),  -- Geeta Devi → MGNREGA ✅
(13, 1, 'pending',   '2024-09-10', NULL),          -- Ramesh Yadav → PM Kisan ⏳
(14, 10,'approved',  '2024-01-15', '2024-02-01'),  -- Pooja Singh → Beti Bachao ✅
(15, 10,'pending',   '2024-10-01', NULL),          -- Kavya Reddy → Beti Bachao ⏳
(17, 2, 'approved',  '2024-05-20', '2024-06-01'),  -- Fatima Begum → Ujjwala ✅
(18, 1, 'approved',  '2024-06-22', '2024-07-08'),  -- Chandra Babu → PM Kisan ✅
(19, 9, 'rejected',  '2024-08-12', '2024-08-25'),  -- Nirmala Devi → MGNREGA ❌
(20, 8, 'pending',   '2024-09-15', NULL);          -- Srinivas Rao → Mudra ⏳


-- ============================================================
-- GRIEVANCES (realistic complaints for hotspot demo)
-- ============================================================
INSERT INTO grievances (citizen_id, scheme_id, location, category, description, severity, status, filed_on, resolved_on) VALUES
(4,  1, 'Karnataka',    'wrong rejection',  'PM Kisan application rejected without valid reason', 'high',   'open',        '2024-06-21', NULL),
(2,  9, 'Karnataka',    'delay',            'MGNREGA payment not received for 3 months',          'high',   'in_progress', '2024-09-01', NULL),
(19, 9, 'Karnataka',    'wrong rejection',  'MGNREGA rejected despite being eligible',            'high',   'open',        '2024-08-26', NULL),
(5,  9, 'Karnataka',    'no awareness',     'Was unaware of PM Kisan scheme for 2 years',         'medium', 'resolved',    '2024-05-01', '2024-06-01'),
(12, 9, 'Bihar',        'delay',            'Job cards not issued under MGNREGA for 4 months',    'high',   'open',        '2024-07-15', NULL),
(13, 1, 'Bihar',        'corruption',       'Local official demanding bribe for PM Kisan approval','high',  'in_progress', '2024-09-12', NULL),
(9,  1, 'West Bengal',  'delay',            'PM Kisan amount delayed by 5 months',                'medium', 'resolved',    '2024-04-10', '2024-07-10'),
(10, 9, 'Rajasthan',    'no awareness',     'Unaware of MGNREGA scheme entirely',                 'low',    'resolved',    '2024-03-01', '2024-04-01'),
(11, 1, 'Rajasthan',    'delay',            'PM Kisan pending approval for 6 months',             'medium', 'open',        '2024-08-01', NULL),
(6,  8, 'Kerala',       'wrong rejection',  'Mudra loan rejected without explanation',            'medium', 'open',        '2024-07-20', NULL),
(7,  9, 'Kerala',       'corruption',       'MGNREGA job cards sold by panchayat official',       'high',   'in_progress', '2024-08-05', NULL),
(15, 10,'Telangana',    'delay',            'Beti Bachao application stuck for 2 months',         'low',    'open',        '2024-10-02', NULL),
(18, 1, 'Karnataka',    'no awareness',     'Was unaware of Karnataka state farmer scheme',       'low',    'resolved',    '2024-05-15', '2024-06-15'),
(1,  7, 'Karnataka',    'delay',            'Karnataka Rajiv Gandhi Scheme approval taking too long','medium','open',      '2024-10-01', NULL),
(17, 2, 'Karnataka',    'no awareness',     'Neighbours still unaware of Ujjwala Yojana',         'low',    'resolved',    '2024-04-01', '2024-05-01');


-- ============================================================
-- POLICY ANALYTICS (precomputed — would normally be auto-updated)
-- ============================================================
INSERT INTO policy_analytics (scheme_id, total_eligible, total_applied, total_approved, efficiency_score) VALUES
(1,  8,  5, 3, 37.50),   -- PM Kisan: 8 eligible, only 5 applied
(2,  6,  2, 2, 33.33),   -- Ujjwala: 6 eligible women, only 2 applied
(3,  12, 0, 0,  0.00),   -- PMAY: 12 eligible, ZERO applied (big gap!)
(8,  5,  2, 1, 20.00),   -- Mudra: 5 eligible, 2 applied
(9,  10, 5, 3, 30.00),   -- MGNREGA: 10 eligible, 5 applied
(10, 4,  2, 1, 25.00);   -- Beti Bachao: 4 eligible, 2 applied

