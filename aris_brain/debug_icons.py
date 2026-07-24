"""Debug: trace icon conversion"""
import sys
sys.path.insert(0, 'D:/LAAP/harness/laap_coding/core')
from intent_mapper import IntentMapper, FEATURE_TEMPLATES, lucide_icon, DEFAULT_CONTENT

# Test direct lucide_icon call
print("1. lucide_icon('Brain') works:", bool(lucide_icon('Brain')))

# Test template has features
tmpl = FEATURE_TEMPLATES.get('saas', DEFAULT_CONTENT)
feats = tmpl.get('features', [])
print(f"2. Template features: {len(feats)} items")
if feats:
    item = feats[0]
    print(f"3. First feature keys: {list(item.keys())}")
    print(f"4. icon='{item.get('icon','?')}', has icon_svg: {'icon_svg' in item}")

# Test conversion
card = dict(item)
if "icon" in card and not card.get("icon_svg"):
    card["icon_svg"] = lucide_icon(card.pop("icon", ""), size=20)
print(f"5. After conversion: icon_svg length={len(card.get('icon_svg',''))}")

# Now test through IntentMapper
m = IntentMapper()
spec = m.parse('暗色 SaaS 落地页')
for sec in spec.get('sections', []):
    if sec.get('type') == 'grid':
        cards = sec.get('cards', [])
        for i, c in enumerate(cards[:3]):
            svg = c.get('icon_svg', '')
            print(f"6. Built card {i}: has_svg={bool(svg)} len={len(svg)}")
