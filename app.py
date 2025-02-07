import PyPDF2
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def sanitize_file_path(file_path):
    """Sanitize the file path to ensure it is safe."""
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)
    return file_path

def is_valid_pdf(file_path):
    """Check if the file is a valid PDF."""
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            return True
    except PyPDF2.PdfReadError:
        return False

def read_pdf(file_path):
    """Read and extract text from a PDF file."""
    # Validate file path
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")
    
    if not file_path.lower().endswith('.pdf'):
        raise ValueError("The file must be a PDF.")
    
    # Limit file size to 2 MB
    max_file_size = 2 * 1024 * 1024  # 2 MB
    file_size = os.path.getsize(file_path)
    if file_size > max_file_size:
        logging.warning(f"The file is large ({file_size / (1024 * 1024):.2f} MB). Proceeding with reading...")
    
    try:
        # Open the PDF file in binary mode
        with open(file_path, 'rb') as file:
            # Create a PDF reader object
            reader = PyPDF2.PdfReader(file)
            
            # Check if the PDF is encrypted
            if reader.is_encrypted:
                password = input("The PDF is encrypted. Enter the password: ")
                if not reader.decrypt(password):
                    raise ValueError("Incorrect password. The PDF could not be decrypted.")
            
            # Initialize an empty string to store the text
            text = ""
            
            # Loop through each page and extract text
            for page in reader.pages:
                text += page.extract_text()
            
            return text
    except PyPDF2.PdfReadError:
        raise ValueError("The file is not a valid PDF or could not be read.")
    except Exception as e:
        raise RuntimeError(f"An error occurred while reading the PDF: {e}")

# Example usage
if __name__ == "__main__":
    try:
        # Path to your PDF file
        pdf_file_path = input("Enter the path to the PDF file: ").strip()
        
        # Sanitize input: Ensure the path is safe
        pdf_file_path = sanitize_file_path(pdf_file_path)
        
        # Check if the file is a valid PDF
        if not is_valid_pdf(pdf_file_path):
            raise ValueError("The file is not a valid PDF.")
        
        # Read the PDF file
        pdf_text = read_pdf(pdf_file_path)
        
        # Print the extracted text
        print(pdf_text)
    except Exception as e:
        logging.error(f"Error: {e}")