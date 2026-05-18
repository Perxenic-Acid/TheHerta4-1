# Blender下载地址
- https://download.blender.org/release/

# Change Log
为了让工具保持与时俱进，支持3.6开始的所有版本，我们需要时刻关注Blender的API变化：
- 4.4 to 4.5
- https://docs.blender.org/api/4.5/change_log.html#change-log
- 4.3 to 4.4
- https://docs.blender.org/api/4.4/change_log.html#change-log
- 4.2 to 4.3
- https://docs.blender.org/api/4.3/change_log.html#change-log
- 4.1 to 4.2
- https://docs.blender.org/api/4.2/change_log.html#to-4-2
- 4.0 to 4.1
- https://docs.blender.org/api/4.1/change_log.html
- 3.6 to 4.0 
- https://docs.blender.org/api/4.0/change_log.html#change-log

# Blender API手册
- https://www.blender.org/support/
- https://docs.blender.org/api/3.6/
- https://docs.blender.org/api/4.2/
- https://docs.blender.org/api/4.5/

# 开发必备插件
- https://github.com/JacquesLucke/blender_vscode              (推荐，首选)
- https://github.com/BlackStartx/PyCharm-Blender-Plugin       (也能用，但不推荐)

# Blender插件开发中的缓存问题

在使用VSCode进行Blender插件开发中，会创建一个指向项目的软连接，路径大概如下：

C:\Users\Administrator\AppData\Roaming\Blender Foundation\Blender\4.2\scripts\addons

在插件架构发生大幅度变更时可能导致无法启动Blender，此时需要手动删掉插件缓存的这个软链接。

也就是说，迁移插件位置可能会导致如下错误：

```
Traceback (most recent call last):
  File "c:\Users\Administrator\.vscode\extensions\jacqueslucke.blender-development-0.0.30\pythonFiles\launch.py", line 28, in <module>
    blender_vscode.startup(
  File "c:\Users\Administrator\.vscode\extensions\jacqueslucke.blender-development-0.0.30\pythonFiles\include\blender_vscode\__init__.py", line 31, in startup
    path_mappings = load_addons.setup_addon_links(addons_to_load)
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\Administrator\.vscode\extensions\jacqueslucke.blender-development-0.0.30\pythonFiles\include\blender_vscode\load_addons.py", line 40, in setup_addon_links
    load_path = _link_addon_or_extension(addon_info)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\Administrator\.vscode\extensions\jacqueslucke.blender-development-0.0.30\pythonFiles\include\blender_vscode\load_addons.py", line 64, in _link_addon_or_extension
    create_link_in_user_addon_directory(addon_info.load_dir, load_path)
  File "c:\Users\Administrator\.vscode\extensions\jacqueslucke.blender-development-0.0.30\pythonFiles\include\blender_vscode\load_addons.py", line 237, in create_link_in_user_addon_directory
    _winapi.CreateJunction(str(directory), str(link_path))
FileExistsError: [WinError 183] 当文件已存在时，无法创建该文件。
```

出现此报错后，去删除掉对应位置的软链接，再次Ctrl + Shift + P即可正常调试项目

# 文件夹与文件名命名大小写问题 

所有的文件夹都必须小写，因为git无法追踪文件夹名称大小写改变的记录,至少VSCode集成的git做不到，也可能是VSCode的问题。

文件名也必须小写，因为Github也无法追踪文件名的大小写变化。

# Jinja2的ini模板问题

我们不模仿XXMI-Tools和WWMI-Tools使用Jinja2的ini模板，
以便于在生成Mod逻辑发生变更后，能够第一时间通过修改代码来同步特性。

我们的项目尽可能遵循奥卡姆剃刀原理，不引入额外的组件和学习成本，
尽可能让每个人拿到源码后都能像滑雪一样顺畅的读完整个逻辑并理解大概原理，
除非到了哪天由于重要的特性不得不引入，否则暂时不加入Jinja2模板ini功能。


# 现存问题
目前TheHerta3里很多错误的用法限制了整体数据类型的搭建，要进行以下改动：
- 凡不使用类中信息的工具类，应从@classmethod改为@staticmethod。
- 所有的类都应该使用@dataclass,在post_init中进行后初始化，否则难以理解。
- 对于Blender插件开发来说，其对Blender的bpy部分的封装应该在数据结构的较底层，否则将会导致代码混乱且无法理解原理，也就是我们目前面临的情况。有一部分工具类必须是专门负责和bpy中类型进行对接使用的。


# 非镜像工作流问题
在导入时，通过把Scale的X分量设为-1并应用，来让模型不镜像
在导出时，把Scale的X分量再设为-1并应用，让模型镜像回来
这样就避免了底层数据结构的操作，非常优雅，且后续基本上就应该这么做

所以暂时删掉所有旧的非镜像工作流代码，等待后续测试

