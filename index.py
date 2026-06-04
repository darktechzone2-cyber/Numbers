import requests
import re
import time
import json
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

BASE_URL = "https://konektapremium.net"
CREDENTIALS = {"username": "Slaeem777", "password": "Slaeem777"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/sign-in"
}

COUNTRY_MAP = {"1": "US/Canada", "44": "UK", "92": "Pakistan", "91": "India", "58": "Venezuela"}
def get_country(phone):
    s = str(phone).lstrip('+')
    for l in range(4,0,-1):
        if s[:l] in COUNTRY_MAP:
            return COUNTRY_MAP[s[:l]]
    return "Global"

def fetch_numbers():
    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. Get login page
    resp = session.get(f"{BASE_URL}/sign-in")
    if resp.status_code != 200:
        raise Exception(f"Login page error: {resp.status_code}")
    html = resp.text
    soup = BeautifulSoup(html, 'html.parser')

    # 2. Find the login form
    form = soup.find('form')
    if not form:
        raise Exception("No form found on login page")
    action = form.get('action', '/sign-in')
    if not action.startswith('http'):
        action = BASE_URL + action

    # 3. Extract all input fields (including hidden)
    fields = {}
    for inp in form.find_all('input'):
        name = inp.get('name')
        if not name:
            continue
        value = inp.get('value', '')
        fields[name] = value

    # 4. Extract captcha text (look for text containing "What is X + Y = ?")
    captcha_text = None
    for label in soup.find_all(['label', 'span', 'div']):
        txt = label.get_text()
        if 'What is' in txt and '+' in txt and '?' in txt:
            captcha_text = txt
            break
    if not captcha_text:
        raise Exception("Captcha text not found")
    m = re.search(r'(\d+)\s*\+\s*(\d+)\s*=\s*\?', captcha_text)
    if not m:
        raise Exception(f"Could not parse captcha: {captcha_text}")
    captcha_answer = str(int(m[1]) + int(m[2]))

    # 5. Identify which input field is for the captcha answer
    #    Look for an input whose placeholder contains "answer" or "captcha"
    captcha_field = None
    for inp in form.find_all('input'):
        placeholder = inp.get('placeholder', '').lower()
        name = inp.get('name', '')
        if 'answer' in placeholder or 'captcha' in placeholder or name in ('answer', 'captcha', 'ans'):
            captcha_field = name
            break
    if not captcha_field:
        # fallback: the first input that is not username/password/csrf
        for inp in form.find_all('input'):
            name = inp.get('name', '')
            if name and name not in ('username', 'password', '_token'):
                captcha_field = name
                break
    if not captcha_field:
        captcha_field = 'answer'   # last resort

    # 6. Add credentials and captcha answer to fields
    fields['username'] = CREDENTIALS['username']
    fields['password'] = CREDENTIALS['password']
    fields[captcha_field] = captcha_answer

    # 7. Submit the form
    resp2 = session.post(action, data=fields, allow_redirects=True)
    if "sign-in" in resp2.url:
        # Debug info
        snippet = resp2.text[:500]
        raise Exception(f"Login failed. Fields sent: {list(fields.keys())}. Captcha field='{captcha_field}' answer='{captcha_answer}'. Response snippet: {snippet}")

    # 8. Now fetch numbers
    ts = int(time.time() * 1000)
    numbers_url = f"{BASE_URL}/agent/MySMSNumbers?draw=1&start=0&length=-1&_={ts}"
    r3 = session.get(numbers_url, headers={"Referer": f"{BASE_URL}/agent/MySMSNumbers"})
    if r3.status_code != 200:
        raise Exception(f"Numbers endpoint error: {r3.status_code}")
    try:
        data = r3.json()
    except:
        raise Exception(f"Invalid JSON from numbers: {r3.text[:200]}")

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
        if phone:
            numbers.append({
                "phone": phone,
                "plan": row[3] if len(row)>3 else "",
                "country": get_country(phone)
            })
    return numbers

# ---------- CACHING ----------
cache = {"data": None, "last_fetch": 0}
CACHE_TTL = 60

@app.route('/')
def index():
    now = time.time()
    if cache["data"] and (now - cache["last_fetch"]) < CACHE_TTL:
        return jsonify({"success": True, "cached": True, "count": len(cache["data"]), "numbers": cache["data"]})
    try:
        nums = fetch_numbers()
        cache["data"] = nums
        cache["last_fetch"] = now
        return jsonify({"success": True, "cached": False, "count": len(nums), "numbers": nums})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run()
