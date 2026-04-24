import urllib.request, json
r = urllib.request.urlopen("http://localhost:8000/api/predictions")
data = json.loads(r.read())
print(f"OK: {len(data)} predictions")
print(f"Top: {data[0]['district']} | {data[0]['state']} | risk={data[0]['risk_level']} | prob={data[0]['failure_probability']}")
