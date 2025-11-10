import hashlib
from pathlib import Path


def check_file(file_path: str):
    """检查文件是否存在且非空"""
    if not Path(file_path).is_file():
        raise FileNotFoundError(f"文件未找到: {file_path}")

    if not Path(file_path).stat().st_size:
        raise ValueError(f"文件大小为0: {file_path}")


def calc_sha1(file_path: str) -> str:
    check_file(file_path)
    if not Path(file_path).stat().st_size:
        raise ValueError(f"文件大小为0: {file_path}")

    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha1.update(chunk)
    return sha1.hexdigest().upper()


def calc_sha1_range(file_path: str, start: int, end: int) -> str:
    """计算文件[start, end]（包含end）的SHA1并返回大写十六进制。"""
    check_file(file_path)

    start, end = max(0, start), max(start, end)
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        f.seek(start)
        remain = end - start + 1
        while remain > 0:
            chunk = f.read(min(1024 * 1024, remain))
            if not chunk:
                break
            sha1.update(chunk)
            remain -= len(chunk)
    return sha1.hexdigest().upper()


def calc_sign_val(file_path: str, sign_check: str) -> str:
    """根据 sign_check 字符串计算指定文件区间的 SHA1（大写）。

    sign_check 格式示例："2392148-2392298" 或可能带下划线分隔（"2392148_2392298"）。

    Args:
        file_path: 本地文件路径，用于读取并计算 sha1
        sign_check: 形如 "start-end" 的字节区间（包含两端）

    Returns:
        大写的 sha1 字符串
    """
    check_file(file_path)

    rng = str(sign_check).replace("_", "-").split("-")
    if len(rng) != 2:
        raise ValueError(f"sign_check 格式不正确: {sign_check}")

    try:
        start, end = map(int, rng)
    except Exception as e:
        raise ValueError(f"无法解析 sign_check 范围: {sign_check}") from e

    return calc_sha1_range(file_path, start, end)
