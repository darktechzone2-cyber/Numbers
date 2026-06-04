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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/sign-in"
}

@app.route('/debug')
def debug():
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Step 1: GET login page
    r1 = session.get(f"{BASE_URL}/sign-in")
    print("Login page status:", r1.status_code)
    
    # Save the login page HTML for inspection
    login_html = r1.text
    
    # Find all input fields in the login form
    import re
    inputs = re.findall(r'<input[^>]*name=["\']([^"\']+)[^>]*>', login_html)
    
    # Find CSRF token (common names: _token, csrf_token, csrf)
    csrf = None
    for name in ['_token', 'csrf_token', 'csrf', 'authenticity_token']:
        match = re.search(rf'name=["\']{name}["\'][^>]*value=["\']([^"\']+)["\']', login_html)
        if match:
            csrf = match.group(1)
            break
    
    # Try to extract email/username field name
    username_field = 'username'
    if 'email' in login_html and 'name="email"' in login_html:
        username_field = 'email'
    
    # Step 2: POST login with all form data
    login_data = {username_field: CREDENTIALS["username"], "password": CREDENTIALS["password"]}
    if csrf:
        login_data[csrf_name] = csrf  # we need the actual name
        # Actually we need the correct name – we'll find the input name
        csrf_match = re.search(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']' + csrf + '["\']', login_html)
        if csrf_match:
            csrf_name = csrf_match.group(1)
            login_data[csrf_name] = csrf
    
    # Also include any other hidden inputs
    hidden_inputs = re.findall(r'<input[^>]*type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']+)["\']', login_html)
    for name, val in hidden_inputs:
        if name not in login_data:
            login_data[name] = val
    
    r2 = session.post(f"{BASE_URL}/sign-in", data=login_data, allow_redirects=False)
    # Follow redirect manually if needed
    if r2.status_code in (301, 302):
        redirect_url = r2.headers.get('Location')
        r2 = session.get(redirect_url, allow_redirects=True)
    
    # Step 3: Try to fetch numbers page if login succeeded
    numbers_data = None
    if r2.status_code == 200 and 'sign-in' not in r2.url:
        r3 = session.get(f"{BASE_URL}/agent/MySMSNumbers")
        numbers_data = r3.text[:1000]
    else:
        numbers_data = "Login failed; still on sign-in page"
    
    return jsonify({
        "login_page_status": r1.status_code,
        "csrf_found": csrf is not None,
        "csrf_value": csrf,
        "username_field": username_field,
        "hidden_inputs_found": len(hidden_inputs),
        "login_post_status": r2.status_code,
        "final_url_after_login": r2.url,
        "numbers_page_preview": numbers_data,
        "login_html_snippet": login_html[:1500]  # for debugging
    })

@app.route('/')
def index():
    return jsonify({"error": "Use /debug to inspect", "success": False})

if __name__ == "__main__":
    app.run()
