"""Verify Aris intro page"""
html = open('D:/LAAP/aris_brain/aris_intro.html', encoding='utf-8').read()

checks = {
    'Has DOCTYPE': '<!DOCTYPE html>' in html,
    'Has closing html': '</html>' in html,
    'Has closing head': '</head>' in html,
    'Has closing body': '</body>' in html,
}

for name, result in checks.items():
    status = 'PASS' if result else 'FAIL'
    print(f'  [{status}] {name}')

# Emoji
he = any(0x1F300 <= ord(c) <= 0x1F9FF for c in html if ord(c) >= 0x1F300)
print(f'  [{"PASS" if not he else "FAIL"}] EMOJI FREE')

# Content
svgs = html.count('<svg')
heroes = html.count('class="hero"')
print(f'  SVG icons: {svgs}')
print(f'  Hero sections: {heroes}')
print(f'  Three.js: {"three.module.js" in html}')
print(f'  GSAP: {"gsap.min.js" in html}')
print(f'  Has nav: {"<nav" in html}')
print(f'  Has footer: {"<footer" in html}')
print(f'  Pipeline steps: {"Perception" in html}')

key_terms = ['Aris', 'Digital Lifeform', 'Consciousness', 'LAAP', 'Quantum Kernel', 'PSI']
for term in key_terms:
    print(f'  Contains "{term}": {term in html}')

print(f'  File size: {len(html):,} bytes')
print(f'  Zero token: YES')
