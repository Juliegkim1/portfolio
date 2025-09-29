import json
from pathlib import Path
from google import genai
from google.genai import types

# LlamaIndex Imports for RAG
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.readers.file import SimpleDirectoryReader
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding

from config import MODEL, RAG_STORAGE_DIR

# Initialize Gemini Client
try:
    client = genai.Client()
except Exception as e:
    print(f"Error initializing Gemini Client: {e}")
    client = None

class LLMAgents:
    def __init__(self):
        self._index = None # For LlamaIndex RAG
        # Configure LlamaIndex to use Gemini
        Settings.llm = Gemini(model=MODEL)
        # Use Google's standard embedding model
        Settings.embed_model = GeminiEmbedding(model="models/embedding-001") 

    # --- AGENT 1: Categorization and Renaming (Using structured JSON output) ---
    def categorize_and_title(self, document_text: str) -> dict:
        """Analyzes content, assigns category, and suggests a new title."""
        system_prompt = (
            "You are an expert document analyst. Analyze the provided PDF text. "
            "1. Assign a single, broad category (e.g., Finance, Legal, Medical, Research, Technical). "
            "2. Suggest a concise, descriptive title for the document based on its main topic. "
            "Return ONLY a JSON object that matches the requested schema."
        )
        
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[
                    {"role": "user", "parts": [{"text": system_prompt + "\n\nDOCUMENT CONTENT:\n" + document_text[:5000]}]}
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "The determined broad category."},
                            "new_title": {"type": "string", "description": "A concise title reflecting the content."}
                        },
                        "required": ["category", "new_title"]
                    }
                )
            )
            
            # Gemini returns the JSON as a string in response.text
            result = json.loads(response.text)
            
            return {
                'category': result['category'].strip(),
                'new_title': result['new_title'].strip()
            }
        except Exception as e:
            print(f"Error in categorization agent: {e}")
            return {'category': 'UNCATEGORIZED', 'new_title': 'Failed to Analyze'}

    # --- AGENT 2: Summarization ---
    def summarize_content(self, document_text: str) -> str:
        """Generates a detailed summary."""
        system_prompt = (
            "You are a professional abstract generator. Provide a detailed, "
            "three-paragraph summary of the document. Focus on the introduction, "
            "key findings, and final conclusions."
        )
        
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[
                    {"role": "user", "parts": [{"text": system_prompt + "\n\nDOCUMENT CONTENT:\n" + document_text}]}
                ]
            )
            return response.text
        except Exception as e:
            print(f"Error in summarization agent: {e}")
            return "Summary generation failed."

    # --- AGENT 4: Querying (RAG System - Uses LlamaIndex configured for Gemini) ---
    def build_rag_index(self, folder_path: Path):
        """Indexes the summarized articles for querying."""
        print(f"\nBuilding RAG Index from {folder_path.name}...")
        
        reader = SimpleDirectoryReader(input_dir=folder_path)
        documents = reader.load_data()
        
        # Create or load the index
        if not RAG_STORAGE_DIR.exists() or not list(RAG_STORAGE_DIR.iterdir()):
            self._index = VectorStoreIndex.from_documents(documents)
            self._index.storage_context.persist(persist_dir=RAG_STORAGE_DIR)
            print("Index built and saved.")
        else:
            from llama_index.core import StorageContext, load_index_from_storage
            storage_context = StorageContext.from_defaults(persist_dir=RAG_STORAGE_DIR)
            self._index = load_index_from_storage(storage_context)
            print("Index loaded from disk.")

    def query_index(self, question: str) -> str:
        """Queries the built index."""
        if self._index is None:
            return "RAG index has not been built yet. Run the processing step first."

        query_engine = self._index.as_query_engine()
        response = query_engine.query(question)
        return str(response)