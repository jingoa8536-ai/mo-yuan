#!/usr/bin/env python3
"""Check KB stats"""
import json, os
from collections import Counter

d = json.load(open('paper_kb/paper_meta.json'))
print(f'Total papers: {len(d)}')

# Target categories
cats = Counter()
for pid, info in d.items():
    for c in info.get('categories', []):
        cats[c] += 1

print('Target category counts:')
for c in ['cs.AI', 'cs.CL', 'cs.LG', 'cs.NE', 'stat.ML']:
    print(f'  {c}: {cats[c]}')

# Years
years = Counter()
for info in d.values():
    years[info.get('year', '?')] += 1
print('Recent years:')
for y in sorted(years.keys(), reverse=True)[:10]:
    print(f'  {y}: {years[y]}')

# NPZ check
npz_path = 'paper_kb/paper_kb.npz'
if os.path.exists(npz_path):
    sz = os.path.getsize(npz_path)
    print(f'NPZ size: {sz/1024/1024:.1f} MB')
import numpy as np
data = np.load(npz_path, allow_pickle=True)
print(f'Matrix shape: {data["matrix"].shape}')
print(f'Texts: {len(data["texts"])}')
print(f'Sources: {len(data["sources"])}')
