import logging
logger = logging.getLogger(__name__)

import pickle

with open('state/markov_chain.pkl', 'rb') as f:
    data = pickle.load(f)

print('Type:', type(data).__name__)
if isinstance(data, dict):
    print('Top keys:', list(data.keys())[:15])
    for k, v in data.items():
        if isinstance(v, dict):
            logger.info(f'  {k}: dict with {len(v)} items')
        elif isinstance(v, list):
            logger.info(f'  {k}: list with {len(v)} items')
        elif isinstance(v, int):
            logger.info(f'  {k}: int = {v}')
        elif isinstance(v, str):
            logger.info(f'  {k}: str (len={len(v)}) = {v[:60]}')
        else:
            logger.info(f'  {k}: {type(v).__name__}')
elif hasattr(data, '__dict__'):
    print('Object attributes:', list(data.__dict__.keys())[:15])
    for k, v in data.__dict__.items():
        if isinstance(v, dict):
            logger.info(f'  {k}: dict with {len(v)} items')
        elif isinstance(v, (int, float, str)):
            logger.info(f'  {k}: {type(v).__name__} = {v}')
        else:
            logger.info(f'  {k}: {type(v).__name__}')