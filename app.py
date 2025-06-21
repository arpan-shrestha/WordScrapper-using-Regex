from flask import Flask, request, render_template_string
from werkzeug.utils import secure_filename
import os
import fitz  # PyMuPDF
import re

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_quantity(line, code):
    # Remove code substring from line to avoid confusion
    line_wo_code = line.replace(code, '')

    # Look for explicit quantity keywords or standalone numbers
    qty_match = re.search(r'(?:qty|quantity)?[:\s]*([0-9]+|As specified)', line_wo_code, re.IGNORECASE)
    if qty_match:
        return qty_match.group(1)

    standalone_num = re.search(r'\b(\d+)\b', line_wo_code)
    if standalone_num:
        return standalone_num.group(1)

    # Default fallback quantity
    return '1'

def extract_code_descriptions(text):
    lines = text.splitlines()
    results = []

    patterns = {
        'Portal Frame': r'\b\d{3}UB\d{2}\b',              # e.g. 360UB57
        'Reinforcement': r'\bD\d{2}@\d{2,3}\b',           # e.g. D16@200
        'Welded Mesh': r'\b\d{3}\s?mesh\b',                # e.g. 665 mesh
        'Roofing': r'\b0\.55mm BMT\b',                      # e.g. 0.55mm BMT
    }
    combined_pattern = re.compile('|'.join(patterns.values()), re.IGNORECASE)

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = combined_pattern.search(line)
        if match:
            code = match.group()
            category = next((cat for cat, pat in patterns.items() if re.search(pat, code, re.IGNORECASE)), 'Unknown')

            # Improved quantity extraction
            quantity = extract_quantity(line, code)

            description_lines = []
            desc_count = 0
            i += 1
            while i < len(lines) and desc_count < 3:
                next_line = lines[i].strip()
                if not next_line or combined_pattern.search(next_line):
                    break
                description_lines.append(next_line)
                desc_count += 1
                i += 1

            description = ' '.join(description_lines).strip()

            results.append({
                'code': code,
                'desc': description,
                'qty': quantity,
                'type': category
            })
        else:
            i += 1
    return results

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            text = extract_text_from_pdf(filepath)
            codes = extract_code_descriptions(text)

            if not codes:
                return "<h2>No engineering specifications found. Please check the document format.</h2>"

            table_html = """
            <h2>Extracted Engineering Codes and Descriptions:</h2>
            <table border="1" cellpadding="8" cellspacing="0">
            <tr>
                <th>Code</th>
                <th>Description</th>
                <th>Category</th>
                <th>Qty</th>
            </tr>
            """
            for item in codes:
                table_html += f"<tr><td>{item['code']}</td><td>{item['desc']}</td><td>{item['type']}</td><td>{item['qty']}</td></tr>"
            table_html += "</table><br><a href='/'>Upload another file</a>"
            return table_html

    return '''
    <!doctype html>
    <title>Upload PDF</title>
    <h1>Upload Engineering Spec PDF</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file accept=".pdf">
      <input type=submit value=Upload>
    </form>
    '''

if __name__ == '__main__':
    app.run(debug=True)
