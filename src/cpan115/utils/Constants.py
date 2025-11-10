## 有关授权的
AUTH_BASE = "https://passportapi.115.com"
API_BASE = "https://proapi.115.com"


class API:
    """115 接口路径和方法统一管理"""

    AUTH_BASE = AUTH_BASE
    API_BASE = API_BASE

    class Oauth2:
        AUTHORIZE = AUTH_BASE + "/open/authorize"
        TOKEN = AUTH_BASE + "/open/authCodeToToken"
        REFRESH = AUTH_BASE + "/open/refreshToken"

    class JWT:
        # 115 没有JWT, 这里只是占位
        TOKEN = AUTH_BASE + "/api/v1/access_token"  # 获取访问令牌

    class FilePath:
        # --------- 文件上传下载相关接口 ----------
        UPLOAD_TOKEN = API_BASE + "/open/upload/get_token"
        UPLOAD_INIT = API_BASE + "/open/upload/init"
        UPLOAD_RESUME = API_BASE + "/open/upload/resume"

        # --------- 文件夹相关接口 ----------
        FOLDER_ADD = API_BASE + "/open/folder/add"
        FOLDER_INFO = API_BASE + "/open/folder/get_info"

        # --------- 文件相关接口 ----------
        UFILE_FILES = API_BASE + "/open/ufile/files"
        UFILE_SEARCH = API_BASE + "/open/ufile/search"
        UFILE_COPY = API_BASE + "/open/ufile/copy"
        UFILE_MOVE = API_BASE + "/open/ufile/move"
        UFILE_DOWNURL = API_BASE + "/open/ufile/downurl"
        UFILE_UPDATE = API_BASE + "/open/ufile/update"
        UFILE_DELETE = API_BASE + "/open/ufile/delete"

        # --------- 回收站相关接口 ----------
        RB_LIST = API_BASE + "/open/rb/list"
        RB_REVERT = API_BASE + "/open/rb/revert"
        RB_DELETE = API_BASE + "/open/rb/del"

    class UserPath:
        USER_INFO = API_BASE + "/open/user/info"


ERROR_MAP = {
    40100000: "参数缺失",
    40101017: "用户验证失败",
    40110000: "请求异常，需要重试",
    40140100: "client_id错误",
    40140101: "code_challenge必填",
    40140102: "code_challenge_method必须是sha256、sha1、md5之一",
    40140103: "sign必填",
    40140104: "sign签名失败",
    40140105: "生成二维码失败",
    40140106: "APP ID无效",
    40140107: "应用不存在",
    40140108: "应用未审核通过",
    40140109: "应用已被停用",
    40140110: "应用已过期",
    40140111: "APP Secret错误",
    40140112: "code_verifier长度要求43~128位",
    40140113: "code_verifier验证失败",
    40140114: "refresh_token格式错误（防篡改）",
    40140115: "refresh_token签名校验失败（防篡改）",
    40140116: "refresh_token无效（已解除授权）",
    40140117: "access_token刷新太频繁",
    40140118: "开发者认证已过期",
    40140119: "refresh_token已过期",
    40140120: "refresh_token检验失败（防篡改）",
    40140121: "access_token刷新失败",
    40140122: "超出授权应用个数上限",
    40140123: "access_token格式错误（防篡改）",
    40140124: "access_token签名校验失败（防篡改）",
    40140125: "access_token无效（已过期或解除授权）",
    40140126: "access_token校验失败（防篡改）",
    40140127: "response_type错误",
    40140128: "redirect_uri缺少协议",
    40140129: "redirect_uri缺少域名",
    40140130: "没有配置重定向域名",
    40140131: "redirect_uri非法域名",
    40140132: "grant_type错误",
    40140133: "client_secret验证失败",
    40140134: "授权码 code验证失败",
    40140135: "client_id验证失败",
    40140136: "redirect_uri验证失败（防MITM）",
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
