"""
Aris Corpus Downloader — standalone, zero external deps.
Downloads from HuggingFace dataset viewer API using built-in urllib.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from typing import List


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus", "datasets")
os.makedirs(DATA_DIR, exist_ok=True)


def download_fineweb_chinese(limit: int = 500) -> List[str]:
    """Download Fineweb-Edu-Chinese using HuggingFace dataset viewer API."""
    texts = []
    url = (
        "https://datasets-server.huggingface.co/rows"
        "?dataset=opencsg/Fineweb-Edu-Chinese-V2.1"
        "&config=default&split=train"
        f"&offset=0&length={min(limit, 100)}"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Aris-RSI/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        rows = data.get("rows", [])
        for row in rows:
            row_data = row.get("row", {})
            text = row_data.get("text", "") or row_data.get("content", "")
            if text and len(text) > 50:
                texts.append(text[:2000])
                if len(texts) >= limit:
                    break

        print(f"  Downloaded {len(texts)} texts from datasets-server API")
    except Exception as e:
        print(f"  datasets-server API failed: {e}")

    # If we got fewer than limit, try a second batch with different offset
    if len(texts) < limit:
        try:
            url2 = (
                "https://datasets-server.huggingface.co/rows"
                "?dataset=opencsg/Fineweb-Edu-Chinese-V2.1"
                "&config=default&split=train"
                f"&offset=100&length={min(limit - len(texts), 100)}"
            )
            req2 = urllib.request.Request(url2, headers={"User-Agent": "Aris-RSI/1.0"})
            with urllib.request.urlopen(req2, timeout=30) as resp2:
                data2 = json.loads(resp2.read().decode("utf-8"))

            rows2 = data2.get("rows", [])
            for row in rows2:
                row_data = row.get("row", {})
                text = row_data.get("text", "") or row_data.get("content", "")
                if text and len(text) > 50:
                    texts.append(text[:2000])
                    if len(texts) >= limit:
                        break
            print(f"  Second batch: {len(texts)} texts total")
        except Exception as e:
            print(f"  Second batch failed: {e}")

    return texts


def download_common_crawl_sample(limit: int = 500) -> List[str]:
    """Fallback: download Chinese text from common crawl samples."""
    texts = []
    # Try mc4 (multilingual C4) via datasets-server
    url = (
        "https://datasets-server.huggingface.co/rows"
        "?dataset=mc4&config=zh&split=train"
        f"&offset=0&length={min(limit, 100)}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Aris-RSI/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rows = data.get("rows", [])
        for row in rows:
            row_data = row.get("row", {})
            text = row_data.get("text", "") or row_data.get("content", "")
            if text and len(text) > 50:
                texts.append(text[:2000])
                if len(texts) >= limit:
                    break
        print(f"  mc4 fallback: {len(texts)} texts")
    except Exception as e:
        print(f"  mc4 fallback failed: {e}")
    return texts


def save_texts(texts: List[str], prefix: str = "fineweb_chinese"):
    """Save texts with timestamp filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.txt"
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for t in texts:
            f.write(t.strip().replace("\n", " ") + "\n")
    size_kb = os.path.getsize(filepath) // 1024
    print(f"  Saved: {filepath} ({len(texts)} lines, {size_kb} KB)")
    return filepath


def get_existing_files() -> List[str]:
    """List existing corpus dataset files."""
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(
        [f for f in os.listdir(DATA_DIR) if f.endswith(".txt") and f.startswith("fineweb_chinese")]
    )


if __name__ == "__main__":
    existing = get_existing_files()
    print(f"Existing corpus files: {len(existing)}")

    # Try primary dataset
    texts = download_fineweb_chinese(limit=500)

    # Fallback if primary fails
    if len(texts) < 50:
        print("Primary dataset failed, trying fallback...")
        texts = download_common_crawl_sample(limit=500)

    if len(texts) > 0:
        save_texts(texts)
        print(f"Download complete: {len(texts)} texts")
    else:
        print("No texts downloaded (no internet or API unavailable)")
        sys.exit(0)
