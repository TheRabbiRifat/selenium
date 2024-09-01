import base64
import requests
import pdfkit
import fitz  # PyMuPDF
import random
import json
import time
import threading
from flask import Flask, jsonify, session, make_response, request
from flask_session import Session
from bs4 import BeautifulSoup

app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['PERMANENT_SESSION_LIFETIME'] = 300  # 5 minutes
Session(app)

# The URL that will always be scraped
TARGET_URL = 'https://everify.bdris.gov.bd'

# Proxy and user-agent configurations
PROXY_FILE_PATH = 'proxies.txt'
PROXY_VERIFY_INTERVAL = 300  # Time in seconds between proxy verifications
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.192 Safari/537.36"
]

# Global variable to store verified proxies
verified_proxies = []
last_proxy_check_time = 0

# Function to read proxies from the file
def read_proxies_from_file():
    try:
        with open(PROXY_FILE_PATH, 'r') as f:
            proxy_list = f.read().splitlines()
        return proxy_list
    except Exception as e:
        print(f"Error reading proxy file: {e}")
        return []

# Fetch and verify proxies
def fetch_and_verify_proxies():
    global verified_proxies, last_proxy_check_time
    while True:
        try:
            proxy_list = read_proxies_from_file()
            verified_proxies = []
            for proxy in proxy_list:
                if verify_proxy(proxy):
                    verified_proxies.append(proxy)
            last_proxy_check_time = time.time()
            with open('/tmp/verified_proxies.txt', 'w') as f:
                f.write("\n".join(verified_proxies))
        except Exception as e:
            print(f"Error fetching/verifying proxies: {e}")
        time.sleep(PROXY_VERIFY_INTERVAL)

# Function to verify if a proxy is alive
def verify_proxy(proxy):
    ip_port, username, password = proxy.split(":")
    proxies = {
        "http": f"http://{username}:{password}@{ip_port}",
        "https": f"https://{username}:{password}@{ip_port}"
    }
    test_url = "https://everify.bdris.gov.bd"
    try:
        response = requests.get(test_url, proxies=proxies, timeout=5)
        return response.status_code == 200
    except:
        return False

# Background thread to keep proxies up to date
threading.Thread(target=fetch_and_verify_proxies, daemon=True).start()

@app.route('/get_captcha', methods=['POST'])
def convert_to_pdf():
    try:
        global last_proxy_check_time, verified_proxies

        # Ensure proxies are verified within the last minute
        if time.time() - last_proxy_check_time > PROXY_VERIFY_INTERVAL:
            fetch_and_verify_proxies()

        # Start a session to fetch the webpage content using a proxy
        session.clear()
        session['requests_session'] = requests.Session()

        if verified_proxies:
            proxy = random.choice(verified_proxies)
            ip_port, username, password = proxy.split(":")
            session['requests_session'].proxies = {
                "http": f"http://{username}:{password}@{ip_port}",
                "https": f"https://{username}:{password}@{ip_port}"
            }

        # Select a random user agent from the list
        random_user_agent = random.choice(USER_AGENTS)
        session['requests_session'].headers.update({
            'User-Agent': random_user_agent
        })

        response = session['requests_session'].get(TARGET_URL, verify=False, timeout=10)
        response.raise_for_status()

        # Collect the status code from the website response
        status_code = response.status_code

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract hidden inputs
        hidden_inputs = {}
        for hidden_input in soup.find_all("input", type="hidden"):
            hidden_inputs[hidden_input.get("name")] = hidden_input.get("value", "")

        # Convert webpage to PDF
        pdf_path = '/tmp/webpage.pdf'
        pdfkit.from_url(TARGET_URL, pdf_path)

        # Extract images from PDF
        pdf_document = fitz.open(pdf_path)
        first_image_base64 = None

        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            images = page.get_images(full=True)
            if images:
                xref = images[0][0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]
                content_type = base_image["ext"]
                first_image_base64 = f"data:image/{content_type};base64," + base64.b64encode(image_bytes).decode('utf-8')
                break  # Exit after extracting the first image

        pdf_document.close()

        if not first_image_base64:
            first_image_base64 = None  # Set to None if no image found

        # Fetch cookies from the response
        cookies = session['requests_session'].cookies.get_dict()

        # Get the origin IP (the IP that made the request)
        origin_ip = request.remote_addr

        # Prepare the response data
        response_data = {
            'status': status_code,
            'token': {
                'cookies': cookies,
                'values': hidden_inputs
            },
            'captcha': first_image_base64,
            'user_agent': random_user_agent,
            'origin_ip': origin_ip,
            'proxy': session['requests_session'].proxies  # Include the proxy used
        }

        # Create and return the response with JSON formatted with indent
        return make_response(json.dumps(response_data, indent=4), 200)

    except Exception as e:
        return jsonify({'status': 500, 'error': 'Conversion Error', 'details': str(e)}), 500

@app.route('/get_verified_proxies', methods=['GET'])
def get_verified_proxies():
    try:
        global verified_proxies
        return jsonify({'verified_proxies': verified_proxies}), 200
    except Exception as e:
        return jsonify({'status': 500, 'error': 'Error fetching proxies', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
