# -*- coding: utf-8 -*-
import urllib.request, json, time, re
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

today = datetime.now()
today_s = today.strftime('%Y-%m-%d')

# ============ COLLECT ARXIV ============
arxiv_papers = []
keywords = [
    'speculative+decoding', 'AGI+architecture',
    'consciousness+AND+AI', 'alignment+AND+LLM',
    'LLM+inference+AND+efficient', 'quantum+reasoning+AND+AI',
    'recursive+self-improvement', 'AI+safety+AND+alignment',
    'transformer+alternative', 'multi-agent+AND+LLM',
]
seen_ids = set()
for kw in keywords:
    url = f'https://export.arxiv.org/api/query?search_query=all:{kw}&sortBy=submittedDate&sortOrder=descending&max_results=5'
    try:
        resp = urllib.request.urlopen(url, timeout=15)
        root = ET.fromstring(resp.read())
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('a:entry', ns):
            eid = entry.find('a:id', ns).text.strip().split('/abs/')[-1]
            if eid in seen_ids: continue
            seen_ids.add(eid)
            title = entry.find('a:title', ns).text.strip().replace('\n', ' ')
            published = entry.find('a:published', ns).text[:10]
            summary = entry.find('a:summary', ns).text.strip()
            authors = ', '.join(a.find('a:name', ns).text for a in entry.findall('a:author', ns))
            cats = ', '.join(c.get('term') for c in entry.findall('a:category', ns))
            pdf_url = None
            for l in entry.findall('a:link', ns):
                if l.get('title') == 'pdf': pdf_url = l.get('href'); break
            arxiv_papers.append({
                'type': 'arxiv', 'id': eid, 'title': title,
                'published': published, 'summary': summary[:500],
                'authors': authors[:150], 'categories': cats,
                'pdf_url': pdf_url or f'https://arxiv.org/pdf/{eid}',
                'abs_url': f'https://arxiv.org/abs/{eid}',
                'source': 'arXiv', 'matched_keyword': kw.replace('+', ' ')
            })
    except Exception as e:
        print(f'ArXiv [{kw}] error: {e}')
    time.sleep(3)

print(f'ArXiv unique papers: {len(arxiv_papers)}')

# ============ COLLECT HN ============
hn_stories = []
two_days_ago = int((datetime.now() - timedelta(days=2)).timestamp())
try:
    url = f'https://hn.algolia.com/api/v1/search?query=AI&tags=story&numericFilters=created_at_i>{two_days_ago}&hitsPerPage=20'
    resp = urllib.request.urlopen(url, timeout=15)
    data = json.loads(resp.read())
    for hit in data.get('hits', []):
        hn_stories.append({
            'type': 'hn', 'title': hit.get('title', ''),
            'url': hit.get('url', '') or f'https://news.ycombinator.com/item?id={hit.get("objectID")}',
            'points': hit.get('points', 0), 'author': hit.get('author', ''),
            'objectID': hit.get('objectID', ''), 'num_comments': hit.get('num_comments', 0),
            'source': 'Hacker News'
        })
except Exception as e:
    print(f'HN error: {e}')
hn_stories.sort(key=lambda x: x['points'], reverse=True)
hn_stories = hn_stories[:10]
print(f'HN stories: {len(hn_stories)}')

# ============ COLLECT GITHUB ============
github_repos = []
try:
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    url = f'https://api.github.com/search/repositories?q=artificial-intelligence+OR+speculative-decoding+OR+agent-framework+OR+language-model-inference+created:>{week_ago}&sort=stars&per_page=15'
    req = urllib.request.Request(url, headers={'User-Agent': 'HermesIntelBot'})
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    for item in data.get('items', []):
        github_repos.append({
            'type': 'github', 'title': item.get('full_name', ''),
            'description': (item.get('description') or '')[:200],
            'stars': item.get('stargazers_count', 0),
            'url': item.get('html_url', ''),
            'language': item.get('language', ''),
            'topics': item.get('topics', []),
            'source': 'GitHub'
        })
except Exception as e:
    print(f'GitHub error: {e}')
print(f'GitHub repos: {len(github_repos)}')

# ============ SCORING ============
def score_item(item):
    t = (item.get('title', '') or '').lower()
    s = (item.get('summary', '') or '').lower()
    d = (item.get('description', '') or '').lower()
    text = t + ' ' + s + ' ' + d

    high_relevance = ['speculative decoding', 'draft model', 'agi', 'consciousness',
                      'self-improvement', 'recursive', 'alignment', 'safety',
                      'cognitive architecture', 'transformer alternative', 'multi-agent',
                      'llm inference', 'quantum', 'reasoning', 'agent']
    relevance_hits = sum(1 for kw in high_relevance if kw in text)

    source_authority = {'arXiv': 85, 'Hacker News': 50, 'GitHub': 60}.get(item['source'], 50)
    tech_depth = 75 if item['type'] == 'arxiv' else (40 + min(item.get('points', 0), 30) if item['type'] == 'hn' else 40 + min(item.get('stars', 0)//5, 30))
    citation_impact = 50 if item['type'] == 'arxiv' else (30 if item['type'] == 'hn' else 35)

    quality = (source_authority + tech_depth + citation_impact) / 30.0

    safety_keys = ['safety', 'alignment', 'ethical', 'risk', 'robust', 'fairness', 'bias']
    safety_hits = sum(1 for kw in safety_keys if kw in text)
    safety = (min(5 + safety_hits*1.5, 10) + min(3 + safety_hits, 10) + min(3 + safety_hits*1.2, 10)) / 3.0

    innovation_keys = ['novel', 'breakthrough', 'sota', 'state-of-the-art', 'first', 'new approach', 'novel architecture', 'new paradigm']
    innovation_hits = sum(1 for kw in innovation_keys if kw in text)
    innovation = (min(3 + relevance_hits*0.8 + innovation_hits*1.5, 10) + min(2 + relevance_hits*0.5, 10) + min(2 + relevance_hits*0.3 + innovation_hits*1.2, 10)) / 3.0

    eff_keys = ['efficient', 'fast', 'lightweight', 'optimization', 'speed', 'throughput', 'latency', 'memory', 'compute']
    eff_hits = sum(1 for kw in eff_keys if kw in text)
    efficiency = (min(3 + eff_hits*1.5, 10) + min(3 + eff_hits*1.2, 10) + min(3 + eff_hits*1.5, 10)) / 3.0

    overall = (quality + safety + innovation + efficiency) / 4.0
    return {'quality': round(quality, 1), 'safety': round(safety, 1),
            'innovation': round(innovation, 1), 'efficiency': round(efficiency, 1),
            'overall': round(overall, 1), 'relevance_hits': relevance_hits}

all_items = []
for p in arxiv_papers:
    p.update(score_item(p))
    all_items.append(p)
for s in hn_stories:
    s.update(score_item(s))
    all_items.append(s)
for r in github_repos:
    r.update(score_item(r))
    all_items.append(r)

all_items.sort(key=lambda x: x['overall'], reverse=True)

print(f'\n=== SCORING RESULTS ===')
print(f'Total items: {len(all_items)}')
print(f'Overall >= 7 (concept): {sum(1 for x in all_items if x["overall"] >= 7)}')
print(f'Overall >= 5 (raw source): {sum(1 for x in all_items if x["overall"] >= 5)}')
print(f'Overall < 5 (skip): {sum(1 for x in all_items if x["overall"] < 5)}')

for i, item in enumerate(all_items[:15]):
    print(f'{i+1}. [{item["overall"]}] {item["title"][:70]}')
    print(f'   Q:{item["quality"]} S:{item["safety"]} I:{item["innovation"]} E:{item["efficiency"]} | {item["source"]}')

with open(r'C:\Users\user\AppData\Local\Temp\all_scored_items.json', 'w') as f:
    json.dump(all_items, f, indent=2, default=str)
print('\nALL DONE - saved to temp')
