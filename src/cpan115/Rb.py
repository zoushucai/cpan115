from pydantic import Field, validate_call

from .Auth import Auth
from .utils.Constants import API


class Rb:
    """文件相关操作封装"""

    def __init__(self, auth: Auth):
        """初始化

        Args:
            auth: 已授权的 Auth 实例
        """
        self.auth = auth

    @validate_call
    def lists(self, limit: int = Field(30, ge=1, le=200), offset: int = Field(0, ge=0)) -> dict:
        """回收站列表


        回收站列表

        Args:
            limit:      单页记录数，int，默认30，最大200
            offset:     数据显示偏移量

        Returns:
            包含文件列表信息

        """
        params = {"limit": limit, "offset": offset}
        resp = self.auth.request_json("GET", API.FilePath.RB_LIST, params=params)
        return resp

    @validate_call
    def revert(self, tid: list[int] | int) -> dict:
        """还原回收站文件

        还原回收站文件(夹)

        Args:
            tid:   需要还原的ID，可多个，用半角逗号分开，最多1150个

        Returns:
            包含还原结果

        """
        if isinstance(tid, list):
            tid_str = ",".join(str(t) for t in tid)
        else:
            tid_str = str(tid)

        payload = {"tid": tid_str}
        resp = self.auth.request_json("POST", API.FilePath.RB_REVERT, data=payload)
        return resp

    @validate_call
    def delete(self, tid: list[int] | int | None = None) -> dict:
        """彻底删除回收站文件

        批量删除回收站文件、清空回收站

        Args:
            tid:  需要删除的文件的Id,如若不传就是清空回收站(最多支持1150个)

        Returns:
            包含删除结果

        """
        if tid is None:
            payload = {}
        elif isinstance(tid, list):
            tid_str = ",".join(str(t) for t in tid)
            payload = {"tid": tid_str}
        elif isinstance(tid, int):
            payload = {"tid": str(tid)}
        else:
            payload = {}
        resp = self.auth.request_json("POST", API.FilePath.RB_DELETE, data=payload)
        return resp
