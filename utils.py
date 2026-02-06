import os
import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler()
        ]
    )

def ensure_directories():
    os.makedirs("./cache", exist_ok=True)
    os.makedirs("./out", exist_ok=True)
    os.makedirs("./templates", exist_ok=True)
