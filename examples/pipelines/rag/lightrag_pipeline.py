from typing import List, Union, Generator, Iterator
from schemas import OpenAIChatMessage
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.llm import gpt_4o_mini_complete, gpt_4o_complete
from llama_index.readers.web import SimpleWebPageReader

# Load environment variables
load_dotenv()

class Pipeline:
    class Valves(BaseModel):
        # OpenAI Configuration
        OPENAI_API_KEY: str
        
        # LightRAG Configuration
        WORKING_DIR: str
        SEARCH_MODE: str  # Can be 'naive', 'local', 'global', or 'hybrid'
        LLM_MODEL: str  # Can be 'gpt-4' or other OpenAI models
        USE_MINI_MODEL: bool  # Whether to use gpt_4o_mini_complete or gpt_4o_complete
        
        # Web Scraping Configuration
        TARGET_URL: str
        HTML_TO_TEXT: bool
        
        # Index Configuration
        CHUNK_SIZE: int
        CHUNK_OVERLAP: int
        DISTANCE_METRIC: str  # Can be 'cosine', 'euclidean', etc.
        TOP_K: int  # Number of chunks to retrieve

    def __init__(self):
        self.type = "pipeline"
        self.name = "LightRAG Pipeline"
        self.valves = self.Valves(
            **{
                # OpenAI Configuration
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "your-openai-api-key-here"),
                
                # LightRAG Configuration
                "WORKING_DIR": os.getenv("WORKING_DIR", ".ra"),
                "SEARCH_MODE": os.getenv("SEARCH_MODE", "hybrid"),
                "LLM_MODEL": os.getenv("LLM_MODEL", "gpt-4"),
                "USE_MINI_MODEL": os.getenv("USE_MINI_MODEL", "true").lower() == "true",
                
                # Web Scraping Configuration
                "TARGET_URL": os.getenv("TARGET_URL", "https://lightrag.github.io/"),
                "HTML_TO_TEXT": os.getenv("HTML_TO_TEXT", "true").lower() == "true",
                
                # Index Configuration
                "CHUNK_SIZE": int(os.getenv("CHUNK_SIZE", "1000")),
                "CHUNK_OVERLAP": int(os.getenv("CHUNK_OVERLAP", "200")),
                "DISTANCE_METRIC": os.getenv("DISTANCE_METRIC", "cosine"),
                "TOP_K": int(os.getenv("TOP_K", "5"))
            }
        )
        self.rag = None
        self.set_pipelines()
        
        # Set OpenAI API key
        os.environ["OPENAI_API_KEY"] = self.valves.OPENAI_API_KEY

    def set_pipelines(self):
        search_modes = ["naive", "local", "global", "hybrid"]
        self.pipelines = [
            {"id": mode, "name": f"LightRAG ({mode.capitalize()} Search)"} 
            for mode in search_modes
        ]
        print(f"lightrag_pipeline - search modes: {self.pipelines}")

    async def on_startup(self):
        print(f"on_startup:{__name__}")
        
        # Create working directory if it doesn't exist
        os.makedirs(self.valves.WORKING_DIR, exist_ok=True)

        # Initialize LightRAG with appropriate model function
        llm_func = gpt_4o_mini_complete if self.valves.USE_MINI_MODEL else gpt_4o_complete
        
        self.rag = LightRAG(
            working_dir=self.valves.WORKING_DIR,
            llm_model_func=llm_func,
            chunk_size=self.valves.CHUNK_SIZE,
            chunk_overlap=self.valves.CHUNK_OVERLAP,
            distance_metric=self.valves.DISTANCE_METRIC,
            top_k=self.valves.TOP_K
        )

        try:
            # Try to load existing content
            if not os.path.exists(os.path.join(self.valves.WORKING_DIR, "index.faiss")):
                raise FileNotFoundError("No existing index found")
            print("Loaded existing index from storage")
        except FileNotFoundError:
            # If no index exists, create new one
            print("Creating new index...")
            # Scrape target URL
            reader = SimpleWebPageReader(html_to_text=self.valves.HTML_TO_TEXT)
            documents = await reader.aload_data([self.valves.TARGET_URL])
            
            # Insert documents into LightRAG
            for doc in documents:
                self.rag.insert(doc.text)
            print("Created and persisted new index")

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")
        pass

    async def on_valves_updated(self):
        # Update pipelines
        self.set_pipelines()
        
        # Reinitialize LightRAG with updated settings
        llm_func = gpt_4o_mini_complete if self.valves.USE_MINI_MODEL else gpt_4o_complete
        
        self.rag = LightRAG(
            working_dir=self.valves.WORKING_DIR,
            llm_model_func=llm_func,
            chunk_size=self.valves.CHUNK_SIZE,
            chunk_overlap=self.valves.CHUNK_OVERLAP,
            distance_metric=self.valves.DISTANCE_METRIC,
            top_k=self.valves.TOP_K
        )
        print("LightRAG reinitialized with updated valves")

    async def inlet(self, body: dict, user: dict) -> dict:
        return body

    async def outlet(self, body: dict, user: dict) -> dict:
        return body

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        print(f"pipe:{__name__}")

        # Get search mode from model_id or use default
        search_mode = model_id or self.valves.SEARCH_MODE
        
        # Create query parameters
        query_param = QueryParam(
            mode=search_mode,
            top_k=self.valves.TOP_K,
            distance_metric=self.valves.DISTANCE_METRIC
        )
        
        # Generate response
        response = self.rag.query(user_message, param=query_param)
        
        # Since LightRAG doesn't support streaming directly, we'll yield the response
        def response_generator():
            yield response
            
        return response_generator()
