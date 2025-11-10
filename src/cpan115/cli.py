from typing import Optional

import click

from . import Pan115OpenAPI


class AliasedGroup(click.Group):
    """A click Group that supports registering aliases for commands and
    shows each command once in help with its aliases listed in parentheses.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aliases: dict[str, str] = {}

    def add_alias(self, alias: str, command_name: str) -> None:
        self._aliases[alias] = command_name

    def get_command(self, ctx, cmd_name):
        # First try normal lookup
        rv = super().get_command(ctx, cmd_name)
        if rv is not None:
            return rv
        # Then try aliases mapping
        real = self._aliases.get(cmd_name)
        if real:
            return super().get_command(ctx, real)
        return None

    def list_commands(self, ctx):
        # Only list real commands (no duplicate alias names)
        return sorted(self.commands.keys())

    def format_commands(self, ctx, formatter):
        """Customize the help output to show aliases next to command name."""
        commands = []
        for name in self.list_commands(ctx):
            cmd = self.get_command(ctx, name)
            if cmd is None:
                continue
            # collect aliases that map to this command
            aliases = [a for a, real in self._aliases.items() if real == name]
            if aliases:
                display = f"{name} ({', '.join(aliases)})"
            else:
                display = name
            commands.append((display, cmd.get_short_help_str()))

        if commands:
            with formatter.section("Commands"):
                formatter.write_dl(commands)


@click.group(cls=AliasedGroup)
def cli():
    """Pan115 CLI 工具"""
    pass


@cli.command("upload")
@click.argument("path", type=click.Path(exists=True))
@click.option("--target", default="0", help="目标文件夹ID，默认 '0'（根目录）")
@click.option("--create-folder/--no-create-folder", default=True, help="是否在目标位置创建同名文件夹（仅文件夹上传时有效）")
@click.option("--show-progress/--no-progress", default=True, help="显示上传进度")
def upload(path: str, target: str, create_folder: bool, show_progress: bool):
    """上传文件或文件夹到网盘（自动判断类型）"""
    api = Pan115OpenAPI()
    info = api.uploader.upload(path=path, target=target, create_folder=create_folder, show_progress=show_progress)
    if info is True:
        click.echo(f"{path} 上传成功")
    elif info is False:
        click.echo(f"{path} 上传失败: {info}")
    else:
        if isinstance(info, dict):
            info.pop("data", None)
        click.echo(f"{path} 上传结果: {info}")


@cli.command("download")
@click.argument("target")
@click.argument("save_path", required=False)
@click.option("--filename", default=None, help="保存为的文件名（仅文件下载时有效，默认使用云端文件名）")
@click.option("--overwrite", is_flag=True, default=False, help="如果存在则覆盖")
@click.option("--show-progress/--no-progress", default=True, help="是否显示下载进度")
@click.option("--create-folder/--no-create-folder", default=True, help="是否创建同名文件夹（仅文件夹下载时有效）")
@click.option("--mode", type=click.Choice(["concurrent", "loop"]), default="concurrent", help="下载模式（仅文件夹下载时有效）")
@click.option("--max-workers", default=5, type=int, help="并发下载线程数（mode=concurrent 时生效）")
def download(
    target: str, save_path: Optional[str], filename: Optional[str], overwrite: bool, show_progress: bool, create_folder: bool, mode: str, max_workers: int
):
    """下载文件或文件夹（自动判断类型）

    TARGET 可以是：
    - 文件或文件夹ID（整数）
    - 云端文件路径（字符串，如 "/资料/报告.pdf"）
    """
    api = Pan115OpenAPI()
    final_save_path = save_path or "."

    # 尝试转换为整数ID
    try:
        target_id = int(target)
    except ValueError:
        # 如果不能转换为整数，说明是路径字符串
        target_id = target

    return api.downloader.download_auto(
        target=target_id,
        save_path=final_save_path,
        filename=filename,
        show_progress=show_progress,
        overwrite=overwrite,
        create_folder=create_folder,
        mode=mode,
        max_workers=max_workers,
    )


cli.add_alias("up", "upload")
cli.add_alias("down", "download")

if __name__ == "__main__":
    cli()
