import requests
import re
import time
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

BASE_URL = "https://konektapremium.net"
CREDENTIALS = {"username": "Slaeem777", "password": "Slaeem777"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Accept-Language": "en-US,en;q=0.9"
}

@app.route('/debug')
def debug():
    """Return raw responses for debugging."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # 1. Get login page
    r1 = session.get(f"{BASE_URL}/sign-in")
    print(f"Login page status: {r1.status_code}")
    
    # Extract CSRF token
    csrf_token = None
    match = re.search(r'name="_token" value="([^"]+)"', r1.text)
    if match:
        csrf_token = match.group(1)
    
    # 2. Login
    login_data = {"username": CREDENTIALS["username"], "password": CREDENTIALS["password"]}
    if csrf_token:
        login_data["_token"] = csrf_token
    r2 = session.post(f"{BASE_URL}/sign-in", data=login_data, allow_redirects=True)
    print(f"Login response status: {r2.status_code}, final URL: {r2.url}")
    
    # 3. Fetch numbers page
    r3 = session.get(f"{BASE_URL}/agent/MySMSNumbers")
    
    return jsonify({
        "login_status": r1.status_code,
        "csrf_found": csrf_token is not None,
        "login_post_status": r2.status_code,
        "login_redirect_url": r2.url,
        "numbers_page_status": r3.status_code,
        "numbers_page_url": r3.url,
        "response_preview": r3.text[:1500]  # first 1500 chars
    })

@app.route('/')
def index():
    return jsonify({"error": "Use /debug to inspect", "success": False})

if __name__ == "__main__":
    app.run()
