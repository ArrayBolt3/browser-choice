#!/usr/bin/python3 -Bsu

# Copyright (C) 2025 - 2025 ENCRYPTED SUPPORT LLC <adrelanos@whonix.org>
# See the file COPYING for copying conditions.

"""
browser_choice_core.py - Non-graphical routines for browser-choice.
"""

## NOTE: This file must not be named 'browser_choice.py', it confuses mypy.
## See https://github.com/python/mypy/issues/19410

import subprocess
import re
from pathlib import Path
from typing import Any

from PyQt5.QtCore import (
    QObject,
    QProcess,
)

from PyQt5.QtGui import (
    QImage,
    QPixmap,
)


## Caches the commands used for checking whether a package can be installed
## without privileges or not, so that duplicate commands aren't run
## unnecessarily.
unprivileged_check_cache: dict[str, bool] = {}


def str_or_none(data: str) -> str | None:
    """
    Returns the input string, or None if the input string is empty.
    """

    if data == "":
        return None
    return data


# pylint: disable=too-many-instance-attributes
class ChoicePluginRepo(QObject):
    """
    Represents a repo defined in a browser-choice plugin. You can install,
    remove, or purge an application from a particular repo.
    """

    # pylint: disable=too-many-arguments,too-many-locals
    def __init__(
        self,
        config_file: Path,
        internal_id: str | None,
        method_name: str | None,
        method_name_short: str | None,
        method_subtext: str | None,
        method_type: str | None,
        method_logo: QPixmap | None,
        install_warn_text: str | None,
        unprivileged_check_script: str | None,
        update_and_install_script: str | None,
        install_script: str | None,
        uninstall_script: str | None,
        purge_script: str | None,
        update_and_install_script_unprivileged: str | None,
        install_script_unprivileged: str | None,
        uninstall_script_unprivileged: str | None,
        purge_script_unprivileged: str | None,
        launch_script: str | None,
        install_status: str | None,
        capability: str | None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)

        none_check_dict: dict[str, Any] = {
            "internal_id": internal_id,
            "method_name": method_name,
            "method_name_short": method_name_short,
            "method_subtext": method_subtext,
            "method_logo": method_logo,
            "method_type": method_type,
            "launch_script": launch_script,
            "install_status": install_status,
            "capability": capability,
        }
        for key, value in none_check_dict.items():
            if value is None:
                throw_config_error(
                    config_file,
                    f"'{key}' in repo '{internal_id}' cannot be None!",
                )

        assert internal_id is not None
        assert method_name is not None
        assert method_name_short is not None
        assert method_subtext is not None
        assert method_type is not None
        assert method_logo is not None
        assert launch_script is not None
        assert install_status is not None
        assert capability is not None

        if unprivileged_check_script is None:
            if install_script is None:
                throw_config_error(
                    config_file,
                    f"'install_script' in repo '{internal_id}' cannot be "
                    + "None when 'unprivileged_check_script' is None!",
                )
        else:
            if install_script_unprivileged is None:
                throw_config_error(
                    config_file,
                    f"'install_script_unprivileged' in repo '{internal_id}' "
                    + "cannot be None when 'unprivileged_check_script' is "
                    + "not None!",
                )

        self.internal_id: str = internal_id
        self.method_name: str = method_name
        self.method_name_short: str = method_name_short
        self.method_subtext: str = method_subtext
        self.method_logo: QPixmap = method_logo
        self.method_type: str = method_type
        self.install_warn_text: str | None = install_warn_text
        self.unprivileged_check_script: str | None = unprivileged_check_script
        self.update_and_install_script: str | None = update_and_install_script
        self.install_script: str | None = install_script
        self.uninstall_script: str | None = uninstall_script
        self.purge_script: str | None = purge_script
        self.update_and_install_script_unprivileged: str | None = (
            update_and_install_script_unprivileged
        )
        self.install_script_unprivileged: str | None = (
            install_script_unprivileged
        )
        self.uninstall_script_unprivileged: str | None = (
            uninstall_script_unprivileged
        )
        self.purge_script_unprivileged: str | None = purge_script_unprivileged
        self.launch_script: str = launch_script
        self.install_status: str = install_status
        self.capability: str = capability
        self.is_installed: bool = self.check_installed()
        self.capability_info: str = self.check_capability()

        self.mod_requires_privileges: bool = True
        if self.unprivileged_check_script is not None:
            self.mod_requires_privileges = self.check_mod_unprivileged()

    def __run_script(
        self, script: str, set_x: bool = False, detach: bool = False
    ) -> QProcess:
        """
        Runs the provided script asynchronously with QProcess. Used internally
        to run plugin-defined scripts.
        """

        if set_x:
            script = "set -x; " + script

        output_process: QProcess = QProcess(self)
        output_process.setProgram("/usr/bin/bash")
        output_process.setProcessChannelMode(QProcess.MergedChannels)
        output_process.setArguments(
            [
                "-c",
                "--",
                script,
            ]
        )
        if detach:
            output_process.startDetached()
        else:
            output_process.start()
            if not output_process.waitForStarted():
                raise OSError("Failed to start script!")
        return output_process

    def run_update_and_install(self) -> QProcess | None:
        """
        Run a plugin's 'update-and-install-script' asynchronously.
        """

        if self.update_and_install_script is None:
            return None
        return self.__run_script(self.update_and_install_script, set_x=True)

    def run_install(self) -> QProcess | None:
        """
        Run a plugin's 'install-script' asynchronously.
        """

        if self.install_script is None:
            return None
        return self.__run_script(self.install_script, set_x=True)

    def run_uninstall(self) -> QProcess | None:
        """
        Run a plugin's 'uninstall-script' asynchronously.
        """

        if self.uninstall_script is None:
            return None
        return self.__run_script(self.uninstall_script, set_x=True)

    def run_purge(self) -> QProcess | None:
        """
        Run a plugin's 'purge-script' asynchronously.
        """

        if self.purge_script is None:
            return None
        return self.__run_script(self.purge_script, set_x=True)

    def run_update_and_install_unprivileged(self) -> QProcess | None:
        """
        Run a plugin's 'update-and-install-script-unprivileged'
        asynchronously.
        """

        if self.update_and_install_script_unprivileged is None:
            return None
        return self.__run_script(
            self.update_and_install_script_unprivileged, set_x=True
        )

    def run_install_unprivileged(self) -> QProcess | None:
        """
        Run a plugin's 'install-script-unprivileged' asynchronously.
        """

        if self.install_script_unprivileged is None:
            return None
        return self.__run_script(self.install_script_unprivileged, set_x=True)

    def run_uninstall_unprivileged(self) -> QProcess | None:
        """
        Run a plugin's 'uninstall-script-unprivileged' asynchronously.
        """

        if self.uninstall_script_unprivileged is None:
            return None
        return self.__run_script(self.uninstall_script_unprivileged, set_x=True)

    def run_purge_unprivileged(self) -> QProcess | None:
        """
        Run a plugin's 'purge-script-unprivileged' asynchronously.
        """

        if self.purge_script_unprivileged is None:
            return None
        return self.__run_script(self.purge_script_unprivileged, set_x=True)

    def run_launch(self, extra_args: str | None = None) -> QProcess | None:
        """
        Run a plugin's 'launch-script' asynchronously, detached from the
        parent so the parent can terminate without terminating the child.
        """

        if extra_args is None:
            return self.__run_script(self.launch_script, detach=True)
        return self.__run_script(
            self.launch_script + " " + extra_args, detach=True
        )

    def check_installed(self) -> bool:
        """
        Check if the defined package is installed by running the
        'install-status' script synchronously with subprocess.run.
        """

        check_process = subprocess.run(
            [
                "/usr/bin/bash",
                "-c",
                "--",
                self.install_status,
            ],
            check=False,
            capture_output=True,
        )
        if check_process.returncode == 0:
            return True
        return False

    def check_capability(self) -> str:
        """
        Check if a package can be installed on the current machine by running
        the 'capability' script synchronously with subprocess.run.
        """

        capability_process = subprocess.run(
            [
                "/usr/bin/bash",
                "-c",
                "--",
                self.capability,
            ],
            check=False,
            capture_output=True,
        )
        if capability_process.returncode == 0:
            return ""
        capability_process_str = capability_process.stdout.decode(
            encoding="utf-8"
        )
        if capability_process_str.strip() == "":
            return "Unsupported on this system."
        return capability_process_str

    def check_mod_unprivileged(self) -> bool:
        """
        Check if a package can be modified without administrative privileges
        by running the 'unprivileged-check-cmd' script synchronously with
        subprocess.run. Caches command results to improve performance.
        """

        assert self.unprivileged_check_script is not None

        if self.unprivileged_check_script in unprivileged_check_cache:
            return unprivileged_check_cache[self.unprivileged_check_script]

        unprivileged_check_process = subprocess.run(
            [
                "/usr/bin/bash",
                "-c",
                "--",
                self.unprivileged_check_script,
            ],
            check=False,
            capture_output=True,
        )

        if unprivileged_check_process.returncode == 0:
            unprivileged_check_cache[self.unprivileged_check_script] = False
            return False
        unprivileged_check_cache[self.unprivileged_check_script] = True
        return True


class ChoicePlugin(QObject):
    """
    Represents a browser-choice plugin.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        product_name: str,
        product_category: str,
        product_website: str,
        product_logo: QPixmap,
        vendor_name: str,
        vendor_website: str,
        vendor_logo: QPixmap,
        wiki_link: str,
        is_official_plugin: bool,
        repo_list: list[ChoicePluginRepo],
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.product_name: str = product_name
        self.product_category: str = product_category
        self.product_website: str = product_website
        self.product_logo: QPixmap = product_logo
        self.vendor_name: str = vendor_name
        self.vendor_website: str = vendor_website
        self.vendor_logo: QPixmap = vendor_logo
        self.wiki_link: str = wiki_link
        self.is_official_plugin: bool = is_official_plugin
        self.repo_list: list[ChoicePluginRepo] = repo_list


class ChoicePluginCategory(QObject):
    """
    Represents a group of plugins that fall into the same category. These
    categories are defined by the 'product-category' key in plugins.
    """

    def __init__(self, category_name: str, parent: QObject | None = None):
        super().__init__(parent)

        self.category_name = category_name
        self.plugin_list: list[ChoicePlugin] = []

    def add_plugin(self, plugin: ChoicePlugin) -> None:
        """
        Adds a plugin to the category.
        """

        if plugin.product_category != self.category_name:
            raise ValueError(
                "Mismatch between category object and plugin category"
            )
        self.plugin_list.append(plugin)


def throw_config_error(config_file: Path, error_reason: str) -> None:
    """
    Convenience function for throwing exceptions related to config file
    parsing.
    """

    raise ValueError(
        f"Invalid config file '{str(config_file)}' " f"({error_reason})"
    )


def load_image(
    image_path_str: str, config_file: Path, image_type: str
) -> QPixmap:
    """
    Loads an image from the specified path. Throws an exception specifying the
    problematic config file and image type if something goes wrong.
    """

    logo_file: Path = Path(image_path_str)
    if not logo_file.is_file():
        throw_config_error(config_file, f"{image_type} does not exist")
    logo_image: QImage = QImage(image_path_str)
    if logo_image.isNull():
        throw_config_error(config_file, f"{image_type} could not be loaded")
    logo_pixmap: QPixmap = QPixmap.fromImage(logo_image)
    return logo_pixmap


# pylint: disable=too-many-locals,too-many-branches,too-many-statements
def parse_config_file(config_file: Path) -> ChoicePlugin:
    """
    Parses a single plugin config file and returns the plugin it defines.
    """

    detect_comment_regex: re.Pattern[str] = re.compile(r"\s*#")
    detect_header_regex: re.Pattern[str] = re.compile(r"\[.*]\Z")
    hit_product_header: bool = False
    hit_repo_header: bool = False
    current_repo_name: str | None = None

    product_name: str | None = None
    product_category: str | None = None
    product_website: str | None = None
    product_logo: QPixmap | None = None
    vendor_name: str | None = None
    vendor_website: str | None = None
    vendor_logo: QPixmap | None = None
    wiki_link: str | None = None
    is_official_plugin: bool | None = None
    repo_list: list[ChoicePluginRepo] = []

    repo_method_name: str | None = None
    repo_method_name_short: str | None = None
    repo_method_subtext: str | None = None
    repo_method_logo: QPixmap | None = None
    repo_method_type: str | None = None
    repo_install_warn_text: str | None = None
    repo_unprivileged_check_script: str | None = None
    repo_update_and_install_script: str | None = None
    repo_install_script: str | None = None
    repo_uninstall_script: str | None = None
    repo_purge_script: str | None = None
    repo_update_and_install_script_unprivileged: str | None = None
    repo_install_script_unprivileged: str | None = None
    repo_uninstall_script_unprivileged: str | None = None
    repo_purge_script_unprivileged: str | None = None
    repo_launch_script: str | None = None
    repo_install_status: str | None = None
    repo_capability: str | None = None

    with open(config_file, "r", encoding="utf-8") as conf_stream:
        for line in conf_stream:
            line = line.strip()
            if line == "":
                continue

            if detect_comment_regex.match(line):
                continue

            if detect_header_regex.match(line):
                current_header_name = line[1 : len(line) - 1]
                if current_header_name == "product":
                    if not hit_product_header:
                        hit_product_header = True
                    else:
                        throw_config_error(
                            config_file, "multiple product headers hit"
                        )
                    continue
                if current_header_name.startswith("repo:"):
                    if not hit_product_header:
                        throw_config_error(
                            config_file,
                            "repo headers found before product header",
                        )

                    if hit_repo_header:
                        assert current_repo_name is not None
                        new_repo: ChoicePluginRepo = ChoicePluginRepo(
                            config_file=config_file,
                            internal_id=current_repo_name,
                            method_name=repo_method_name,
                            method_name_short=repo_method_name_short,
                            method_type=repo_method_type,
                            method_subtext=repo_method_subtext,
                            method_logo=repo_method_logo,
                            install_warn_text=repo_install_warn_text,
                            unprivileged_check_script=(
                                repo_unprivileged_check_script
                            ),
                            update_and_install_script=(
                                repo_update_and_install_script
                            ),
                            install_script=repo_install_script,
                            uninstall_script=repo_uninstall_script,
                            purge_script=repo_purge_script,
                            update_and_install_script_unprivileged=(
                                repo_update_and_install_script_unprivileged
                            ),
                            install_script_unprivileged=(
                                repo_install_script_unprivileged
                            ),
                            uninstall_script_unprivileged=(
                                repo_uninstall_script_unprivileged
                            ),
                            purge_script_unprivileged=(
                                repo_purge_script_unprivileged
                            ),
                            launch_script=repo_launch_script,
                            install_status=repo_install_status,
                            capability=repo_capability,
                        )
                        repo_list.append(new_repo)

                    hit_repo_header = True
                    current_repo_name = current_header_name.split(
                        ":",
                        maxsplit=1,
                    )[1]
                    continue
                throw_config_error(
                    config_file,
                    f"unrecognized header '{current_header_name}'",
                )

            if not "=" in line:
                throw_config_error(config_file, "non-header line missing '='")
            line_parts: list[str] = line.split("=", maxsplit=1)
            line_key: str = line_parts[0]
            line_val: str = line_parts[1]

            if not hit_product_header:
                throw_config_error(config_file, "config lines before headers")
            elif hit_product_header and not hit_repo_header:
                match line_key:
                    case "product-name":
                        product_name = str_or_none(line_val)
                    case "product-category":
                        product_category = str_or_none(line_val)
                    case "product-website":
                        product_website = str_or_none(line_val)
                    case "product-logo":
                        product_logo = load_image(
                            line_val, config_file, "product logo"
                        )
                    case "vendor-name":
                        vendor_name = str_or_none(line_val)
                    case "vendor-website":
                        vendor_website = str_or_none(line_val)
                    case "vendor-logo":
                        vendor_logo = load_image(
                            line_val, config_file, "vendor logo"
                        )
                    case "wiki":
                        wiki_link = str_or_none(line_val)
                    case "official-plugin":
                        if line_val.lower() == "yes":
                            is_official_plugin = True
                        elif line_val.lower() == "no":
                            is_official_plugin = False
                        else:
                            throw_config_error(
                                config_file,
                                "'official-plugin' boolean not set to 'yes' "
                                "or 'no'",
                            )
            else:
                match line_key:
                    case "method-name":
                        repo_method_name = str_or_none(line_val)
                    case "method-name-short":
                        repo_method_name_short = str_or_none(line_val)
                    case "method-subtext":
                        repo_method_subtext = str_or_none(line_val)
                    case "method-logo":
                        repo_method_logo = load_image(
                            line_val,
                            config_file,
                            f"method logo for '{current_repo_name}'",
                        )
                    case "method-type":
                        repo_method_type = str_or_none(line_val)
                    case "install-warn-text":
                        repo_install_warn_text = str_or_none(line_val)
                    case "unprivileged-check-script":
                        repo_unprivileged_check_script = str_or_none(line_val)
                    case "update-and-install-script":
                        repo_update_and_install_script = str_or_none(line_val)
                    case "install-script":
                        repo_install_script = str_or_none(line_val)
                    case "uninstall-script":
                        repo_uninstall_script = str_or_none(line_val)
                    case "purge-script":
                        repo_purge_script = str_or_none(line_val)
                    case "update-and-install-script-unprivileged":
                        repo_update_and_install_script_unprivileged = (
                            str_or_none(line_val)
                        )
                    case "install-script-unprivileged":
                        repo_install_script_unprivileged = str_or_none(line_val)
                    case "uninstall-script-unprivileged":
                        repo_uninstall_script_unprivileged = str_or_none(
                            line_val
                        )
                    case "purge-script-unprivileged":
                        repo_purge_script_unprivileged = str_or_none(line_val)
                    case "launch-script":
                        repo_launch_script = str_or_none(line_val)
                    case "install-status":
                        repo_install_status = str_or_none(line_val)
                    case "capability":
                        repo_capability = str_or_none(line_val)

    if not hit_product_header and not hit_repo_header:
        throw_config_error(config_file, "no headers found")
    elif hit_product_header and not hit_repo_header:
        throw_config_error(
            config_file, "product header found but no repo headers"
        )

    new_repo = ChoicePluginRepo(
        config_file=config_file,
        internal_id=current_repo_name,
        method_name=repo_method_name,
        method_name_short=repo_method_name_short,
        method_subtext=repo_method_subtext,
        method_logo=repo_method_logo,
        method_type=repo_method_type,
        install_warn_text=repo_install_warn_text,
        unprivileged_check_script=repo_unprivileged_check_script,
        update_and_install_script=repo_update_and_install_script,
        install_script=repo_install_script,
        uninstall_script=repo_uninstall_script,
        purge_script=repo_purge_script,
        update_and_install_script_unprivileged=(
            repo_update_and_install_script_unprivileged
        ),
        install_script_unprivileged=repo_install_script_unprivileged,
        uninstall_script_unprivileged=repo_uninstall_script_unprivileged,
        purge_script_unprivileged=repo_purge_script_unprivileged,
        launch_script=repo_launch_script,
        install_status=repo_install_status,
        capability=repo_capability,
    )
    repo_list.append(new_repo)

    if product_name is None:
        throw_config_error(config_file, "no product name")
    elif product_category is None:
        throw_config_error(config_file, "no product category")
    elif product_website is None:
        throw_config_error(config_file, "no product website")
    elif product_logo is None:
        throw_config_error(config_file, "no product logo")
    elif vendor_name is None:
        throw_config_error(config_file, "no vendor name")
    elif vendor_website is None:
        throw_config_error(config_file, "no vendor website")
    elif vendor_logo is None:
        throw_config_error(config_file, "no vendor logo")
    elif wiki_link is None:
        throw_config_error(config_file, "no wiki link")
    elif is_official_plugin is None:
        throw_config_error(config_file, "no official plugin indicator")

    assert product_name is not None
    assert product_category is not None
    assert product_website is not None
    assert product_logo is not None
    assert vendor_name is not None
    assert vendor_website is not None
    assert vendor_logo is not None
    assert wiki_link is not None
    assert is_official_plugin is not None

    output_plugin: ChoicePlugin = ChoicePlugin(
        product_name=product_name,
        product_category=product_category,
        product_website=product_website,
        product_logo=product_logo,
        vendor_name=vendor_name,
        vendor_website=vendor_website,
        vendor_logo=vendor_logo,
        wiki_link=wiki_link,
        is_official_plugin=is_official_plugin,
        repo_list=repo_list,
    )
    return output_plugin


def parse_config_dir(config_dir: Path) -> list[ChoicePluginCategory]:
    """
    Parses all plugin config files from the specified directory.
    """

    config_file_list: list[Path] = []
    for config_file in config_dir.iterdir():
        if not config_file.is_file():
            continue
        config_file_list.append(config_file)
    config_file_list.sort()

    plugin_list: list[ChoicePlugin] = []
    for config_file in config_file_list:
        plugin_list.append(parse_config_file(config_file))

    category_dict: dict[str, ChoicePluginCategory] = {}
    for plugin in plugin_list:
        if not plugin.product_category in category_dict:
            category_dict[plugin.product_category] = ChoicePluginCategory(
                plugin.product_category,
            )
        category_dict[plugin.product_category].add_plugin(plugin)

    return list(category_dict.values())
