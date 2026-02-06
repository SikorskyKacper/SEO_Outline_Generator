# SEO Content Generator

Szybkie i tanie narzędzie do tworzenia konspektów SEO w formacie Excel.

## Wymagania
- Python 3.9+
- Chrome/Chromium (dla crawl4ai/playwright)

## Instalacja

1. Zainstaluj biblioteki:
```bash
pip install -r requirements.txt
playwright install
```

2. (Opcjonalnie) Ustaw klucz Gemini:
```batch
set GEMINI_API_KEY=twoj_klucz_api
```

## Uruchomienie

1. Wygeneruj domyślny szablon (jeśli nie posiadasz własnego):
```bash
python create_template.py
```

2. Uruchom aplikację:
```bash
streamlit run app.py
```

## Funkcje
- Tryb **Gemini** (wymaga klucza): Pełna analiza AI.
- Tryb **Local** (darmowy): Heurystyczna analiza słów kluczowych i nagłówków.
- **BM25 Filtering**: Inteligentny wybór treści dla oszczędności tokenów.
- **Excel**: Zachowanie formatowania oryginalnego szablonu.
