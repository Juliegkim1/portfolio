import pyttsx3
import os
from pathlib import Path
from connect.data_handler import DataHandler
from app.llm_agents import LLMAgents
from config.config import BASE_DIR, SUMMARIES_DIR

class DocumentApp:
    def __init__(self):
        self.data_handler = DataHandler(source_type="local")
        self.llm_agents = LLMAgents()
        # Agent 3: TTS setup
        self.verbalizer = pyttsx3.init()
        # Set faster speaking rate
        self.verbalizer.setProperty('rate', 170) 

    # --- Agent 3: Text-to-Speech ---
    def speak(self, text: str):
        """Reads text aloud using pyttsx3."""
        print("\n--- VOICE OUTPUT START ---")
        self.verbalizer.say(text)
        self.verbalizer.runAndWait()
        print("--- VOICE OUTPUT END ---\n")

    # --- Orchestration Function ---
    def process_all_documents(self):
        """Runs Agents 1 and 2 sequentially on all unprocessed PDFs."""
        unprocessed_files = self.data_handler.get_local_pdf_files()
        
        if not unprocessed_files:
            print("No new documents found in the base folder to process.")
            return

        print(f"\n--- Starting Processing for {len(unprocessed_files)} documents ---")
        
        for i, file_path in enumerate(unprocessed_files):
            print(f"\n[{i+1}/{len(unprocessed_files)}] Processing: {file_path.name}")
            
            # 1. Extract Content
            content = self.data_handler.extract_text_from_pdf(file_path)
            if not content or len(content) < 100:
                print("Skipping due to insufficient content.")
                continue

            # 2. Agent 1: Categorize and Rename
            metadata = self.llm_agents.categorize_and_title(content)
            category = metadata['category']
            new_title = metadata['new_title']
            
            print(f"  > Category: {category} | New Title: {new_title}")
            
            # 3. Agent 2: Summarize
            summary = self.llm_agents.summarize_content(content)
            
            # 4. Save and Move
            self.data_handler.save_summary(file_path.name, summary)
            self.data_handler.rename_and_move_pdf(file_path, new_title, category)

        # 5. Build/Update RAG Index after processing
        self.llm_agents.build_rag_index(SUMMARIES_DIR)
        print("\n--- Processing Complete ---")

    def run_cli(self):
        """Main command-line interface loop."""
        while True:
            print("\n=============================================")
            print("        DOCUMENT MANAGEMENT AGENT SYSTEM")
            print("=============================================")
            print("1. Process All Unprocessed PDFs (Categorize & Summarize)")
            print("2. Ask a Question about Processed Topics (RAG)")
            print("3. Hear a Summary Aloud (TTS)")
            print("4. Quit")
            
            choice = input("Enter choice (1-4): ")

            if choice == '1':
                self.process_all_documents()
            
            elif choice == '2':
                # Ensure index is built if we skipped step 1
                if self.llm_agents._index is None and any(SUMMARIES_DIR.iterdir()):
                    self.llm_agents.build_rag_index(SUMMARIES_DIR)

                question = input("What topic are you curious about (e.g., 'What medical breakthroughs did I read about?' or 'What files are still left to read?')?\n> ")
                if question.lower() == 'what is left to read?':
                    left = self.data_handler.get_local_pdf_files()
                    if left:
                        print("Files left to read/process:")
                        print('\n'.join([f"- {f.name}" for f in left]))
                    else:
                        print("All files have been processed!")
                else:
                    answer = self.llm_agents.query_index(question)
                    print("\n--- AGENT ANSWER ---")
                    print(answer)
                    print("--------------------\n")

            elif choice == '3':
                summary_files = [f.name for f in SUMMARIES_DIR.glob("*.txt")]
                if not summary_files:
                    print("No summaries found. Please run option 1 first.")
                    continue
                
                print("\nAvailable summaries:")
                for i, name in enumerate(summary_files):
                    print(f"{i+1}. {name}")
                
                file_choice = input("Enter number of the summary to hear: ")
                try:
                    index = int(file_choice) - 1
                    summary_path = SUMMARIES_DIR / summary_files[index]
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        text_to_speak = f.read()
                    
                    self.speak(text_to_speak)
                except (ValueError, IndexError):
                    print("Invalid choice.")
            
            elif choice == '4':
                print("Exiting application.")
                break

            else:
                print("Invalid choice. Please try again.")

if __name__ == "__main__":
    app = DocumentApp()
    app.run_cli()