import base64
import fitz  # PyMuPDF
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from weasyprint import HTML

app = Flask(__name__)

def get_webpage_pdf(url):
    # Set up Selenium with options
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--headless")

    # Initialize WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    # Open the webpage
    driver.get(url)
    
    # Get the page source (HTML)
    page_source = driver.page_source
    
    # Convert the HTML to a PDF using WeasyPrint
    html = HTML(string=page_source)
    pdf_file_path = "output.pdf"
    html.write_pdf(pdf_file_path)
    
    # Close the browser
    driver.quit()
    
    return pdf_file_path

def extract_images_from_pdf(pdf_path):
    pdf_document = fitz.open(pdf_path)
    images_base64 = []

    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]  # File extension
            
            # Convert image to Base64
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            mime_type = f"image/{image_ext}"
            
            # Store the Base64 string with MIME type
            images_base64.append({
                "base64": image_base64,
                "mime_type": mime_type
            })
    
    return images_base64

@app.route('/scrape-to-pdf', methods=['POST'])
def scrape_to_pdf():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    try:
        # Step 1: Get the PDF of the webpage
        pdf_path = get_webpage_pdf(url)
        
        # Step 2: Extract images from the PDF
        images_base64 = extract_images_from_pdf(pdf_path)
        
        # Step 3: Return the images in Base64 format
        return jsonify({"images": images_base64}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
  
