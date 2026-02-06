import asyncio
import json
import os
import hashlib
from typing import List, Optional
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import NoExtractionStrategy
from bs4 import BeautifulSoup
from schemas import ScrapedPage

CACHE_DIR = "./cache"

def get_cache_path(url: str) -> str:
    hash_object = hashlib.md5(url.encode())
    return os.path.join(CACHE_DIR, f"{hash_object.hexdigest()}.json")

async def crawl_urls(urls: List[str]) -> List[ScrapedPage]:
    results = []
    
    # Initialize crawler
    # Using 'async with' context manager is recommended way now
    async with AsyncWebCrawler(verbose=True) as crawler:
        for url in urls:
            url = url.strip()
            if not url:
                continue
                
            cache_path = get_cache_path(url)
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        results.append(ScrapedPage(**data))
                    continue
                except Exception as e:
                    print(f"Cache read error for {url}: {e}")

            try:
                # Crawl
                result = await crawler.arun(url=url)
                
                if not result.success:
                    print(f"Failed to crawl {url}: {result.error_message}")
                    continue

                # Parse
                markdown_content = result.markdown
                html_content = result.html
                
                # Basic parsing for headers and meta
                soup = BeautifulSoup(html_content, 'html.parser')
                
                title = ""
                if soup.title:
                    title = soup.title.string
                
                meta_desc = ""
                meta = soup.find('meta', attrs={'name': 'description'})
                if meta:
                    meta_desc = meta.get('content', '')

                h1s = [h.get_text(strip=True) for h in soup.find_all('h1')]
                h2s = [h.get_text(strip=True) for h in soup.find_all('h2')]
                h3s = [h.get_text(strip=True) for h in soup.find_all('h3')]

                # Naive block splitting by newlines in markdown for now, 
                # but better to use the result.markdown and split by double newline
                # filtering out small bits.
                blocks = [b.strip() for b in markdown_content.split('\n\n') if len(b.strip()) > 50]
                
                page = ScrapedPage(
                    url=url,
                    title=title or "",
                    description=meta_desc or "",
                    h1=h1s,
                    h2=h2s,
                    h3=h3s,
                    main_content=markdown_content, # Storing full md for context
                    blocks=blocks
                )
                
                # Cache
                with open(cache_path, 'w', encoding='utf-8') as f:
                    f.write(page.model_dump_json())
                
                results.append(page)
                
            except Exception as e:
                print(f"Error processing {url}: {e}")
                
    return results
