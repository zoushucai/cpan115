from typing import Any, Literal

from pydantic import validate_call

from .Auth import Auth
from .model.Base import UserInfoModel
from .model.model import FileSearchParams, FilesListParams
from .utils.Constants import API

SortField = Literal["file_name", "file_size", "user_utime", "file_type"]


class File:
    """文件相关操作封装"""

    def __init__(self, auth: Auth, userinfo: UserInfoModel | None = None):
        """初始化

        Args:
            auth: 已授权的 Auth 实例
            userinfo: 可选的用户信息模型
        """
        self.auth = auth
        self.userinfo = userinfo

    @validate_call
    def add(self, pid: int | str, file_name: str) -> dict:
        """新建文件夹

        Args:
            pid: 新建文件夹所在的父目录ID (根目录的ID为0)
            file_name: 新建文件夹名称, 限制255个字符

        Returns:
            包含新建文件夹的信息

        """
        assert str(pid).isdigit() and int(pid) >= 0, "pid 必须是非负整数"

        data = {"pid": str(pid), "file_name": file_name}
        resp = self.auth.request_json("POST", API.FilePath.FOLDER_ADD, data=data)
        return resp

    @validate_call
    def files(
        self,
        cid: int | None = None,
        type: int | None = None,
        limit: int = 20,
        offset: int = 0,
        suffix: str | None = None,
        asc: int | None = None,
        o: SortField | None = None,
        custom_order: int | None = None,
        stdir: int | None = None,
        star: int | None = None,
        cur: int | None = None,
        show_dir: int = 0,
    ) -> dict:
        """获取文件列表

        获取指定目录下的文件列表

        Args:
            cid:        目录ID, 对应parent_id
            type:       文件类型；1.文档；2.图片；3.音乐；4.视频；5.压缩；6.应用；7.书籍
            limit:      查询数量, 默认20, 最大1150
            offset:     查询起始位, 默认0
            suffix:     文件后缀名
            asc:        排序, 1: 升序 0: 降序
            o:          排序字段, file_name: 文件名 file_size: 文件大小 user_utime: 更新时间 file_type 文件类型
            custom_order: 是否使用记忆排序。1 使用自定义排序, 不使用记忆排序,0 使用记忆排序, 自定义排序失效,2自定义排序, 非文件夹置顶
            stdir:          筛选文件时, 是否显示文件夹；1:要展示文件夹 0不展示
            star:        筛选星标文件, 1:是 0全部
            cur:         是否只显示当前文件夹内文件
            show_dir:   是否显示目录；0 或 1, 默认为0, 解读: 1表示显示目录和文件, 0表示只显示文件

        Returns:
            包含文件列表信息

        Example:
            解读:
            - 当show_dir=0 且 cur=True时, 表示只显示当前目录下的所有文件,不显示目录(不含子文件夹内文件)

            - 当show_dir=0 且 cur=False时,表 示显示当前目录下的所有文件,不显示目录(含子文件夹内文件)

            - 当show_dir=1 且 cur=False时,表示显示当前目录下的所有文件和目录(不含子文件夹内文件)

            - 当show_dir=1 且 cur=True时, 表示只显示当前目录下的文件和目录(不含子文件夹内文件)

        """
        params = FilesListParams(
            cid=cid,
            type=type,
            limit=limit,
            offset=offset,
            suffix=suffix,
            asc=asc,
            o=o,
            custom_order=custom_order,
            stdir=stdir,
            star=star,
            cur=cur,
            show_dir=show_dir,
        )
        data = params.model_dump(exclude_none=True)

        resp = self.auth.request_json("GET", API.FilePath.UFILE_FILES, params=data)
        return resp

    def get_info(self, file_id: int | None = None, path: str | None = None) -> dict:
        """获取文件(夹)详情

        获取文件(夹)详情

        Args:
            file_id: 文件ID
            path: 文件路径,  二者选一传入即可,如果都传入则以 file_id 为准

        Returns:
            包含文件信息

        """
        assert file_id is None or path is None, "file_id 和 path 不能同时为None"

        if file_id == 0 or path == "/":
            raise ValueError("不能传递根目录的 file_id 或 path 参数")
        elif file_id is None:
            params = {"path": path}
        else:
            assert file_id is not None and file_id >= 0, "file_id 必须是非负整数"
            params = {"file_id": str(file_id)}

        resp = self.auth.request_json("GET", API.FilePath.FOLDER_INFO, params=params)
        return resp

    @validate_call
    def search(
        self,
        search_value: str,
        limit: int = 20,
        offset: int = 0,
        file_label: str | None = None,
        cid: int | None = None,
        gte_day: str | None = None,
        lte_day: str | None = None,
        fc: int | None = None,
        type: int | None = None,
        suffix: str | None = None,
    ) -> dict:
        """搜索文件

        Args:
            search_value: 查找关键字
            limit: 单页记录数, 默认20, offset+limit最大不超过10000
            offset: 数据显示偏移量
            file_label: 文件标签搜索
            cid: 目标目录cid
            gte_day: 开始时间, 格式 2020-11-19
            lte_day: 结束时间, 格式2020-11-20
            fc: 只显示文件或文件夹。1 只显示文件夹, 2 只显示文件
            type: 文件类型, 1: 文档, 2: 图片, 3: 音乐, 4: 视频, 5: 压缩包, 6: 应用
            suffix: 文件后缀名
        """
        params = FileSearchParams(
            search_value=search_value,
            limit=limit,
            offset=offset,
            file_label=file_label,
            cid=cid,
            gte_day=gte_day,
            lte_day=lte_day,
            fc=fc,
            type=type,
            suffix=suffix,
        )

        data = params.model_dump(exclude_none=True)
        resp = self.auth.request_json("GET", API.FilePath.UFILE_SEARCH, params=data)
        return resp

    @validate_call
    def copy(self, pid: int, file_id: int | list[int], nodupli: int | None = None) -> dict:
        """文件复制

        批量复制文件

        Args:
            pid: 目标目录，即所需移动到的目录ID
            file_id: 所复制的文件和目录ID，多个文件和目录请以, 隔开(这里直接传入整数列表或单个整数)
            nodupli: 复制的文件在目标目录是否允许重复，默认0：0：可以；1：不可以

        Returns:
            包含复制结果信息

        """
        assert pid >= 0, "pid 必须是非负整数"

        if isinstance(file_id, list):
            file_id_str = ",".join(str(fid) for fid in file_id)
        else:
            file_id_str = str(file_id)

        data: dict[str, str] = {"pid": str(pid), "file_id": file_id_str}
        if nodupli is not None:
            data["nodupli"] = str(nodupli)

        resp = self.auth.request_json("POST", API.FilePath.UFILE_COPY, data=data)
        return resp

    @validate_call
    def move(self, file_ids: list[int] | int, to_cid: int) -> dict:
        """文件移动

        批量移动文件

        Args:
            file_ids: 所移动的文件和目录ID，多个文件和目录请以, 隔开(这里直接传入整数列表或单个整数)
            to_cid: 要移动所在的目录ID，根目录为0

        """
        assert to_cid >= 0, "to_cid 必须是非负整数"

        if isinstance(file_ids, list):
            file_ids_str = ",".join(str(fid) for fid in file_ids)
        else:
            file_ids_str = str(file_ids)

        data = {"to_cid": to_cid, "file_ids": file_ids_str}
        resp = self.auth.request_json("POST", API.FilePath.UFILE_MOVE, data=data)
        return resp

    @validate_call
    def downurl(self, pick_code: str) -> dict:
        """获取文件下载地址

        根据文件提取码取文件下载地址

        Args:
            pick_code: 文件提取码

        Returns:
            包含文件下载地址信息

        """

        params = {"pick_code": pick_code}
        resp = self.auth.request_json("POST", API.FilePath.UFILE_DOWNURL, data=params)
        if not resp.get("data"):
            print("提取码对应的文件不存在或提取码错误，下载地址为空")
        return resp

    @validate_call
    def update(self, file_id: int, file_name: str | None = None, star: int | None = None) -> dict:
        """文件(夹)更新

        更新文件名或星标文件

        Args:
            file_id: 需要更改名字的文件(夹)ID
            file_name: 新的文件(夹)名字(文件夹名称限制255字节)
            star: 是否星标；1：星标；0：取消星标

        Returns:
            包含更新结果信息
        """
        assert file_name is not None or star is not None, "file_name 和 star 不能同时为 None"

        params: dict[str, Any] = {"file_id": file_id}
        if file_name is not None:
            params["file_name"] = str(file_name)
        if star is not None:
            params["star"] = star

        resp = self.auth.request_json("POST", API.FilePath.UFILE_UPDATE, data=params)
        return resp

    @validate_call
    def delete(self, file_ids: list[int] | int, parent_id: int | None = None) -> dict:
        """删除文件

        批量删除文件(夹)


        Args:
            file_ids: 需要删除的文件(夹)ID，多个文件和目录请以, 隔开(这里直接传入整数列表或单个整数)
            parent_id: 删除的文件(夹)ID所在的父目录ID
        """
        if isinstance(file_ids, list):
            file_ids_str = ",".join(str(fid) for fid in file_ids)
        else:
            file_ids_str = str(file_ids)

        data = {"file_ids": file_ids_str, "parent_id": parent_id}
        data = {k: v for k, v in data.items() if v is not None}
        resp = self.auth.request_json("POST", API.FilePath.UFILE_DELETE, data=data)
        return resp
