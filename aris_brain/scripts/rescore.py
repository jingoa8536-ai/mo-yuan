# -*- coding: utf-8 -*-
"""Re-score items with smarter innovation scoring."""
import json

data = json.load(open(r'C:\Users\user\AppData\Local\Temp\all_scored_items.json'))

# Paper-specific boosts based on actual relevance
boosts = {
    '2607.08690v1': {'innovation': 3.0, 'efficiency': 2.0},
    '2607.08642v1': {'innovation': 3.0, 'efficiency': 2.0},
    '2606.10413v1': {'innovation': 3.5, 'efficiency': 0.5},
    '2606.06380v1': {'innovation': 3.5, 'efficiency': 0.5},
    '2607.08662v1': {'innovation': 2.5, 'efficiency': 1.0},
    '2607.08646v1': {'innovation': 2.0, 'efficiency': 1.5},
    '2607.08643v1': {'innovation': 2.5, 'efficiency': 3.0},
    '2607.08740v1': {'innovation': 2.5, 'efficiency': 1.0},
    '2607.08374v1': {'innovation': 2.0, 'safety': 1.5},
    '2606.16319v1': {'innovation': 2.5, 'safety': 1.5},
    '2606.05528v1': {'innovation': 2.5, 'safety': 3.0},
    '2607.08758v1': {'innovation': 2.5, 'efficiency': 1.0},
    '2607.08282v1': {'innovation': 2.0, 'safety': 2.0},
    '2607.08288v1': {'innovation': 2.5, 'efficiency': 1.0},
    '2607.08193v1': {'innovation': 3.0, 'efficiency': 1.0},
    '2607.08771v1': {'innovation': 1.5, 'efficiency': 2.0},
    '2607.08734v1': {'innovation': 2.0, 'safety': 1.5},
    '2607.08766v1': {'innovation': 2.5, 'efficiency': 1.5},
}

# Keyword boost mapping
kw_boost = {
    'speculative decoding': 0.5, 'draft model': 0.5,
    'agi': 0.5, 'consciousness': 0.5,
    'self-improvement': 0.5, 'recursive': 0.5,
    'alignment': 0.5, 'safety': 0.3,
    'multi-agent': 0.5, 'agent': 0.3,
    'llm inference': 0.3, 'quantum': 0.3,
    'reasoning': 0.3,
}

for item in data:
    item_id = item.get('id', '')
    kw = item.get('matched_keyword', '').lower()
    title_lower = item['title'].lower()
    summary_lower = (item.get('summary', '') or '').lower()
    text = title_lower + ' ' + summary_lower
    
    # Apply paper-specific boosts
    b = boosts.get(item_id, {})
    if b:
        for dim, val in b.items():
            item[dim] = min(item[dim] + val, 9.5)
    
    # Generic keyword boost
    for kword, boost_val in kw_boost.items():
        if kword in kw or kword in text:
            item['innovation'] = min(item['innovation'] + 0.3, 9.0)
    
    # Recalculate overall
    item['overall'] = round((item['quality'] + item['safety'] + item['innovation'] + item['efficiency']) / 4.0, 1)
    
    # Storage decision
    if item['overall'] >= 7:
        item['storage'] = 'concept'
    elif item['overall'] >= 5:
        item['storage'] = 'raw'
    else:
        item['storage'] = 'skip'

data.sort(key=lambda x: x['overall'], reverse=True)

print('=== RE-SCORED RESULTS ===')
print('Total:', len(data))
conc = sum(1 for x in data if x.get('storage')=='concept')
rawc = sum(1 for x in data if x.get('storage')=='raw')
skipc = sum(1 for x in data if x.get('storage')=='skip')
print('Concept (>=7):', conc)
print('Raw (>=5):', rawc)
print('Skip (<5):', skipc)

for i, item in enumerate(data):
    st = item.get('storage')
    if st in ('concept', 'raw'):
        print(f'{i+1}. [{item["overall"]}] [{st}] {item["title"][:80]}')
        print('   Q:%s S:%s I:%s E:%s | %s' % (item['quality'], item['safety'], item['innovation'], item['efficiency'], item['source']))
        print()

with open(r'C:\Users\user\AppData\Local\Temp\all_scored_items.json','w') as f:
    json.dump(data, f, indent=2, default=str)
print('Saved')
