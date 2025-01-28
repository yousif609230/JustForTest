import PyPDF2
import os

def read_pdf(file_path):
    # Validate file path
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")
    
    if not file_path.lower().endswith('.pdf'):
        raise ValueError("The file must be a PDF.")
    
    # Limit file size (e.g., 10 MB)
    max_file_size = 10 * 1024 * 1024  # 10 MB
    file_size = os.path.getsize(file_path)
    if file_size > max_file_size:
        raise ValueError(f"The file is too large. Maximum allowed size is {max_file_size / (1024 * 1024)} MB.")
    
    try:
        # Open the PDF file in binary mode
        with open(file_path, 'rb') as file:
            # Create a PDF reader object
            reader = PyPDF2.PdfReader(file)
            
            # Check if the PDF is encrypted
            if reader.is_encrypted:
                raise ValueError("The PDF is encrypted and cannot be read.")
            
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
        if not os.path.isabs(pdf_file_path):
            pdf_file_path = os.path.abspath(pdf_file_path)
        
        # Read the PDF file
        pdf_text = read_pdf(pdf_file_path)
        
        # Print the extracted text
        print(pdf_text)
    except Exception as e:
        print(f"Error: {e}")