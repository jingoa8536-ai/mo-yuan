"""
Aris Corpus Update Pipeline
Downloads 500 new Chinese entries from Fineweb-Edu-Chinese,
saves with timestamp, and retrains Markov chain.
"""
import os, sys, json, time, re, pickle, gzip
from collections import defaultdict, Counter
from typing import List, Dict, Tuple
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(BASE_DIR, 'state')
DATASET_DIR = os.path.join(BASE_DIR, 'corpus', 'datasets')

os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(STATE_DIR, exist_ok=True)

# ─── Step 1: Download from HuggingFace without datasets library ───

def download_fineweb_chinese(limit: int = 500) -> List[str]:
    """
    Download Chinese text from HuggingFace dataset using direct HTTPS.
    Tries multiple strategies:
    1. HuggingFace dataset viewer API (JSON rows)
    2. Direct parquet download from HF repo
    """
    import requests
    
    texts = []
    
    # Strategy 1: Try the HF datasets server API
    api_url = "https://datasets-server.huggingface.co/rows"
    params = {
        "dataset": "opencsg/Fineweb-Edu-Chinese-V2.1",
        "config": "default",
        "split": "train",
        "offset": 0,
        "length": min(limit, 100)  # API max 100 per page
    }
    
    print(f"[Corpus] Downloading {limit} entries via HF datasets API...")
    offset = 0
    attempts = 0
    while len(texts) < limit and attempts < 10:
        attempts += 1
        params["offset"] = offset
        params["length"] = min(limit - len(texts), 100)
        if params["length"] <= 0:
            break
        
        try:
            resp = requests.get(api_url, params=params, timeout=30)
            if resp.status_code != 200:
                print(f"[Corpus] API returned {resp.status_code}, trying parquet fallback...")
                break
            
            data = resp.json()
            rows = data.get("rows", [])
            if not rows:
                print(f"[Corpus] No more rows at offset {offset}")
                break
            
            for row in rows:
                text = ""
                row_data = row.get("row", {})
                for key in ["text", "content"]:
                    if key in row_data and row_data[key]:
                        text = row_data[key]
                        break
                if text and isinstance(text, str) and len(text.strip()) > 50:
                    texts.append(text.strip()[:2000])
                    if len(texts) >= limit:
                        break
            
            offset += len(rows)
            print(f"[Corpus]  Downloaded {len(texts)}/{limit} (offset {offset})")
            
        except Exception as e:
            print(f"[Corpus] API error: {e}")
            break
    
    if len(texts) >= limit:
        print(f"[Corpus] Download complete: {len(texts)} entries via API")
        return texts
    
    # Strategy 2: Try HF Hub API for parquet files
    print(f"[Corpus] API gave {len(texts)}, trying parquet download...")
    try:
        # List parquet files in the dataset repo
        hub_api = f"https://huggingface.co/api/datasets/opencsg/Fineweb-Edu-Chinese-V2.1/parquet/default/train"
        resp = requests.get(hub_api, timeout=15)
        if resp.status_code == 200:
            parquet_files = resp.json()
            print(f"[Corpus] Found {len(parquet_files)} parquet shards")
            
            import io
            for pf in parquet_files:
                pf_url = pf.get("url") or pf
                if isinstance(pf_url, dict):
                    pf_url = pf_url.get("url", "")
                if not pf_url:
                    continue
                    
                print(f"[Corpus]  Downloading parquet: {pf_url.split('/')[-1]}...")
                try:
                    pr = requests.get(pf_url, timeout=60)
                    if pr.status_code == 200:
                        # Try pyarrow if available
                        try:
                            import pyarrow.parquet as pq
                            table = pq.read_table(io.BytesIO(pr.content))
                            for i in range(table.num_rows):
                                row = table.slice(i, 1).to_pydict()
                                for key in ["text", "content"]:
                                    if key in row and row[key] and row[key][0]:
                                        text = str(row[key][0])
                                        if len(text.strip()) > 50:
                                            texts.append(text.strip()[:2000])
                                            if len(texts) >= limit:
                                                break
                                        break
                                if len(texts) >= limit:
                                    break
                        except ImportError:
                            print(f"[Corpus] pyarrow not available, skipping parquet")
                            break
                except Exception as e:
                    print(f"[Corpus]  Parquet download error: {e}")
                    continue
                
                if len(texts) >= limit:
                    break
        else:
            print(f"[Corpus] Parquet API: {resp.status_code}")
    except Exception as e:
        print(f"[Corpus] Parquet listing error: {e}")
    
    print(f"[Corpus] Total downloaded: {len(texts)} entries")
    return texts[:limit]


def save_corpus(texts: List[str]) -> str:
    """Save texts to corpus/datasets/ with timestamp."""
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"fineweb_chinese_{ts}.txt"
    fpath = os.path.join(DATASET_DIR, fname)
    
    with open(fpath, 'w', encoding='utf-8') as f:
        for t in texts:
            f.write(t.strip().replace('\n', ' ') + '\n')
    
    size_kb = os.path.getsize(fpath) // 1024
    print(f"[Corpus] Saved {fpath} ({len(texts)} lines, {size_kb}KB)")
    return fpath


# ─── Step 2: Retrain Markov chain from ALL corpus files ───

def _tokenize(text: str) -> List[str]:
    """Tokenize text into tokens matching MarkovChainGenerator logic."""
    if not text:
        return []
    text = text.strip()
    tokens = []
    i = 0
    
    # CJK ranges
    CJK = set()
    for cp_range in [('\u4e00', '\u9fff'), ('\u3040', '\u30ff'),
                     ('\uac00', '\ud7af'), ('\u3130', '\u318f'),
                     ('\u3000', '\u303f')]:
        for cp in range(ord(cp_range[0]), ord(cp_range[1]) + 1):
            CJK.add(chr(cp))
    
    CJK_PUNCT = set('，。！？、；：""''（）【】《》「」『』…—～')
    LATIN_PUNCT = set(',.!?;:\'"()[]{}')
    
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c in CJK:
            tokens.append(c)
            i += 1
            continue
        if c in CJK_PUNCT:
            tokens.append(c)
            i += 1
            continue
        if c in LATIN_PUNCT:
            tokens.append(c)
            i += 1
            continue
        word = ''
        while i < len(text):
            ch = text[i]
            if ch.isspace() or ch in CJK or ch in CJK_PUNCT or ch in LATIN_PUNCT:
                break
            word += ch
            i += 1
        if word:
            tokens.append(word)
    return tokens


def _is_sentence_boundary(token: str) -> bool:
    return token in '。！？.!?\n' or token == ''


def _get_ngrams(tokens: List[str], order: int) -> List[Tuple]:
    ngrams = []
    for i in range(len(tokens) - order + 1):
        context = tuple(tokens[i:i + order - 1])
        target = tokens[i + order - 1]
        ngrams.append((context, target))
    return ngrams


def load_markov_state(path: str) -> dict:
    """Load saved Markov state (dict format from save())."""
    with open(path, 'rb') as f:
        data = pickle.load(f)
    return data


def retrain_markov(min_freq: int = 2, order: int = 3) -> dict:
    """
    Load all .txt files from corpus/datasets/, train a fresh Markov chain.
    Returns dict with stats.
    """
    files = sorted([f for f in os.listdir(DATASET_DIR) if f.endswith('.txt')])
    if not files:
        print("[Corpus] No corpus files found!")
        return None
    
    print(f"[Markov] Retraining from {len(files)} corpus files: {files}")
    
    transitions = defaultdict(Counter)
    starters = []
    vocab = set()
    total_ngrams = 0
    total_chars = 0
    
    for fname in files:
        fpath = os.path.join(DATASET_DIR, fname)
        size_kb = os.path.getsize(fpath) // 1024
        print(f"[Markov]  Loading {fname} ({size_kb}KB)...")
        
        with open(fpath, 'r', encoding='utf-8') as f:
            text = f.read()
        
        total_chars += len(text)
        
        # Split into sentences
        sentences = re.split(r'(?<=[。！？.!?\n])\s*', text)
        for sentence in sentences:
            if not sentence.strip():
                continue
            tokens = _tokenize(sentence)
            if len(tokens) < order:
                continue
            
            starters.append(tuple(tokens[:order - 1]))
            ngrams = _get_ngrams(tokens, order)
            for context, target in ngrams:
                transitions[context][target] += 1
                vocab.add(target)
                for t in context:
                    vocab.add(t)
                total_ngrams += 1
    
    # Filter low-frequency transitions
    if min_freq > 1:
        old_count = sum(len(c) for c in transitions.values())
        to_delete = []
        for context, counter in transitions.items():
            for word, count in list(counter.items()):
                if count < min_freq:
                    del counter[word]
            if not counter:
                to_delete.append(context)
        for ctx in to_delete:
            del transitions[ctx]
        new_count = sum(len(c) for c in transitions.values())
        print(f"[Markov]  Filtered min_freq={min_freq}: {old_count}→{new_count} transitions")
    
    # Build save dict
    data = {
        'order': order,
        'min_freq': min_freq,
        'vocab_size': len(vocab),
        'total_ngrams': total_ngrams,
        'starters': [list(s) for s in starters],
        'transitions': {
            '|'.join(ctx): dict(counter)
            for ctx, counter in transitions.items()
        },
    }
    
    elapsed_ms = 0  # placeholder
    print(f"[Markov] Retrained: {len(vocab)} words, "
          f"{len(transitions)} contexts, "
          f"{total_ngrams} n-grams")
    print(f"[Markov] Total corpus: {total_chars:,} chars from {len(files)} files")
    
    return data


def save_markov(data: dict, path: str = None):
    """Save Markov state dict to pickle."""
    if path is None:
        path = os.path.join(STATE_DIR, 'markov_chain.pkl')
    with open(path, 'wb') as f:
        pickle.dump(data, f, protocol=5)
    size_kb = os.path.getsize(path) / 1024
    print(f"[Markov] Saved to {path} ({size_kb:.0f}KB)")
    return path


# ─── Main Pipeline ───

def run_pipeline(limit: int = 500):
    print(f"{'='*60}")
    print(f"  Aris Corpus Update Pipeline — {datetime.now().isoformat()}")
    print(f"{'='*60}")
    
    # Step 1: Check existing state
    existing_files = sorted([f for f in os.listdir(DATASET_DIR) if f.endswith('.txt')])
    print(f"\n[Phase 1] Existing corpus: {len(existing_files)} files")
    for f in existing_files:
        size_kb = os.path.getsize(os.path.join(DATASET_DIR, f)) // 1024
        print(f"  {f} ({size_kb}KB)")
    
    # Step 2: Download new data
    print(f"\n[Phase 2] Downloading {limit} new Chinese entries...")
    texts = download_fineweb_chinese(limit=limit)
    
    if not texts or len(texts) < 10:
        print(f"[Phase 2] ❌ Download failed or insufficient data ({len(texts)} entries).")
        print("[Corpus] Silently aborting — no new data.")
        return None
    
    new_file = save_corpus(texts)
    
    # Step 3: Retrain Markov
    print(f"\n[Phase 3] Retraining Markov chain with ALL corpus files...")
    markov_data = retrain_markov(min_freq=2, order=3)
    
    if markov_data is None:
        print("[Phase 3] ❌ Markov retrain failed.")
        return None
    
    save_markov(markov_data)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  ✅ Corpus Update Complete")
    print(f"{'='*60}")
    total_files = len([f for f in os.listdir(DATASET_DIR) if f.endswith('.txt')])
    total_size_kb = sum(
        os.path.getsize(os.path.join(DATASET_DIR, f)) // 1024
        for f in os.listdir(DATASET_DIR) if f.endswith('.txt')
    )
    print(f"  Total corpus files: {total_files}")
    print(f"  Total corpus size:  {total_size_kb}KB")
    print(f"  New file:           {new_file}")
    print(f"  New entries:        {len(texts)}")
    print(f"  Markov vocab:       {markov_data['vocab_size']:,}")
    print(f"  Markov n-grams:     {markov_data['total_ngrams']:,}")
    print(f"  Markov contexts:    {len(markov_data['transitions']):,}")
    print(f"{'='*60}")
    
    return {
        'total_files': total_files,
        'total_size_kb': total_size_kb,
        'new_entries': len(texts),
        'new_file': new_file,
        'vocab_size': markov_data['vocab_size'],
        'total_ngrams': markov_data['total_ngrams'],
        'contexts': len(markov_data['transitions']),
    }


if __name__ == '__main__':
    result = run_pipeline(limit=500)
    if result is None:
        sys.exit(0)  # Silent abort is OK
