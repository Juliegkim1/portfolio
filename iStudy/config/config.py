
# --- Configuration ---

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# --- Configuration ---
# d
if 'GEMINI_API_KEY' not in os.environ:
    print("WARNING: GEMINI_API_KEY environment variable not set.")

# Define the base directory for processing
BASE_DIR = Path("./document_corpus")
PROCESSED_DIR = BASE_DIR / "processed_articles"
SUMMARIES_DIR = BASE_DIR / "summarized_articles"
RAG_STORAGE_DIR = BASE_DIR / "rag_index" # LlamaIndex storage

# Create directories if they don't exist
BASE_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)
SUMMARIES_DIR.mkdir(exist_ok=True)
RAG_STORAGE_DIR.mkdir(exist_ok=True)

# LLM settings
# Using a high-performing model for categorization/summarization
MODEL = "gemini-2.5-pro"






# Ensure your OPENAI_API_KEY is set as an environment variable
# if 'OPENAI_API_KEY' not in os.environ:
#     print("WARNING: OPENAI_API_KEY environment variable not set.")

# # LLM settings
# MODEL = "gpt-4-turbo"