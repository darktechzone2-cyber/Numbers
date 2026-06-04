import os
import requests
import re
import time
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# ========== CONFIGURATION ==========
BASE_URL = "https://konektapremium.net"
# Credentials – now hardcoded (you can still use env vars)
CREDENTIALS = {
    "username": "Slaeem777",
    "password": "Slaeem777"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Accept-Language": "en-US,en;q=0.9"
}

# Country mapping (same as before – you can reuse the full dict)
COUNTRY_MAP = {
    "1": "US/Canada", "44": "UK", "92": "Pakistan", "91": "India", "58": "Venezuela",
    # Add more as needed – keeping it minimal for brevity
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

    # Step 1: Get login page – capture any CSRF token
    r1 = session.get(f"{BASE_URL}/sign-in")
    if r1.status_code != 200:
        raise Exception(f"Failed to load login page: {r1.status_code}")

    # Extract CSRF token if present (common in Laravel apps)
    csrf_token = None
    match = re.search(r'name="_token" value="([^"]+)"', r1.text)
    if match:
        csrf_token = match.group(1)
    
    # Prepare login data
    login_data = {
        "username": CREDENTIALS["username"],
        "password": CREDENTIALS["password"]
    }
    if csrf_token:
        login_data["_token"] = csrf_token

    # Step 2: Submit login
    r2 = session.post(f"{BASE_URL}/sign-in", data=login_data, headers={"Referer": f"{BASE_URL}/sign-in"}, allow_redirects=True)
    
    # Check if login succeeded (should not redirect back to login page)
    if "sign-in" in r2.url or r2.status_code != 200:
        # Debug: print response snippet
        snippet = r2.text[:500]
        raise Exception(f"Login failed. Response snippet: {snippet}")

    # Step 3: Fetch numbers from the panel's numbers endpoint
    # The original Node.js used /agent/MySMSNumbers; we'll use it with typical DataTables parameters
    ts = int(time.time() * 1000)
    url = f"{BASE_URL}/agent/MySMSNumbers?draw=1&start=0&length=-1&_={ts}"
    r3 = session.get(url, headers={"Referer": f"{BASE_URL}/agent/MySMSNumbers"})
    if r3.status_code != 200:
        raise Exception(f"Numbers endpoint returned {r3.status_code}")
    
    # Try to parse JSON
    try:
        data = r3.json()
    except Exception as e:
        raise Exception(f"Invalid JSON from numbers endpoint. Response: {r3.text[:200]}")

    numbers = []
    # The response format may be { "data": [ ... ] } (DataTables format)
    rows = data.get("data", []) if isinstance(data, dict) else data
    if not rows:
        # if it's aaData (some panels)
        rows = data.get("aaData", [])
    
    for row in rows:
        # We need to identify which column holds the phone number.
        # Based on typical layouts, it could be at index 2 or 3.
        # Let's try to find any 10-15 digit string in the row.
        phone = None
        for cell in row:
            if isinstance(cell, str) and re.search(r'\d{7,15}', cell):
                phone = cell
                break
        if not phone:
            continue
        # Plan may be at a different index; we can leave blank if not found
        plan = row[3] if len(row) > 3 else ""
        numbers.append({
            "phone": phone,
            "plan": plan,
            "country": get_country(phone)
        })
    
    return numbers

# Caching
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
