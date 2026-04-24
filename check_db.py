import sqlite3
conn = sqlite3.connect('npide.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("Tables:", tables)
if any('district_monthly' in str(t) for t in tables):
    cur.execute("SELECT COUNT(*) FROM district_monthly")
    print("district_monthly rows:", cur.fetchone()[0])
    cur.execute("SELECT * FROM district_monthly LIMIT 2")
    print("Sample:", cur.fetchall())
conn.close()
