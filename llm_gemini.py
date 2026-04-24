import os
import json
import google.generativeai as genai
from openai import OpenAI
from typing import List, Optional
from schemas import ScrapedPage, PageCard, Outline, Keyword, ScrapedBlock
 
 
class LLMClient:
    def __init__(self, provider: str = "gemini", api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = None
        self.client = None
        self.model_name = model_name
 
        if self.api_key:
            if self.provider == "gemini":
                genai.configure(api_key=self.api_key)
                if not self.model_name:
                    self.model_name = "gemini-2.0-flash-exp"
                self.model = genai.GenerativeModel(self.model_name)
            elif self.provider == "openrouter":
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.api_key,
                )
                if not self.model_name:
                    self.model_name = "google/gemini-2.0-flash-001"
 
    def is_available(self) -> bool:
        return bool(self.api_key)
 
    def generate_page_card(self, page: ScrapedPage, relevant_blocks: List[str], language: str = "pl") -> PageCard:
        if not self.is_available():
            raise ValueError(f"API Key not configured for {self.provider}")
 
        blocks_text = "\n---\n".join(relevant_blocks)
        prompt = f"""
You are an SEO analyst. Extract a compact "page card" from a crawled web page.
 
Rules:
- Use ONLY the information present in the input.
- Do NOT invent facts, numbers, or claims.
- Output MUST be valid JSON only. No extra text.
 
INPUT:
URL: {page.url}
Language: {language}
Page title: {page.title}
Meta description: {page.description}
Headings H1: {page.h1}
Headings H2: {page.h2}
Headings H3: {page.h3}
Content blocks:
{blocks_text}
 
Return JSON with this schema:
{{
  "url": "string",
  "topics": ["string"],
  "questions": ["string"],
  "key_points": ["string"],
  "suggested_headings": ["string"]
}}
 
- topics: 8-14 items, 2-7 words each
- questions: 6-12 natural search questions
- key_points: 8-14 factual bullets
- suggested_headings: 8-14 cleaned headings
- Language: {language}
 
Return JSON only.
"""
 
        try:
            if self.provider == "gemini":
                response = self.model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                text_response = response.text
            elif self.provider == "openrouter":
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://localhost:8501",
                        "X-Title": "SEO Outline Generator",
                    },
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful SEO assistant. Output valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                text_response = completion.choices[0].message.content
 
            data = json.loads(text_response)
            data["url"] = page.url
            return PageCard(**data)
 
        except Exception as e:
            print(f"LLM Error (Card - {self.provider}): {e}")
            return PageCard(url=page.url, topics=[f"Error processing page: {str(e)}"])
 
    def synthesize_outline(self, query: str, keywords: List[Keyword], cards: List[PageCard], language: str = "pl") -> Outline:
        if not self.is_available():
            raise ValueError(f"API Key not configured for {self.provider}")
 
        cards_text = json.dumps([c.model_dump() for c in cards], indent=2)
        kw_text = json.dumps([{"keyword": k.keyword, "search_volume": k.search_volume} for k in keywords])
 
        prompt = f"""
You are an SEO content strategist. Produce a complete, copywriter-ready content outline based on page cards extracted from top sources.
 
Rules:
- Use ONLY the information present in the input page cards and the provided keywords.
- Do NOT invent facts, numbers, or claims.
- Output MUST be valid JSON only. No extra text.
- Language: {language}
 
INPUT:
Main query: {query}
Keywords: {kw_text}
Page cards: {cards_text}
 
Return JSON with this exact schema:
{{
  "meta_title": "string",
  "meta_description": "string",
  "h1_title": "string",
  "lead": "string",
  "outline": [
    {{
      "level": "H2",
      "heading": "string",
      "content": "string"
    }}
  ]
}}
 
Requirements:
1) meta_title: max 60 chars, include main query
2) meta_description: max 160 chars, include value proposition
3) h1_title: clear editorial title in {language}
4) lead: 2-4 sentences, who the article is for and what they will learn
5) outline:
   - Use mostly H2, add H3 only when genuinely needed
   - content: 3-6 concrete bullet points for the copywriter
   - If data is missing: "Add verified data/example (source needed)"
6) Cover: definition, how it works, step-by-step (if applicable), pros/cons (if applicable), common mistakes, FAQ
7) Target 8-12 H2 sections
 
Return JSON only.
"""
 
        try:
            if self.provider == "gemini":
                response = self.model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                text_response = response.text
            elif self.provider == "openrouter":
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://localhost:8501",
                        "X-Title": "SEO Outline Generator",
                    },
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful SEO assistant. Output valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                text_response = completion.choices[0].message.content
 
            data = json.loads(text_response)
 
            # Normalize key: LLM may return "items" instead of "outline"
            if "items" in data and "outline" not in data:
                data["outline"] = data.pop("items")
 
            # Normalize each item: convert "brief" list to "content" string if needed
            for item in data.get("outline", []):
                if "brief" in item and "content" not in item:
                    brief = item.pop("brief")
                    if isinstance(brief, list):
                        item["content"] = "\n".join(f"- {b}" for b in brief)
                    else:
                        item["content"] = str(brief)
                elif "content" not in item:
                    item["content"] = ""
 
            return Outline(**data)
 
        except Exception as e:
            print(f"LLM Error (Synthesis - {self.provider}): {e}")
            return Outline(
                meta_title="Error generating outline",
                meta_description="",
                h1_title="Error",
                lead=f"An error occurred during synthesis: {str(e)}",
                outline=[]
            )
