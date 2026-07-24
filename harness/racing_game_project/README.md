# Racing Game Demo

基于 LAAP Harness 自动生成的赛车游戏项目。

## 📁 项目结构

```
racing_game_project/
├── project.godot          # 项目配置文件
├── icon.png               # 应用图标
├── resources/
│   ├── audio/
│   │   └── race_audio_bus.tres   # 音频总线布局
│   └── materials/
│       └── car_material.tres     # 赛车材质
├── scenes/
│   └── racing/
│       ├── main.tscn             # 主场景
│       ├── engine_sound.tscn     # 引擎声音场景
│       ├── skid_sound.tscn       # 刹车打滑音效场景
│       ├── ui_animations.tscn    # UI 动画场景
│       ├── ghost_recorder.tscn   # 幽灵记录器场景
│       ├── ghost_player.tscn     # 幽灵播放器场景
│       └── race_camera.tscn      # 赛道相机场景
└── scripts/
    ├── test_run.gd               # 测试运行脚本
    └── racing/
        ├── physics_vehicle.gd        # 物理车辆控制
        ├── engine_sound_controller.gd # 引擎声音控制
        ├── ghost_recorder.gd         # 幽灵记录逻辑
        └── ghost_player_controller.gd # 幽灵回放控制
```

## 🎮 游戏功能

1. **车辆控制**
   - 加速：Enter / Space
   - 刹车：Backspace
   - 转向：A / D 或 方向键

2. **引擎声音**
   - 基于 RPM 的音量调节
   - 自动同步车辆速度

3. **幽灵系统**
   - 记录玩家驾驶轨迹
   - 回放之前的驾驶记录

4. **音频总线**
   - Master、Engine、SFX、Music、UI 五条音频总线

## 🚀 运行方式

### 方法一：使用 Godot 编辑器

1. 下载并安装 [Godot Engine](https://godotengine.org/download/)
2. 打开 Godot 编辑器
3. 点击 "Import" 按钮，选择项目目录 `racing_game_project`
4. 点击 "Open" 打开项目
5. 点击 "Play" 按钮运行游戏

### 方法二：使用命令行

```bash
# Windows
godot --path "D:\LAAP\harness\racing_game_project" --run

# 或使用 headless 模式运行测试脚本
godot --headless --path "D:\LAAP\harness\racing_game_project" --script "res://scripts/test_run.gd" --quit
```

### 方法三：使用 LAAP Harness

```bash
cd D:\LAAP\harness\laap_coding
python -c "
from godot_resource_generator import GodotResourceGenerator

generator = GodotResourceGenerator(output_dir='racing_game_project')
# 使用配置重新生成资源
"
```

## 📝 测试脚本

运行 `scripts/test_run.gd` 可以验证项目资源是否正确加载：

```bash
godot --headless --path . --script res://scripts/test_run.gd --quit
```

## 🎨 生成的资源

### .tscn 场景文件
| 文件 | 节点类型 | 用途 |
|------|----------|------|
| main.tscn | Node3D | 主游戏场景 |
| engine_sound.tscn | AudioStreamPlayer3D | 引擎音效 |
| skid_sound.tscn | AudioStreamPlayer3D | 刹车音效 |
| race_camera.tscn | Camera3D | 赛道视角 |

### .tres 资源文件
| 文件 | 类型 | 用途 |
|------|------|------|
| race_audio_bus.tres | AudioBusLayout | 音频总线配置 |
| car_material.tres | StandardMaterial3D | 赛车材质 |

### .gd 脚本文件
| 文件 | 继承 | 功能 |
|------|------|------|
| physics_vehicle.gd | VehicleBody3D | 车辆物理控制 |
| engine_sound_controller.gd | Node3D | 引擎声音管理 |
| ghost_recorder.gd | Node3D | 幽灵记录 |
| ghost_player_controller.gd | Node3D | 幽灵回放 |

## ⚙️ 项目配置

项目配置在 `project.godot` 中：

- **窗口大小**: 1280x720
- **帧率限制**: 60 FPS
- **渲染驱动**: Vulkan
- **音频总线**: `res://resources/audio/race_audio_bus.tres`

## 🔧 自定义

可以通过修改以下文件来自定义游戏：

1. **调整车辆参数**: 修改 `scripts/racing/physics_vehicle.gd` 中的导出变量
2. **修改材质**: 编辑 `resources/materials/car_material.tres`
3. **调整音频**: 编辑 `resources/audio/race_audio_bus.tres`
4. **修改场景**: 编辑 `scenes/racing/main.tscn`

## 📋 生成日志

资源生成过程会输出详细日志，方便排查问题：

```
[2026-07-05 10:55:15] [godot_resource_generator] [INFO] [Generator] 处理资源 1/8: scenes/racing/engine_sound.tscn
[2026-07-05 10:55:15] [godot_resource_generator] [INFO] [TSCN] 开始生成 .tscn 场景，节点数量: 1
[2026-07-05 10:55:15] [godot_resource_generator] [INFO] [Generator]   成功生成: racing_game_output\scenes/racing/engine_sound.tscn
```

## 📧 技术支持

如果在运行过程中遇到问题：

1. 检查 `project.godot` 中的路径配置
2. 确保所有 `.gd` 脚本没有语法错误
3. 验证 `.tscn` 文件中的资源引用路径
4. 查看 Godot 编辑器的输出日志
