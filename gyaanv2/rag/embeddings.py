from sentence_transformers import SentenceTransformer
import torch

class Embedder:
    def __init__(self, model_name:str):
        with torch.device("cpu"):
            self.model = SentenceTransformer(model_name, device="cpu")
    @property
    def dimension(self):
        return self.model.get_sentence_embedding_dimension()
    def embed_texts(self, texts:list[str])->list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()
    def embed_query(self, text:str)->list[float]:
        return self.embed_texts([text])[0]