from typing import List
from rank_bm25 import BM25Okapi
from schemas import ScrapedPage, Keyword
import logging

def select_relevant_blocks(
    page: ScrapedPage,
    query: str,
    keywords: List[Keyword],
    bm25_threshold: float = 1.8,
    min_word_threshold: int = 90,
    target_blocks: int = 10
) -> List[str]:
    """
    Selects relevant blocks from the page using BM25.
    Adapts threshold if too many or too few blocks are found.
    """
    if not page.blocks:
        return []

    # 1. Base filter by word count
    # Remove extremely short blocks that are likely noise (menus, footers)
    candidates = [b for b in page.blocks if len(b.split()) >= 20] # Soft hard-limit
    
    if not candidates:
        return []

    # Tokenize blocks
    tokenized_corpus = [doc.lower().split() for doc in candidates]
    bm25 = BM25Okapi(tokenized_corpus)

    # Queries
    q_core = query.lower().split()
    kw_str = " ".join([k.keyword for k in keywords])
    q_coverage = (query + " " + kw_str).lower().split()

    # Score
    scores_core = bm25.get_scores(q_core)
    scores_coverage = bm25.get_scores(q_coverage)

    # Adaptive Selection Loop
    current_threshold = bm25_threshold
    selected_indices = []
    
    # Try up to 3 times to adjust threshold
    for _ in range(3):
        selected_indices = []
        for i, (s_core, s_cov) in enumerate(zip(scores_core, scores_coverage)):
            # Check length again against strict threshold
            if len(candidates[i].split()) < min_word_threshold:
                continue
            
            # Relevancy check: passes if core OR coverage score logic meets threshold
            # Normalized slightly or just raw score? BM25 scores are not normalized 0-1.
            # Usually unique terms give higher scores.
            # Simple heuristic: if score > threshold
            if s_core > current_threshold or s_cov > current_threshold:
                selected_indices.append(i)
        
        count = len(selected_indices)
        if count > 15: # Too many
            current_threshold += 0.2
        elif count < 6 and count < len(candidates): # Too few
            current_threshold -= 0.2
            if current_threshold < 0:
                current_threshold = 0
        else:
            break
            
    # Final selection
    # Limit to target_blocks + buffer (e.g. max 15) to save tokens
    final_blocks = [candidates[i] for i in selected_indices]
    
    # If we still have too many after adaptation, soft limit by score
    if len(final_blocks) > 15:
        # Re-sort by max score and take top 15
        # This is complicated because we lost the score/index mapping.
        # Let's just take top N based on original indices (assuming candidates order implies structural order?)
        # Or just take top N.
        final_blocks = final_blocks[:15]

    return final_blocks
