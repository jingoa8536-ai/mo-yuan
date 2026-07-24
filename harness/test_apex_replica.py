import asyncio
import json
import os
from pathlib import Path

from laap_coding.core.web_crawler import WebCrawler
from laap_coding.core.web_replicator import WebReplicator
from laap_coding.core.matching_engine import MatchingEngine


async def analyze_website(url: str):
    """分析网站结构"""
    print("=" * 80)
    print("🔍 第一步: 网站分析")
    print("=" * 80)
    
    crawler = WebCrawler(max_pages=5, timeout=30, delay=1.0)
    result = await crawler.crawl_and_analyze(url, use_playwright=False)
    
    print(f"\n📋 网站基本信息:")
    print(f"  URL: {result.website.url}")
    print(f"  域名: {result.website.domain}")
    print(f"  标题: {result.website.title}")
    print(f"  描述: {result.website.description}")
    
    print(f"\n🔧 技术栈检测:")
    tech_stack = result.website.tech_stack
    if tech_stack:
        for tech in tech_stack:
            print(f"  ✅ {tech}")
    else:
        print(f"  ⚠️  未检测到明确技术栈")
    
    print(f"\n📊 内容结构:")
    print(f"  爬取页面数: {result.pages_crawled}")
    print(f"  内部链接: {result.website.internal_links}")
    print(f"  外部链接: {result.website.external_links}")
    
    print(f"\n🗺️ 页面列表:")
    for page in result.pages:
        print(f"  - {page.title} ({page.url})")
    
    print(f"\n🎨 设计令牌:")
    tokens = crawler.extract_tokens(result)
    print(f"  颜色: {tokens['colors']}")
    print(f"  字体: {tokens['typography']}")
    
    return result, tokens, tech_stack


async def match_components(tokens, tech_stack):
    """匹配最佳组件库"""
    print("\n" + "=" * 80)
    print("🎯 第二步: 组件匹配")
    print("=" * 80)
    
    engine = MatchingEngine(use_enhancements=True)
    
    tags = []
    for tech in tech_stack:
        tags.extend([t.lower() for t in tech.split()])
    tags.extend(["racing", "game", "sports", "ui", "components", "website"])
    
    intent = {
        "tags": tags,
        "style": "modern-minimal",
        "tech": ", ".join(tech_stack) if tech_stack else "React",
    }
    
    print(f"\n匹配意图:")
    print(f"  标签: {intent['tags']}")
    print(f"  风格: {intent['style']}")
    print(f"  技术: {intent['tech']}")
    
    matches = engine.match_intent(intent)
    
    print(f"\n最佳匹配结果:")
    for i, match in enumerate(matches[:5], 1):
        scores = match["scores"]
        print(f"\n  {i}. {match['name']} ({match['type']})")
        print(f"     综合评分: {scores['total_score']:.4f} [{match['match_level']}]")
        print(f"     - 标签相似度: {scores['tag_similarity']:.4f}")
        print(f"     - 风格兼容性: {scores['style_compatibility']:.4f}")
        print(f"     - 依赖匹配度: {scores['dependency_match']:.4f}")
        print(f"     - 质量评分: {scores['quality_score']:.4f}")
    
    return matches


async def replicate_website(url: str):
    """执行零Token网站复刻"""
    print("\n" + "=" * 80)
    print("⚡ 第三步: 零Token复刻")
    print("=" * 80)
    
    replicator = WebReplicator(output_dir="replicas")
    result = await replicator.replicate(url)
    
    if result["success"]:
        print(f"\n🎉 复刻成功!")
        print(f"\n📋 执行步骤:")
        for step in result["steps"]:
            status_icon = "✅" if step["status"] == "completed" else "❌"
            print(f"  {status_icon} {step['name']}: {step['status']}")
            if "pages_crawled" in step:
                print(f"     - 爬取页面: {step['pages_crawled']}")
            if "tech_stack" in step:
                print(f"     - 技术栈: {', '.join(step['tech_stack'])}")
            if "best_match" in step and step["best_match"]:
                print(f"     - 最佳匹配: {step['best_match']}")
            if "files_generated" in step:
                print(f"     - 生成文件: {step['files_generated']}")
        
        print(f"\n💾 输出文件 ({len(result['output_files'])} 个):")
        for file_path in result["output_files"]:
            print(f"  - {file_path}")
            
            if file_path.endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    spec = json.load(f)
                print(f"    ├─ URL: {spec.get('url', '')}")
                print(f"    ├─ 标题: {spec.get('title', '')}")
                print(f"    ├─ 技术栈: {spec.get('tech_stack', [])}")
                print(f"    ├─ 页面数: {len(spec.get('pages', []))}")
        
        print(f"\n💰 Token节省: ~{result['token_savings']:,} tokens")
        print(f"   (传统方式需要 ~{result['estimated_tokens_traditional']:,} tokens)")
        print(f"   (Harness方式仅需 ~67 tokens)")
        
        return result
    else:
        print(f"\n❌ 复刻失败: {result.get('error', '未知错误')}")
        return None


def show_replica_files(output_files):
    """展示复刻生成的文件内容"""
    print("\n" + "=" * 80)
    print("📄 第四步: 查看复刻文件")
    print("=" * 80)
    
    for file_path in output_files:
        if file_path.endswith((".html", ".css", ".js")):
            print(f"\n{'─' * 60}")
            print(f"文件: {os.path.basename(file_path)}")
            print(f"路径: {file_path}")
            print(f"{'─' * 60}")
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                lines = content.split('\n')
                print(f"行数: {len(lines)}")
                print(f"大小: {len(content)} 字节")
                
                if len(lines) <= 50:
                    print("\n内容:")
                    print(content)
                else:
                    print("\n前30行:")
                    print("\n".join(lines[:30]))
                    print("\n...")
                    print("后10行:")
                    print("\n".join(lines[-10:]))
            except Exception as e:
                print(f"读取失败: {e}")


async def main():
    url = "https://apex-racing-v1.vercel.app/"
    
    print("=" * 80)
    print("🚀 LAAP Harness — 网站复刻测试")
    print("=" * 80)
    print(f"目标网站: {url}")
    print("=" * 80)
    
    try:
        crawl_result, tokens, tech_stack = await analyze_website(url)
        matches = await match_components(tokens, tech_stack)
        replica_result = await replicate_website(url)
        
        if replica_result and replica_result["output_files"]:
            show_replica_files(replica_result["output_files"])
        
        print("\n" + "=" * 80)
        print("🎉 测试完成!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())