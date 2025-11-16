from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class UserInfoModel(BaseModel):
    """统一的用户模型, 过滤掉其他不必要的字段"""

    model_config = ConfigDict(extra="ignore")  # ✅ 忽略所有未定义字段

    username: str | None = None
    userid: str | None = None
    isvip: bool | None = None
    viptype: int | None = None


class AuthError(Exception):
    """115 平台统一异常"""

    def __init__(self, code: int, message: str, detail: dict | None = None):
        self.code = code
        self.message = message
        self.detail = detail or {}
        super().__init__(f"[{code}] {message}")


class BaseResponse(BaseModel):
    """统一响应模型"""

    state: bool | int
    message: str
    code: int
    data: dict[str, Any] | list
    model_config = ConfigDict(extra="allow")  # ✅ 保留所有未定义字段

    @model_validator(mode="after")
    def check_state(self) -> "BaseResponse":
        """验证 state 字段，失败时抛出 AuthError"""
        if not self.state:  # state == 0 或 False
            raise AuthError(self.code, self.message)
        return self
