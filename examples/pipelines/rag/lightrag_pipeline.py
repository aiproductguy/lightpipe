from typing import List, Union, Generator, Iterator
from schemas import OpenAIChatMessage
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.llm import gpt_4o_mini_complete
from llama_index.readers.web import SimpleWebPageReader

# Load environment variables
load_dotenv()

class Pipeline:
    class Valves(BaseModel):
        OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
        WORKING_DIR: str = os.getenv("WORKING_DIR", ".ra")
        SEARCH_MODE: str = "hybrid"  # Can be 'naive', 'local', 'global', or 'hybrid'

    def __init__(self):
        self.name = "LightRAG Pipeline"
        self.rag = None
        self.valves = self.Valves()
        
        # Set OpenAI API key
        os.environ["OPENAI_API_KEY"] = self.valves.OPENAI_API_KEY

    async def on_startup(self):
        print(f"on_startup:{__name__}")
        
        # Create working directory if it doesn't exist
        os.makedirs(self.valves.WORKING_DIR, exist_ok=True)

        # Initialize LightRAG
        self.rag = LightRAG(
            working_dir=self.valves.WORKING_DIR,
            llm_model_func=gpt_4o_mini_complete,
        )

        try:
            # Try to load existing content
            if not os.path.exists(os.path.join(self.valves.WORKING_DIR, "index.faiss")):
                raise FileNotFoundError("No existing index found")
            print("Loaded existing index from storage")
        except FileNotFoundError:
            # If no index exists, create new one
            print("Creating new index...")
            # Scrape lightrag.github.io
            reader = SimpleWebPageReader(html_to_text=True)
            documents = await reader.aload_data(["https://lightrag.github.io/"])
            
            # Insert documents into LightRAG
            for doc in documents:
                self.rag.insert(doc.text)
            print("Created and persisted new index")

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")
        pass

    async def on_valves_updated(self):
        pass

    async def inlet(self, body: dict, user: dict) -> dict:
        return body

    async def outlet(self, body: dict, user: dict) -> dict:
        return body

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        print(f"pipe:{__name__}")

        # Get search mode from body or use default
        search_mode = body.get("search_mode", self.valves.SEARCH_MODE)
        
        # Create query parameters
        query_param = QueryParam(mode=search_mode)
        
        # Generate response
        response = self.rag.query(user_message, param=query_param)
        
        # Since LightRAG doesn't support streaming directly, we'll yield the response
        def response_generator():
            yield response
            
        return response_generator()
