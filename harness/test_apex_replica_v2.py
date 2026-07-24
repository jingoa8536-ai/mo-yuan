import asyncio
import json
import os
import re
from pathlib import Path

from laap_coding.core.web_crawler import WebCrawler, WebsiteAnalyzer
from laap_coding.core.web_replicator import WebReplicator
from laap_coding.core.matching_engine import MatchingEngine


async def analyze_with_playwright(url: str):
    """使用Playwright深度分析网站"""
    print("=" * 80)
    print("🔍 深度网站分析 (Playwright)")
    print("=" * 80)
    
    crawler = WebCrawler(max_pages=3, timeout=60, delay=2.0)
    result = await crawler.crawl_and_analyze(url, use_playwright=True)
    
    print(f"\n📋 网站基本信息:")
    print(f"  URL: {result.website.url}")
    print(f"  域名: {result.website.domain}")
    print(f"  标题: {result.website.title}")
    print(f"  描述: {result.website.description}")
    
    print(f"\n🔧 技术栈检测:")
    for tech in result.website.tech_stack:
        print(f"  ✅ {tech}")
    
    print(f"\n📊 内容结构:")
    print(f"  爬取页面数: {result.pages_crawled}")
    print(f"  爬取耗时: {result.crawl_time:.2f}秒")
    
    if result.pages:
        page = result.pages[0]
        print(f"\n📄 首页详情:")
        print(f"  标题: {page.title}")
        print(f"  字数: {page.word_count}")
        print(f"  图片数: {len(page.images)}")
        print(f"  链接数: {len(page.links)}")
        
        print(f"\n📝 页面标题层级:")
        for i, heading in enumerate(page.headings[:10], 1):
            print(f"  {i}. {heading}")
        
        print(f"\n📷 页面图片:")
        for img in page.images[:5]:
            print(f"  - {img['src']} ({img.get('alt', '无描述')})")
    
    tokens = crawler.extract_tokens(result)
    print(f"\n🎨 设计令牌:")
    print(f"  颜色: {tokens['colors']}")
    print(f"  字体: {tokens['typography']}")
    
    return result, tokens


def extract_game_features(html: str):
    """提取游戏相关特性"""
    features = {
        'game_elements': [],
        'ui_components': [],
        'racing_features': [],
        'color_scheme': [],
    }
    
    if 'leaderboard' in html.lower():
        features['game_elements'].append('leaderboard')
        features['racing_features'].append('排行榜')
    
    if 'lap' in html.lower():
        features['game_elements'].append('lap_timer')
        features['racing_features'].append('圈速计时')
    
    if 'race' in html.lower():
        features['racing_features'].append('比赛')
    
    if 'car' in html.lower():
        features['game_elements'].append('car')
        features['racing_features'].append('赛车')
    
    if 'track' in html.lower():
        features['game_elements'].append('track')
        features['racing_features'].append('赛道')
    
    if 'speed' in html.lower():
        features['racing_features'].append('速度')
    
    if 'time' in html.lower():
        features['game_elements'].append('timer')
    
    if 'button' in html.lower():
        features['ui_components'].append('button')
    
    if 'card' in html.lower():
        features['ui_components'].append('card')
    
    if 'modal' in html.lower():
        features['ui_components'].append('modal')
    
    if 'dashboard' in html.lower():
        features['ui_components'].append('dashboard')
    
    color_matches = re.findall(r'#([0-9a-fA-F]{6})', html)
    if color_matches:
        features['color_scheme'] = list(set(color_matches))[:8]
    
    return features


async def enhanced_replicate(url: str):
    """增强版复刻 - 针对赛车游戏网站"""
    print("\n" + "=" * 80)
    print("⚡ 增强版零Token复刻")
    print("=" * 80)
    
    analyzer = WebsiteAnalyzer()
    result = await analyzer.analyze(url, use_playwright=True)
    
    if result.pages:
        page = result.pages[0]
        game_features = extract_game_features(page.html)
        
        print(f"\n🎮 提取的游戏特性:")
        print(f"  游戏元素: {game_features['game_elements']}")
        print(f"  UI组件: {game_features['ui_components']}")
        print(f"  赛车特性: {game_features['racing_features']}")
        print(f"  配色方案: {game_features['color_scheme']}")
    
    engine = MatchingEngine(use_enhancements=True)
    
    tags = ['react', 'racing', 'game', 'sports', 'ui', 'components', 'website']
    tags.extend(game_features.get('game_elements', []))
    tags.extend(game_features.get('ui_components', []))
    
    intent = {
        "tags": tags,
        "style": "modern-minimal",
        "tech": "React",
    }
    
    matches = engine.match_intent(intent)
    best_match = matches[0] if matches else None
    
    print(f"\n🎯 最佳匹配: {best_match['name'] if best_match else '无'}")
    
    replicator = WebReplicator(output_dir="replicas")
    
    custom_spec = {
        "title": "APEX Racing",
        "description": "Set a lap, climb the leaderboard, and challenge the next driver to beat your time in APEX.",
        "tech_stack": ["React", "Next.js"],
        "design_tokens": {
            "colors": game_features.get('color_scheme', ['#000000', '#ffffff', '#ef4444', '#f59e0b']),
            "typography": ['Inter', 'system-ui'],
            "spacing": ['16px', '24px', '32px'],
        },
        "layout_pattern": {
            "columns": 12,
            "gutter": "24px",
            "pattern": "game-dashboard",
        },
        "components": ['hero', 'leaderboard', 'stats', 'cta', 'footer'],
        "features": game_features,
    }
    
    print(f"\n🏗️ 生成定制化复刻...")
    
    base_path = os.path.join("replicas", "apex-racing-enhanced")
    os.makedirs(base_path, exist_ok=True)
    
    html = generate_racing_html(custom_spec)
    html_path = os.path.join(base_path, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    css = generate_racing_css(custom_spec)
    css_path = os.path.join(base_path, "style.css")
    with open(css_path, "w", encoding="utf-8") as f:
        f.write(css)
    
    js = generate_racing_js(custom_spec)
    js_path = os.path.join(base_path, "app.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js)
    
    spec_path = os.path.join(base_path, "replica_spec.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(custom_spec, f, indent=2, ensure_ascii=False)
    
    output_files = [html_path, css_path, js_path, spec_path]
    
    print(f"\n🎉 增强版复刻成功!")
    print(f"\n💾 输出文件 ({len(output_files)} 个):")
    for file_path in output_files:
        print(f"  - {file_path}")
    
    return output_files


def generate_racing_html(spec):
    """生成赛车游戏风格的HTML"""
    colors = spec.get('design_tokens', {}).get('colors', [])
    primary_color = colors[0] if colors else '#ef4444'
    
    html_parts = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html lang=\"en\">")
    html_parts.append("<head>")
    html_parts.append("    <meta charset=\"UTF-8\">")
    html_parts.append("    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")
    html_parts.append(f"    <title>{spec['title']}</title>")
    html_parts.append(f"    <meta name=\"description\" content=\"{spec['description']}\">")
    html_parts.append("    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">")
    html_parts.append("    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>")
    html_parts.append("    <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap\" rel=\"stylesheet\">")
    html_parts.append("    <link rel=\"stylesheet\" href=\"style.css\">")
    html_parts.append("</head>")
    html_parts.append("<body>")
    
    html_parts.append("    <!-- Navigation -->")
    html_parts.append("    <nav class=\"navbar\">")
    html_parts.append("        <div class=\"container\">")
    html_parts.append("            <div class=\"logo\">")
    html_parts.append("                <span class=\"logo-icon\">⚡</span>")
    html_parts.append("                <span class=\"logo-text\">APEX</span>")
    html_parts.append("            </div>")
    html_parts.append("            <ul class=\"nav-links\">")
    html_parts.append("                <li><a href=\"#home\">Home</a></li>")
    html_parts.append("                <li><a href=\"#leaderboard\">Leaderboard</a></li>")
    html_parts.append("                <li><a href=\"#stats\">Stats</a></li>")
    html_parts.append("                <li><a href=\"#about\">About</a></li>")
    html_parts.append("            </ul>")
    html_parts.append("            <button class=\"nav-btn\">Start Race</button>")
    html_parts.append("        </div>")
    html_parts.append("    </nav>")
    
    html_parts.append("    <!-- Hero Section -->")
    html_parts.append("    <section class=\"hero\" id=\"home\">")
    html_parts.append("        <div class=\"container\">")
    html_parts.append("            <div class=\"hero-content\">")
    html_parts.append("                <div class=\"hero-badge\">RACING GAME</div>")
    html_parts.append("                <h1>Set a Lap,")
    html_parts.append("                <br>Climb the Leaderboard</h1>")
    html_parts.append("                <p>Challenge the next driver to beat your time in APEX.")
    html_parts.append("                Every second counts.</p>")
    html_parts.append("                <div class=\"hero-actions\">")
    html_parts.append("                    <button class=\"btn btn-primary\">Start Racing</button>")
    html_parts.append("                    <button class=\"btn btn-secondary\">Watch Trailer</button>")
    html_parts.append("                </div>")
    html_parts.append("            </div>")
    html_parts.append("            <div class=\"hero-stats\">")
    html_parts.append("                <div class=\"stat-card\">")
    html_parts.append("                    <div class=\"stat-value\">10K+</div>")
    html_parts.append("                    <div class=\"stat-label\">Active Players</div>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"stat-card\">")
    html_parts.append("                    <div class=\"stat-value\">1M+</div>")
    html_parts.append("                    <div class=\"stat-label\">Races Completed</div>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"stat-card\">")
    html_parts.append("                    <div class=\"stat-value\">50+</div>")
    html_parts.append("                    <div class=\"stat-label\">Tracks Available</div>")
    html_parts.append("                </div>")
    html_parts.append("            </div>")
    html_parts.append("        </div>")
    html_parts.append("    </section>")
    
    html_parts.append("    <!-- Leaderboard Section -->")
    html_parts.append("    <section class=\"leaderboard\" id=\"leaderboard\">")
    html_parts.append("        <div class=\"container\">")
    html_parts.append("            <div class=\"section-header\">")
    html_parts.append("                <h2>Leaderboard</h2>")
    html_parts.append("                <p>Top drivers this week</p>")
    html_parts.append("            </div>")
    html_parts.append("            <div class=\"leaderboard-table\">")
    html_parts.append("                <div class=\"table-header\">")
    html_parts.append("                    <span>Rank</span>")
    html_parts.append("                    <span>Driver</span>")
    html_parts.append("                    <span>Car</span>")
    html_parts.append("                    <span>Best Time</span>")
    html_parts.append("                    <span>Points</span>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"table-row podium-1\">")
    html_parts.append("                    <span class=\"rank\">🥇</span>")
    html_parts.append("                    <span class=\"driver\">SpeedDemon_99</span>")
    html_parts.append("                    <span class=\"car\">Ferrari SF90</span>")
    html_parts.append("                    <span class=\"time\">1:23.456</span>")
    html_parts.append("                    <span class=\"points\">12,840</span>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"table-row podium-2\">")
    html_parts.append("                    <span class=\"rank\">🥈</span>")
    html_parts.append("                    <span class=\"driver\">RacingPro_X</span>")
    html_parts.append("                    <span class=\"car\">McLaren P1</span>")
    html_parts.append("                    <span class=\"time\">1:25.789</span>")
    html_parts.append("                    <span class=\"points\">11,520</span>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"table-row podium-3\">")
    html_parts.append("                    <span class=\"rank\">🥉</span>")
    html_parts.append("                    <span class=\"driver\">TurboCharged</span>")
    html_parts.append("                    <span class=\"car\">Lamborghini Huracan</span>")
    html_parts.append("                    <span class=\"time\">1:27.123</span>")
    html_parts.append("                    <span class=\"points\">10,380</span>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"table-row\">")
    html_parts.append("                    <span class=\"rank\">4</span>")
    html_parts.append("                    <span class=\"driver\">FormulaOne</span>")
    html_parts.append("                    <span class=\"car\">Red Bull RB19</span>")
    html_parts.append("                    <span class=\"time\">1:28.456</span>")
    html_parts.append("                    <span class=\"points\">9,240</span>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"table-row\">")
    html_parts.append("                    <span class=\"rank\">5</span>")
    html_parts.append("                    <span class=\"driver\">DriftKing</span>")
    html_parts.append("                    <span class=\"car\">Nissan GT-R</span>")
    html_parts.append("                    <span class=\"time\">1:29.789</span>")
    html_parts.append("                    <span class=\"points\">8,670</span>")
    html_parts.append("                </div>")
    html_parts.append("            </div>")
    html_parts.append("        </div>")
    html_parts.append("    </section>")
    
    html_parts.append("    <!-- Stats Section -->")
    html_parts.append("    <section class=\"stats\" id=\"stats\">")
    html_parts.append("        <div class=\"container\">")
    html_parts.append("            <div class=\"section-header\">")
    html_parts.append("                <h2>Real-time Stats</h2>")
    html_parts.append("                <p>Track your performance</p>")
    html_parts.append("            </div>")
    html_parts.append("            <div class=\"stats-grid\">")
    html_parts.append("                <div class=\"stat-card-large\">")
    html_parts.append("                    <div class=\"stat-icon\">⏱️</div>")
    html_parts.append("                    <div class=\"stat-info\">")
    html_parts.append("                        <div class=\"stat-value-lg\">1:23.456</div>")
    html_parts.append("                        <div class=\"stat-label\">Best Lap Time</div>")
    html_parts.append("                    </div>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"stat-card-large\">")
    html_parts.append("                    <div class=\"stat-icon\">🏁</div>")
    html_parts.append("                    <div class=\"stat-info\">")
    html_parts.append("                        <div class=\"stat-value-lg\">47</div>")
    html_parts.append("                        <div class=\"stat-label\">Races Won</div>")
    html_parts.append("                    </div>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"stat-card-large\">")
    html_parts.append("                    <div class=\"stat-icon\">💨</div>")
    html_parts.append("                    <div class=\"stat-info\">")
    html_parts.append("                        <div class=\"stat-value-lg\">320</div>")
    html_parts.append("                        <div class=\"stat-label\">Top Speed (km/h)</div>")
    html_parts.append("                    </div>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"stat-card-large\">")
    html_parts.append("                    <div class=\"stat-icon\">🔥</div>")
    html_parts.append("                    <div class=\"stat-info\">")
    html_parts.append("                        <div class=\"stat-value-lg\">89%</div>")
    html_parts.append("                        <div class=\"stat-label\">Completion Rate</div>")
    html_parts.append("                    </div>")
    html_parts.append("                </div>")
    html_parts.append("            </div>")
    html_parts.append("        </div>")
    html_parts.append("    </section>")
    
    html_parts.append("    <!-- CTA Section -->")
    html_parts.append("    <section class=\"cta\">")
    html_parts.append("        <div class=\"container\">")
    html_parts.append("            <h2>Ready to Race?</h2>")
    html_parts.append("            <p>Join thousands of drivers and climb the leaderboard today.</p>")
    html_parts.append("            <div class=\"cta-actions\">")
    html_parts.append("                <button class=\"btn btn-primary\">Download Now</button>")
    html_parts.append("                <button class=\"btn btn-outline\">Learn More</button>")
    html_parts.append("            </div>")
    html_parts.append("        </div>")
    html_parts.append("    </section>")
    
    html_parts.append("    <!-- Footer -->")
    html_parts.append("    <footer class=\"footer\" id=\"about\">")
    html_parts.append("        <div class=\"container\">")
    html_parts.append("            <div class=\"footer-content\">")
    html_parts.append("                <div class=\"footer-brand\">")
    html_parts.append("                    <span class=\"logo-icon\">⚡</span>")
    html_parts.append("                    <span class=\"logo-text\">APEX</span>")
    html_parts.append("                    <p>Experience the thrill of racing.</p>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"footer-links\">")
    html_parts.append("                    <h4>Quick Links</h4>")
    html_parts.append("                    <ul>")
    html_parts.append("                        <li><a href=\"#home\">Home</a></li>")
    html_parts.append("                        <li><a href=\"#leaderboard\">Leaderboard</a></li>")
    html_parts.append("                        <li><a href=\"#stats\">Stats</a></li>")
    html_parts.append("                        <li><a href=\"#about\">About</a></li>")
    html_parts.append("                    </ul>")
    html_parts.append("                </div>")
    html_parts.append("                <div class=\"footer-links\">")
    html_parts.append("                    <h4>Support</h4>")
    html_parts.append("                    <ul>")
    html_parts.append("                        <li><a href=\"#\">Help Center</a></li>")
    html_parts.append("                        <li><a href=\"#\">Community</a></li>")
    html_parts.append("                        <li><a href=\"#\">Contact</a></li>")
    html_parts.append("                        <li><a href=\"#\">Privacy Policy</a></li>")
    html_parts.append("                    </ul>")
    html_parts.append("                </div>")
    html_parts.append("            </div>")
    html_parts.append("            <div class=\"footer-bottom\">")
    html_parts.append("                <p>&copy; 2024 APEX Racing. All rights reserved.</p>")
    html_parts.append("            </div>")
    html_parts.append("        </div>")
    html_parts.append("    </footer>")
    
    html_parts.append("    <script src=\"app.js\"></script>")
    html_parts.append("</body>")
    html_parts.append("</html>")
    
    return "\n".join(html_parts)


def generate_racing_css(spec):
    """生成赛车游戏风格的CSS"""
    colors = spec.get('design_tokens', {}).get('colors', ['#000000', '#ffffff', '#ef4444', '#f59e0b'])
    
    if len(colors) >= 4:
        primary = colors[2]
        accent = colors[3]
    else:
        primary = '#ef4444'
        accent = '#f59e0b'
    
    css_parts = []
    css_parts.append(":root {")
    css_parts.append("    --color-primary: " + primary + ";")
    css_parts.append("    --color-accent: " + accent + ";")
    css_parts.append("    --color-bg: #0a0a0f;")
    css_parts.append("    --color-bg-secondary: #12121a;")
    css_parts.append("    --color-bg-card: #1a1a24;")
    css_parts.append("    --color-text: #ffffff;")
    css_parts.append("    --color-text-secondary: #888899;")
    css_parts.append("    --color-border: #2a2a3a;")
    css_parts.append("    --font-sans: 'Inter', system-ui, sans-serif;")
    css_parts.append("    --spacing-xs: 8px;")
    css_parts.append("    --spacing-sm: 16px;")
    css_parts.append("    --spacing-md: 24px;")
    css_parts.append("    --spacing-lg: 32px;")
    css_parts.append("    --spacing-xl: 48px;")
    css_parts.append("    --radius-sm: 8px;")
    css_parts.append("    --radius-md: 12px;")
    css_parts.append("    --radius-lg: 16px;")
    css_parts.append("}")
    
    css_parts.append("* {")
    css_parts.append("    margin: 0;")
    css_parts.append("    padding: 0;")
    css_parts.append("    box-sizing: border-box;")
    css_parts.append("}")
    
    css_parts.append("body {")
    css_parts.append("    font-family: var(--font-sans);")
    css_parts.append("    background-color: var(--color-bg);")
    css_parts.append("    color: var(--color-text);")
    css_parts.append("    line-height: 1.6;")
    css_parts.append("    overflow-x: hidden;")
    css_parts.append("}")
    
    css_parts.append(".container {")
    css_parts.append("    max-width: 1400px;")
    css_parts.append("    margin: 0 auto;")
    css_parts.append("    padding: 0 var(--spacing-md);")
    css_parts.append("}")
    
    css_parts.append(".navbar {")
    css_parts.append("    padding: var(--spacing-sm) 0;")
    css_parts.append("    background: rgba(10, 10, 15, 0.95);")
    css_parts.append("    backdrop-filter: blur(20px);")
    css_parts.append("    border-bottom: 1px solid var(--color-border);")
    css_parts.append("    position: sticky;")
    css_parts.append("    top: 0;")
    css_parts.append("    z-index: 1000;")
    css_parts.append("}")
    
    css_parts.append(".navbar .container {")
    css_parts.append("    display: flex;")
    css_parts.append("    justify-content: space-between;")
    css_parts.append("    align-items: center;")
    css_parts.append("}")
    
    css_parts.append(".logo {")
    css_parts.append("    display: flex;")
    css_parts.append("    align-items: center;")
    css_parts.append("    gap: var(--spacing-sm);")
    css_parts.append("}")
    
    css_parts.append(".logo-icon {")
    css_parts.append("    font-size: 1.5rem;")
    css_parts.append("}")
    
    css_parts.append(".logo-text {")
    css_parts.append("    font-size: 1.5rem;")
    css_parts.append("    font-weight: 700;")
    css_parts.append("    background: linear-gradient(135deg, var(--color-primary), var(--color-accent));")
    css_parts.append("    -webkit-background-clip: text;")
    css_parts.append("    -webkit-text-fill-color: transparent;")
    css_parts.append("    background-clip: text;")
    css_parts.append("}")
    
    css_parts.append(".nav-links {")
    css_parts.append("    display: flex;")
    css_parts.append("    gap: var(--spacing-lg);")
    css_parts.append("    list-style: none;")
    css_parts.append("}")
    
    css_parts.append(".nav-links a {")
    css_parts.append("    color: var(--color-text-secondary);")
    css_parts.append("    text-decoration: none;")
    css_parts.append("    font-weight: 500;")
    css_parts.append("    transition: color 0.2s;")
    css_parts.append("}")
    
    css_parts.append(".nav-links a:hover {")
    css_parts.append("    color: var(--color-text);")
    css_parts.append("}")
    
    css_parts.append(".nav-btn {")
    css_parts.append("    padding: var(--spacing-sm) var(--spacing-lg);")
    css_parts.append("    background: linear-gradient(135deg, var(--color-primary), var(--color-accent));")
    css_parts.append("    border: none;")
    css_parts.append("    border-radius: var(--radius-md);")
    css_parts.append("    color: white;")
    css_parts.append("    font-weight: 600;")
    css_parts.append("    cursor: pointer;")
    css_parts.append("    transition: transform 0.2s, box-shadow 0.2s;")
    css_parts.append("}")
    
    css_parts.append(".nav-btn:hover {")
    css_parts.append("    transform: translateY(-2px);")
    css_parts.append("    box-shadow: 0 4px 20px rgba(239, 68, 68, 0.4);")
    css_parts.append("}")
    
    css_parts.append(".hero {")
    css_parts.append("    padding: var(--spacing-xl) 0;")
    css_parts.append("    position: relative;")
    css_parts.append("    overflow: hidden;")
    css_parts.append("}")
    
    css_parts.append(".hero::before {")
    css_parts.append("    content: '';")
    css_parts.append("    position: absolute;")
    css_parts.append("    top: 0;")
    css_parts.append("    left: 50%;")
    css_parts.append("    transform: translateX(-50%);")
    css_parts.append("    width: 800px;")
    css_parts.append("    height: 800px;")
    css_parts.append("    background: radial-gradient(circle, rgba(239, 68, 68, 0.15) 0%, transparent 70%);")
    css_parts.append("    border-radius: 50%;")
    css_parts.append("    z-index: 0;")
    css_parts.append("}")
    
    css_parts.append(".hero .container {")
    css_parts.append("    position: relative;")
    css_parts.append("    z-index: 1;")
    css_parts.append("    display: flex;")
    css_parts.append("    flex-direction: column;")
    css_parts.append("    align-items: center;")
    css_parts.append("    text-align: center;")
    css_parts.append("}")
    
    css_parts.append(".hero-badge {")
    css_parts.append("    display: inline-block;")
    css_parts.append("    padding: var(--spacing-xs) var(--spacing-md);")
    css_parts.append("    background: rgba(239, 68, 68, 0.15);")
    css_parts.append("    border: 1px solid var(--color-primary);")
    css_parts.append("    border-radius: 20px;")
    css_parts.append("    color: var(--color-primary);")
    css_parts.append("    font-size: 0.875rem;")
    css_parts.append("    font-weight: 600;")
    css_parts.append("    margin-bottom: var(--spacing-lg);")
    css_parts.append("}")
    
    css_parts.append(".hero h1 {")
    css_parts.append("    font-size: 4rem;")
    css_parts.append("    font-weight: 700;")
    css_parts.append("    margin-bottom: var(--spacing-md);")
    css_parts.append("    line-height: 1.2;")
    css_parts.append("}")
    
    css_parts.append(".hero p {")
    css_parts.append("    font-size: 1.25rem;")
    css_parts.append("    color: var(--color-text-secondary);")
    css_parts.append("    max-width: 600px;")
    css_parts.append("    margin-bottom: var(--spacing-xl);")
    css_parts.append("}")
    
    css_parts.append(".hero-actions {")
    css_parts.append("    display: flex;")
    css_parts.append("    gap: var(--spacing-md);")
    css_parts.append("    margin-bottom: var(--spacing-xl);")
    css_parts.append("}")
    
    css_parts.append(".btn {")
    css_parts.append("    padding: var(--spacing-md) var(--spacing-xl);")
    css_parts.append("    border-radius: var(--radius-md);")
    css_parts.append("    font-weight: 600;")
    css_parts.append("    text-decoration: none;")
    css_parts.append("    transition: all 0.2s;")
    css_parts.append("    border: none;")
    css_parts.append("    cursor: pointer;")
    css_parts.append("    font-size: 1rem;")
    css_parts.append("}")
    
    css_parts.append(".btn-primary {")
    css_parts.append("    background: linear-gradient(135deg, var(--color-primary), var(--color-accent));")
    css_parts.append("    color: white;")
    css_parts.append("}")
    
    css_parts.append(".btn-primary:hover {")
    css_parts.append("    transform: translateY(-2px);")
    css_parts.append("    box-shadow: 0 4px 20px rgba(239, 68, 68, 0.4);")
    css_parts.append("}")
    
    css_parts.append(".btn-secondary {")
    css_parts.append("    background: transparent;")
    css_parts.append("    color: var(--color-text);")
    css_parts.append("    border: 1px solid var(--color-border);")
    css_parts.append("}")
    
    css_parts.append(".btn-secondary:hover {")
    css_parts.append("    background: var(--color-bg-card);")
    css_parts.append("    border-color: var(--color-primary);")
    css_parts.append("}")
    
    css_parts.append(".btn-outline {")
    css_parts.append("    background: transparent;")
    css_parts.append("    color: var(--color-text);")
    css_parts.append("    border: 1px solid var(--color-primary);")
    css_parts.append("}")
    
    css_parts.append(".btn-outline:hover {")
    css_parts.append("    background: var(--color-primary);")
    css_parts.append("}")
    
    css_parts.append(".hero-stats {")
    css_parts.append("    display: grid;")
    css_parts.append("    grid-template-columns: repeat(3, 1fr);")
    css_parts.append("    gap: var(--spacing-lg);")
    css_parts.append("    width: 100%;")
    css_parts.append("    max-width: 800px;")
    css_parts.append("}")
    
    css_parts.append(".stat-card {")
    css_parts.append("    background: var(--color-bg-card);")
    css_parts.append("    padding: var(--spacing-lg);")
    css_parts.append("    border-radius: var(--radius-lg);")
    css_parts.append("    border: 1px solid var(--color-border);")
    css_parts.append("    text-align: center;")
    css_parts.append("    transition: transform 0.2s, border-color 0.2s;")
    css_parts.append("}")
    
    css_parts.append(".stat-card:hover {")
    css_parts.append("    transform: translateY(-4px);")
    css_parts.append("    border-color: var(--color-primary);")
    css_parts.append("}")
    
    css_parts.append(".stat-value {")
    css_parts.append("    font-size: 2rem;")
    css_parts.append("    font-weight: 700;")
    css_parts.append("    color: var(--color-primary);")
    css_parts.append("    margin-bottom: var(--spacing-xs);")
    css_parts.append("}")
    
    css_parts.append(".stat-label {")
    css_parts.append("    font-size: 0.875rem;")
    css_parts.append("    color: var(--color-text-secondary);")
    css_parts.append("}")
    
    css_parts.append(".section-header {")
    css_parts.append("    text-align: center;")
    css_parts.append("    margin-bottom: var(--spacing-xl);")
    css_parts.append("}")
    
    css_parts.append(".section-header h2 {")
    css_parts.append("    font-size: 2.5rem;")
    css_parts.append("    font-weight: 700;")
    css_parts.append("    margin-bottom: var(--spacing-sm);")
    css_parts.append("}")
    
    css_parts.append(".section-header p {")
    css_parts.append("    font-size: 1.125rem;")
    css_parts.append("    color: var(--color-text-secondary);")
    css_parts.append("}")
    
    css_parts.append(".leaderboard {")
    css_parts.append("    padding: var(--spacing-xl) 0;")
    css_parts.append("    background: var(--color-bg-secondary);")
    css_parts.append("}")
    
    css_parts.append(".leaderboard-table {")
    css_parts.append("    max-width: 900px;")
    css_parts.append("    margin: 0 auto;")
    css_parts.append("    background: var(--color-bg-card);")
    css_parts.append("    border-radius: var(--radius-lg);")
    css_parts.append("    overflow: hidden;")
    css_parts.append("    border: 1px solid var(--color-border);")
    css_parts.append("}")
    
    css_parts.append(".table-header {")
    css_parts.append("    display: grid;")
    css_parts.append("    grid-template-columns: 80px 1fr 1fr 120px 100px;")
    css_parts.append("    padding: var(--spacing-md);")
    css_parts.append("    background: var(--color-bg);")
    css_parts.append("    border-bottom: 1px solid var(--color-border);")
    css_parts.append("    font-weight: 600;")
    css_parts.append("    color: var(--color-text-secondary);")
    css_parts.append("}")
    
    css_parts.append(".table-row {")
    css_parts.append("    display: grid;")
    css_parts.append("    grid-template-columns: 80px 1fr 1fr 120px 100px;")
    css_parts.append("    padding: var(--spacing-md);")
    css_parts.append("    border-bottom: 1px solid var(--color-border);")
    css_parts.append("    align-items: center;")
    css_parts.append("    transition: background 0.2s;")
    css_parts.append("}")
    
    css_parts.append(".table-row:hover {")
    css_parts.append("    background: rgba(239, 68, 68, 0.05);")
    css_parts.append("}")
    
    css_parts.append(".table-row:last-child {")
    css_parts.append("    border-bottom: none;")
    css_parts.append("}")
    
    css_parts.append(".table-row.podium-1 {")
    css_parts.append("    background: linear-gradient(90deg, rgba(251, 191, 36, 0.1) 0%, transparent 100%);")
    css_parts.append("    border-left: 3px solid #fbbf24;")
    css_parts.append("}")
    
    css_parts.append(".table-row.podium-2 {")
    css_parts.append("    background: linear-gradient(90deg, rgba(192, 192, 192, 0.1) 0%, transparent 100%);")
    css_parts.append("    border-left: 3px solid #c0c0c0;")
    css_parts.append("}")
    
    css_parts.append(".table-row.podium-3 {")
    css_parts.append("    background: linear-gradient(90deg, rgba(205, 127, 50, 0.1) 0%, transparent 100%);")
    css_parts.append("    border-left: 3px solid #cd7f32;")
    css_parts.append("}")
    
    css_parts.append(".rank {")
    css_parts.append("    font-size: 1.25rem;")
    css_parts.append("}")
    
    css_parts.append(".driver {")
    css_parts.append("    font-weight: 600;")
    css_parts.append("}")
    
    css_parts.append(".car {")
    css_parts.append("    color: var(--color-text-secondary);")
    css_parts.append("}")
    
    css_parts.append(".time {")
    css_parts.append("    font-family: monospace;")
    css_parts.append("    font-weight: 600;")
    css_parts.append("}")
    
    css_parts.append(".points {")
    css_parts.append("    color: var(--color-primary);")
    css_parts.append("    font-weight: 600;")
    css_parts.append("}")
    
    css_parts.append(".stats {")
    css_parts.append("    padding: var(--spacing-xl) 0;")
    css_parts.append("}")
    
    css_parts.append(".stats-grid {")
    css_parts.append("    display: grid;")
    css_parts.append("    grid-template-columns: repeat(2, 1fr);")
    css_parts.append("    gap: var(--spacing-lg);")
    css_parts.append("    max-width: 800px;")
    css_parts.append("    margin: 0 auto;")
    css_parts.append("}")
    
    css_parts.append(".stat-card-large {")
    css_parts.append("    display: flex;")
    css_parts.append("    align-items: center;")
    css_parts.append("    gap: var(--spacing-md);")
    css_parts.append("    background: var(--color-bg-card);")
    css_parts.append("    padding: var(--spacing-lg);")
    css_parts.append("    border-radius: var(--radius-lg);")
    css_parts.append("    border: 1px solid var(--color-border);")
    css_parts.append("    transition: transform 0.2s, border-color 0.2s;")
    css_parts.append("}")
    
    css_parts.append(".stat-card-large:hover {")
    css_parts.append("    transform: translateY(-4px);")
    css_parts.append("    border-color: var(--color-primary);")
    css_parts.append("}")
    
    css_parts.append(".stat-icon {")
    css_parts.append("    font-size: 2.5rem;")
    css_parts.append("}")
    
    css_parts.append(".stat-value-lg {")
    css_parts.append("    font-size: 2.5rem;")
    css_parts.append("    font-weight: 700;")
    css_parts.append("    color: var(--color-primary);")
    css_parts.append("    margin-bottom: var(--spacing-xs);")
    css_parts.append("}")
    
    css_parts.append(".cta {")
    css_parts.append("    padding: var(--spacing-xl) 0;")
    css_parts.append("    text-align: center;")
    css_parts.append("    background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(245, 158, 11, 0.1) 100%);")
    css_parts.append("    border-top: 1px solid var(--color-border);")
    css_parts.append("    border-bottom: 1px solid var(--color-border);")
    css_parts.append("}")
    
    css_parts.append(".cta h2 {")
    css_parts.append("    font-size: 2.5rem;")
    css_parts.append("    font-weight: 700;")
    css_parts.append("    margin-bottom: var(--spacing-sm);")
    css_parts.append("}")
    
    css_parts.append(".cta p {")
    css_parts.append("    font-size: 1.125rem;")
    css_parts.append("    color: var(--color-text-secondary);")
    css_parts.append("    margin-bottom: var(--spacing-lg);")
    css_parts.append("}")
    
    css_parts.append(".cta-actions {")
    css_parts.append("    display: flex;")
    css_parts.append("    gap: var(--spacing-md);")
    css_parts.append("    justify-content: center;")
    css_parts.append("}")
    
    css_parts.append(".footer {")
    css_parts.append("    padding: var(--spacing-xl) 0;")
    css_parts.append("    background: var(--color-bg-secondary);")
    css_parts.append("}")
    
    css_parts.append(".footer-content {")
    css_parts.append("    display: grid;")
    css_parts.append("    grid-template-columns: repeat(3, 1fr);")
    css_parts.append("    gap: var(--spacing-xl);")
    css_parts.append("    margin-bottom: var(--spacing-xl);")
    css_parts.append("}")
    
    css_parts.append(".footer-brand {")
    css_parts.append("    display: flex;")
    css_parts.append("    flex-direction: column;")
    css_parts.append("    gap: var(--spacing-sm);")
    css_parts.append("}")
    
    css_parts.append(".footer-brand p {")
    css_parts.append("    color: var(--color-text-secondary);")
    css_parts.append("}")
    
    css_parts.append(".footer-links h4 {")
    css_parts.append("    margin-bottom: var(--spacing-md);")
    css_parts.append("    font-weight: 600;")
    css_parts.append("}")
    
    css_parts.append(".footer-links ul {")
    css_parts.append("    list-style: none;")
    css_parts.append("    display: flex;")
    css_parts.append("    flex-direction: column;")
    css_parts.append("    gap: var(--spacing-sm);")
    css_parts.append("}")
    
    css_parts.append(".footer-links a {")
    css_parts.append("    color: var(--color-text-secondary);")
    css_parts.append("    text-decoration: none;")
    css_parts.append("    transition: color 0.2s;")
    css_parts.append("}")
    
    css_parts.append(".footer-links a:hover {")
    css_parts.append("    color: var(--color-primary);")
    css_parts.append("}")
    
    css_parts.append(".footer-bottom {")
    css_parts.append("    padding-top: var(--spacing-lg);")
    css_parts.append("    border-top: 1px solid var(--color-border);")
    css_parts.append("    text-align: center;")
    css_parts.append("    color: var(--color-text-secondary);")
    css_parts.append("}")
    
    css_parts.append("@media (max-width: 768px) {")
    css_parts.append("    .hero h1 {")
    css_parts.append("        font-size: 2.5rem;")
    css_parts.append("    }")
    css_parts.append("    .hero-stats {")
    css_parts.append("        grid-template-columns: 1fr;")
    css_parts.append("    }")
    css_parts.append("    .hero-actions {")
    css_parts.append("        flex-direction: column;")
    css_parts.append("    }")
    css_parts.append("    .table-header, .table-row {")
    css_parts.append("        grid-template-columns: 60px 1fr;")
    css_parts.append("    }")
    css_parts.append("    .table-header span:not(:nth-child(1)):not(:nth-child(2)),")
    css_parts.append("    .table-row span:not(:nth-child(1)):not(:nth-child(2)) {")
    css_parts.append("        display: none;")
    css_parts.append("    }")
    css_parts.append("    .stats-grid {")
    css_parts.append("        grid-template-columns: 1fr;")
    css_parts.append("    }")
    css_parts.append("    .footer-content {")
    css_parts.append("        grid-template-columns: 1fr;")
    css_parts.append("        text-align: center;")
    css_parts.append("    }")
    css_parts.append("    .nav-links {")
    css_parts.append("        display: none;")
    css_parts.append("    }")
    css_parts.append("}")
    
    return "\n".join(css_parts)


def generate_racing_js(spec):
    """生成赛车游戏风格的JavaScript"""
    js_parts = []
    js_parts.append("document.addEventListener('DOMContentLoaded', function() {")
    js_parts.append("    console.log('APEX Racing Replica Loaded');")
    js_parts.append("")
    js_parts.append("    const navLinks = document.querySelectorAll('.nav-links a');")
    js_parts.append("    navLinks.forEach(link => {")
    js_parts.append("        link.addEventListener('click', function(e) {")
    js_parts.append("            const href = this.getAttribute('href');")
    js_parts.append("            if (href.startsWith('#')) {")
    js_parts.append("                e.preventDefault();")
    js_parts.append("                const target = document.querySelector(href);")
    js_parts.append("                if (target) {")
    js_parts.append("                    target.scrollIntoView({ behavior: 'smooth' });")
    js_parts.append("                }")
    js_parts.append("            }")
    js_parts.append("        });")
    js_parts.append("    });")
    js_parts.append("")
    js_parts.append("    const navbar = document.querySelector('.navbar');")
    js_parts.append("    window.addEventListener('scroll', function() {")
    js_parts.append("        if (window.scrollY > 50) {")
    js_parts.append("            navbar.style.background = 'rgba(10, 10, 15, 0.98)';")
    js_parts.append("            navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.3)';")
    js_parts.append("        } else {")
    js_parts.append("            navbar.style.background = 'rgba(10, 10, 15, 0.95)';")
    js_parts.append("            navbar.style.boxShadow = 'none';")
    js_parts.append("        }")
    js_parts.append("    });")
    js_parts.append("")
    js_parts.append("    const statCards = document.querySelectorAll('.stat-card');")
    js_parts.append("    statCards.forEach((card, index) => {")
    js_parts.append("        card.style.opacity = '0';")
    js_parts.append("        card.style.transform = 'translateY(20px)';")
    js_parts.append("        setTimeout(() => {")
    js_parts.append("            card.style.transition = 'all 0.5s ease';")
    js_parts.append("            card.style.opacity = '1';")
    js_parts.append("            card.style.transform = 'translateY(0)';")
    js_parts.append("        }, index * 100);")
    js_parts.append("    });")
    js_parts.append("")
    js_parts.append("    const tableRows = document.querySelectorAll('.table-row');")
    js_parts.append("    tableRows.forEach((row, index) => {")
    js_parts.append("        row.style.opacity = '0';")
    js_parts.append("        row.style.transform = 'translateX(-20px)';")
    js_parts.append("        setTimeout(() => {")
    js_parts.append("            row.style.transition = 'all 0.4s ease';")
    js_parts.append("            row.style.opacity = '1';")
    js_parts.append("            row.style.transform = 'translateX(0)';")
    js_parts.append("        }, index * 80);")
    js_parts.append("    });")
    js_parts.append("")
    js_parts.append("    const buttons = document.querySelectorAll('.btn');")
    js_parts.append("    buttons.forEach(btn => {")
    js_parts.append("        btn.addEventListener('click', function() {")
    js_parts.append("            this.style.transform = 'scale(0.95)';")
    js_parts.append("            setTimeout(() => {")
    js_parts.append("                this.style.transform = 'scale(1)';")
    js_parts.append("            }, 150);")
    js_parts.append("        });")
    js_parts.append("    });")
    js_parts.append("");
    js_parts.append("    function animateNumbers() {")
    js_parts.append("        const values = document.querySelectorAll('.stat-value, .stat-value-lg');")
    js_parts.append("        values.forEach(el => {")
    js_parts.append("            const text = el.textContent;")
    js_parts.append("            const match = text.match(/([0-9,]+)/);")
    js_parts.append("            if (match) {")
    js_parts.append("                const num = parseInt(match[1].replace(',', ''));")
    js_parts.append("                const duration = 2000;")
    js_parts.append("                const steps = 60;")
    js_parts.append("                const increment = num / steps;")
    js_parts.append("                let current = 0;")
    js_parts.append("                const timer = setInterval(() => {")
    js_parts.append("                    current += increment;")
    js_parts.append("                    if (current >= num) {")
    js_parts.append("                        current = num;")
    js_parts.append("                        clearInterval(timer);")
    js_parts.append("                    }")
    js_parts.append("                    el.textContent = text.replace(/[0-9,]+/, Math.floor(current).toLocaleString());")
    js_parts.append("                }, duration / steps);")
    js_parts.append("            }")
    js_parts.append("        });")
    js_parts.append("    }")
    js_parts.append("")
    js_parts.append("    const observer = new IntersectionObserver((entries) => {")
    js_parts.append("        entries.forEach(entry => {")
    js_parts.append("            if (entry.isIntersecting) {")
    js_parts.append("                animateNumbers();")
    js_parts.append("                observer.disconnect();")
    js_parts.append("            }")
    js_parts.append("        });")
    js_parts.append("    }, { threshold: 0.3 });")
    js_parts.append("")
    js_parts.append("    const heroSection = document.querySelector('.hero');")
    js_parts.append("    if (heroSection) {")
    js_parts.append("        observer.observe(heroSection);")
    js_parts.append("    }")
    js_parts.append("});")
    
    return "\n".join(js_parts)


async def main():
    url = "https://apex-racing-v1.vercel.app/"
    
    print("=" * 80)
    print("🚀 LAAP Harness — APEX Racing 网站复刻")
    print("=" * 80)
    print(f"目标网站: {url}")
    print("=" * 80)
    
    try:
        await analyze_with_playwright(url)
        output_files = await enhanced_replicate(url)
        
        print("\n" + "=" * 80)
        print("🎉 复刻完成!")
        print("=" * 80)
        print(f"\n输出目录: replicas/apex-racing-enhanced")
        print("\n文件清单:")
        for f in output_files:
            print(f"  ✅ {os.path.basename(f)}")
        print("\n使用浏览器打开 replicas/apex-racing-enhanced/index.html 查看效果")
        
    except Exception as e:
        print(f"\n❌ 复刻失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())