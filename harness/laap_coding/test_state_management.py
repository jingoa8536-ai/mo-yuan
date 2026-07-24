"""
LAAP Harness 跨会话状态管理体系验证测试
"""

import os
import tempfile
from core.harness import MemoryLayer, TaskStatePersistence, ContextCompressor

print('=' * 60)
print('LAAP Harness 跨会话状态管理验证')
print('=' * 60)

# 1. 三层记忆持久化验证
print('\n[1/4] 三层记忆持久化验证')
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = MemoryLayer(project_root=tmpdir)
        
        memory.add_working_memory('current_task', '创建博客系统')
        memory.add_short_term_memory('project_rules', '遵循PEP8规范')
        memory.add_long_term_memory('error_pattern', '避免循环依赖')
        
        status1 = memory.get_memory_status()
        print('  OK 写入记忆 - 工作记忆:', status1['working_memory']['size'], '项')
        print('  OK 写入记忆 - 短期记忆:', status1['short_term_memory']['size'], '项')
        print('  OK 写入记忆 - 长期记忆:', status1['long_term_memory']['size'], '项')
        
        memory2 = MemoryLayer(project_root=tmpdir)
        status2 = memory2.get_memory_status()
        print('  OK 重新加载后 - 工作记忆:', status2['working_memory']['size'], '项')
        print('  OK 重新加载后 - 短期记忆:', status2['short_term_memory']['size'], '项')
        print('  OK 重新加载后 - 长期记忆:', status2['long_term_memory']['size'], '项')
        
        short_term_val = memory2.get_short_term_memory('project_rules')
        long_term_val = memory2.get_long_term_memory('error_pattern')
        print('  OK 短期记忆内容:', short_term_val)
        print('  OK 长期记忆内容:', long_term_val)
        
except Exception as e:
    print('  FAIL 三层记忆持久化验证失败:', e)

# 2. 任务状态保存和恢复验证
print('\n[2/4] 任务状态保存和恢复验证')
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        persistence = TaskStatePersistence(tmpdir)
        
        task_state = {
            'task_id': 'test_task_001',
            'description': '测试任务',
            'subtasks': ['subtask_1', 'subtask_2', 'subtask_3'],
            'current_subtask_index': 1,
            'status': 'in_progress',
            'metadata': {'user': 'test_user', 'priority': 'high'},
        }
        
        saved_path = persistence.save_task_state('test_task_001', task_state)
        print('  OK 任务状态保存路径:', saved_path)
        
        restored_state = persistence.restore_task_state('test_task_001')
        print('  OK 任务状态恢复成功:', restored_state is not None)
        print('  OK 恢复的任务ID:', restored_state.get('task_id'))
        print('  OK 恢复的状态:', restored_state.get('status'))
        print('  OK 恢复的当前子任务索引:', restored_state.get('current_subtask_index'))
        
        tasks_with_state = persistence.list_tasks_with_state()
        print('  OK 列出有状态任务数量:', len(tasks_with_state))
        
except Exception as e:
    print('  FAIL 任务状态保存和恢复验证失败:', e)

# 3. 上下文压缩验证
print('\n[3/4] 上下文压缩验证')
try:
    compressor = ContextCompressor()
    
    long_context = """这是一段非常长的上下文内容，包含多个任务描述。任务1：创建一个基于Python的Web应用，使用FastAPI框架。任务2：实现用户认证功能，包含JWT令牌验证。任务3：设计数据库模型，使用SQLAlchemy ORM。任务4：创建RESTful API接口，支持CRUD操作。任务5：实现日志系统，记录所有操作。任务6：添加单元测试，确保代码质量。任务7：优化性能，使用缓存机制。任务8：部署应用到生产环境。任务9：配置CI/CD流水线，实现自动化部署。任务10：创建监控系统，实时监控应用状态。任务11：实现国际化支持，支持多语言。任务12：添加权限管理，实现角色控制。任务13：优化数据库查询，提高响应速度。任务14：实现消息队列，异步处理任务。任务15：创建API文档，使用OpenAPI规范。任务16：添加WebSocket支持，实现实时通信。任务17：实现文件上传功能，支持大文件。任务18：创建定时任务，自动清理数据。任务19：添加健康检查端点，监控应用状态。任务20：实现限流功能，防止API滥用。"""
    
    compressed = compressor.compress(long_context, max_tokens=100)
    ratio = compressor.calculate_ratio(long_context, compressed)
    
    print('  OK 原始长度:', len(long_context), '字符')
    print('  OK 压缩后长度:', len(compressed), '字符')
    print('  OK 压缩比率:', f'{ratio:.2%}')
    print('  OK 压缩比率达标:', ratio >= 0.5)
    
    compressed_with_summary = compressor.compress_with_summary(long_context, max_tokens=100)
    print('  OK 带摘要压缩结果:', compressed_with_summary.keys())
    print('  OK 摘要:', compressed_with_summary.get('summary', '')[:50], '...')
    
except Exception as e:
    print('  FAIL 上下文压缩验证失败:', e)

# 4. 特征列表存储验证
print('\n[4/4] 特征列表存储验证')
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        persistence = TaskStatePersistence(tmpdir)
        
        features = {
            'task_id': 'feat_task_001',
            'description': '特征列表测试',
            'keywords': ['python', 'fastapi', 'web'],
            'architecture_patterns': ['Dependency Injection', 'Repository'],
            'completed_subtasks': ['subtask_1'],
            'context_summary': '创建Web应用',
        }
        
        persistence.save_feature_list('feat_task_001', features)
        
        loaded_features = persistence.get_feature_list('feat_task_001')
        print('  OK 特征列表加载成功:', loaded_features is not None)
        print('  OK 关键词:', loaded_features.get('keywords'))
        print('  OK 架构模式:', loaded_features.get('architecture_patterns'))
        print('  OK 已完成子任务:', loaded_features.get('completed_subtasks'))
        
except Exception as e:
    print('  FAIL 特征列表存储验证失败:', e)

print('\n' + '=' * 60)
print('验证完成!')
print('=' * 60)