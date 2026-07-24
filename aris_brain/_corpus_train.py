import sys, json, os, glob, pickle
sys.path.insert(0,'D:/LAAP/aris_brain')
from aris_markov_generator import MarkovChainGenerator

# 1. Load existing Markov chain
print("=== Loading existing Markov chain ===")
mc = MarkovChainGenerator(order=3, min_freq=1)
loaded = mc.load('D:/LAAP/aris_brain/state/markov_chain.pkl')
print(f"Loaded: {loaded}")

# Check attributes after load
attrs = {}
for k in dir(mc):
    if not k.startswith('_'):
        v = getattr(mc, k)
        if not callable(v):
            attrs[k] = v
print(f"Attributes: {list(attrs.keys())}")
for k, v in attrs.items():
    if isinstance(v, dict):
        print(f"  {k}: dict({len(v)} keys)")
    elif isinstance(v, (list, tuple)):
        print(f"  {k}: {type(v).__name__}({len(v)})")
    elif isinstance(v, (int, float)):
        print(f"  {k}: {v}")
    else:
        print(f"  {k}: {type(v).__name__} = {str(v)[:50]}")

# Stats
vocab = attrs.get('vocab', {})
n_grams = attrs.get('n_grams', {})
total_tokens = attrs.get('total_tokens', 0)
print(f"\nBefore: vocab={len(vocab)}, n_grams keys={len(n_grams)}, tokens={total_tokens}")

# 2. Read all corpus files
print("\n=== Reading corpus files ===")
corpus_dir = 'D:/LAAP/aris_brain/corpus/datasets'
all_files = sorted(glob.glob(os.path.join(corpus_dir, '*')))
all_texts = []

for f in all_files:
    fname = os.path.basename(f)
    size_kb = os.path.getsize(f) // 1024
    try:
        if f.endswith('.json'):
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            if isinstance(data, list):
                texts = [str(t) if not isinstance(t, dict) else str(t.get('text', t.get('content', ''))) for t in data]
            elif isinstance(data, dict):
                texts = [str(v) for v in data.values() if isinstance(v, str)]
            else:
                texts = []
        elif f.endswith('.txt'):
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
            texts = [line for line in content.split('\n') if len(line.strip()) > 20]
        else:
            texts = []
        
        if texts:
            all_texts.extend(texts)
            print(f"  {fname}: {size_kb}KB -> {len(texts)} texts ({sum(len(t) for t in texts)} chars)")
    except Exception as e:
        print(f"  {fname}: ERROR {e}")

print(f"\nTotal texts from corpus: {len(all_texts)}, chars: {sum(len(t) for t in all_texts)}")

# 3. Train incrementally
if all_texts:
    print("\n=== Training Markov chain (this will take a while...) ===")
    mc.train(all_texts)
    print(f"After: vocab={len(mc.vocab)}, n_grams keys={len(mc.n_grams)}, tokens={mc.total_tokens}")
    
    # 4. Save
    print("\n=== Saving Markov chain ===")
    mc.save('D:/LAAP/aris_brain/state/markov_chain.pkl')
    
    # Verify
    mc2 = MarkovChainGenerator(order=3, min_freq=1)
    mc2.load('D:/LAAP/aris_brain/state/markov_chain.pkl')
    print(f"Verified: vocab={len(mc2.vocab)}, n_grams keys={len(mc2.n_grams)}, tokens={mc2.total_tokens}")
else:
    print("No texts found - nothing to train")

print("\n=== Summary ===")
print(f"Corpus files: {len(all_files)}")
print(f"Total texts processed: {len(all_texts)}")
print(f"Markov vocab: {len(mc.vocab)}")
print(f"Markov n-grams: {len(mc.n_grams)}")
print(f"Markov total tokens: {mc.total_tokens if hasattr(mc,'total_tokens') else '?'}")
