import sys, json, os, glob, pickle
sys.path.insert(0,'D:/LAAP/aris_brain')
from aris_markov_generator import MarkovChainGenerator

# 1. Load existing Markov chain
print("=== Loading existing Markov chain ===")
mc = MarkovChainGenerator(order=3, min_freq=1)
mc.load('D:/LAAP/aris_brain/state/markov_chain.pkl')
print(f"Loaded: vocab={len(mc._vocab) if hasattr(mc,'_vocab') else '?'}, tokens={mc.total_tokens if hasattr(mc,'total_tokens') else '?'}")
print(f"Before stats: vocab={len(mc._vocab)}, transitions={len(mc._transitions)}, total_ngrams={mc._total_ngrams}, tokens={mc.total_tokens}")

# 2. Read ONLY new corpus files (wikipedia zh - not already in markov)
corpus_dir = 'D:/LAAP/aris_brain/corpus/datasets'
new_file = 'D:/LAAP/aris_brain/corpus/datasets/wikipedia_zh_20260710_153841.json'

with open(new_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
texts = [str(t) if not isinstance(t, dict) else str(t.get('text', t.get('content', ''))) for t in data]
print(f"\n=== New corpus file: wikipedia_zh_20260710_153841.json ===")
print(f"Texts: {len(texts)}, chars: {sum(len(t) for t in texts)}")

# 3. Train incrementally on new data only
print("\n=== Training Markov incrementally ===")
mc.train(texts)
print(f"Trained: vocab={len(mc._vocab)}, transitions={len(mc._transitions)}, total_ngrams={mc._total_ngrams}, tokens={mc.total_tokens}")

# 4. Save
print("\n=== Saving Markov chain ===")
mc.save('D:/LAAP/aris_brain/state/markov_chain.pkl')

# 5. Verify
mc2 = MarkovChainGenerator(order=3, min_freq=1)
mc2.load('D:/LAAP/aris_brain/state/markov_chain.pkl')
print(f"Verified: vocab={len(mc2._vocab)}, transitions={len(mc2._transitions)}, total_ngrams={mc2._total_ngrams}, tokens={mc2.total_tokens}")

# 6. Summary
old_vocab = 34272
old_ngrams = 54741367
print("\n=== SUMMARY ===")
print(f"Vocab: {old_vocab} -> {len(mc._vocab)} (+{len(mc._vocab)-old_vocab})")
print(f"N-grams: {old_ngrams} -> {mc._total_ngrams} (+{mc._total_ngrams-old_ngrams})")
print(f"Tokens: {mc.total_tokens}")
print(f"New corpus files added: 1 (wikipedia_zh, 500 docs, {sum(len(t) for t in texts)} chars)")
