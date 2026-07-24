# -*- coding: utf-8 -*-
"""Update wiki index.md and log.md with new intel findings."""
import json, re

data = json.load(open(r'C:\Users\user\AppData\Local\Temp\all_scored_items.json'))
raw_items = [x for x in data if x.get('storage') == 'raw']

def slugify(title):
    s = title.lower().replace(':', '').replace('(', '').replace(')', '')
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:60]
    return s

# ============ UPDATE INDEX ============
idx = open(r'D:\LAAP\wiki\index.md', encoding='utf-8').read()

# Check if Intel Reports / Raw Sources sections exist
# The index may have different structure - let's check
lines = idx.split('\n')
has_intel_concepts = any('Intel Reports' in l for l in lines)
has_raw_sources = any('## Raw Sources' in l for l in lines)

print(f'Has Intel Reports section: {has_intel_concepts}')
print(f'Has Raw Sources section: {has_raw_sources}')

# Find the end of the index to add new sections
# Count existing pages
page_count = 0
for line in lines:
    m = re.match(r'pages: (\d+)', line)
    if m:
        page_count = int(m.group(1))
        break

print(f'Current page count: {page_count}')

# Build new raw sources entries
new_entries = []
for item in raw_items:
    slug = slugify(item['title'])
    fname = f'intel-{slug}'
    title = item['title'][:60]
    new_entries.append(f'- [[{fname}]] - {title}')

new_entries.sort()

# Add Raw Sources section if needed
raw_section = '\n## Raw Sources\n\n'
raw_section += '\n'.join(new_entries)

if has_raw_sources:
    # Replace existing section
    pass

print('=== NEW RAW ENTRIES ===')
for e in new_entries:
    print(f'  {e}')
print(f'Total new: {len(new_entries)}')

# ============ UPDATE LOG ============
log = open(r'D:\LAAP\wiki\log.md', encoding='utf-8').read()

today = '2026-07-10'
log_entry = f"""## [{today}] intel pipeline | Daily AGI/ASI intelligence collection

**Source**: arXiv (39 papers), HN (20 stories), GitHub Search API
**Results**: Collected 49 items → 15 stored (raw sources) | Highest score: {raw_items[0]['overall']} ({raw_items[0]['title'][:50]})
**Blogs**: Google AI, Meta AI, Anthropic, DeepMind - all JS-rendered/unreachable. OpenAI - 403 Forbidden.
**Notes**: No items reached concept threshold (7.0). 15 items stored as raw sources.

### Files created:
"""
for item in raw_items:
    slug = slugify(item['title'])
    fname = f'intel-{slug}'
    log_entry += f'- raw/sources/{fname}.md | {item["overall"]}/10 | {item["title"][:50]}\n'

# Prepend to log
new_log = log_entry + '\n' + log

# Write updated log
with open(r'D:\LAAP\wiki\log.md', 'w', encoding='utf-8') as f:
    f.write(new_log)
print('Log updated successfully')

# ============ WRITE UPDATED INDEX ============
# Build new index with raw sources section
# Find the right place to insert - after concepts, before comparisons/queries
# Or at the end

# For now, let's append the raw sources section before any trailing empty lines
idx = idx.rstrip()
idx += '\n\n## Raw Sources\n\n'
# Add entries grouped by source
idx += '### arXiv Papers\n\n'
arxiv_entries = [e for i, e in zip(raw_items, new_entries) if i['source'] == 'arXiv']
for e in arxiv_entries:
    idx += e + '\n'

hn_entries = [e for i, e in zip(raw_items, new_entries) if i['source'] == 'Hacker News']
if hn_entries:
    idx += '\n### Hacker News\n\n'
    for e in hn_entries:
        idx += e + '\n'

gh_entries = [e for i, e in zip(raw_items, new_entries) if i['source'] == 'GitHub']
if gh_entries:
    idx += '\n### GitHub\n\n'
    for e in gh_entries:
        idx += e + '\n'

# Update page count
new_page_count = page_count + len(raw_items)
idx = re.sub(r'pages: \d+', f'pages: {new_page_count}', idx)
idx = re.sub(r'updated: \d{4}-\d{2}-\d{2}', f'updated: {today}', idx)

with open(r'D:\LAAP\wiki\index.md', 'w', encoding='utf-8') as f:
    f.write(idx)
print(f'Index updated: {page_count} -> {new_page_count} pages')

print('\nDONE - index and log updated')
