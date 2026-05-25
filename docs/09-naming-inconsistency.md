# 09 — 命名不一致

## 严重程度

🟢 **低** — 不影响功能但增加认知负担，让新人怀疑"我是不是用错了版本"。

## 问题清单

### A. d3d11GameType vs d3d11_game_type

同一概念在不同文件中使用了两种命名风格：

| 文件 | 属性/变量名 | 风格 |
|------|------------|:----:|
| `model/drawib_model.py` | `d3d11_game_type` | snake_case |
| `model/submesh_model.py` | `d3d11_game_type` | snake_case |
| `model/drawib_model_wwmi.py` | `d3d11GameType` | camelCase |
| `games/efmi.py` | `d3d11_game_type`（通过 submesh_model 访问） | snake_case |
| `games/srmi.py` | `d3d11_game_type` | snake_case |

**问题根源**：`drawib_model_wwmi.py` 是后加的 WWMI 专用模型，没有遵循已有命名规范。

**修复**：将 `drawib_model_wwmi.py` 中的 `d3d11GameType` 重命名为 `d3d11_game_type`。

```python
# 修复前（drawib_model_wwmi.py）
self.d3d11GameType = D3D11GameType.from_submesh_json_dict(...)

# 需要检查所有使用 sites：
# self.d3d11GameType.GameTypeName
# self.d3d11GameType.CategoryStrideDict
# ...
```

### B. select_obj vs select_object

`ObjUtils` 中有两个选择物体的方法：

| 方法 | 行号 | 行为 |
|------|:----:|------|
| `ObjUtils.select_object(obj)` | ~870 | 简单设置 `obj.select_set(True)` |
| `ObjUtils.select_obj(target_obj)` | ~440 | 先清空所有选择，再设置活动对象，最后选中 |

**问题**：两者行为完全不同，但命名没有体现差异。

**建议**：
```python
# 重命名为更清晰的名称
ObjUtils.set_selected(obj)         # 原 select_object — 简单选中
ObjUtils.set_active_and_selected(obj)  # 原 select_obj — 清空+设活动+选中
```

或者至少给 `select_obj` 添加清晰的 docstring 说明它与 `select_object` 的区别。

### C. 游戏 ID 命名

| 游戏 | 文件夹 `games/` | LogicName `common/global_config.py` |
|------|:---:|:---:|
| Genshin Impact | `gimi.py` | `"GIMI"` |
| Honkai Impact 3rd | `himi.py` | `"HIMI"` |
| Honkai: Star Rail | `srmi.py` | `"SRMI"` |
| Zenless Zone Zero | `zzmi.py` | `"ZZMI"` |
| Wuthering Waves | `wwmi.py` | `"WWMI"` |
| Arknights: Endfield | `efmi.py` | `"EFMI"` |
| Neverness to Everness | `ntemi.py` | `"NTEMI"` |
| Identity V | `identityv.py` | `"IdentityV"` |
| Snowbreak | `snowbreak.py` | `"SnowBreak"` |
| Where Winds Meet | `yysls.py` | `"YYSLS"` |
| Girls' Frontline 2 | `gf2.py`（预留） | `"GF2"` |
| Azur Promilia | `apmi.py`（预留） | `"APMI"` |

**模式**：大部分游戏 ID 是大写的引擎缩写（GIMI/HIMI/SRMI/ZZMI/WWMI/EFMI/NTEMI），但 IdentityV 和 SnowBreak 是 PascalCase。没有一致的规则。

### D. 重复跟踪变量命名

`m_ini_helper.py` 中，同一概念（去重跟踪）在不同方法中使用不同变量名：

| 方法 | 变量名 |
|------|--------|
| `generate_hash_style_texture_ini()` | `repeat_hash_list` |
| `generate_shared_slot_style_texture_ini()` | `appended_resource_names` |

**建议**：统一为 `seen_hashes` 或 `deduped_names`。

## 修复优先级

| 优先级 | 问题 | 原因 |
|:------:|------|------|
| **中** | `d3d11GameType` → `d3d11_game_type` | 一个文件的 10+ 处改名，影响 WWMI 导出 |
| **低** | `select_obj` vs `select_object` | 影响范围小，可逐步改名 |
| **低** | 游戏 ID 命名不一致 | 涉及 README、代码、配置文件，改动面大 |
| **低** | 去重变量名 | 纯内部实现，不影响外部 API |

## 验证方法

1. 全局搜索确认旧名称不再出现
2. Blender 中执行全流程测试
