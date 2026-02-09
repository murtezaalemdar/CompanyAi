import urllib.request
import json
import sys

url = "http://localhost:8000/api/ask"
data = {"question": "Merhaba, sen kimsin?"}
json_data = json.dumps(data).encode('utf-8')

req = urllib.request.Request(url, data=json_data, headers={'Content-Type': 'application/json'})

try:
    print(f"Sending request to {url}...")
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.getcode()}")
        response_body = response.read().decode('utf-8')
        print("Response JSON:")
        print(response_body)
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Exception: {e}")
