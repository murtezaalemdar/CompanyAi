import urllib.request
import urllib.parse
import json
import sys

base_url = "http://localhost:8000"

def login():
    url = f"{base_url}/api/auth/login"
    # Form-encoded data for OAuth2
    data = urllib.parse.urlencode({
        "username": "admin@company.ai",
        "password": "admin123"
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    
    try:
        print(f"Logging in to {url}...")
        with urllib.request.urlopen(req) as response:
            if response.getcode() == 200:
                body = json.loads(response.read().decode('utf-8'))
                return body['access_token']
    except Exception as e:
        print(f"Login failed: {e}")
        return None

def ask_question(token):
    url = f"{base_url}/api/ask"
    data = {"question": "Merhaba, sen kimsin?"}
    json_data = json.dumps(data).encode('utf-8')
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    
    req = urllib.request.Request(url, data=json_data, headers=headers)
    
    try:
        print(f"Asking question to {url}...")
        with urllib.request.urlopen(req) as response:
            print(f"Status Code: {response.getcode()}")
            response_body = response.read().decode('utf-8')
            print("Response JSON:")
            print(json.dumps(json.loads(response_body), indent=2, ensure_ascii=False))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(e.read().decode('utf-8'))
    except Exception as e:
        print(f"Exception: {e}")

# Main execution
token = login()
if token:
    print(f"Got token: {token[:10]}...")
    ask_question(token)
else:
    print("Could not get token, aborting.")
