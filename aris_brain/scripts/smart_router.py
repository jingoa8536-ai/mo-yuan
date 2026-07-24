#!/usr/bin/env python3
"""
Aris Smart Router — 智能路由脚本
根据任务类型自动路由到最优免费模型：
  GLM-4.7-Flash    → 中文对话、创意写作、前端开发、Agentic Coding
  Deepseek-V4-Flash → 代码生成、复杂推理、数学逻辑
"""

import requests
import json
import sys
import re

# ============ Config ============
GLM_KEY = '5ca95183169f49169795609e1c487209.fC7DgrVzbN5EJGuz'
DS_KEY   = 'sk-8f0...4d97'

GLM_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
DS_URL  = 'https://api.deepseek.com/chat/completions'

# ============ Task Classifier ============

# 关键词模式 → 模型名
PATTERNS = {
    'glm': [
        r'(中文|写作|创作|故事|角色|扮演|文案|诗|歌词|文章)',
        r'(前端|网页|HTML|CSS|布局|设计|UI|审美|PPT|海报)',
        r'(Agent|工具调用|MCP|函数|function|tool)',
        r'(翻译|长文本|情感|沉浸|画面感|氛围)',
        r'(对话|聊天|闲聊|情感支持)',
    ],
    'deepseek': [
        r'(代码|coding|编程|代码生成|算法|debug|bug)',
        r'(推理|数学|逻辑|证明|计算|公式)',
        r'(JSON|数据结构|算法|复杂度|优化)',
        r'(shell|bash|命令行|脚本|CI|CD|部署)',
        r'(架构|系统设计|微服务|后端|API)',
    ]
}

def classify_task(prompt: str) -> str:
    """根据任务提示词分类到 'glm' 或 'deepseek'"""
    prompt_lower = prompt.lower()
    
    dscore = sum(1 for p in PATTERNS['deepseek'] if re.search(p, prompt_lower))
    gscore = sum(1 for p in PATTERNS['glm'] if re.search(p, prompt_lower))
    
    if dscore > gscore:
        return 'deepseek'
    elif gscore > dscore:
        return 'glm'
    else:
        return 'glm'  # 默认走 GLM，中文更好
    
def get_model_info(model: str):
    if model == 'deepseek':
        return {
            'model': 'deepseek-v4-flash',
            'url': DS_URL,
            'key': DS_KEY,
            'name': 'Deepseek-V4-Flash',
            'strength': '代码/推理/数学'
        }
    else:
        return {
            'model': 'glm-4.7-flash',
            'url': GLM_URL,
            'key': GLM_KEY,
            'name': 'GLM-4.7-Flash',
            'strength': '中文/写作/前端/Agent'
        }

# ============ Chat Function ============

def chat(messages: list, model_override: str = None) -> dict:
    """
    智能路由对话
    - messages: OpenAI 格式的消息列表
    - model_override: 可选，强制使用 'glm' 或 'deepseek'
    """
    # 从用户消息推断任务
    user_msgs = [m for m in messages if m['role'] == 'user']
    user_prompt = user_msgs[-1]['content'] if user_msgs else ''
    
    target = model_override or classify_task(user_prompt)
    info = get_model_info(target)
    
    print(f'🤖 路由到: {info["name"]} ({info["strength"]})', file=sys.stderr)
    
    headers = {
        'Authorization': f'Bearer {info["key"]}',
        'Content-Type': 'application/json'
    }
    
    # 系统提示词
    payload = {
        'model': info['model'],
        'messages': messages,
        'max_tokens': 8192,
        'temperature': 0.7,
        'stream': False
    }
    
    resp = requests.post(info['url'], headers=headers, json=payload, timeout=60)
    result = resp.json()
    
    return {
        'model_used': info['name'],
        'content': result.get('choices', [{}])[0].get('message', {}).get('content', ''),
        'finish_reason': result.get('choices', [{}])[0].get('finish_reason'),
        'status': resp.status_code
    }


# ============ CLI Entry Point ============

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Aris 智能路由 — GLM-4.7-Flash / Deepseek-V4-Flash')
    parser.add_argument('prompt', nargs='?', help='用户输入')
    parser.add_argument('--model', '-m', choices=['glm', 'deepseek'], help='强制指定模型')
    parser.add_argument('--system', '-s', default='你是一个有帮助的AI助手', help='系统提示词')
    parser.add_argument('--stream', '-S', action='store_true', help='流式输出')
    args = parser.parse_args()
    
    if not args.prompt:
        print('交互模式 — 输入 /glm 强制使用GLM, /ds 强制使用Deepseek, /q 退出')
        messages = [{'role': 'system', 'content': args.system}]
        while True:
            try:
                user_input = input('\n💬 > ')
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input:
                continue
            if user_input == '/q':
                break
            if user_input == '/glm':
                messages.append({'role': 'user', 'content': 'Test'})
                result = chat(messages, model_override='glm')
                messages.pop()
                continue
            if user_input == '/ds':
                messages.append({'role': 'user', 'content': 'Test'})
                result = chat(messages, model_override='deepseek')
                messages.pop()
                continue
            
            messages.append({'role': 'user', 'content': user_input})
            result = chat(messages)
            reply = result['content']
            print(f'\n{result["model_used"]}: {reply}')
            messages.append({'role': 'assistant', 'content': reply})
    else:
        messages = [{'role': 'system', 'content': args.system}]
        messages.append({'role': 'user', 'content': args.prompt})
        result = chat(messages, model_override=args.model)
        print(result['content'])
