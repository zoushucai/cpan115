from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class FilesListParams(BaseModel):
    cid: Optional[int] = None
    type: Optional[int] = Field(None, ge=1, le=7)
    limit: int = Field(20, ge=1, le=1150)
    offset: int = Field(0, ge=0)
    suffix: Optional[str] = None
    asc: Optional[int] = Field(None, ge=0, le=1)
    o: Optional[Literal["file_name", "file_size", "user_utime", "file_type"]] = None
    custom_order: Optional[int] = Field(None, ge=0, le=2)
    stdir: Optional[int] = Field(None, ge=0, le=1)
    star: Optional[int] = Field(None, ge=0, le=1)
    cur: Optional[int] = None  # 如果传入boolean值，则会被自动转换为0或1
    show_dir: int = Field(0, ge=0, le=1)


class FileSearchParams(BaseModel):
    search_value: str
    limit: int = Field(20, ge=1, le=10000)
    offset: int = Field(0, ge=0)
    file_label: Optional[str] = None
    cid: Optional[int] = None
    gte_day: Optional[str] = None
    lte_day: Optional[str] = None
    fc: Optional[int] = Field(None, ge=1, le=2)
    type: Optional[int] = Field(None, ge=1, le=6)
    suffix: Optional[str] = None

    @field_validator("gte_day", "lte_day")
    @classmethod
    def validate_date_format(cls, v):
        """验证日期格式是否为 YYYY-MM-DD"""
        if v is not None:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("日期格式必须为 YYYY-MM-DD, 例如: 2024-01-31")
        return v


class FileUploadParams(BaseModel):
    file_name: str = Field(..., description="文件名")
    file_size: int = Field(..., ge=1, description="文件大小(字节)")
    target: str | int = Field(..., description="文件上传目标约定")
    fileid: str = Field(..., description="文件sha1值")
    preid: Optional[str] = Field(None, description="文件前128Ksha1")
    pick_code: Optional[str] = Field(None, description="上传任务key")
    topupload: Optional[int] = Field(None, ge=-1, le=2, description="上传调度文件类型调度标记")
    sign_key: Optional[str] = Field(None, description="二次认证需要")
    sign_val: Optional[str] = Field(None, description="二次认证需要(大写)")

    @field_validator("target", mode="before")
    @classmethod
    def validate_target(cls, v):
        if isinstance(v, int):
            # 如果是整数，转换为字符串并添加前缀
            return f"U_1_{v}"
        elif isinstance(v, str):
            if v.startswith("U_1"):
                # 如果已经是U_1开头，保持不变
                return v
            else:
                # 如果不是U_1开头，尝试解析为数字或直接添加前缀
                try:
                    # 尝试转换为整数（处理纯数字字符串）
                    folder_id = int(v)
                    return f"U_1_{folder_id}"
                except ValueError:
                    # 如果不是纯数字，直接添加前缀
                    return f"U_1_{v}"
        else:
            raise ValueError("target必须是字符串或整数类型")

    @field_validator("sign_val", mode="before")
    @classmethod
    def validate_sign_val(cls, v):
        if v is not None:
            # 将 sign_val 转换为大写
            return v.upper()
        return v
