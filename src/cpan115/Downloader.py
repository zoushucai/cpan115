import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import httpx
from pydantic import validate_call
from tqdm import tqdm

from .Auth import Auth, log
from .File import File
from .model.Base import UserInfoModel


class Downloader:
    def __init__(self, auth: Auth, userinfo: UserInfoModel | None = None):
        self.auth = auth
        self.file = File(auth, userinfo)
        self.userinfo = userinfo
        self._HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://115.com/",
        }

    @validate_call
    def download(
        self,
        pick_code: str,
        save_path: str | None = None,
        *,
        filename: str | None = None,
        show_progress: bool = True,
        chunk_size: int = 8192,
        overwrite: bool = False,
        relative_path: str | None = None,
    ) -> dict:
        """
        下载单个文件

        Args:
            pick_code: 文件提取码
            save_path: 保存路径（文件夹路径），默认为当前目录
            filename: 保存的文件名，如果不指定则使用云端文件名
            show_progress: 是否显示下载进度条
            chunk_size: 下载块大小（字节），默认8KB
            overwrite: 是否覆盖已存在的文件，默认False
            relative_path: 云端相对路径（用于进度条显示），如果不指定则使用文件名

        Returns:
            dict: 下载结果信息，包含：
                - success: 是否成功
                - pick_code: 文件提取码
                - file_name: 文件名
                - file_size: 文件大小（字节）
                - save_path: 保存的完整路径
                - message: 消息

        Raises:
            ValueError: 当参数无效时
            RuntimeError: 当下载失败时
        """
        try:
            # 1. 获取下载地址
            resp = self.file.downurl(pick_code=pick_code)

            if not resp.get("state"):
                raise RuntimeError(f"获取下载地址失败: {resp}")

            # 2. 解析下载信息
            # data 是一个字典，键是文件ID，值是文件信息
            data_dict = resp.get("data", {})
            if not data_dict:
                raise RuntimeError("下载地址为空，请检查提取码是否正确, 不能传入文件夹")

            # 获取第一个（也是唯一的）文件信息
            file_info = next(iter(data_dict.values()), None)
            if not file_info:
                raise RuntimeError("无法解析文件信息")

            download_url = file_info.get("url", {}).get("url")
            file_name = file_info.get("file_name", "unknown")
            file_size = int(file_info.get("file_size", 0))

            if not download_url:
                raise RuntimeError("未能获取有效的下载URL")

            # 3. 确定保存路径
            save_dir = Path(save_path or ".")
            save_dir.mkdir(parents=True, exist_ok=True)

            # 确定文件名
            final_filename = filename or file_name
            full_path = save_dir / final_filename

            # 检查文件是否已存在
            if full_path.exists() and not overwrite:
                log.warning(f"文件已存在: {full_path}")
                return {
                    "success": False,
                    "pick_code": pick_code,
                    "file_name": final_filename,
                    "file_size": file_size,
                    "save_path": str(full_path),
                    "message": "文件已存在，跳过下载（设置 overwrite=True 可覆盖）",
                }

            # 4. 下载文件
            progress_desc = relative_path or final_filename
            self._download_file(
                url=download_url,
                save_path=full_path,
                file_size=file_size,
                show_progress=show_progress,
                chunk_size=chunk_size,
                progress_desc=progress_desc,
            )

            return {
                "success": True,
                "pick_code": pick_code,
                "file_name": final_filename,
                "file_size": file_size,
                "save_path": str(full_path),
                "message": "下载成功",
            }

        except Exception as e:
            return {
                "success": False,
                "pick_code": pick_code,
                "file_name": filename or "unknown",
                "file_size": 0,
                "save_path": "",
                "message": f"下载失败: {str(e)}",
            }

    @validate_call
    def download_by_path(
        self,
        path: str,
        save_path: str | None = None,
        *,
        filename: str | None = None,
        show_progress: bool = True,
        chunk_size: int = 8192,
        overwrite: bool = False,
    ) -> dict:
        """通过云端绝对路径下载单个文件（无需手动提供提取码）

        此方法会调用 get_info(path=...) 获取文件信息，并提取 pick_code 后复用 download() 进行下载。

        Args:
            path: 云端文件的绝对路径（例如 "/资料/报告.pdf"），不支持文件夹
            save_path: 保存目录，默认当前目录
            filename: 保存文件名，默认使用云端文件名
            show_progress: 是否显示进度条
            chunk_size: 下载块大小（字节）
            overwrite: 是否覆盖已存在的文件

        Returns:
            dict: 下载结果信息（同 download 返回结构）
        """
        # 规范化路径：允许传相对路径，这里统一转为以 / 开头
        cloud_path = path.strip()
        if not cloud_path:
            return {"success": False, "message": "路径不能为空"}
        if cloud_path != "/" and not cloud_path.startswith("/"):
            cloud_path = "/" + cloud_path

        # 根路径不允许作为文件
        if cloud_path == "/":
            return {"success": False, "message": "不能传递根目录路径 /"}

        # 查询文件信息
        info_resp = self.file.get_info(path=cloud_path)
        if not info_resp.get("state"):
            return {"success": False, "message": f"获取文件信息失败: {info_resp}"}

        data = info_resp.get("data", {}) or {}
        # file_category: 按现有约定，"0" 为文件夹，文件应为非 "0"（通常为 "1"）
        if str(data.get("file_category", "")) == "0":
            return {"success": False, "message": "指定路径是文件夹，请提供文件路径"}

        pick_code = data.get("pick_code") or data.get("pc")
        cloud_file_name = data.get("file_name") or filename or "unknown"
        if not pick_code:
            return {"success": False, "message": "未能从文件信息中获取提取码，无法下载"}

        # 复用已有下载逻辑
        return self.download(
            pick_code=pick_code,
            save_path=save_path,
            filename=filename or cloud_file_name,
            show_progress=show_progress,
            chunk_size=chunk_size,
            overwrite=overwrite,
        )

    def _download_file(
        self,
        url: str,
        save_path: Path,
        file_size: int,
        show_progress: bool,
        chunk_size: int,
        progress_desc: str | None = None,
    ):
        """
        实际下载文件的内部方法

        Args:
            url: 下载URL
            save_path: 保存路径
            file_size: 文件大小
            show_progress: 是否显示进度条
            chunk_size: 下载块大小
            progress_desc: 进度条显示的描述（如果不指定则使用文件名）
        """

        # 使用 httpx.Client 进行流式下载（更稳定，可复用连接）
        with httpx.Client(headers=self._HEADERS, follow_redirects=True, timeout=60.0) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()

                progress = None
                if show_progress and file_size > 0:
                    desc = progress_desc or save_path.name
                    progress = tqdm(
                        total=file_size,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=desc,
                    )

                try:
                    with open(save_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                if progress:
                                    progress.update(len(chunk))
                except Exception as e:
                    if progress:
                        progress.close()
                    if save_path.exists():
                        save_path.unlink()
                    raise RuntimeError(f"下载过程中发生错误: {e}") from e
                finally:
                    if progress:
                        progress.close()

    # -------- 通用帮助方法 --------
    def _get_all_items(self, cid: int, show_dir: int = 1, limit: int = 1150) -> list[dict]:
        """分页获取目录下所有项目并返回合并后的列表"""
        all_items: list[dict] = []
        offset = 0
        while True:
            resp = self.file.files(cid=cid, show_dir=show_dir, limit=limit, offset=offset)
            if not resp.get("state", False):
                raise RuntimeError(f"获取文件列表失败: {resp}")
            page = resp.get("data", []) or []
            if not page:
                break
            all_items.extend(page)
            count = resp.get("count", 0)
            if len(all_items) >= count or len(page) < limit:
                break
            offset += len(page)
        return all_items

    def _make_error(self, folder_id: int | None, message: str, error: str | None = None) -> dict:
        """统一错误返回结构"""
        return {"success": False, "folder_id": folder_id, "message": message, "error": error or message}

    @validate_call
    def _download_folder_loop(
        self,
        file_id: int,
        save_path: str | None = None,
        *,
        show_progress: bool = True,
        chunk_size: int = 8192,
        overwrite: bool = False,
        create_folder: bool = True,
    ) -> dict:
        """下载整个文件夹（递归下载所有文件）"""

        # 1. 获取文件夹信息并验证
        folder_info_resp = self.file.get_info(file_id=file_id)
        if not folder_info_resp.get("state"):
            return self._make_error(file_id, "获取文件夹信息失败")

        folder_data = folder_info_resp.get("data", {})
        if folder_data.get("file_category", "0") != "0":
            return self._make_error(file_id, "指定的ID不是文件夹")

        folder_name = folder_data.get("file_name", "unknown_folder")

        # 2. 确定保存路径
        base_dir = Path(save_path or ".")
        if create_folder:
            base_dir = base_dir / folder_name
        base_dir.mkdir(parents=True, exist_ok=True)

        # 3. 递归获取所有文件
        all_files = self._collect_all_files(file_id, base_dir)

        # 4. 下载所有文件
        results = []
        downloaded_count = 0

        for idx, file_item in enumerate(all_files, 1):
            try:
                file_item["target_path"].parent.mkdir(parents=True, exist_ok=True)

                result = self.download(
                    pick_code=file_item["pick_code"],
                    save_path=str(file_item["target_path"].parent),
                    filename=file_item["file_name"],
                    show_progress=show_progress,
                    chunk_size=chunk_size,
                    overwrite=overwrite,
                    relative_path=file_item["relative_path"],
                )
                result["relative_path"] = file_item["relative_path"]
                results.append(result)
                if result.get("success"):
                    downloaded_count += 1

            except Exception as e:
                results.append(
                    {
                        "success": False,
                        "pick_code": file_item.get("pick_code", ""),
                        "file_name": file_item.get("file_name", "unknown"),
                        "relative_path": file_item.get("relative_path", ""),
                        "message": str(e),
                    }
                )

        # 5. 统计结果
        failed_count = len(all_files) - downloaded_count

        return {
            "success": failed_count == 0,
            "folder_id": file_id,
            "folder_name": folder_name,
            "save_path": str(base_dir),
            "total_files": len(all_files),
            "downloaded": downloaded_count,
            "failed": failed_count,
            "results": results,
        }

    def _collect_all_files(self, folder_id: int, base_path: Path, current_relative_path: str = "") -> list[dict]:
        """递归收集文件夹中的所有文件"""
        all_files: list[dict] = []
        try:
            items = self._get_all_items(folder_id, show_dir=1)

            for item in items:
                fc, fn, fid, pc = str(item.get("fc", "")), str(item.get("fn", "")), item.get("fid"), item.get("pc")
                relative = f"{current_relative_path}/{fn}" if current_relative_path else fn

                if fc == "0" and fid:
                    try:
                        all_files.extend(self._collect_all_files(int(fid), base_path, relative))
                    except Exception:
                        pass
                elif fc == "1" and pc:
                    all_files.append(
                        {
                            "file_id": fid,
                            "file_name": fn,
                            "pick_code": pc,
                            "relative_path": relative,
                            "target_path": base_path / Path(relative),
                        }
                    )
        except Exception:
            # print(f"收集文件夹 {folder_id} 内容时发生错误: {e}")
            pass
        return all_files

    @validate_call
    def _download_folder_concurrent(
        self,
        file_id: int,
        save_path: str | None = None,
        *,
        show_progress: bool = True,
        chunk_size: int = 8192,
        overwrite: bool = False,
        create_folder: bool = True,
        max_workers: int = 5,
    ) -> dict:
        """多线程并发下载整个文件夹"""
        # 1. 获取文件夹信息并验证
        folder_info_resp = self.file.get_info(file_id=file_id)
        if not folder_info_resp.get("state"):
            return self._make_error(file_id, "获取文件夹信息失败")

        folder_data = folder_info_resp.get("data", {})
        if folder_data.get("file_category", "0") != "0":
            return self._make_error(file_id, "指定的ID不是文件夹")

        folder_name = folder_data.get("file_name", "unknown_folder")

        # 2. 确定保存路径并收集文件
        base_dir = Path(save_path or ".")
        if create_folder:
            base_dir = base_dir / folder_name
        base_dir.mkdir(parents=True, exist_ok=True)

        all_files = self._collect_all_files(file_id, base_dir)

        if not all_files:
            return {
                "success": True,
                "folder_id": file_id,
                "folder_name": folder_name,
                "save_path": str(base_dir),
                "total_files": 0,
                "downloaded": 0,
                "failed": 0,
                "results": [],
                "message": "文件夹为空",
            }

        # 3. 并发下载
        results = []
        downloaded_count = 0
        results_lock = Lock()

        def _worker(item):
            item["target_path"].parent.mkdir(parents=True, exist_ok=True)
            res = self.download(
                pick_code=item["pick_code"],
                save_path=str(item["target_path"].parent),
                filename=item["file_name"],
                show_progress=False,
                chunk_size=chunk_size,
                overwrite=overwrite,
                relative_path=item.get("relative_path"),
            )
            res["relative_path"] = item.get("relative_path")
            return res

        # 创建总体进度条
        overall_progress = tqdm(total=len(all_files), desc="总进度", unit="files") if show_progress else None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {executor.submit(_worker, it): it for it in all_files}
            for future in as_completed(future_to_item):
                it = future_to_item[future]
                try:
                    r = future.result()
                    with results_lock:
                        results.append(r)
                        if r.get("success"):
                            downloaded_count += 1
                        if overall_progress:
                            status = "✓" if r.get("success") else "✗"
                            overall_progress.set_postfix_str(f"{status} {r.get('relative_path', r.get('file_name'))}")
                            overall_progress.update(1)
                except Exception as e:
                    with results_lock:
                        results.append(
                            {
                                "success": False,
                                "pick_code": it.get("pick_code", ""),
                                "file_name": it.get("file_name", "unknown"),
                                "relative_path": it.get("relative_path", ""),
                                "message": str(e),
                            }
                        )
                        if overall_progress:
                            overall_progress.update(1)

        if overall_progress:
            overall_progress.close()

        failed_count = len(all_files) - downloaded_count

        return {
            "success": failed_count == 0,
            "folder_id": file_id,
            "folder_name": folder_name,
            "save_path": str(base_dir),
            "total_files": len(all_files),
            "downloaded": downloaded_count,
            "failed": failed_count,
            "results": results,
        }

    @validate_call
    def download_folder(
        self,
        file_id: int,
        save_path: str | None = None,
        *,
        show_progress: bool = True,
        chunk_size: int = 8192,
        overwrite: bool = False,
        create_folder: bool = True,
        mode: str = "concurrent",
        max_workers: int | None = 5,
    ) -> dict:
        """下载文件夹

        下载整个文件

        Args:
            file_id: 文件夹ID
            save_path: 保存路径（文件夹路径），默认为当前目录
            show_progress: 是否显示下载进度条
            chunk_size: 下载块大小（字节），默认8KB
            overwrite: 是否覆盖已存在的文件，默认False
            create_folder: 是否在保存路径下创建以文件夹名命名的子文件夹，默认True
            mode: 下载模式, "loop"（循环下载）、"concurrent"（多线程下载）
            max_workers: 多线程下载时的最大线程数，仅在 mode="concurrent" 时有效

        Returns:
            下载结果信息
        """
        try:
            if mode == "concurrent":
                if max_workers is None or max_workers < 1:
                    max_workers = max(1, os.cpu_count() or 1)

                resp = self._download_folder_concurrent(
                    file_id=file_id,
                    save_path=save_path,
                    show_progress=show_progress,
                    chunk_size=chunk_size,
                    overwrite=overwrite,
                    create_folder=create_folder,
                    max_workers=max_workers,
                )
            elif mode == "loop":
                resp = self._download_folder_loop(
                    file_id=file_id,
                    save_path=save_path,
                    show_progress=show_progress,
                    chunk_size=chunk_size,
                    overwrite=overwrite,
                    create_folder=create_folder,
                )

            else:
                raise ValueError(f"不支持的下载模式: {mode}")

            # 打印总结信息
            total_files = resp.get("total_files", 0)
            downloaded = resp.get("downloaded", 0)
            failed = resp.get("failed", 0)

            log.info(f"下载完成！总计: {total_files}，成功: {downloaded}，失败: {failed}")
            return resp
        except Exception as e:
            return self._make_error(file_id, f"下载文件夹失败: {str(e)}", str(e))

    @validate_call
    def download_auto(
        self,
        target: int | str,
        save_path: str | None = None,
        *,
        filename: str | None = None,
        show_progress: bool = True,
        chunk_size: int = 8192,
        overwrite: bool = False,
        create_folder: bool = True,
        mode: str = "concurrent",
        max_workers: int | None = 5,
    ) -> dict:
        """自动判断目标类型并下载文件或文件夹

        根据 target 参数自动判断是文件ID、文件夹ID还是文件路径，并调用相应的下载方法。

        Args:
            target: 下载目标，可以是：
                - 整数：文件或文件夹ID
                - 字符串：云端文件的绝对路径（例如 "/资料/报告.pdf"）
            save_path: 保存路径（文件夹路径），默认为当前目录
            filename: 保存的文件名（仅文件下载时有效），如果不指定则使用云端文件名
            show_progress: 是否显示下载进度条
            chunk_size: 下载块大小（字节），默认8KB
            overwrite: 是否覆盖已存在的文件，默认False
            create_folder: 是否在保存路径下创建同名文件夹（仅文件夹下载时有效），默认True
            mode: 下载模式（仅文件夹下载时有效），"loop"（循环下载）或 "concurrent"（多线程下载）
            max_workers: 多线程下载时的最大线程数（仅文件夹下载时有效）

        Returns:
            dict: 下载结果信息

        Raises:
            ValueError: 当参数无效时
            RuntimeError: 当下载失败时

        Examples:
            >>> downloader = Downloader(auth)
            >>> # 通过ID下载文件
            >>> downloader.download_auto(123456)
            >>> # 通过路径下载文件
            >>> downloader.download_auto("/资料/报告.pdf")
            >>> # 下载文件夹
            >>> downloader.download_auto(789012, mode="concurrent", max_workers=10)
        """
        # 情况1：target 是字符串路径
        if isinstance(target, str):
            # 通过路径下载（只支持文件）
            return self.download_by_path(
                path=target,
                save_path=save_path,
                filename=filename,
                show_progress=show_progress,
                chunk_size=chunk_size,
                overwrite=overwrite,
            )

        # 情况2：target 是整数ID，需要查询类型
        try:
            file_id = int(target)
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的目标参数: {target}") from e

        # 获取文件/文件夹信息
        info_resp = self.file.get_info(file_id=file_id)
        if not info_resp.get("state"):
            raise RuntimeError(f"获取文件信息失败: {info_resp}")

        data = info_resp.get("data", {}) or {}
        file_category = str(data.get("file_category", "1"))

        # 判断是文件夹还是文件
        if file_category == "0":
            # 文件夹
            return self.download_folder(
                file_id=file_id,
                save_path=save_path,
                show_progress=show_progress,
                chunk_size=chunk_size,
                overwrite=overwrite,
                create_folder=create_folder,
                mode=mode,
                max_workers=max_workers,
            )
        else:
            # 文件
            pick_code = data.get("pick_code") or data.get("pc")
            if not pick_code:
                raise RuntimeError("无法从文件信息中获取提取码")

            return self.download(
                pick_code=pick_code,
                save_path=save_path,
                filename=filename,
                show_progress=show_progress,
                chunk_size=chunk_size,
                overwrite=overwrite,
            )
