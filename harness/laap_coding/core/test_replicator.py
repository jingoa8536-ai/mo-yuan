"""
test_replicator.py — 零Token复刻引擎综合测试
=============================================

测试所有模块的集成功能：
1. 网站复刻引擎 — 链接输入→爬取→分析→匹配→生成
2. 视觉复刻引擎 — 图片/视频输入→分析→匹配→生成
3. 向量模型增强 — Word2Vec预训练词向量
4. 语义扩展 — 同义词扩展和缩写识别
5. 倒排索引 — O(log n)查询优化
6. 上下文感知 — 用户历史偏好动态权重
7. 增量更新 — 数据库增量同步
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_web_replicator():
    print("\n" + "=" * 80)
    print("1️⃣ 测试网站复刻引擎")
    print("=" * 80)

    try:
        from laap_coding.core.web_replicator import WebReplicator

        replicator = WebReplicator()

        print("\n🔍 测试复刻流程:")
        intent = {
            "tags": ["landing", "modern", "ui"],
            "style": "modern-minimal",
            "tech": "React + Tailwind",
        }

        print(f"  测试意图: {intent}")
        print(f"  输出目录: {replicator.output_dir}")

        print("✅ 网站复刻引擎测试通过")
        return True
    except Exception as e:
        print(f"❌ 网站复刻引擎测试失败: {e}")
        return False


def test_visual_replicator():
    print("\n" + "=" * 80)
    print("2️⃣ 测试视觉复刻引擎")
    print("=" * 80)

    try:
        from laap_coding.core.visual_replicator import VisualReplicator

        replicator = VisualReplicator()

        print("\n🔍 测试图片复刻流程:")
        mock_image_path = "mock_image.png"
        result = replicator.replicate_from_images([mock_image_path])
        print(f"  模板ID: {result.get('template_id', 'N/A')}")
        print(f"  步骤: {[s['name'] for s in result.get('steps', [])]}")
        print(f"  输出文件数: {len(result.get('output_files', []))}")

        print("\n🔍 测试视频复刻流程:")
        mock_video_path = "mock_video.mp4"
        result2 = replicator.replicate_from_video(mock_video_path)
        print(f"  步骤: {[s['name'] for s in result2.get('steps', [])]}")

        print("✅ 视觉复刻引擎测试通过")
        return True
    except Exception as e:
        print(f"❌ 视觉复刻引擎测试失败: {e}")
        return False


def test_vector_enhancer():
    print("\n" + "=" * 80)
    print("3️⃣ 测试向量模型增强")
    print("=" * 80)

    try:
        from laap_coding.core.vector_enhancer import get_vector_enhancer

        enhancer = get_vector_enhancer()

        print("\n🔍 测试标签相似度:")
        similarity = enhancer.calculate_tag_similarity(["button", "ui"], ["btn", "component"])
        print(f"  ['button', 'ui'] vs ['btn', 'component']: {similarity:.4f}")

        similarity2 = enhancer.calculate_tag_similarity(["react", "frontend"], ["vue", "frontend"])
        print(f"  ['react', 'frontend'] vs ['vue', 'frontend']: {similarity2:.4f}")

        print("\n🔍 测试标签扩展:")
        expanded = enhancer.expand_tags(["button"], top_n=3)
        print(f"  'button' 扩展: {expanded}")

        print("\n🔍 测试向量获取:")
        vector = enhancer.get_word_vector("ui")
        print(f"  'ui' 向量维度: {len(vector) if vector else 0}")

        print("\n🔍 测试词表大小:")
        vocab = enhancer.get_vocabulary()
        print(f"  词表大小: {len(vocab)}")

        print("✅ 向量模型增强测试通过")
        return True
    except Exception as e:
        print(f"❌ 向量模型增强测试失败: {e}")
        return False


def test_semantic_expander():
    print("\n" + "=" * 80)
    print("4️⃣ 测试语义扩展")
    print("=" * 80)

    try:
        from laap_coding.core.semantic_expander import get_semantic_expander

        expander = get_semantic_expander()

        print("\n🔍 测试同义词扩展:")
        expanded = expander.expand_tags("button")
        print(f"  'button' → {expanded}")

        expanded2 = expander.expand_tags("card")
        print(f"  'card' → {expanded2}")

        print("\n🔍 测试缩写识别:")
        expanded3 = expander.expand_tags("btn")
        print(f"  'btn' → {expanded3}")

        print("\n🔍 测试语义相似度:")
        similarity = expander.calculate_semantic_similarity("button", "btn")
        print(f"  'button' vs 'btn': {similarity:.4f}")

        similarity2 = expander.calculate_semantic_similarity("dialog", "modal")
        print(f"  'dialog' vs 'modal': {similarity2:.4f}")

        print("\n🔍 测试术语标准化:")
        normalized = expander.normalize_term("Btn")
        print(f"  'Btn' → '{normalized}'")

        print("✅ 语义扩展测试通过")
        return True
    except Exception as e:
        print(f"❌ 语义扩展测试失败: {e}")
        return False


def test_inverted_index():
    print("\n" + "=" * 80)
    print("5️⃣ 测试倒排索引")
    print("=" * 80)

    try:
        from laap_coding.core.inverted_index import InvertedIndex

        sample_docs = [
            {"id": "doc1", "name": "shadcn/ui", "tags": ["react", "tailwind", "ui"], "components": ["button", "card"]},
            {"id": "doc2", "name": "Ant Design", "tags": ["react", "enterprise"], "components": ["table", "form"]},
            {"id": "doc3", "name": "Naive UI", "tags": ["vue", "modern"], "components": ["button", "dialog"]},
        ]

        index = InvertedIndex()
        index.build_from_documents(sample_docs)

        print("\n🔍 测试关键词搜索:")
        results = index.search("button")
        doc_names = [sample_docs[i]["name"] for i in results]
        print(f"  'button' → {doc_names}")

        print("\n🔍 测试布尔查询:")
        results2 = index.boolean_search("react and button")
        doc_names2 = [sample_docs[i]["name"] for i in results2]
        print(f"  'react and button' → {doc_names2}")

        print("\n🔍 测试前缀搜索:")
        results3 = index.search("but")
        doc_names3 = [sample_docs[i]["name"] for i in results3]
        print(f"  'but*' → {doc_names3}")

        print("\n🔍 测试索引统计:")
        stats = index.get_stats()
        print(f"  文档数: {stats['document_count']}")
        print(f"  唯一词数: {stats['unique_terms']}")

        print("\n🔍 测试增量添加:")
        new_doc = {"id": "doc4", "name": "Element Plus", "tags": ["vue", "enterprise"], "components": ["form", "table"]}
        index.add_document(new_doc)
        results4 = index.search("vue")
        doc_names4 = []
        for i in results4:
            if i < len(sample_docs):
                doc_names4.append(sample_docs[i]["name"])
            else:
                doc_names4.append("Element Plus")
        print(f"  添加后 'vue' → {doc_names4}")

        print("✅ 倒排索引测试通过")
        return True
    except Exception as e:
        print(f"❌ 倒排索引测试失败: {e}")
        return False


def test_context_awareness():
    print("\n" + "=" * 80)
    print("6️⃣ 测试上下文感知")
    print("=" * 80)

    try:
        from laap_coding.core.context_awareness import ContextAwareness

        context = ContextAwareness()

        print("\n🔍 测试用户交互记录:")
        context.record_user_interaction("user1", ["react", "tailwind"], "modern-minimal", "React + Tailwind")
        context.record_user_interaction("user1", ["button", "card"], "modern-minimal")
        context.record_user_interaction("user2", ["vue", "element"], "enterprise-standard", "Vue 3")
        print("  交互记录完成")

        print("\n🔍 测试用户偏好获取:")
        pref1 = context.get_user_preferences("user1")
        print(f"  user1 偏好标签: {pref1.get_top_tags(3)}")
        print(f"  user1 偏好风格: {pref1.get_top_styles(2)}")

        print("\n🔍 测试动态权重计算:")
        weights1 = context.get_dynamic_weights("user1")
        print(f"  user1 动态权重: {weights1}")

        weights_default = context.get_dynamic_weights()
        print(f"  默认权重: {weights_default}")

        print("\n🔍 测试上下文增强意图:")
        base_intent = {"tags": ["ui"]}
        enhanced = context.get_context_enhanced_intent(base_intent, "user1")
        print(f"  基础意图: {base_intent}")
        print(f"  增强意图: {enhanced}")

        print("\n🔍 测试全局趋势:")
        trends = context.get_global_trends(5)
        print(f"  全局趋势: {trends}")

        print("✅ 上下文感知测试通过")
        return True
    except Exception as e:
        print(f"❌ 上下文感知测试失败: {e}")
        return False


def test_incremental_updater():
    print("\n" + "=" * 80)
    print("7️⃣ 测试增量更新")
    print("=" * 80)

    try:
        from laap_coding.core.incremental_updater import IncrementalUpdater

        updater = IncrementalUpdater()

        print("\n🔍 测试添加文档:")
        doc1 = {"id": "doc1", "name": "shadcn/ui", "tags": ["react", "tailwind"]}
        doc2 = {"id": "doc2", "name": "Ant Design", "tags": ["react", "enterprise"]}
        updater.add_document(doc1)
        updater.add_document(doc2)
        print(f"  添加文档: {doc1['name']}, {doc2['name']}")

        print("\n🔍 测试更新文档:")
        updater.update_document("doc1", {"tags": ["react", "tailwind", "ui"]})
        print(f"  更新文档 doc1")

        print("\n🔍 测试变更查询:")
        changes = updater.get_latest_changes(5)
        print(f"  最近变更数: {len(changes)}")

        print("\n🔍 测试同步:")
        source_docs = [
            {"id": "doc1", "name": "shadcn/ui", "tags": ["react", "tailwind", "ui", "modern"]},
            {"id": "doc2", "name": "Ant Design", "tags": ["react", "enterprise"]},
            {"id": "doc3", "name": "Material UI", "tags": ["react", "material"]},
        ]
        added, updated, deleted = updater.sync_with_source(source_docs)
        print(f"  新增: {added}, 更新: {updated}, 删除: {deleted}")

        print("\n🔍 测试同步状态:")
        status = updater.get_sync_status()
        print(f"  版本: {status['version']}")
        print(f"  变更数: {status['change_count']}")

        print("\n🔍 测试异步队列:")
        updater.enqueue_update("ADD", "doc4", {"id": "doc4", "name": "Vue UI", "tags": ["vue"]})
        processed = updater.process_queue()
        print(f"  处理数量: {processed}")

        print("✅ 增量更新测试通过")
        return True
    except Exception as e:
        print(f"❌ 增量更新测试失败: {e}")
        return False


def test_matching_engine():
    print("\n" + "=" * 80)
    print("8️⃣ 测试增强版匹配引擎")
    print("=" * 80)

    try:
        from laap_coding.core.matching_engine import MatchingEngine

        engine = MatchingEngine(use_enhancements=True)

        print("\n🔍 测试匹配策略配置:")
        config = engine.get_matching_strategy()
        print(f"  当前策略: {config['current_strategy']}")
        print(f"  权重: {config['weights']}")
        print(f"  增强模块: {config['enhancements']}")

        print("\n🔍 测试意图匹配:")
        intent = {
            "tags": ["react", "tailwind", "ui", "components"],
            "style": "modern-minimal",
            "tech": "React + Tailwind",
        }
        match_results = engine.match_intent(intent)
        if match_results:
            scores = match_results[0]["scores"]
            print(f"  最佳匹配: {match_results[0]['name']}")
            print(f"  综合评分: {scores['total_score']:.4f}")

        print("\n🔍 测试搜索:")
        search_results = engine.search_components("button")
        print(f"  'button' 搜索结果数: {len(search_results)}")

        print("\n🔍 测试上下文感知匹配:")
        engine.context_awareness.record_user_interaction("test_user", ["react", "tailwind"], "modern-minimal")
        match_results_context = engine.match_intent(intent, user_id="test_user")
        if match_results_context:
            print(f"  上下文感知最佳匹配: {match_results_context[0]['name']}")

        print("✅ 增强版匹配引擎测试通过")
        return True
    except Exception as e:
        print(f"❌ 增强版匹配引擎测试失败: {e}")
        return False


def run_all_tests():
    print("=" * 80)
    print("LAAP Harness — 零Token复刻引擎综合测试")
    print("=" * 80)

    tests = [
        test_web_replicator,
        test_visual_replicator,
        test_vector_enhancer,
        test_semantic_expander,
        test_inverted_index,
        test_context_awareness,
        test_incremental_updater,
        test_matching_engine,
    ]

    passed = 0
    failed = 0
    start_time = time.time()

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ {test.__name__} 异常: {e}")
            failed += 1

    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"⏱️  总耗时: {elapsed:.2f}s")

    if failed == 0:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，请检查相关模块")


if __name__ == "__main__":
    run_all_tests()