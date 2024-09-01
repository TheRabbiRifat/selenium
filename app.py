import base64
import requests
import pdfkit
import fitz  # PyMuPDF
import random
import json
from flask import Flask, jsonify, make_response, request
from bs4 import BeautifulSoup

app = Flask(__name__)

# The URL that will always be scraped
TARGET_URL = 'https://everify.bdris.gov.bd'

# Proxy and user-agent configurations
PROXY_STRINGS = [
    "173.0.9.209:5792:jdqqvqgw:5b37ub9e7wp8",
    "192.168.0.2:8081:user2:pass2",
    "192.168.0.3:8082:user3:pass3",
    # Add more proxies as needed
]

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

# Convert proxy strings to a list of proxy dictionaries
def parse_proxies(proxy_strings):
    proxies = []
    for proxy_str in proxy_strings:
        parts = proxy_str.split(":")
        if len(parts) == 4:
            proxies.append({
                "ip": parts[0],
                "port": parts[1],
                "username": parts[2],
                "password": parts[3]
            })
    return proxies

PROXIES = parse_proxies(PROXY_STRINGS)

# Function to make a request using a random proxy and user-agent
def request_with_proxy():
    while True:
        proxy = random.choice(PROXIES)
        user_agent = random.choice(USER_AGENTS)
        proxies = {
            "http": f"http://{proxy['username']}:{proxy['password']}@{proxy['ip']}:{proxy['port']}",
            "https": f"https://{proxy['username']}:{proxy['password']}@{proxy['ip']}:{proxy['port']}"
        }
        headers = {
            "User-Agent": user_agent
        }
        try:
            response = requests.get(TARGET_URL, headers=headers, proxies=proxies, timeout=10, verify=False)
            if response.status_code == 200:
                return response
        except Exception as e:
            print(f"Proxy failed: {proxy['ip']}:{proxy['port']} - {e}")
            # Retry with another proxy
            continue

@app.route('/get_captcha', methods=['POST'])
def convert_to_pdf():
    try:
        response = request_with_proxy()
        soup = BeautifulSoup(response.content, 'html.parser')

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
        cookies = response.cookies.get_dict()

        # Get the origin IP (the IP that made the request)
        origin_ip = request.remote_addr

        # Prepare the response data
        response_data = {
            'status': response.status_code,
            'token': {
                'cookies': cookies,
                'values': hidden_inputs
            },
            'captcha': first_image_base64,
            'user_agent': response.request.headers['User-Agent'],
            'origin_ip': origin_ip,
            'proxy': response.request.proxies  # Include the proxy used
        }

        # Create and return the response with JSON formatted with indent
        return make_response(json.dumps(response_data, indent=4), 200)

    except Exception as e:
        return jsonify({'status': 500, 'error': 'Conversion Error', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
