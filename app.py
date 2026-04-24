import streamlit as st
import pandas as pd
import asyncio
import os
from app_utils import setup_logging, ensure_directories
from crawler import crawl_urls
from outline_builder import OutlineBuilder
from llm_gemini import LLMClient
from excel_writer import write_to_excel
from schemas import Keyword
import json

# Setup
setup_logging()
ensure_directories()

# Playwright fix for Streamlit Cloud
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    os.system("pip install playwright")

def install_browsers():
    print("Installing browsers...")
    os.system("playwright install chromium")
    print("Browsers installed.")

# Check if browser is installed (naive check, or just force run on first launch)
# On Streamlit cloud, we can simple run it if it fails or always run it on startup (it's fast if already installed)
if not os.path.exists("browsers_installed.flag"):
     install_browsers()
     with open("browsers_installed.flag", "w") as f:
         f.write("done")


st.set_page_config(page_title="SEO Link Building Outline Generator", layout="wide")

st.title("SEO Content Outline Generator")

# Sidebar
st.sidebar.header("Configuration")

provider_options = ["Gemini", "OpenRouter", "Local"]
provider = st.sidebar.selectbox("LLM Provider", provider_options, index=0)

model_name = None
api_key = None

if provider == "Gemini":
    default_key = os.environ.get("GEMINI_API_KEY", "")
    api_key = st.sidebar.text_input("Gemini API Key", value=default_key, type="password")
    model_name = st.sidebar.text_input("Model Name", value="gemini-2.0-flash-lite-preview-02-05")
elif provider == "OpenRouter":
    api_key = st.sidebar.text_input("OpenRouter API Key", value="", type="password")
    model_name = st.sidebar.text_input("Model Name", value="google/gemini-2.5-flash-lite")

if provider != "Local" and not api_key:
    st.sidebar.warning(f"Please enter API Key for {provider} to use LLM features.")

bm25_threshold = st.sidebar.slider("BM25 Threshold", 0.0, 5.0, 1.8, 0.1)
min_word_threshold = st.sidebar.number_input("Min Words per Block", value=90)
target_blocks_per_page = st.sidebar.number_input("Target Blocks per Page", value=10)

template_file = st.sidebar.file_uploader("Upload Excel Template", type=["xlsx"])

# Main Inputs
query = st.text_input("Główny temat / Query", value="fotowoltaika dla firm")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Słowa Kluczowe")
    # Default data
    default_data = [{"keyword": f"fraza {i+1}", "search_volume": 1000} for i in range(5)]
    
    edited_df = st.data_editor(
        pd.DataFrame(default_data),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "keyword": st.column_config.TextColumn("Słowo kluczowe", required=True),
            "search_volume": st.column_config.NumberColumn("Search Volume", required=True, step=1)
        }
    )

with col2:
    st.subheader("Konkurencja (URL-e)")
    urls_input = st.text_area(
        "Wklej URL-e (jeden w linii)", 
        height=400,
        value="https://example.com/artykul-1\nhttps://example.com/artykul-2"
    )

generate_btn = st.button("Generuj Konspekt", type="primary")

async def main_process():
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 0. Prep Data
    keywords = [Keyword(keyword=r["keyword"], search_volume=r["search_volume"]) for r in edited_df.to_dict("records")]
    urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
    
    if not keywords:
        st.error("Podaj przynajmniej jedno słowo kluczowe!")
        return

    if not urls:
        st.error("Podaj przynajmniej jeden URL!")
        return

    # 1. Crawl
    status_text.text("Crawling pages...")
    pages = await crawl_urls(urls)
    progress_bar.progress(30)
    
    if not pages:
        st.error("Nie udało się pobrać żadnej strony.")
        return

    # 2. Build Outline
    status_text.text(f"Building outline using {provider.upper()} mode...")
    
    # Initialize client with selected provider
    client = LLMClient(provider=provider.lower(), api_key=api_key, model_name=model_name)
    builder = OutlineBuilder(client)
    
    # Force local if selected or no key
    force_local = (provider == "Local" or (provider != "Local" and not api_key))
    
    try:
        outline = await builder.build(
            query=query,
            keywords=keywords,
            pages=pages,
            bm25_threshold=bm25_threshold,
            min_word_threshold=min_word_threshold,
            target_blocks=target_blocks_per_page,
            force_local=force_local,
            language="pl" # Defaulting to Polish as per user context
        )
    except Exception as e:
        st.error(f"Error building outline: {e}")
        return

    progress_bar.progress(80)
    
    # Validation / Self-Check
    if outline:
        warnings = []
        
        # 1. Keywords check
        if not keywords:
            warnings.append("Brak słów kluczowych")
            
        # 2. Headings as questions
        non_question_headings = [item.heading for item in outline.outline if not item.heading.strip().endswith("?")] # items -> outline
        if len(non_question_headings) > len(outline.outline) * 0.5:
             warnings.append(f"Większość nagłówków nie jest pytaniami ({len(non_question_headings)}/{len(outline.outline)})")
        
        # 3. FAQ Presence
        faq_found = False
        for item in outline.outline:
            if "często zadawane pytania" in item.heading.lower() or "freq" in item.heading.lower():
                faq_found = True
                break
        if not faq_found:
            warnings.append("Brak sekcji 'Często zadawane pytania'")
            
        # 4. Content length (brief -> content)
        short_briefs = [item.heading for item in outline.outline if len(item.content) < 50]
        if short_briefs:
            warnings.append(f"Zbyt krótkie treści w {len(short_briefs)} sekcjach")

        if warnings:
            with st.expander("Ostrzeżenia dotyczące jakości konspektu", expanded=True):
                for w in warnings:
                    st.warning(w)

    # 3. Save Excel
    status_text.text("Generating Excel...")
    
    # Determine template path
    if template_file:
        temp_path = "temp_template.xlsx"
        with open(temp_path, "wb") as f:
            f.write(template_file.getbuffer())
        template_source = temp_path
    else:
        template_source = "templates/konspekt_template.xlsx"
        if not os.path.exists(template_source):
            # Auto-generate if missing
            from create_template import create_template
            create_template(template_source)
            
    output_path = "out/result.xlsx"
    
    try:
        write_to_excel(outline, keywords, template_source, output_path)
    except Exception as e:
        status_text.text("Error generating excel")
        st.error(f"Excel Error: {e}")
        return

    progress_bar.progress(100)
    status_text.text("Done!")
    
    # 4. Display & Download
    st.success("Konspekt wygenerowany!")
    
    with open(output_path, "rb") as f:
        st.download_button(
            "Pobierz Excel",
            f,
            file_name=f"konspekt_{query.replace(' ', '_')}.xlsx"
        )
        
    st.subheader("Podgląd struktury (JSON)")
    st.json(outline.model_dump())

if generate_btn:
    asyncio.run(main_process())
