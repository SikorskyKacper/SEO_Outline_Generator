import os
import json
import google.generativeai as genai
from openai import OpenAI
from typing import List, Optional
from schemas import ScrapedPage, PageCard, Outline, Keyword, ScrapedBlock

class LLMClient:
    def __init__(self, provider: str = "gemini", api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") # Fallback for Gemini
        self.model = None
        self.client = None
        self.model_name = model_name

        if self.api_key:
            if self.provider == "gemini":
                genai.configure(api_key=self.api_key)
                if not self.model_name:
                    self.model_name = "gemini-2.0-flash-exp" # Default fallback
                self.model = genai.GenerativeModel(self.model_name)
            elif self.provider == "openrouter":
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.api_key,
                )
                if not self.model_name:
                    self.model_name = "google/gemini-2.0-flash-001" # Default OpenRouter fallback
        
    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_page_card(self, page: ScrapedPage, relevant_blocks: List[str], language: str = "pl") -> PageCard:
        if not self.is_available():
            raise ValueError(f"API Key not configured for {self.provider}")

        prompt = f"""
You are an SEO analyst. Your job is to extract a compact “page card” from a crawled web page so that another model can later synthesize a complete content outline.

Rules:
- Use ONLY the information present in the input.
- Do NOT invent facts, numbers, or claims.
- Be concise, dense, and structured. No marketing language.
- Output MUST be valid JSON only. No extra text.

INPUT:
URL: {page.url}
Language: {language}
Query (main topic): {page.title} 

Crawled data (already cleaned):
- Page title: {page.title}
- Meta description: {page.description}
- Headings:
  H1: {page.h1}
  H2: {page.h2}
  H3: {page.h3}
- Selected content blocks (BM25-filtered + min words, ordered by relevance):
{"\n---\n".join(relevant_blocks)}

TASK:
Create a “page card” that captures what this page covers. Return JSON with this exact schema:

{{
  "url": "string",
  "topics": ["string"],
  "questions": ["string"],
  "key_points": ["string"],
  "suggested_headings": ["string"]
}}

Constraints:
- topics: 8–14 items max; each item 2–7 words
- questions: 6–12 items max; make them natural search questions
- key_points: 8–14 items max; short factual bullets; avoid duplicates
- suggested_headings: 8–14 items max; cleaned headings you would keep (remove cookie/CTA/about/contact and generic “summary” unless meaningful)
- If the page does not contain enough info, keep lists shorter rather than guessing.
- Keep everything in {language}. If headings are mixed languages, translate to {language}.

Return JSON only.
"""

        try:
            if self.provider == "gemini":
                response = self.model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                text_response = response.text
            elif self.provider == "openrouter":
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://localhost:8501", # Required by OpenRouter, using dummy
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
            # Ensure URL is kept
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
You are an SEO content strategist. Your goal is to produce a complete, copywriter-ready content outline (conspectus) based on multiple “page cards” extracted from top sources.

Rules:
- Use ONLY the information present in the input page cards and the provided keywords.
- Do NOT invent facts, numbers, or claims.
- The outline must be exhaustive for the given topic (cover what commonly appears across sources), but not repetitive.
- Output MUST be valid JSON only. No extra text.
- Language: {language}

INPUT:
Main query: {query}

Keywords (exactly 15, with search volume):
{kw_text}

Page cards (from 5–10 URLs):
{cards_text}

TASK:
Generate a final conspectus JSON with this exact schema:

{{
  "meta_title": "string",
  "meta_description": "string",
  "h1_title": "string",
  "lead": "string",
  "items": [
    {{
      "level": "H2",
      "heading": "string",
      "brief": ["string"]
    }},
     {{
      "level": "H3",
      "heading": "string",
      "brief": ["string"]
    }}
  ]
}}

Requirements:
1) meta_title:
- <= 60 characters
- include the main query or its closest natural variation
- not clickbait, not all caps

2) meta_description:
- <= 160 characters
- include value proposition + mention the topic clearly
- no invented claims

3) h1_title:
- clear editorial title in {language}
- aligned with query intent

4) lead:
- 2–4 sentences
- explain who the article is for + what they will learn
- no invented facts

5) outline items:
- Create a logical structure that a copywriter can follow to write a comprehensive article.
- Use mostly H2. Add H3 only when it genuinely helps (subtopics under an H2).
- It is OK if there are 0 H3.
- Each heading must have a brief:
  - 3–6 bullets
  - bullets must be concrete instructions for the copywriter: what to include, explain, compare, list, define, give examples of, etc.
  - avoid vague bullets like “describe more”
  - if data is needed but not provided by sources, add a bullet like: "Add verified data/example (source needed)" instead of making up numbers.

6) Coverage & prioritization:
- Identify the most recurring topics across page cards and prioritize them as early H2 sections.
- Ensure the outline covers: definition/overview, key mechanisms/how it works, step-by-step (if applicable), pros/cons or comparison (if applicable), common mistakes, FAQ-style section.
- Integrate the 15 keywords naturally into headings and briefs (do not force exact-match everywhere). Aim to cover all keywords across the outline.

7) Length guidance:
- Target 8–12 H2 sections typically.
- If topic is broad and sources show many distinct topics, allow up to 14 H2.
- Keep the outline free of redundant sections.

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
            
            # Map "outline" key from prompt to "items" key expected by Outline schema if mismatch occurs
            if "outline" in data and "items" not in data:
                 data["items"] = data["outline"]
            
            # Ensure items structure is correct (flat list of H2/H3)
            # The prompt asks for "items" list with levels, which matches our schema pretty well.
            
            return Outline(**data)
        except Exception as e:
            print(f"LLM Error (Synthesis - {self.provider}): {e}")
            # Return empty or error outline
            return Outline(
                meta_title="Error generating outline",
                meta_description="",
                h1_title="Error",
                lead=f"An error occurred during synthesis: {str(e)}",
                items=[]
            )
