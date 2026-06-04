import os
import requests
import re
import time
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# ========== CONFIGURATION ==========
BASE_URL = "https://konektapremium.net"
CREDENTIALS = {
    "username": os.environ.get("KONEK_USER", "Slaeem777"),
    "password": os.environ.get("KONEK_PASS", "Slaeem777")
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Accept-Language": "en-US,en;q=0.9"
}

# Same country mapping as above (you can reuse the same dict)
COUNTRY_MAP = {
    "1": "US/Canada", "44": "UK", "92": "Pakistan", "91": "India", "58": "Venezuela",
    # ... (add full mapping as in st_api.py)
}

def get_country(phone):
    s = str(phone).lstrip('+')
    for length in range(4, 0, -1):
        prefix = s[:length]
        if prefix in COUNTRY_MAP:
            return COUNTRY_MAP[prefix]
    return "Global"

def fetch_numbers():
    session = requests.Session()
    session.headers.update(HEADERS)

    # Step 1: Get login page – may have a different captcha or no captcha
    r1 = session.get(f"{BASE_URL}/sign-in")
    if r1.status_code != 200:
        raise Exception("Failed to load login page")
    
    # Check for captcha (if present). This panel might not have one.
    # For now, assume simple login with username/password.
    # If there is a CSRF token, extract it.
    csrf_token = None
    match = re.search(r'name="_token" value="([^"]+)"', r1.text)
    if match:
        csrf_token = match.group(1)
    
    login_data = {
        "username": CREDENTIALS["username"],
        "password": CREDENTIALS["password"]
    }
    if csrf_token:
        login_data["_token"] = csrf_token
    
    # Step 2: Submit login
    r2 = session.post(f"{BASE_URL}/sign-in", data=login_data, headers={"Referer": f"{BASE_URL}/sign-in"}, allow_redirects=True)
    if "login" in r2.url or r2.status_code != 200:
        raise Exception("Login failed – check credentials")
    
    # Step 3: Fetch numbers from the numbers endpoint
    ts = int(time.time() * 1000)
    # The endpoint might require a specific parameters; adjust as needed.
    # The user provided: /agent/MySMSNumbers
    url = f"{BASE_URL}/agent/MySMSNumbers?draw=1&start=0&length=-1&_={ts}"
    r3 = session.get(url, headers={"Referer": f"{BASE_URL}/agent/MySMSNumbers"})
    if "login" in r3.url or r3.status_code != 200:
        raise Exception("Session expired or numbers endpoint inaccessible")
    
    # Parse response – the structure may differ. Inspect the JSON.
    data = r3.json()
    numbers = []
    # The structure might be similar to the other panel: {"data": [...]}
    rows = data.get("data", []) if isinstance(data, dict) else data
    for row in rows:
        # Adjust indexes based on actual response
        # For now, assume phone is at index 2, plan at index 3 (example)
        phone = row[2] if len(row) > 2 else ""
        plan = row[3] if len(row) > 3 else ""
        if phone:
            numbers.append({
                "phone": phone,
                "plan": plan,
                "country": get_country(phone)
            })
    return numbers

# Caching (same as before)
cache = {"data": None, "last_fetch": 0}
CACHE_TTL = 60

@app.route('/')
def index():
    now = time.time()
    if cache["data"] and (now - cache["last_fetch"]) < CACHE_TTL:
        return jsonify({
            "success": True,
            "cached": True,
            "count": len(cache["data"]),
            "numbers": cache["data"]
        })
    try:
        numbers = fetch_numbers()
        cache["data"] = numbers
        cache["last_fetch"] = now
        return jsonify({
            "success": True,
            "cached": False,
            "count": len(numbers),
            "numbers": numbers
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run()
