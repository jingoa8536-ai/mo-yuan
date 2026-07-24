"""手机马尔科夫模型生成器 - 从PC模型提取手机版"""

import logging
logger = logging.getLogger(__name__)

import pickle, json, os, sys

logger.info('Loading PC Markov model (8.8MB)...')
with open('D:/LAAP/aris_brain/state/markov_chain.pkl', 'rb') as f:
    data = pickle.load(f)

chain = data['transitions']
logger.info(f'Original: {len(chain)} contexts')
mobile_chain = {}
total_orig = 0
total_mobile = 0
for ctx, next_words in chain.items():
    total_orig += len(next_words)
    sorted_items = sorted(next_words.items(), key=lambda x: -x[1])[:8]
    mobile_chain[ctx] = dict(sorted_items)
    total_mobile += len(sorted_items)

# 只保留总频率最高的8000个context
sorted_ctx = sorted(mobile_chain.items(), key=lambda x: -sum(x[1].values()))
mobile_chain = dict(sorted_ctx[:8000])

# 精简starters
starters = data['starters'][:3000]

mobile_data = {
    'order': 2,
    'vocab_size': min(data['vocab_size'], 4000),
    'total_ngrams': total_mobile,
    'starters': starters,
    'transitions': mobile_chain,
}

logger.info(f'Mobile chain: {len(mobile_chain)} contexts, {total_mobile} n-grams')
logger.info(f'Starters: {len(data["starters"])} -> {len(starters)}')
out_dir = 'D:/LAAP/aris_brain/mobile_package/state'
os.makedirs(out_dir, exist_ok=True)

# Save as pkl
pkl_path = os.path.join(out_dir, 'markov_mobile.pkl')
with open(pkl_path, 'wb') as f:
    pickle.dump(mobile_data, f, protocol=2)
pkl_size = os.path.getsize(pkl_path)
logger.info(f'pkl size: {pkl_size/1024:.0f}KB')
logger.info('Done!')