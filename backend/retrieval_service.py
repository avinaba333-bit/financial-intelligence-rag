"""CPU-friendly BM25 + dense reciprocal-rank fusion and source deduplication."""
from collections import Counter
from functools import lru_cache
import math
import re

STOP_WORDS = set('a an the is are was were be been of in on at to for from and or as by with what which how did does do this that these those it its report annual selected please tell me about'.split())


def tokens(text):
    return [token for token in re.findall(r"[a-z0-9]+(?:[.,][0-9]+)*", text.lower())
            if token not in STOP_WORDS]


class KeywordIndex:
    def __init__(self, chunks):
        self.counts = [Counter(tokens(c.get('text', ''))) for c in chunks]
        self.lengths = [sum(count.values()) for count in self.counts]
        self.average = sum(self.lengths) / max(len(chunks), 1) or 1
        self.df = Counter(term for count in self.counts for term in count)

    def search(self, question, top_k):
        scores = []
        for position, count in enumerate(self.counts):
            score = 0.0
            for term in set(tokens(question)):
                frequency = count[term]
                if frequency:
                    idf = math.log(1 + (len(self.counts) - self.df[term] + .5) / (self.df[term] + .5))
                    denominator = frequency + 1.5 * (.25 + .75 * self.lengths[position] / self.average)
                    score += idf * frequency * 2.5 / denominator
            if score > 0:
                scores.append((position, score))
        return sorted(scores, key=lambda item: (-item[1], item[0]))[:top_k]


def fuse_results(chunks, dense_results, keyword_results, top_k=5, min_similarity=.15):
    ranks = {}
    dense_scores = {}
    lexical_scores = dict(keyword_results)
    for rank, result in enumerate(dense_results, 1):
        position = result['_index_position']
        score = result['similarity_score']
        dense_scores[position] = score
        if score >= min_similarity:
            ranks[position] = ranks.get(position, 0) + 1 / (60 + rank)
    for rank, (position, _) in enumerate(keyword_results, 1):
        ranks[position] = ranks.get(position, 0) + 1 / (60 + rank)
    output = []
    for position in sorted(ranks, key=lambda i: (-ranks[i], i)):
        chunk = chunks[position]
        if not chunk.get('text', '').strip():
            continue
        result = dict(chunk)
        result.update({'retrieval_score': ranks[position],
                       'similarity_score': dense_scores.get(position),
                       'keyword_score': lexical_scores.get(position, 0)})
        output.append(result)
    return deduplicate(output)[:top_k]


def deduplicate(results):
    seen = set()
    output = []
    for result in results:
        identity = (result.get('document_id', result.get('source_file')),
                    result.get('page_number'),
                    result.get('paragraph_id') or ' '.join(result.get('text', '').split()))
        if identity not in seen:
            seen.add(identity)
            output.append(result)
    return output


@lru_cache(maxsize=1)
def _reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', device='cpu')


def rerank_results(question, results, top_k):
    if not results:
        return []
    scores = _reranker().predict([(question, r['text']) for r in results])
    scored = [dict(result, rerank_score=float(score)) for result, score in zip(results, scores)]
    return sorted(scored, key=lambda result: -result['rerank_score'])[:top_k]
