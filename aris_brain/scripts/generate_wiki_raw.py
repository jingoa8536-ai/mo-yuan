# -*- coding: utf-8 -*-
"""Generate wiki raw source pages for all scored items >=5."""
import json, re, os

data = json.load(open(r'C:\Users\user\AppData\Local\Temp\all_scored_items.json'))

def slugify(title):
    s = title.lower().replace(':', '').replace('(', '').replace(')', '')
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:60]
    return s

raw_dir = r'D:\LAAP\wiki\raw\sources'
os.makedirs(raw_dir, exist_ok=True)

raw_items = [x for x in data if x.get('storage') == 'raw']
created = []
for item in raw_items:
    title = item['title']
    slug = slugify(title)
    fname = f'intel-{slug}.md'
    fpath = os.path.join(raw_dir, fname)
    
    # Build frontmatter
    tags = ['intel', 'pipeline']
    if item['source'] == 'arXiv':
        tags.append('arxiv')
        if 'cs.AI' in item.get('categories',''): tags.append('ai')
        if 'cs.CL' in item.get('categories',''): tags.append('nlp')
        if 'cs.LG' in item.get('categories',''): tags.append('ml')
    elif item['source'] == 'Hacker News':
        tags.append('hn')
    elif item['source'] == 'GitHub':
        tags.append('github')
    
    kw = item.get('matched_keyword', '')
    if kw: tags.append(kw.replace(' ', '-')[:20])
    
    tags_str = '\n'.join(f'  - {t}' for t in tags)
    
    arxiv_id = item.get('id', '')
    url = item.get('abs_url', item.get('url', ''))
    
    content = f"""---
title: "{title}"
source: {item['source']}
source_url: "{url}"
ingested: 2026-07-10
type: raw_intel
tags:
{tags_str}
intel_score:
  quality: {item['quality']}
  safety: {item['safety']}
  innovation: {item['innovation']}
  efficiency: {item['efficiency']}
  overall: {item['overall']}
---

# {title}

**Source**: {item['source']}  
**Score**: {item['overall']}/10 (Q:{item['quality']} S:{item['safety']} I:{item['innovation']} E:{item['efficiency']})  
**URL**: {url}

"""

    if item['source'] == 'arXiv' and arxiv_id:
        content += f"""**arXiv ID**: {arxiv_id}  
**Published**: {item.get('published', '')}  
**Authors**: {item.get('authors', '')}  
**Categories**: {item.get('categories', '')}  
**PDF**: {item.get('pdf_url', '')}

"""
    
    content += f"""## Abstract

{item.get('summary', item.get('description', ''))[:500]}

---
*Auto-ingested by LAAP Intel Pipeline on 2026-07-10*
"""
    
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    created.append(fname)
    print(f'Created: {fpath}')

print(f'\nTotal files created: {len(created)}')
for f in created:
    print(f'  - {f}')

# Save created list for later use
with open(r'C:\Users\user\AppData\Local\Temp\created_files.json','w') as f:
    json.dump(created, f)
print('DONE')
