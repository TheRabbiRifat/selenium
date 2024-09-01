import base64
import requests
import pdfkit
import fitz  # PyMuPDF
from flask import Flask, jsonify, session, make_response
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

@app.route('/convert-to-pdf', methods=['POST'])
def convert_to_pdf():
    try:
        # Start a session to fetch the webpage content
        session.clear()
        session['requests_session'] = requests.Session()
        session['requests_session'].headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'
        })
        
        response = session['requests_session'].get(TARGET_URL, verify=False, timeout=10)
        response.raise_for_status()  # Will raise an HTTPError for bad responses

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

        # Prepare the response data
        response_data = {
            'status': status_code,  # Collect status code from the website response
            'token': {
                'cookies': cookies,
                'values': hidden_inputs
            },
            'image': first_image_base64  # Include the base64 image
        }

        # Create and return the response
        return make_response(jsonify(response_data))

    except Exception as e:
        return jsonify({'status': 500, 'error': 'Conversion Error', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
