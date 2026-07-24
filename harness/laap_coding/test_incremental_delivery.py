"""
LAAP Harness 增量交付约束系统验证测试
"""

from core.incremental_delivery import IncrementalDelivery

print('=' * 60)
print('LAAP Harness 增量交付约束验证')
print('=' * 60)

# 1. 语义化提交验证
print('\n[1/2] 语义化提交验证')
try:
    delivery = IncrementalDelivery()
    
    valid_messages = [
        'feat(api): 添加用户登录接口',
        'fix(auth): 修复JWT令牌过期问题',
        'refactor(utils): 重构日期处理模块',
        'test(core): 添加单元测试用例',
        'docs(readme): 更新项目文档',
    ]
    
    invalid_messages = [
        '添加功能',
        '修复bug',
        'feat: 添加功能',
        'FEAT(API) 添加功能',
        'feat(api) 添加功能',
    ]
    
    print('  OK 有效提交信息:')
    all_valid = True
    for msg in valid_messages:
        valid, err = delivery.validate_commit_message(msg)
        status = 'OK' if valid else 'FAIL'
        if not valid:
            all_valid = False
        print(f'    - {status}: {msg}')
    print('  OK 全部有效验证:', all_valid)
    
    print('  OK 无效提交信息:')
    all_invalid = True
    for msg in invalid_messages:
        valid, err = delivery.validate_commit_message(msg)
        status = 'OK' if not valid else 'FAIL'
        if valid:
            all_invalid = False
        print(f'    - {status}: {msg}')
    print('  OK 全部无效验证:', all_invalid)
    
    commit_msg = delivery.create_conventional_commit(
        type_='feat',
        scope='web_crawler',
        description='集成Playwright动态页面爬取',
        body='支持JavaScript渲染页面的爬取',
        footer='Closes #123'
    )
    print('  OK 自动生成提交信息:', commit_msg.split('\n')[0])
    
except Exception as e:
    print('  FAIL 语义化提交验证失败:', e)

# 2. 增量交付核心功能验证
print('\n[2/2] 增量交付核心功能验证')
try:
    delivery = IncrementalDelivery()
    
    test_description = '实现用户认证模块'
    
    stats = delivery.check_line_count()
    print('  OK 变更统计获取:', stats is not None)
    print('  OK 变更行数:', stats.total_lines)
    print('  OK 添加行数:', stats.added_lines)
    print('  OK 修改文件数:', stats.modified_files)
    
    validation = delivery.validate_subtask_delivery(test_description)
    print('  OK 交付验证:', validation['valid'])
    print('  OK 验证消息:', validation['message'])
    
    commit_msg = delivery.create_conventional_commit(
        type_='feat',
        scope='auth',
        description=test_description
    )
    valid, err = delivery.validate_commit_message(commit_msg)
    print('  OK 生成的提交信息验证:', valid)
    
    history = delivery.get_commit_history(limit=5)
    print('  OK 提交历史获取:', len(history), '条记录')
    
    branch = delivery.get_current_branch()
    print('  OK 当前分支:', branch)
    
    has_changes = delivery.has_uncommitted_changes()
    print('  OK 未提交变更检测:', has_changes)
    
except Exception as e:
    print('  FAIL 增量交付核心功能验证失败:', e)

print('\n' + '=' * 60)
print('验证完成!')
print('=' * 60)