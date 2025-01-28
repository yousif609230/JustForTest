import os
import PyPDF2

def read_pdf(file_path):
    # Open the PDF file in binary mode
    with open(file_path, 'rb') as file:
        # Create a PDF reader object
        reader = PyPDF2.PdfReader(file)
        
        # Initialize an empty string to store the text
        text = ""
        
        # Loop through each page and extract text
        for page in reader.pages:
            text += page.extract_text()
        
        return text

# Path to your PDF file
pdf_file_path = 'example.pdf'

# Read the PDF file
pdf_text = read_pdf(pdf_file_path)

# Print the extracted text
print(pdf_text)