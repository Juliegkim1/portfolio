import os
from pypdf import PdfReader
from pathlib import Path
from config.config import BASE_DIR, PROCESSED_DIR, SUMMARIES_DIR

class DataHandler:
    def __init__(self, source_type="local"):
        self.source_type = source_type
        if source_type == "local":
            print(f"Connecting to local folder: {BASE_DIR.resolve()}")
        elif source_type == "gdrive":
            # NOTE: Google Drive integration requires complex setup (auth flow).
            # This implementation focuses on the local file system structure.
            # Replace the file listing/download logic here with pydrive2 methods.
            print("Google Drive integration requires pydrive2 setup.")
            pass # Placeholder for GDrive initialization

    def get_local_pdf_files(self):
        """Returns a list of unprocessed PDF paths."""
        unprocessed_files = []
        for file_path in BASE_DIR.glob("*.pdf"):
            if not (PROCESSED_DIR / file_path.name).exists():
                 unprocessed_files.append(file_path)
        return unprocessed_files

    @staticmethod
    def extract_text_from_pdf(file_path: Path) -> str:
        """Extracts all text content from a PDF file."""
        print(f"Parsing: {file_path.name}")
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text if text else "Error: Could not extract text."
        except Exception as e:
            print(f"Error parsing PDF {file_path}: {e}")
            return None

    @staticmethod
    def save_summary(original_name: str, summary: str):
        """Saves the summary to the summaries folder."""
        summary_path = SUMMARIES_DIR / f"{original_name.replace('.pdf', '')}_SUMMARY.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)
        print(f"Saved summary to {summary_path.name}")

    @staticmethod
    def rename_and_move_pdf(original_path: Path, new_title: str, category: str):
        """Renames the PDF and moves it to the processed folder."""
        # Clean title for filename use
        safe_title = "".join(c for c in new_title if c.isalnum() or c in (' ', '_')).rstrip()
        new_filename = f"[{category.upper()}] - {safe_title}.pdf"
        new_path = PROCESSED_DIR / new_filename

        try:
            os.rename(original_path, new_path)
            print(f"Moved and renamed to: {new_path.name}")
            return new_path
        except Exception as e:
            print(f"Error renaming/moving {original_path}: {e}")
            return None
