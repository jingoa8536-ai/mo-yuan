import sys
sys.path.insert(0,'D:/LAAP/aris_brain')
from aris_markov_generator import MarkovChainGenerator

mc = MarkovChainGenerator(order=3, min_freq=1)
mc.load('D:/LAAP/aris_brain/state/markov_chain.pkl')

# List ALL public attributes
print("Attributes after load:")
for a in dir(mc):
    if not a.startswith('__'):
        v = getattr(mc, a)
        if not callable(v):
            print(f"  {a}: {type(v).__name__}", end="")
            if isinstance(v, dict):
                print(f"({len(v)} keys)")
            elif isinstance(v, (list, tuple)):
                print(f"({len(v)})")
            elif isinstance(v, (int, float)):
                print(f" = {v}")
            else:
                print()
