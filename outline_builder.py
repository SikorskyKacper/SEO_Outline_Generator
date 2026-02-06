from typing import List
from schemas import ScrapedPage, Outline, PageCard, Keyword, OutlineItem
from content_selector import select_relevant_blocks
from llm_gemini import LLMClient
import os
import collections

class OutlineBuilder:
    def __init__(self, llm_client: LLMClient):
        self.client = llm_client

    async def build(
        self,
        query: str,
        keywords: List[Keyword],
        pages: List[ScrapedPage],
        bm25_threshold: float,
        min_word_threshold: int,
        target_blocks: int,
        force_local: bool = False,
        language: str = "pl"
    ) -> Outline:
        
        # 1. Select Content
        print("Selecting relevant blocks...")
        cards = []
        
        # Determine mode
        use_llm = self.client.is_available() and not force_local
        
        for page in pages:
            rel_blocks = select_relevant_blocks(
                page, query, keywords, bm25_threshold, min_word_threshold, target_blocks
            )
            
            if use_llm:
                # LLM Mode: Generate Card
                card = self.client.generate_page_card(page, rel_blocks, language=language)
                cards.append(card)
            else:
                # Local Mode: Create Heuristic Card
                card = self._create_local_card(page, rel_blocks)
                cards.append(card)

        # 2. Synthesize
        if use_llm:
            print("Synthesizing with LLM...")
            return self.client.synthesize_outline(query, keywords, cards, language=language)
        else:
            print("Synthesizing locally...")
            return self._synthesize_local(query, keywords, cards)

    def _create_local_card(self, page: ScrapedPage, blocks: List[str]) -> PageCard:
        # Simple extraction
        headings = page.h2 + page.h3
        topics = [h for h in headings if len(h.split()) > 2][:10]
        return PageCard(
            url=page.url,
            topics=topics,
            questions=[],
            key_points=[b[:100] + "..." for b in blocks[:5]],
            suggested_headings=headings[:5]
        )

    def _synthesize_local(self, query: str, keywords: List[Keyword], cards: List[PageCard]) -> Outline:
        # 1. Aggregate Headers (Topics)
        all_topics = []
        for c in cards:
            all_topics.extend(c.topics)
            all_topics.extend(c.suggested_headings)
            
        # 2. Frequency / Clustering (Very naive: frequency of words)
        # Better: just take unique headers, limit to 10
        unique_topics = list(set(all_topics))
        
        items = []
        for topic in unique_topics[:8]: # Limit
            items.append(OutlineItem(
                level="H2",
                heading=topic,
                brief=["Omów temat szeroko.", "Uwzględnij słowa kluczowe."]
            ))
            
        return Outline(
            meta_title=f"{query} - Kompletny Poradnik",
            meta_description=f"Dowiedz się wszystkiego o {query}. Przeczytaj nasz artykuł.",
            h1_title=f"{query}: Wszystko co musisz wiedzieć",
            lead=f"W tym artykule omówimy {query}...",
            items=items
        )
