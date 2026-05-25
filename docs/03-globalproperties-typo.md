# 03 — GlobalProterties 拼写错误

## 严重程度

🟡 **中等** — 类名 `GlobalProterties` 应为 `GlobalProperties`，在 **15+ 个文件**中被引用。每次看到都让开发者怀疑"是不是我拼错了"。

## 影响范围

### 定义位置

| 文件 | 行号 |
|------|:----:|
| `common/global_properties.py` | `class GlobalProterties:` |

### 引用位置（15 个文件）

| 文件 | 行号 | 调用示例 |
|------|:----:|----------|
| `common/global_config.py` | 167, 170, 182, 184, 197 | `GlobalProterties.workspace_source_mode()` |
| `model/submesh_model.py` | 导入行 | `from ..common.global_properties import GlobalProterties` |
| `model/drawib_model_wwmi.py` | 导入行 | 同上 |
| `model/drawib_model.py` | 多处 | 使用 `GlobalProterties` |
| `ui/ui_panel_basic.py` | 多处 | 布局属性引用 |
| `ui/ui_panel_fast_texture.py` | 多处 | 布局属性引用 |
| `blueprint/blueprint_node_obj.py` | 导入行 | 使用 `GlobalProterties` |
| `blueprint/blueprint_node_panel.py` | 导入行 | 使用 `GlobalProterties` |
| `blueprint/blueprint_node_menu.py` | 导入行 | 使用 `GlobalProterties` |
| `sword/ui_panel_sword.py` | 导入行 | 使用 `GlobalProterties` |
| `sword/mesh_import_helper.py` | 导入行 | 使用 `GlobalProterties` |
| `common/m_ini_helper.py` | 多处 | `GlobalProterties` 调用 |
| `common/obj_buffer_helper.py` | 导入行 | 使用 `GlobalProterties` |
| `common/global_properties.py` | 自身类名 | 类定义 |
| `blueprint/blueprint_export_helper.py` | 导入行 | 使用 `GlobalProterties` |

## 修复方案

### 步骤 1：修改类定义

```python
# common/global_properties.py
# 修复前
class GlobalProterties:
    ...

# 修复后
class GlobalProperties:
    ...
```

### 步骤 2：全局替换所有引用

```bash
# 在所有 .py 文件中替换
GlobalProterties → GlobalProperties
```

需要替换的文件和模式：
```
from ..common.global_properties import GlobalProterties
→
from ..common.global_properties import GlobalProperties

GlobalProterties.workspace_source_mode()
→
GlobalProperties.workspace_source_mode()

等等所有出现 GlobalProterties 的地方
```

### 步骤 3：验证

1. 全局搜索确认零残留：
```bash
grep -rn "GlobalProterties" --include="*.py" d:\Dev\TheHerta4
```
2. Blender 中执行完整流程

## 风险

- **低风险**：纯重命名，IDE 的 Rename Symbol 功能可以自动完成
- 注意不要改到注释中的 `proterties`（如果有的话）
- 如果有序列化数据（JSON/pickle）中存储了类名字符串 `"GlobalProterties"`，需要额外处理——但目前项目中没有这种情况

## 使用 VSCode Rename Symbol

最安全的方式：
1. 在 `common/global_properties.py` 中右键 `GlobalProterties`
2. 选择 `Rename Symbol`（F2）
3. 输入 `GlobalProperties`
4. VSCode 自动更新所有 15+ 个引用
