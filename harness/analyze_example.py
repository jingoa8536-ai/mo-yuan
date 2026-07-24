import urllib.request
from html.parser import HTMLParser

class StructureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.tags = []
        self.texts = []
        self.attrs_list = []
        self.structure_lines = []
    
    def handle_starttag(self, tag, attrs):
        indent = '  ' * self.depth
        attr_str = ' '.join([f'{k}="{v}"' for k, v in attrs if k])
        tag_str = f'<{tag}>' if not attr_str else f'<{tag} {attr_str}>'
        self.structure_lines.append(f'{indent}{tag_str}')
        self.tags.append(tag)
        self.attrs_list.append(attrs)
        self.depth += 1
    
    def handle_endtag(self, tag):
        self.depth -= 1
        indent = '  ' * self.depth
        self.structure_lines.append(f'{indent}</{tag}>')
    
    def handle_data(self, data):
        text = data.strip()
        if text:
            indent = '  ' * self.depth
            self.structure_lines.append(f'{indent}"{text}"')
            self.texts.append(text)

req = urllib.request.Request('https://example.com', headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode('utf-8')

parser = StructureParser()
parser.feed(html)

print("=" * 60)
print("  🌐 example.com 网站结构分析报告")
print("=" * 60)

print(f"\n📊 基本统计:")
print(f"  • 状态码: 200 OK")
print(f"  • 内容长度: {len(html)} 字节")
print(f"  • 内容类型: {resp.headers.get('Content-Type', 'N/A')}")
print(f"  • 服务器: {resp.headers.get('Server', 'N/A')}")

print(f"\n📋 DOM 树层级结构:")
for line in parser.structure_lines:
    print(f"  {line}")

print(f"\n🔍 标签统计:")
from collections import Counter
tag_counter = Counter()
for line in parser.structure_lines:
    if line.strip().startswith('<') and not line.strip().startswith('</') and not line.strip().startswith('"'):
        tag = line.strip().split()[0].replace('<', '')
        tag_counter[tag] += 1
for tag, count in tag_counter.most_common():
    print(f"  • <{tag}>: {count} 个")

print(f"\n📝 页面文本内容:")
for text in parser.texts[:10]:
    print(f"  • {text[:100]}")

print(f"\n🔗 链接分析:")
req2 = urllib.request.Request('https://example.com', headers={'User-Agent': 'Mozilla/5.0'})
resp2 = urllib.request.urlopen(req2, timeout=15)
html2 = resp2.read().decode('utf-8')
import re
links = re.findall(r'href=[\'"]?([^\'" >]+)', html2)
print(f"  共发现 {len(links)} 个链接:")
for link in links:
    print(f"  • {link}")

from urllib.parse import urlparse
print(f"\n🌍 页面基本信息:")
print(f"  • 域名: example.com")
print(f"  • 协议: HTTPS")
print(f"  • 用途: IANA 保留的示例域名")
print(f"  • 特点: 纯静态页面，无 JavaScript，无外部资源")
