from .Auth import Auth
from .model.Base import UserInfoModel
from .utils.Constants import API

MARK3TONAME = {
    0: "原石用户",
    1: "月费VIP",
    1023: "年费VIP",
    10239: "超级VIP",
    1048575: "长期VIP",
    11: "体验VIP",
    10231: "年费VIP高级版",
    10235: "年费VIP特级版",
}
NAME2MARK = {v: k for k, v in MARK3TONAME.items()}


class User:
    """
    用户信息接口客户端
    用于获取用户空间与 VIP 信息
    """

    def __init__(self, auth: Auth):
        """初始化

        Args:
            auth: 已授权的 Auth 实例
        """
        self.auth = auth
        self._user_resp_cache = None
        self.userinfo: UserInfoModel = self._fetch_user_info()

    def get_user_info(self) -> dict:
        """获取用户信息, 通过调用 GET /open/user/info 接口

        Returns:
            包含用户信息
        """
        if self._user_resp_cache is not None:
            return self._user_resp_cache

        resp = self.auth.request_json("GET", API.UserPath.USER_INFO)

        self._user_resp_cache = resp
        return resp

    def _fetch_user_info(self) -> UserInfoModel:
        """获取并缓存用户信息

        Returns:
            UserInfoModel: 用户信息模型

        Example Response:
             {'state': True, 'message': '', 'code': 0, 'data': {'user_id': 11111, 'user_name': '66m', .... 'vip_info': {'expire': 253402271999, 'level_name': '特级VIP', 'tp_rights': {'is_tp_rights': 0, 'tp_rights_time': 0}}}}
        """
        try:
            resp = self.get_user_info()
        except Exception as e:
            raise ValueError("无法获取用户信息") from e

        try:
            data = resp.get("data", {})
            if not data:
                raise ValueError("响应数据为空")

            user_id = data.get("user_id") or data.get("userid")
            user_name = data.get("user_name") or data.get("username")
            if not user_id or not user_name:
                raise ValueError("缺少必要的用户信息字段")
            vip_info = data.get("vip_info", {})
            level_name = vip_info.get("level_name", "原石用户")
            viptype = NAME2MARK.get(level_name, 1)  # 不是原石用户即视为VIP

            user_info = UserInfoModel(
                username=user_name,
                userid=str(user_id),
                isvip=viptype != 0,
                viptype=viptype,
            )
            return user_info

        except KeyError as e:
            raise ValueError(f"响应数据格式错误，缺少字段: {e}") from e
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            print(f"原始响应: {resp}")
            raise ValueError(f"解析用户信息失败: {e}") from e
