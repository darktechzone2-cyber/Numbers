import requests
import re
import time
import json
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

# ========== CONFIGURATION ==========
BASE_URL = "https://konektapremium.net"
CREDENTIALS = {"username": "Slaeem777", "password": "Slaeem777"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Accept-Language": "en-US,en;q=0.9"
}

# Country mapping (short version – you can extend)
COUNTRY_MAP = {
    "1": "US/Canada", "44": "UK", "92": "Pakistan", "91": "India", "58": "Venezuela",
}

def get_country(phone):
    s = str(phone).lstrip('+')
    for length in range(4, 0, -1):
        prefix = s[:length]
        if prefix in COUNTRY_MAP:
            return COUNTRY_MAP[prefix]
    return "Global"

def extract_login_fields(html):
    """Extract all input fields from login form."""
    soup = BeautifulSoup(html, 'html.parser')
    form = soup.find('form')
    if not form:
        return {}
    fields = {}
    for inp in form.find_all('input'):
        name = inp.get('name')
        if name:
            fields[name] = inp.get('value', '')
    # Also look for captcha text
    captcha_text = None
    for label in soup.find_all(['label', 'span', 'div']):
        text = label.get_text()
        if 'What is' in text and '+' in text and '?' in text:
            captcha_text = text
            break
    return fields, captcha_text

def fetch_numbers():
    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. GET login page
    r1 = session.get(f"{BASE_URL}/sign-in")
    if r1.status_code != 200:
        raise Exception(f"Login page failed: {r1.status_code}")

    html = r1.text
    fields, captcha_text = extract_login_fields(html)
    
    # Extract CSRF token (if any)
    csrf_token = fields.get('_token')
    
    # Extract captcha answer
    if not captcha_text:
        raise Exception("Captcha text not found on login page")
    match = re.search(r'What is (\d+) \+ (\d+) = \?', captcha_text)
    if not match:
        match = re.search(r'(\d+)\s*\+\s*(\d+)\s*=\s*\?', captcha_text)
    if not match:
        raise Exception(f"Could not parse captcha: {captcha_text}")
    captcha_answer = int(match[1]) + int(match[2])
    
    # Determine the field name for the captcha answer
    # Look for an input with placeholder containing "answer" or "captcha"
    soup = BeautifulSoup(html, 'html.parser')
    answer_field = None
    for inp in soup.find_all('input'):
        placeholder = inp.get('placeholder', '').lower()
        name = inp.get('name', '')
        if 'answer' in placeholder or 'captcha' in placeholder or name in ('answer', 'captcha', 'ans'):
            answer_field = name
            break
    if not answer_field:
        # fallback: use the first input that is not username/password/csrf
        for inp in soup.find_all('input'):
            name = inp.get('name', '')
            if name and name not in ('username', 'password', '_token'):
                answer_field = name
                break
    if not answer_field:
        answer_field = 'answer'  # last resort

    # Prepare login data
    login_data = {
        "username": CREDENTIALS["username"],
        "password": CREDENTIALS["password"],
        answer_field: captcha_answer
    }
    if csrf_token:
        login_data["_token"] = csrf_token

    # 2. Submit login
    r2 = session.post(f"{BASE_URL}/sign-in", data=login_data, allow_redirects=True)
    if "sign-in" in r2.url:
        # Debug: print the failure reason
        snippet = r2.text[:500]
        raise Exception(f"Login failed – still on sign-in page. Captcha field used: '{answer_field}', value {captcha_answer}. Response snippet: {snippet}")

    # 3. Fetch numbers
    ts = int(time.time() * 1000)
    numbers_url = f"{BASE_URL}/agent/MySMSNumbers?draw=1&start=0&length=-1&_={ts}"
    r3 = session.get(numbers_url, headers={"Referer": f"{BASE_URL}/agent/MySMSNumbers"})
    if r3.status_code != 200:
        raise Exception(f"Numbers endpoint returned {r3.status_code}")

    try:
        data = r3.json()
    except Exception as e:
        raise Exception(f"Invalid JSON: {r3.text[:200]}")

    numbers = []
    rows = data.get("data", []) if isinstance(data, dict) else data
    if not rows:
        rows = data.get("aaData", [])

    for row in rows:
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

# ---------- DEBUG ENDPOINT ----------
@app.route('/debug')
def debug():
    session = requests.Session()
    session.headers.update(HEADERS)
    r1 = session.get(f"{BASE_URL}/sign-in")
    if r1.status_code != 200:
        return jsonify({"error": f"Login page status {r1.status_code}"})
    fields, captcha_text = extract_login_fields(r1.text)
    soup = BeautifulSoup(r1.text, 'html.parser')
    answer_input = None
    for inp in soup.find_all('input'):
        if 'answer' in inp.get('placeholder', '').lower() or inp.get('name') in ('answer', 'captcha', 'ans'):
            answer_input = inp.get('name')
            break
    return jsonify({
        "status": r1.status_code,
        "captcha_text": captcha_text,
        "form_fields": fields,
        "detected_answer_field": answer_input,
        "html_snippet": r1.text[:800]
    })

# ---------- MAIN ENDPOINT ----------
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
