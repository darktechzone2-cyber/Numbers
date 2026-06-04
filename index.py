import requests
import re
import time
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

BASE_URL = "https://konektapremium.net"
CREDENTIALS = {"username": "Slaeem777", "password": "Slaeem777"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Accept-Language": "en-US,en;q=0.9"
}

# Country mapping (same as before, full list)
COUNTRY_MAP = {
    "1": "US/Canada", "44": "UK", "92": "Pakistan", "91": "India", "58": "Venezuela",
    # ... (add all countries as in previous code, but for brevity I'll include the full dict later)
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

    # 1. Get login page to extract captcha and CSRF token
    r1 = session.get(f"{BASE_URL}/sign-in")
    if r1.status_code != 200:
        raise Exception(f"Login page failed: {r1.status_code}")

    # Extract captcha question (e.g., "What is 2 + 5 = ?")
    captcha_match = re.search(r'What is (\d+) \+ (\d+) = \?', r1.text)
    if not captcha_match:
        raise Exception("Captcha not found on login page")
    ans = int(captcha_match[1]) + int(captcha_match[2])

    # Extract CSRF token (if present)
    csrf_token = None
    match = re.search(r'name="_token" value="([^"]+)"', r1.text)
    if match:
        csrf_token = match.group(1)

    # 2. Submit login with captcha
    login_data = {
        "username": CREDENTIALS["username"],
        "password": CREDENTIALS["password"],
        "capt": str(ans)   # the captcha answer
    }
    if csrf_token:
        login_data["_token"] = csrf_token

    # The form field name may be "capt" or "captcha". Use "capt" (as seen in other panels)
    r2 = session.post(f"{BASE_URL}/sign-in", data=login_data, allow_redirects=False)
    if r2.status_code not in (200, 302):
        raise Exception(f"Login POST failed: {r2.status_code}")

    # Follow redirect if needed
    if r2.status_code == 302:
        redirect_url = r2.headers.get('Location')
        r2 = session.get(redirect_url, allow_redirects=True)

    # Check if login succeeded (should not be on sign-in page)
    if "sign-in" in r2.url:
        raise Exception("Login failed – still on sign-in page")

    # 3. Fetch numbers from the numbers endpoint
    ts = int(time.time() * 1000)
    # Use the exact endpoint from the original Node.js: /agent/MySMSNumbers
    url = f"{BASE_URL}/agent/MySMSNumbers?draw=1&start=0&length=-1&_={ts}"
    r3 = session.get(url, headers={"Referer": f"{BASE_URL}/agent/MySMSNumbers"})
    if r3.status_code != 200:
        raise Exception(f"Numbers endpoint returned {r3.status_code}")

    # Parse JSON response
    try:
        data = r3.json()
    except:
        raise Exception(f"Invalid JSON from numbers endpoint. Response: {r3.text[:200]}")

    numbers = []
    # The panel likely returns DataTables format: { "data": [ ... ] }
    rows = data.get("data", []) if isinstance(data, dict) else data
    if not rows:
        rows = data.get("aaData", [])

    for row in rows:
        # Try to find phone number (look for a 10-15 digit string)
        phone = None
        for cell in row:
            if isinstance(cell, str) and re.search(r'\d{7,15}', cell):
                phone = cell
                break
        if not phone:
            continue
        # Plan might be in a specific column; assume it's at index 3 or 4 if exists
        plan = ""
        if len(row) > 4:
            plan = row[4]
        elif len(row) > 3:
            plan = row[3]
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

@app.route('/debug')
def debug():
    try:
        fetch_numbers()
        return jsonify({"status": "works"})
    except Exception as e:
        return jsonify({"error": str(e), "success": False})

if __name__ == "__main__":
    app.run()
