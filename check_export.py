import json, urllib.request

try:
    resp = urllib.request.urlopen("http://localhost:8000/openapi.json")
    data = json.loads(resp.read())
    export_paths = [p for p in data.get("paths", {}) if "export" in p]
    print("Export endpoints:", export_paths)
except Exception as e:
    print(f"Error: {e}")
