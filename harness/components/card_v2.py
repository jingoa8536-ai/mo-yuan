"""
Card v2 - 阴影卡片组件
=========================================

物种信息：
- 模板: card
- 版本: v2 (shadow + enhanced)
- 属性: Welcome标题、Hello World内容、无border、shadow、hover_lift

生成代码：从认知物种库自动生成
"""

def render_card(title="Welcome", content="Hello World", bordered=False, 
                shadow=True, hover_lift=True):
    """渲染卡片组件"""
    classes = ["card"]
    
    if bordered:
        classes.append("card-bordered")
    if shadow:
        classes.append("card-shadow")
    if hover_lift:
        classes.append("card-hover-lift")
    
    class_str = " ".join(classes)
    return f'<div class="{class_str}"><h3>{title}</h3><p>{content}</p></div>'
