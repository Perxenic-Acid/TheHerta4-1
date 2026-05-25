# 04 — 魔法字符串（Magic Strings）

## 严重程度

🟡 **中等** — D3D11 语义名、格式字符串、slot 标识符散落在 10+ 个文件中，添加新游戏时需要全局 grep 才能找到所有 touch point。

## 问题分类

### A. D3D11 语义名（Semantic Names）

这些字符串标识了顶点缓冲区中的数据类型，如 `"POSITION"`、`"NORMAL"`、`"TEXCOORD"` 等。

**出现位置**：

| 文件 | 行号 | 示例 |
|------|:----:|------|
| `common/obj_buffer_helper.py` | 40-50 | `d3d11_element_name.startswith("COLOR")`、`startswith("TEXCOORD")`、`startswith("BLENDINDICES")`、`startswith("BLENDWEIGHTS")` |
| `games/srmi.py` | 191, 193 | `name == "BLENDINDICES"`、`== "BLENDWEIGHTS"` |
| `games/zzmi.py` | 多处 | 类似的语义名比较 |
| `common/d3d11_element.py` | 多处 | 解析 D3D11 元素时使用语义名字符串 |

**修复方案**：在 `common/d3d11_gametype.py` 或新建 `common/d3d11_semantics.py` 中定义语义名字符串常量：

```python
# common/d3d11_semantics.py（新建）

class D3D11Semantic:
    """D3D11 顶点缓冲区语义名常量"""
    POSITION     = "POSITION"
    NORMAL       = "NORMAL"
    TANGENT      = "TANGENT"
    BINORMAL     = "BINORMAL"
    COLOR        = "COLOR"
    TEXCOORD     = "TEXCOORD"
    BLENDINDICES = "BLENDINDICES"
    BLENDWEIGHTS = "BLENDWEIGHTS"
    SV_POSITION  = "SV_POSITION"
    SV_INSTANCEID = "SV_INSTANCEID"
    POSITIONT    = "POSITIONT"
    TESSFACTOR   = "TESSFACTOR"
```

使用示例：

```python
# 修复前（obj_buffer_helper.py:40）
if d3d11_element_name.startswith("COLOR"):

# 修复后
from ..common.d3d11_semantics import D3D11Semantic
if d3d11_element_name.startswith(D3D11Semantic.COLOR):
```

需要在 3 个文件中做类似替换：
1. `common/obj_buffer_helper.py`
2. `games/srmi.py`
3. `games/zzmi.py`

### B. D3D11 格式字符串（Format Names）

标识顶点缓冲区中每个元素的数据格式，如 `"R32G32B32A32_FLOAT"`、`"R8G8B8A8_UNORM"` 等。

**出现位置**：

| 文件 | 行号 | 示例 |
|------|:----:|------|
| `common/obj_buffer_helper.py` | 200-280 | `'R32G32B32A32_FLOAT'`、`'R8G8B8A8_SNORM'`、`'R8G8B8A8_UNORM'`、`'R32_UINT'`、`'R32G32B32_FLOAT'`、`'R16G16B16A16_FLOAT'`、`'R16G16_FLOAT'`、`'R16G16_SNORM'`、`'R32G32_FLOAT'`、`'R8G8B8A8_UINT'`、`'R8G8_UINT'`、`'R8_UINT'` |

**出现位置**：

| 文件 | 行号 | 示例 |
|------|:----:|------|
| `games/wwmi.py` | 511, 561 | `"stride = 12"`、`"stride = 16"`、`"stride = 4"`、`"stride = 2"` |
| `games/wwmi.py` | 520-532 | `category_name == "Blend"`、`== "Color"`、`== "Texcoord"`、`== "Tangent"`、`== "Position"`、`== "Normal"` |
| `common/m_ini_helper.py` | 多处 | `"Position"`、`"Blend"`、`"TextureOverride_"`、`"Resource"`——INI 生成时的字符串拼接 |

**wwmi.py 中的 stride 魔法数字**：

```python
# 修复前（wwmi.py:511, 561）
"stride = 12"
"stride = 16"
"stride = 4"
"stride = 2"

# 修复后
# 在类中定义常量
STRIDE_FLOAT3 = 12   # 3 * 4 bytes
STRIDE_FLOAT4 = 16   # 4 * 4 bytes
STRIDE_FLOAT1 = 4    # 1 * 4 bytes
STRIDE_HALF2 = 2     # 2 * 2 bytes
```

**wwmi.py 中的 category 名字符串**：

```python
# 修复前（wwmi.py:520）
category_name == "Blend"

# 修复后
class WWMICategory:
    BLEND = "Blend"
    COLOR = "Color"
    TEXCOORD = "Texcoord"
    TANGENT = "Tangent"
    POSITION = "Position"
    NORMAL = "Normal"
```

### C. INI 文件生成字符串（m_ini_helper.py）

`m_ini_helper.py` 中大量使用字符串拼接生成 INI 内容：

```python
"drawindexed = " + str(index_count) + "," + str(draw_offset) + ",0"
"match_first_index = " + str(submesh_model.match_first_index)
"ps-t0 = ResourceTexture" + token
"vb0 = Resource" + unique_key
```

**修复建议**：使用 f-string 或模板格式，提高可读性：

```python
# 修复前
"drawindexed = " + str(index_count) + "," + str(draw_offset) + ",0"

# 修复后
f"drawindexed = {index_count},{draw_offset},0"
```

### D. 导入导出路径字符串

**出现位置**：

| 文件 | 行号 | 示例 |
|------|:----:|------|
| `workspace/ssmt_workspace.py` | 多处 | `"TYPE_"`、`"Import.json"`、`"Config.json"` |
| `common/global_config.py` | 多处 | `"SSMTGeneratedMod\\"`、`"Meshes"`、`"Textures\\"` |
| `model/submesh_model.py` | 70 | `"TEMP_SUBMESH_COLLECTION_"` |
| `utils/collection_utils.py` | 多处 | `"COLOR_01"` 等集合颜色标签 |

**修复建议**：在 `common/global_config.py` 中集中定义：

```python
# common/global_config.py
class PathConstants:
    TYPE_PREFIX      = "TYPE_"
    IMPORT_JSON      = "Import.json"
    CONFIG_JSON      = "Config.json"
    GENERATED_MOD    = "SSMTGeneratedMod"
    MESHES_FOLDER    = "Meshes"
    TEXTURES_FOLDER  = "Textures"
```

## 修复优先级

| 优先级 | 类别 | 原因 |
|:------:|------|------|
| **高** | D3D11 语义名字符串 | 跨 3+ 文件使用，最容易漏改 |
| **高** | wwmi.py category 和 stride | 当前文件内大量散落，可读性差 |
| **中** | D3D11 格式字符串 | 集中在 obj_buffer_helper.py 一个文件 |
| **低** | INI 生成字符串 | 使用 f-string 是代码风格改进，不影响功能 |
| **低** | 路径字符串 | 散落面大但改动风险低 |

## 验证方法

1. 全局搜索确认旧字符串不再出现：
```bash
grep -rn '"BLENDINDICES"' --include="*.py" d:\Dev\TheHerta4
grep -rn '"stride = 12"' --include="*.py" d:\Dev\TheHerta4
```
2. Blender 中生成 Mod，对比修改前后 INI 文件一致（diff）
