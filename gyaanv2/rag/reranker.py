import logging
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


class Reranker:
    """Cross-encoder reranker for scoring query/chunk pairs."""

    def __init__(self, model_name: str, device: str | None = None, max_length: int = 512):
        self.model_name = model_name
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name, trust_remote_code=True)
        self.model.to(self.device)
        self.model.eval()

    def rerank(self, query: str, contexts: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        if not contexts:
            return []

        pairs = [(query, context.get('content', '')) for context in contexts]
        inputs = self.tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors='pt',
        )
        inputs = {name: tensor.to(self.device) for name, tensor in inputs.items()}

        with torch.no_grad():
            logits = self.model(**inputs).logits
            scores = logits.view(-1).detach().cpu().tolist()

        reranked = []
        for context, score in zip(contexts, scores):
            updated = dict(context)
            updated['reranker_score'] = float(score)
            reranked.append(updated)

        reranked.sort(key=lambda item: item['reranker_score'], reverse=True)
        logger.info('Top reranker scores: %s', [round(item['reranker_score'], 4) for item in reranked[:top_k]])
        return reranked[:top_k]
