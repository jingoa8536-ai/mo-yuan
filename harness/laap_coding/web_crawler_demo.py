"""
Web Crawler Demo — 爬虫集成演示

演示harness如何整合顶级爬虫框架，实现网站工程化拆解：
1. 输入URL爬取网站
2. 分析网站结构和技术栈
3. 生成工程化拆解报告
4. 提取设计令牌
"""

import sys
import asyncio
from pathlib import Path

HARNESS_ROOT = Path(__file__).parent
sys.path.insert(0, str(HARNESS_ROOT))

from core.web_crawler import WebCrawler


def run_crawler_demo(url: str):
    """运行爬虫演示"""
    print("=" * 70)
    print("Harness 网站工程化拆解演示")
    print("=" * 70)
    print(f"\n目标网站: {url}")

    crawler = WebCrawler(max_pages=5)

    print("\n" + "=" * 70)
    print("阶段1: 爬取网站")
    print("=" * 70)

    result = asyncio.run(crawler.crawl_and_analyze(url))

    print(f"\n爬取状态: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"爬取页面数: {result.pages_crawled}")
    print(f"爬取耗时: {result.crawl_time:.2f}秒")

    if result.errors:
        print(f"\n警告信息:")
        for error in result.errors:
            print(f"  ⚠️ {error}")

    print("\n" + "=" * 70)
    print("阶段2: 网站结构分析")
    print("=" * 70)

    website = result.website

    print(f"\n📋 基本信息")
    print(f"  域名: {website.domain}")
    print(f"  标题: {website.title}")
    print(f"  描述: {website.description}")

    print(f"\n🔧 技术栈")
    if website.tech_stack:
        for tech in website.tech_stack:
            print(f"  ✅ {tech}")
    else:
        print(f"  ⚠️ 未检测到明确技术栈")

    print(f"\n📊 内容统计")
    print(f"  内部链接: {website.internal_links}")
    print(f"  外部链接: {website.external_links}")

    print(f"\n📁 页面类型分布")
    for content_type, count in website.content_types.items():
        percentage = (count / result.pages_crawled * 100) if result.pages_crawled > 0 else 0
        print(f"  {content_type}: {count}页 ({percentage:.1f}%)")

    print("\n" + "=" * 70)
    print("阶段3: 网站地图")
    print("=" * 70)

    for path, info in website.sitemap.items():
        print(f"\n  {path}")
        print(f"    标题: {info['title']}")
        print(f"    字数: {info['word_count']}")

    print("\n" + "=" * 70)
    print("阶段4: 页面详情")
    print("=" * 70)

    for page in result.pages:
        print(f"\n  URL: {page.url}")
        print(f"    标题: {page.title}")
        print(f"    字数: {page.word_count}")
        print(f"    图片数: {len(page.images)}")
        print(f"    链接数: {len(page.links)}")
        if page.headings:
            print(f"    标题层级: {', '.join(page.headings[:3])}")

    print("\n" + "=" * 70)
    print("阶段5: 设计令牌提取")
    print("=" * 70)

    tokens = crawler.extract_tokens(result)
    print(f"\n🎨 颜色: {tokens['colors']}")
    print(f"📝 字体: {tokens['typography']}")

    print("\n" + "=" * 70)
    print("阶段6: 完整工程化报告")
    print("=" * 70)

    report = crawler.get_report(result)
    print("\n" + report)

    print("\n" + "=" * 70)
    print("🎉 网站工程化拆解完成!")
    print("=" * 70)

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python web_crawler_demo.py <url>")
        print("示例: python web_crawler_demo.py https://example.com")
        sys.exit(1)

    url = sys.argv[1]
    run_crawler_demo(url)
