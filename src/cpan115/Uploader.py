import base64
import copy
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

import alibabacloud_oss_v2 as oss
from pydantic import validate_call
from tqdm import tqdm

from .Auth import Auth
from .File import File
from .model.Base import UserInfoModel
from .model.model import FileUploadParams
from .utils.Constants import API
from .utils.sha import calc_sha1, calc_sha1_range, calc_sign_val


class Uploader:
    """文件上传操作封装"""

    def __init__(self, auth: Auth, userinfo: UserInfoModel | None = None):
        """初始化

        Args:
            auth: 已授权的 Auth 实例
        """

        self.auth = auth
        self.userinfo = userinfo
        self.file = File(auth, userinfo)
        self._counter = 0
        self._counter_lock = Lock()  # 保护 counter 的线程锁

    @validate_call
    def get_token(self) -> dict:
        """获取上传Token

        获取上传文件所需的Token信息

        参考接口文档:  [/open/upload/get_token](https://www.yuque.com/115yun/open/kzacvzl0g7aiyyn4)


        Returns:
            包含上传Token信息

        """
        resp = self.auth.request_json("GET", API.FilePath.UPLOAD_TOKEN)
        return resp

    @validate_call
    def init(
        self,
        file_name: str,
        file_size: int | None = None,
        target: str | int = "0",
        fileid: str | None = None,
        preid: str | None = None,
        pick_code: str | None = None,
        topupload: int | None = None,
        sign_key: str | None = None,
        sign_val: str | None = None,
    ) -> tuple[dict, dict]:
        """文件上传

        断点续传上传初始化调度接口

        参考接口文档: [/open/upload/init](https://www.yuque.com/115yun/open/ul4mrauo5i2uza0q)

        Args:
            file_name:      文件名
            file_size:      文件大小(字节)
            target:         文件上传目标约定, 文件夹ID
            fileid:        文件sha1值
            preid:        文件前128Ksha1
            pick_code:    上传任务key[非秒传的调度接口返回的pick_code字段]
            topupload:    上传调度文件类型调度标记
            sign_key:     二次认证需要
            sign_val:     二次认证需要(大写)

        Returns:
            tuple[dict, dict]: 包含接口返回的 JSON 和上传初始化参数，返回 (resp, fileinfo)

                - resp: 接口返回的 JSON
                - fileinfo: 上传的参数

        """
        # 如果传入的是本地文件路径，避免重复调用 Path() 并只做一次文件存在检查
        p = Path(file_name)
        is_local_file = p.is_file()

        # 从本地文件补全缺失的信息（仅在传入本地路径时）
        if is_local_file:
            file_size = p.stat().st_size if file_size is None else file_size
            fileid = calc_sha1(str(p)) if fileid is None else fileid
            preid = calc_sha1_range(str(p), 0, 128 * 1024 - 1) if preid is None else preid
            # 提取纯文件名作为云端文件名（不包含路径）
            cloud_file_name = p.name
        else:
            # 如果不是本地文件，假定 file_name 就是云端文件名
            cloud_file_name = file_name

        # sign_key 和 sign_val 必须同时提供或同时为 None
        if (sign_key is None) ^ (sign_val is None):
            raise ValueError("sign_key 和 sign_val 必须同时提供或同时为 None")

        if file_size is None or file_size <= 0:
            raise ValueError("file_size 参数不能为空，且必须为正整数")

        if not fileid:
            raise ValueError("fileid 参数不能为空")

        # 使用 pydantic 模型进行参数校验与规范化
        params = FileUploadParams(
            file_name=cloud_file_name,  # 使用提取的纯文件名
            file_size=file_size,
            target=target,
            fileid=fileid,
            preid=preid,
            pick_code=pick_code,
            topupload=topupload,
            sign_key=sign_key,
            sign_val=sign_val,
        )

        fileinfo = params.model_dump(exclude_none=True)

        resp = self.auth.request_json("POST", API.FilePath.UPLOAD_INIT, data=fileinfo)
        data = self._extract_data(resp)
        status = data.get("status")
        sign_key = data.get("sign_key", "")
        if (status == 2 and sign_key == "") or status == 1:
            # 只有秒传,且不需要二次认证时才打印日志
            with self._counter_lock:
                self._counter += 1
                # print("---------------------------------")
                # print(f"第{self._counter}次上传")
                # print(f"上传初始化参数: {json.dumps(fileinfo, ensure_ascii=False, indent=2)}")
                # print("---------------------------------")
        return resp, fileinfo

    @validate_call
    def resume(self, file_size: int, fileid: str, pick_code: str, *, target: int | str = 0) -> dict:
        """断点续传初始化（

        断点续传上传续传调度接口

        参考接口文档: [/open/upload/resume](https://www.yuque.com/115yun/open/tzvi9sbcg59msddz)

        Args:
            file_size: 文件大小（字节）
            target: 上传目标，支持 'U_1_0' 或文件夹ID
            fileid: 文件 sha1 值
            pick_code: 上传任务 key（续传时必需）

        Returns:
            dict: 接口返回的 JSON
        """
        if not str(target).startswith("U_1_"):
            target = f"U_1_{target}"

        data = {"file_size": file_size, "target": target, "fileid": fileid, "pick_code": pick_code}
        resp = self.auth.request_json("POST", API.FilePath.UPLOAD_RESUME, data=data)
        return resp

    @validate_call
    def init_with_auto_sign(
        self,
        file_name: str,
        file_size: int | None = None,
        target: str | int = "0",
        fileid: str | None = None,
        preid: str | None = None,
        pick_code: str | None = None,
        topupload: int | None = None,
    ) -> dict:
        """调用 init 并在需要二次认证时自动计算并提交 sign_val

        调用 init 接口，并在需要二次认证时自动计算 sign_val 并重新调用 init 接口

        Args:
            file_name:      文件名
            file_size:      文件大小(字节)
            target:         文件上传目标约定, 文件夹ID
            fileid:        文件sha1值
            preid:        文件前128Ksha1
            pick_code:    上传任务key[非秒传的调度接口返回的pick_code字段]
            topupload:    上传调度文件类型调度标记

        Returns:
            响应数据


        """
        resp, fileinfo = self.init(
            file_name=file_name,
            file_size=file_size,
            target=target,
            fileid=fileid,
            preid=preid,
            pick_code=pick_code,
            topupload=topupload,
        )
        item = self._extract_data(resp)

        status = item.get("status")
        code = item.get("code") or resp.get("code")

        # 秒传成功
        if status == 2:
            return resp

        # 判断是否需要二次认证
        sign_check = str(item.get("sign_check"))
        sign_key = str(item.get("sign_key"))
        if (status in {6, 7, 8} or code in {700, 701, 702}) and sign_check and sign_key:
            fileinfo["sign_key"] = sign_key
            fileinfo["sign_val"] = calc_sign_val(file_name, sign_check)

            # 第二次带签名的 init
            resp2, fileinfo2 = self.init(**fileinfo)
            return resp2

        return resp

    # ---------- 上传到 OSS(只支持单文件,且文件大小<5GB) ----------
    @validate_call
    def upload_to_oss(
        self,
        token_data: dict,
        init_data: dict,
        file_path: str,
        *,
        show_progress: bool = True,
    ) -> dict:
        """上传文件到 OSS

        Args:
            token_data:     get_token 接口返回的 data 字段
            init_data:      init/init_with_auto_sign 接口返回的 JSON
            file_path:      本地文件路径
            show_progress:  是否显示上传进度条

        Returns:
            上传结果,只要 {"state": True, ...} 就表示上传成功

        """
        data = self._extract_data(init_data)
        bucket, obj = data.get("bucket"), data.get("object")
        if not (bucket and obj):
            raise ValueError(f"初始化数据缺少 bucket/object: {data}")

        cbobj = data.get("callback", {})
        cb, cb_var = cbobj.get("callback"), cbobj.get("callback_var")
        if not all(isinstance(x, str) for x in (cb, cb_var)):
            raise ValueError(f"回调字段缺失或类型错误: {cbobj}")

        cb_b64 = base64.b64encode(cb.encode()).decode()
        cb_var_b64 = base64.b64encode(cb_var.encode()).decode()

        endpoint = token_data["endpoint"]
        host = endpoint.split("://")[-1]
        region = host.split(".")[0].replace("oss-", "") if host else ""

        credentials_provider = oss.credentials.StaticCredentialsProvider(
            token_data["AccessKeyId"],
            token_data["AccessKeySecret"],
            token_data["SecurityToken"],
        )
        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        cfg.region = region
        client = oss.Client(cfg)

        # 创建进度回调
        progress_fn, bar = self._make_progress_fn(file_path, show_progress)

        result = client.put_object_from_file(
            oss.PutObjectRequest(
                bucket=bucket,  # 存储空间名称
                key=obj,  # 对象名称
                callback=cb_b64,
                callback_var=cb_var_b64,
                progress_fn=progress_fn,
            ),
            file_path,  # 本地文件路径
        )

        if bar:
            bar.close()
            print()

        result_dict = vars(result) if hasattr(result, "__dict__") else {}
        return {"state": True, "message": "文件上传成功", "code": 200, "data": result_dict}

    # ---------- 上传文件 ----------
    @validate_call
    def upload_file(
        self,
        file_name: str,
        file_size: int | None = None,
        target: str | int = "0",
        fileid: str | None = None,
        preid: str | None = None,
        pick_code: str | None = None,
        topupload: int | None = None,
        show_progress: bool = True,
    ) -> bool:
        """上传单个文件到115网盘(仅支持单个文件上传且文件大小小于5GB)

        Args:
            file_name:      文件名或本地文件路径
            file_size:      文件大小(字节) (可选, 若 file_name 是本地路径则可自动计算)
            target:         文件上传目标约定, 文件夹ID (默认根目录0)
            fileid:        文件sha1值 (可选, 若 file_name 是本地路径则可自动计算)
            preid:        文件前128Ksha1 (可选, 若 file_name 是本地路径则可自动计算)
            pick_code:    上传任务key[非秒传的调度接口返回的pick_code字段]
            topupload:    上传调度文件类型调度标记
            show_progress: 是否显示上传进度条

        Returns:
            bool: 上传是否成功

        """
        resp_init = self.init_with_auto_sign(
            file_name=file_name,
            file_size=file_size,
            target=target,
            fileid=fileid,
            preid=preid,
            pick_code=pick_code,
            topupload=topupload,
        )
        item = self._extract_data(resp_init)
        status = item.get("status")

        # 秒传成功
        if status == 2:
            return True

        token_resp = self.get_token()
        token_data = token_resp.get("data") or {}

        resp = self.upload_to_oss(
            token_data=token_data,
            init_data=resp_init,
            file_path=file_name,
            show_progress=show_progress,
        )
        if resp.get("state"):
            return True

        return False

    def upload_folder(self, folder_path: str, target: str | int = "0", *, create_folder: bool = True, show_progress: bool = True) -> dict:
        """上传文件夹(单个文件大小要小于5GB)

        多线程上传文件夹，保持本地与云端目录结构一致

        Args:
            folder_path:   本地文件夹路径
            target:        目标文件夹ID, 默认根目录 '0'
            create_folder: 是否在目标位置创建与本地同名的文件夹
            show_progress: 是否显示总体上传进度条

        """
        folder = Path(folder_path)
        if not folder.is_dir():
            raise ValueError(f"{folder_path} 不是有效文件夹")

        try:
            target_id = int(target)
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的目标文件夹ID: {target}") from e

        # 如果需要，创建文件夹本身
        if create_folder:
            target_id = self._get_or_create_folder(target_id, folder.name)

        cloud_folder_cache = {"": target_id}
        cache_lock = Lock()
        cpus = os.cpu_count() or 1
        max_workers = max(1, cpus - 1)

        # 第一步：顺序创建所有文件夹
        all_items = sorted(folder.rglob("*"), key=lambda p: len(p.relative_to(folder).parts))
        folders = [p for p in all_items if p.is_dir()]
        files = [p for p in all_items if p.is_file()]

        for folder_path_item in folders:
            rel_path = folder_path_item.relative_to(folder)
            rel_path_str = str(rel_path)

            if rel_path_str in cloud_folder_cache:
                continue

            parent_rel_path = str(rel_path.parent) if rel_path.parent != Path(".") else ""
            parent_id = cloud_folder_cache.get(parent_rel_path, target_id)

            folder_id = self._get_or_create_folder(parent_id, folder_path_item.name)
            cloud_folder_cache[rel_path_str] = folder_id

        # 第二步：多线程并发上传文件
        results = []

        def upload_single_file(local_path):
            """上传单个文件的工作函数"""
            try:
                rel_path = local_path.relative_to(folder)
                parent_rel_path = str(rel_path.parent) if rel_path.parent != Path(".") else ""

                with cache_lock:
                    target_folder_id = cloud_folder_cache.get(parent_rel_path, target_id)

                # 静默上传（关闭所有进度条和日志）
                res = self.upload_file(
                    file_name=str(local_path),
                    target=int(target_folder_id),
                    show_progress=False,
                )

                return {
                    "local_path": str(local_path),
                    "relative_path": str(rel_path),
                    "cloud_folder_id": target_folder_id,
                    "result": res,
                    "success": True,
                }

            except Exception as e:
                return {
                    "local_path": str(local_path),
                    "relative_path": str(rel_path) if "rel_path" in locals() else "unknown",
                    "error": str(e),
                    "success": False,
                }

        # 创建总体进度条
        overall_progress = (
            tqdm(
                total=len(files),
                desc="📦 上传中",
                unit="个",
                leave=True,
            )
            if show_progress
            else None
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(upload_single_file, file_path): file_path for file_path in files}

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)

                    if overall_progress:
                        # 在进度条右边动态显示当前完成的文件
                        status = "✓" if result.get("success") else "✗"
                        rel_path = result.get("relative_path", file_path.name)
                        overall_progress.set_postfix_str(f"{status} {rel_path}")
                        overall_progress.update(1)

                except Exception as e:
                    results.append(
                        {
                            "local_path": str(file_path),
                            "relative_path": "unknown",
                            "error": str(e),
                            "success": False,
                        }
                    )
                    if overall_progress:
                        overall_progress.set_postfix_str(f"✗ {file_path.name} (异常)")
                        overall_progress.update(1)

        if overall_progress:
            overall_progress.close()

        success_count = sum(1 for r in results if r.get("success"))
        failed_count = len(results) - success_count

        return {
            "state": True,
            "message": "上传完成",
            "code": 200,
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
            "data": results,
        }

    @staticmethod
    def _extract_data(d: dict) -> dict:
        """从115返回的 JSON 响应中提取首个 data 项"""
        data = d.get("data")
        if isinstance(data, list):
            data1 = data[0] if data else None
            return data1 if isinstance(data1, dict) else {}
        if isinstance(data, dict):
            return data
        return {}

    @staticmethod
    def _make_progress_fn(file_path: str, show_progress=True):
        """创建一个进度回调函数 progress_fn(n, written, total)"""
        if not show_progress:
            return None, None

        total_size = Path(file_path).stat().st_size
        bar = None
        try:
            bar = tqdm(total=total_size, unit="B", unit_scale=True, desc="上传", leave=False)

            def progress_fn(n: int, written: int, total: int):
                bar.update(n)

            return progress_fn, bar
        except Exception:
            return None, None

    def _get_all_files(self, parent_id: int, show_dir: int = 1) -> dict:
        """获取指定文件夹下的所有文件和文件夹（支持分页）"""
        all_items = []
        offset = 0
        limit = 1150

        while True:
            resp = self.file.files(cid=parent_id, show_dir=show_dir, limit=limit, offset=offset)

            if not resp.get("state", False):
                raise RuntimeError(f"获取文件列表失败: {resp}")

            items = resp.get("data", [])
            if not items:
                break

            all_items.extend(items)
            count = resp.get("count", 0)
            if len(all_items) >= count or len(items) < limit:
                break

            offset += limit

        respjson = copy.deepcopy(resp)
        respjson["data"] = all_items
        return respjson

    @validate_call
    def _get_or_create_folder(self, parent_id: int, folder_name: str) -> int:
        """获取或创建文件夹（支持超过1150个文件的目录）"""
        if parent_id < 0:
            raise ValueError(f"无效的父文件夹ID: {parent_id}")

        # 查找同名文件夹
        all_items = self._get_all_files(parent_id, show_dir=1).get("data", [])
        for item in all_items:
            if str(item.get("fc")) == "0" and str(item.get("fn")) == folder_name and str(item.get("pid")) == str(parent_id):
                folder_id = item.get("fid")
                if folder_id:
                    return int(folder_id)

        # 创建新文件夹
        create_resp = self.file.add(pid=parent_id, file_name=folder_name)

        if not create_resp.get("state", False):
            raise RuntimeError(f"创建文件夹失败: {create_resp}")

        new_folder_id = create_resp.get("file_id") or create_resp.get("data", {}).get("file_id")
        if not new_folder_id:
            raise RuntimeError("创建文件夹成功但未返回文件夹ID")

        return int(new_folder_id)

    def upload_loop(
        self,
        folder_path: str,
        target: int | str = "0",
        *,
        create_folder: bool = True,
        show_progress: bool = False,
    ) -> dict:
        """循环上传文件夹，保持本地与云端目录结构一致

        推荐使用 upload_folder 方法，支持多线程并发上传

        Args:
            folder_path:   本地文件夹路径
            target:        目标文件夹ID, 默认根目录 '0'
            create_folder: 是否在目标位置创建与本地同名的文件夹
            show_progress: 是否显示总体上传进度条

        Returns:
            包含每个文件上传结果的字典
        """
        folder = Path(folder_path)
        if not folder.is_dir():
            raise ValueError(f"{folder_path} 不是有效文件夹")

        try:
            target_id = int(target)
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的目标文件夹ID: {target}") from e

        # 如果需要，创建文件夹本身
        if create_folder:
            target_id = self._get_or_create_folder(target_id, folder.name)

        # 缓存云端文件夹路径
        cloud_folder_cache = {"": target_id}
        results = []

        # 按路径深度排序，确保先创建父目录
        all_files = sorted(folder.rglob("*"), key=lambda p: len(p.relative_to(folder).parts))

        for local_path in all_files:
            try:
                rel_path = local_path.relative_to(folder)

                if local_path.is_dir():
                    # 处理文件夹
                    rel_path_str = str(rel_path)
                    if rel_path_str in cloud_folder_cache:
                        continue

                    parent_rel_path = str(rel_path.parent) if rel_path.parent != Path(".") else ""
                    parent_id = cloud_folder_cache.get(parent_rel_path, target_id)

                    folder_id = self._get_or_create_folder(parent_id, local_path.name)
                    cloud_folder_cache[rel_path_str] = folder_id

                elif local_path.is_file():
                    # 处理文件
                    parent_rel_path = str(rel_path.parent) if rel_path.parent != Path(".") else ""

                    # 如果父目录还没在缓存中，递归创建
                    if parent_rel_path and parent_rel_path not in cloud_folder_cache:
                        current_parent_id = target_id
                        current_path = ""

                        for part in rel_path.parent.parts:
                            current_path = f"{current_path}/{part}" if current_path else part
                            if current_path not in cloud_folder_cache:
                                folder_id = self._get_or_create_folder(current_parent_id, part)
                                cloud_folder_cache[current_path] = folder_id
                                current_parent_id = folder_id
                            else:
                                current_parent_id = cloud_folder_cache[current_path]

                    target_folder_id = cloud_folder_cache.get(parent_rel_path, target_id)

                    # 上传文件
                    res = self.upload_file(
                        file_name=str(local_path),
                        target=str(target_folder_id),
                        show_progress=show_progress,
                    )
                    results.append(
                        {
                            "local_path": str(local_path),
                            "relative_path": str(rel_path),
                            "cloud_folder_id": target_folder_id,
                            "result": res,
                            "success": True,
                        }
                    )

            except Exception as e:
                results.append(
                    {
                        "local_path": str(local_path),
                        "relative_path": str(rel_path) if "rel_path" in locals() else "unknown",
                        "error": str(e),
                        "success": False,
                    }
                )

        return {
            "state": True,
            "message": "上传完成",
            "code": 200,
            "total": len(results),
            "success": sum(1 for r in results if r.get("success")),
            "failed": sum(1 for r in results if not r.get("success")),
            "data": results,
        }

    @validate_call
    def upload(
        self,
        path: str,
        target: str | int = "0",
        *,
        create_folder: bool = True,
        show_progress: bool = True,
        **kwargs: Any,
    ) -> dict | bool:
        """自动判断路径类型并上传文件或文件夹

        根据路径自动判断是文件还是文件夹，并调用相应的上传方法。

        Args:
            path: 本地文件或文件夹路径
            target: 目标文件夹ID，默认根目录 '0'
            create_folder: 是否在目标位置创建与本地同名的文件夹（仅文件夹上传时有效）
            show_progress: 是否显示上传进度条
            **kwargs: 其他参数，透传给 upload_file（如 file_size, fileid, preid, pick_code, topupload）

        Returns:
            - 文件上传：返回 bool（True 表示成功）
            - 文件夹上传：返回 dict（包含上传统计信息）

        Raises:
            ValueError: 当路径不存在或无法访问时

        Examples:
            >>> uploader = Uploader(auth)
            >>> # 上传单个文件
            >>> uploader.upload("test.txt", target="0")
            True
            >>> # 上传文件夹
            >>> uploader.upload("my_folder", target="0", create_folder=True)
            {'state': True, 'message': '上传完成', ...}
        """
        p = Path(path)

        if not p.exists():
            raise ValueError(f"路径不存在或无法访问: {path}")

        # 判断是文件夹还是文件
        if p.is_dir():
            resp = self.upload_folder(
                folder_path=str(p),
                target=target,
                create_folder=create_folder,
                show_progress=show_progress,
            )
        elif p.is_file():
            # 提取 upload_file 支持的参数
            resp = self.upload_file(
                file_name=str(p),
                file_size=kwargs.get("file_size"),
                target=target,
                fileid=kwargs.get("fileid"),
                preid=kwargs.get("preid"),
                pick_code=kwargs.get("pick_code"),
                topupload=kwargs.get("topupload"),
                show_progress=show_progress,
            )
        else:
            raise ValueError(f"不支持的路径类型: {path}")
        return resp
