"""Pillow dependency installation for Material Combiner.

This module provides an operator to install the Pillow (PIL) library,
which is a required dependency for image processing in the Material Combiner.
It handles installation of pip if needed, and works across different Blender versions.

Usage example:
    bpy.ops.smc.get_pillow()
    bpy.ops.smc.check_pillow()
"""

import importlib.util
import os
import subprocess
import sys
from typing import Set

import bpy

from .. import globs


# 默认走清华 PyPI 镜像，官方 PyPI 在国内经常超时导致安装失败
PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_FALLBACK_INDEX_URL = "https://pypi.org/simple"


def _refresh_combiner_pillow_cache() -> bool:
    """Refresh cached Pillow globals used by the combiner module."""
    try:
        from .combiner import combiner_ops

        return combiner_ops.initialize_pillow()
    except Exception as e:
        globs.pil_install_error_message = "刷新 Pillow 模块缓存失败: {}".format(e)
        return False


class InstallPIL(bpy.types.Operator):
    """Installs the Pillow library for image processing functionality.

    This operator first checks if pip is available in the current Blender
    installation, installs it if needed, then installs the Pillow library.
    May require administrative privileges depending on the system configuration.
    """

    bl_idname = "smc.get_pillow"
    bl_label = "安装 PIL"
    bl_description = "点击安装 Pillow 库。这可能需要一些时间，可能需要以管理员身份运行 Blender。"

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """Executes the Pillow installation process.

        Checks for pip and PIL dependencies, attempts to install them as needed,
        and reports success or failure to the user.

        Args:
            context: Current Blender context.

        Returns:
            Set containing "FINISHED" if the installation completes successfully,
            or "CANCELLED" if the installation fails.
        """
        # 重置错误信息
        globs.pil_install_error_message = ""

        has_pip = all(self._module_exists(m) for m in ("pip", "pip._internal"))
        has_pil = all(
            self._module_exists(m)
            for m in ("PIL", "PIL.Image", "PIL.ImageChops")
        )

        # 如果已经都有了，就不需要安装
        if has_pip and has_pil:
            globs.pil_install_attempted = True
            globs.pil_install_success = _refresh_combiner_pillow_cache()
            globs.pil_available = globs.pil_install_success
            if not globs.pil_install_success:
                self.report({"ERROR"}, globs.pil_install_error_message)
                return {"CANCELLED"}
            self.report({"INFO"}, "Pillow 已经安装了！")
            return {"FINISHED"}

        success = False
        if not has_pip:
            success = self._install_pip()
            if success:
                success = self._install_pillow()
        else:
            # pip 已存在，直接安装 pillow
            success = self._install_pillow()

        globs.pil_install_attempted = True
        globs.pil_install_success = success

        # 验证安装是否真的成功
        if success:
            try:
                import PIL
                import PIL.Image
                import PIL.ImageChops
                success = _refresh_combiner_pillow_cache()
                globs.pil_install_success = success
                globs.pil_available = success
            except ImportError:
                success = False
                globs.pil_install_success = False
                globs.pil_install_error_message = "安装后仍无法导入 Pillow 库，请尝试重启 Blender。"

        self.report(
            {"INFO" if success else "ERROR"},
            "安装完成" if success else "安装失败",
        )
        return {"FINISHED"} if success else {"CANCELLED"}

    @staticmethod
    def _module_exists(module_name: str) -> bool:
        """Checks if a Python module exists in the current environment.

        Args:
            module_name: Name of the module to check for.

        Returns:
            True if the module exists, False otherwise.
        """
        return importlib.util.find_spec(module_name) is not None

    @staticmethod
    def _run_pip_install(pip_main, args: list) -> int:
        """Runs pip install with the Tsinghua mirror first, falling back to PyPI."""
        last_result = -1
        for index_url in (PIP_INDEX_URL, PIP_FALLBACK_INDEX_URL):
            last_result = pip_main(args + ["-i", index_url])
            if last_result == 0:
                break
        return last_result

    def _install_pip(self) -> bool:
        """Attempts to install pip using an appropriate method for the Blender version.

        For modern Blender versions, uses the built-in ensurepip module when available.
        Falls back to manual installation using get-pip.py for older versions.

        Returns:
            True if pip installation succeeds, False otherwise.
        """
        try:
            if globs.is_blender_modern:
                return self._try_install_pip_with_ensurepip()
            else:
                return self._install_pip_clean()
        except Exception as e:
            error_msg = "pip 安装失败: {}".format(e)
            self.report({"ERROR"}, error_msg)
            globs.pil_install_error_message = error_msg
            return False

    def _try_install_pip_with_ensurepip(self) -> bool:
        """Attempts to install pip using the ensurepip module.

        Uses Blender's built-in ensurepip module when available in modern versions.
        Falls back to manual installation if the module is not present or fails.

        Returns:
            True if pip installation succeeds, False otherwise.
        """
        try:
            import ensurepip

            ensurepip.bootstrap()
            return True
        except ImportError:
            return self._install_pip_clean()
        except Exception as e:
            error_msg = "ensurepip 失败: {}".format(e)
            self.report({"ERROR"}, error_msg)
            globs.pil_install_error_message = error_msg
            return self._install_pip_clean()

    def _install_pip_clean(self) -> bool:
        """Installs pip manually using get-pip.py.

        Uses the embedded get-pip.py script to perform a clean installation
        of pip with user privileges. Captures and reports errors if they occur.

        Returns:
            True if pip installation succeeds, False otherwise.
        """
        try:
            python_executable = (
                sys.executable
                if globs.is_blender_2_92_plus
                else bpy.app.binary_path_python
            )
            get_pip = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "get-pip.py"
            )

            last_error = "未知错误"
            for index_url in (PIP_INDEX_URL, PIP_FALLBACK_INDEX_URL):
                process = subprocess.run(
                    [python_executable, get_pip, "--force-reinstall", "-i", index_url],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if process.returncode == 0:
                    return True
                last_error = process.stderr or process.stdout or "未知错误"

            error_msg = "get-pip.py 执行失败: {}".format(last_error)
            self.report({"ERROR"}, error_msg)
            globs.pil_install_error_message = error_msg
            return False
        except Exception as e:
            error_msg = "运行 get-pip.py 失败: {}".format(e)
            self.report({"ERROR"}, error_msg)
            globs.pil_install_error_message = error_msg
            return False

    def _install_pillow(self) -> bool:
        """Installs Pillow using pip.

        First updates pip, setuptools, and wheel to ensure compatibility,
        then installs the Pillow package with user privileges. Captures
        and reports any errors encountered during the process.

        Returns:
            True if Pillow installation succeeds, False otherwise.
        """
        try:
            from pip import _internal

            deps_result = self._run_pip_install(
                _internal.main,
                ["install", "pip", "setuptools", "wheel", "-U", "--user"],
            )
            if deps_result != 0:
                error_msg = "更新 pip 依赖失败 (错误代码: {})".format(deps_result)
                self.report({"ERROR"}, error_msg)
                globs.pil_install_error_message = error_msg
                return False

            pillow_result = self._run_pip_install(
                _internal.main,
                ["install", "Pillow", "--user"],
            )
            if pillow_result != 0:
                error_msg = "Pillow 安装失败 (错误代码: {})".format(pillow_result)
                self.report({"ERROR"}, error_msg)
                globs.pil_install_error_message = error_msg
                return False

            return True
        except ImportError as e:
            error_msg = "安装后无法导入 pip: {}".format(e)
            self.report({"ERROR"}, error_msg)
            globs.pil_install_error_message = error_msg
            return False
        except Exception as e:
            error_msg = "Pillow 安装过程中出错: {}".format(e)
            self.report({"ERROR"}, error_msg)
            globs.pil_install_error_message = error_msg
            return False


class CheckPillow(bpy.types.Operator):
    """Checks if Pillow is installed and refreshes the status.

    This operator re-checks the Pillow installation status and updates
    the global flags accordingly. Useful after manual installation or
    to refresh the UI without restarting Blender.
    """

    bl_idname = "smc.check_pillow"
    bl_label = "检查 Pillow"
    bl_description = "重新检查 Pillow 库是否已安装，可以在不重启的情况下刷新状态。"

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """Executes the Pillow status check.

        Args:
            context: Current Blender context.

        Returns:
            Set containing "FINISHED".
        """
        success = globs.refresh_pil_availability()

        if success:
            success = _refresh_combiner_pillow_cache()
            if success:
                self.report({"INFO"}, "Pillow 已安装，可以使用！")
                # 清除之前的错误状态
                globs.pil_install_success = True
                globs.pil_available = True
                globs.pil_install_error_message = ""
            else:
                globs.pil_install_success = False
                globs.pil_available = False
                self.report({"ERROR"}, globs.pil_install_error_message)
        else:
            self.report({"ERROR"}, "Pillow 仍未安装，请尝试重新安装或手动安装。")

        return {"FINISHED"}
