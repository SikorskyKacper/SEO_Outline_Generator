from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class Keyword(BaseModel):
    keyword: str
    search_volume: int

class KeywordInput(BaseModel):
    items: List[Keyword] = Field(min_length=15, max_length=15, description="Exact 15 keywords required")

class ScrapedBlock(BaseModel):
    content: str
    tag: str = "p"
    score: float = 0.0

class ScrapedPage(BaseModel):
    url: str
    title: str = ""
    description: str = ""
    h1: List[str] = []
    h2: List[str] = []
    h3: List[str] = []
    main_content: str = "" # Full text for backup/debug
    blocks: List[str] = [] # Raw text blocks

class PageCard(BaseModel):
    url: str
    topics: List[str] = Field(default_factory=list, description="Main topics extracted")
    questions: List[str] = Field(default_factory=list, description="Relevant questions found or implied")
    key_points: List[str] = Field(default_factory=list, description="Key information points")
    suggested_headings: List[str] = Field(default_factory=list, description="Structure ideas")

class OutlineItem(BaseModel):
    level: Literal["H2", "H3"]
    heading: str
    brief: List[str] = Field(default_factory=list, description="Bullet points for the section")

class Outline(BaseModel):
    meta_title: str
    meta_description: str
    h1_title: str
    lead: str
    items: List[OutlineItem]
