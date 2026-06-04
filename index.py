import requests
import re
import time
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# ========== CONFIGURATION ==========
BASE_URL = "https://konektapremium.net"
CREDENTIALS = {"username": "Slaeem777", "password": "Slaeem777"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/agent/MySMSNumbers",
    "Accept-Language": "en-US,en;q=0.9"
}

# Country mapping (short version – add your full list)
COUNTRY_MAP = {
    "1": "US/Canada", "44": "UK", "92": "Pakistan", "91": "India", "58": "Venezuela",
    # add more as needed
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

    # 1. GET login page
    r1 = session.get(f"{BASE_URL}/sign-in")
    if r1.status_code != 200:
        raise Exception(f"Login page failed: {r1.status_code}")

    html = r1.text

    # 2. Extract CSRF token (if any)
    csrf_token = None
    match = re.search(r'name="_token" value="([^"]+)"', html)
    if match:
        csrf_token = match.group(1)

    # 3. Extract captcha question – e.g., "What is 2 + 5 = ?"
    captcha_match = re.search(r'What is (\d+) \+ (\d+) = \?', html)
    if not captcha_match:
        # try alternative patterns
        captcha_match = re.search(r'(\d+)\s*\+\s*(\d+)\s*=\s*\?', html)
    if not captcha_match:
        raise Exception("Captcha question not found on login page")
    num1 = int(captcha_match.group(1))
    num2 = int(captcha_match.group(2))
    captcha_answer = num1 + num2
    print(f"[CAPTCHA] {num1} + {num2} = {captcha_answer}")

    # 4. Build login data
    login_data = {
        "username": CREDENTIALS["username"],
        "password": CREDENTIALS["password"],
        "captcha": captcha_answer          # field name may be 'captcha' or 'answer'
    }
    if csrf_token:
        login_data["_token"] = csrf_token

    # 5. Submit login
    r2 = session.post(f"{BASE_URL}/sign-in", data=login_data, allow_redirects=True)
    
    # Check if login succeeded – should NOT be on sign-in page
    if "sign-in" in r2.url:
        raise Exception("Login failed – still on sign-in page (wrong captcha or credentials)")

    # 6. Now fetch numbers (after successful login)
    ts = int(time.time() * 1000)
    numbers_url = f"{BASE_URL}/agent/MySMSNumbers?draw=1&start=0&length=-1&_={ts}"
    r3 = session.get(numbers_url, headers={"Referer": f"{BASE_URL}/agent/MySMSNumbers"})
    if r3.status_code != 200:
        raise Exception(f"Numbers endpoint returned {r3.status_code}")

    # Parse JSON response
    try:
        data = r3.json()
    except Exception as e:
        raise Exception(f"Invalid JSON from numbers endpoint: {r3.text[:200]}")

    numbers = []
    rows = data.get("data", []) if isinstance(data, dict) else data
    if not rows:
        rows = data.get("aaData", [])

    for row in rows:
        # Find phone number in row (any cell containing 7-15 digits)
        phone = None
        for cell in row:
            if isinstance(cell, str) and re.search(r'\d{7,15}', cell):
                phone = cell
                break
        if not phone:
            continue
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
