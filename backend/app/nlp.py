import asyncio
from collections import Counter
from difflib import SequenceMatcher

import spacy
from transformers import pipeline

from app.schemas import AnalysisResult, DiffChunk


class NlpService:
    def __init__(self) -> None:
        self._nlp = spacy.blank('ru')
        self._sentiment_pipe = pipeline(
            'text-classification',
            model='blanchefort/rubert-base-cased-sentiment',
            return_all_scores=False,
        )

    async def analyze(self, text: str) -> AnalysisResult:
        return await asyncio.to_thread(self._analyze_sync, text)

    def _analyze_sync(self, text: str) -> AnalysisResult:
        doc = self._nlp(text)
        tokens = [t.text.lower() for t in doc if t.is_alpha and not t.is_stop and len(t.text) > 3]
        topics = [w for w, _ in Counter(tokens).most_common(5)]

        sentiment_raw = self._sentiment_pipe(text[:512])[0]['label'].lower()
        sentiment = 'neutral'
        if 'positive' in sentiment_raw or 'pos' in sentiment_raw:
            sentiment = 'positive'
        elif 'negative' in sentiment_raw or 'neg' in sentiment_raw:
            sentiment = 'tense'

        formal_markers = ('уважаем', 'благодар', 'сообщаем', 'просим', 'коллег')
        informal_markers = ('привет', 'ок', 'ладно', 'щас', 'сорян')
        lower = text.lower()
        formal_score = sum(1 for m in formal_markers if m in lower) - sum(1 for m in informal_markers if m in lower)
        if formal_score >= 2:
            formality = 'high'
        elif formal_score <= -1:
            formality = 'low'
        else:
            formality = 'medium'

        if not topics:
            topics = ['общее обсуждение']

        return AnalysisResult(sentiment=sentiment, topics=topics, formality=formality)

    @staticmethod
    def make_diff(source: str, target: str) -> list[DiffChunk]:
        matcher = SequenceMatcher(a=source, b=target)
        chunks: list[DiffChunk] = []
        for op, a0, a1, b0, b1 in matcher.get_opcodes():
            if op == 'equal':
                chunks.append(DiffChunk(type='equal', value=source[a0:a1]))
            elif op == 'delete':
                chunks.append(DiffChunk(type='delete', value=source[a0:a1]))
            elif op == 'insert':
                chunks.append(DiffChunk(type='insert', value=target[b0:b1]))
            elif op == 'replace':
                chunks.append(DiffChunk(type='delete', value=source[a0:a1]))
                chunks.append(DiffChunk(type='insert', value=target[b0:b1]))
        return chunks


nlp_service = NlpService()
