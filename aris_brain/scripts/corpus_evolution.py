"""
Aris Corpus Evolution Script — Cron Job
Downloads 500 new Chinese entries from Fineweb-Edu-Chinese,
saves as timestamped file, retrains Markov chain.
"""
import os, sys, time, pickle, glob, json
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

CORPUS_DIR = os.path.join(BASE, 'corpus', 'datasets')
STATE_DIR = os.path.join(BASE, 'state')
os.makedirs(CORPUS_DIR, exist_ok=True)
os.makedirs(STATE_DIR, exist_ok=True)

# ─── Step 1: Count existing files ───
existing = sorted(glob.glob(os.path.join(CORPUS_DIR, '*.txt')))
print(f"Existing corpus files: {len(existing)}")
for f in existing:
    sz = os.path.getsize(f)
    print(f"  {os.path.basename(f)} ({sz//1024:,} KB)")

# ─── Step 2: Download ───
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
outfile = os.path.join(CORPUS_DIR, f'fineweb_chinese_{timestamp}.txt')

downloaded = False
try:
    from datasets import load_dataset
    print(f"\nDownloading 500 entries from Fineweb-Edu-Chinese-V2.1...")
    ds = load_dataset(
        "opencsg/Fineweb-Edu-Chinese-V2.1",
        split="train",
        streaming=True,
        trust_remote_code=True,
    )
    texts = []
    for i, item in enumerate(ds):
        if i >= 500:
            break
        text = item.get("text", "") or item.get("content", "")
        if text and len(text) > 50:
            texts.append(text[:2000].strip().replace('\n', ' '))
    print(f"Downloaded {len(texts)} texts")
    
    if texts:
        with open(outfile, 'w', encoding='utf-8') as f:
            for t in texts:
                f.write(t + '\n')
        print(f"Saved to: {outfile} ({os.path.getsize(outfile)//1024:,} KB)")
        downloaded = True
    else:
        print("No texts downloaded, skipping save")
except ImportError as e:
    print(f"datasets not available: {e}")
except Exception as e:
    print(f"Download failed: {e}")

# ─── Step 3: Retrain Markov chain with ALL corpus files ───
print(f"\n--- Markov chain retrain ---")
from aris_markov_generator import MarkovChainGenerator

# Load existing state
mg = MarkovChainGenerator(order=3, min_freq=1)
pkl_path = os.path.join(STATE_DIR, 'markov_chain.pkl')
json_path = os.path.join(STATE_DIR, 'markov_chain.json')

if os.path.exists(pkl_path):
    try:
        mg.load(pkl_path)
        print(f"Loaded existing model: {len(mg._vocab)} vocab, {len(mg._transitions)} contexts, {mg._total_ngrams} n-grams")
    except Exception as e:
        print(f"Pickle load failed ({e}), trying JSON fallback...")
        if os.path.exists(json_path):
            mg.load(json_path)
            print(f"Loaded from JSON: {len(mg._vocab)} vocab, {len(mg._transitions)} contexts, {mg._total_ngrams} n-grams")
        else:
            print("No existing state found, starting fresh")
else:
    print("No existing state, starting fresh")

# Train on ALL corpus files
all_files = sorted(glob.glob(os.path.join(CORPUS_DIR, '*.txt')))
total_texts = 0
for fpath in all_files:
    fname = os.path.basename(fpath)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            text = f.read()
        # Split into sentences
        import re
        sentences = re.split(r'(?<=[。！？.!?\\n])\\s*', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        print(f"  Training {fname}: {len(sentences)} sentences")
        mg.train(sentences)
        total_texts += len(sentences)
    except Exception as e:
        print(f"  ERROR training {fname}: {e}")

print(f"\nTraining complete: {total_texts} total sentences processed")

# Save
try:
    mg.save(pkl_path)
    print(f"Saved model to {pkl_path}")
except Exception as e:
    print(f"Pickle save failed: {e}, trying JSON...")
    mg.save(json_path)
    print(f"Saved model to {json_path}")

# ─── Summary ───
print(f"\n{'='*50}")
print(f"CORPUS EVOLUTION SUMMARY")
print(f"{'='*50}")
print(f"Time:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Corpus files:  {len(all_files)}")
if downloaded:
    print(f"New download:  fineweb_chinese_{timestamp}.txt ({os.path.getsize(outfile)//1024:,} KB)")
else:
    print(f"New download:  NONE")
print(f"Markov vocab:  {len(mg._vocab):,}")
print(f"Contexts:      {len(mg._transitions):,}")
print(f"Total n-grams: {mg._total_ngrams:,}")
print(f"Trained:       {mg._trained}")
print(f"{'='*50}")

# If nothing new was added, signal silence
if not downloaded and len(all_files) == len(existing):
    print("\n[SILENT_CHECK] Nothing new added -> signal SILENT")
else:
    print(f"\n[SILENT_CHECK] New data added -> report findings")
