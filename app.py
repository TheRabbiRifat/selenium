import base64
import requests
import pdfkit
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, session
from flask_session import Session
from bs4 import BeautifulSoup

app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['PERMANENT_SESSION_LIFETIME'] = 300  # 5 minutes
Session(app)

@app.route('/convert-to-pdf', methods=['POST'])
def convert_to_pdf():
    url = request.json.get('url')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        # Convert webpage to PDF
        pdf_path = '/tmp/webpage.pdf'
        pdfkit.from_url(url, pdf_path)

        # Extract images from PDF
        pdf_document = fitz.open(pdf_path)
        images = []

        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]
                content_type = base_image["ext"]
                image_base64 = f"data:image/{content_type};base64," + base64.b64encode(image_bytes).decode('utf-8')
                images.append(image_base64)

        pdf_document.close()

        return jsonify({
            'status': 'success',
            'images': images
        })

    except Exception as e:
        return jsonify({'error': 'Conversion Error', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
