import os, glob, pickle, json

# Corpus files
files = sorted(glob.glob('D:/LAAP/aris_brain/corpus/datasets/*'))
print("=== CORPUS FILES ===")
for f in files:
    sz = os.path.getsize(f)
    mb = sz / 1024 / 1024
    print(f"{mb:6.1f}M  {os.path.basename(f)}")
total_sz = sum(os.path.getsize(f) for f in files)
print(f"Total: {len(files)} files, {total_sz/1024/1024:.0f}M total")

# Markov state
print("\n=== MARKOV CHAIN ===")
with open('D:/LAAP/aris_brain/state/markov_chain.pkl','rb') as f:
    mc = pickle.load(f)
for k, v in mc.items():
    if isinstance(v, dict):
        print(f"{k}: dict({len(v)} keys)")
    elif isinstance(v, (list, tuple)):
        print(f"{k}: {type(v).__name__}({len(v)})")
    else:
        print(f"{k}: {v}")
