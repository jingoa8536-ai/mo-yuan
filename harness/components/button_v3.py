"""
Button v3 - 激进弹性效果按钮组件
=========================================

物种信息：
- 模板: button
- 版本: v3
- 属性: gradient颜色、primary变体、lg尺寸、激进弹性动效

生成代码：从认知物种库自动生成（属性更新后）

动效类型：
- bounce: 激进弹性效果 (cubic-bezier(0.68, -0.55, 0.265, 1.55))
- pulse: 脉冲效果
- glow: 发光效果
- float: 浮动效果
"""

def render_button(label="Submit", color="gradient", 
                  variant="primary", size="lg", 
                  rounded=True, shadow=True, 
                  hover_effect="bounce"):
    """渲染按钮组件（支持激进弹性动效）"""
    classes = ["btn"]
    
    if color == "gradient":
        classes.append("btn-gradient")
    else:
        classes.append(f"btn-{color}")
    
    classes.append(f"btn-{variant}")
    classes.append(f"btn-{size}")
    
    if rounded:
        classes.append("btn-rounded")
    if shadow:
        classes.append("btn-shadow")
    
    if hover_effect == "bounce":
        classes.append("btn-hover-bounce")
    elif hover_effect == "pulse":
        classes.append("btn-hover-pulse")
    elif hover_effect == "glow":
        classes.append("btn-hover-glow")
    elif hover_effect == "float":
        classes.append("btn-hover-float")
    else:
        classes.append("btn-hover")
    
    class_str = " ".join(classes)
    return f'<button class="{class_str}">{label}</button>'
