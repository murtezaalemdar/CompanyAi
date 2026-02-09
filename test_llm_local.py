import requests
import json
import sys

url = "http://localhost:8000/api/ask"
headers = {"Content-Type": "application/json"}
data = {"question": "Merhaba, sen kimsin?"}

try:
    print(f"Sending request to {url}...")
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Response JSON:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print("Error Response:")
        print(response.text)
except Exception as e:
    print(f"Exception: {e}")
