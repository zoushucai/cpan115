from .Auth import Auth
from .Downloader import Downloader
from .File import File
from .Rb import Rb
from .Uploader import Uploader
from .User import User
from .utils.Constants import API
from .utils.Logger import log


class Pan115OpenAPI:
    """
    115开放接口客户端
    包含用户信息与上传等功能
    """

    def __init__(self, envpath: str | None = None, verbose: bool = False):
        self.API = API
        self.log = log
        self.auth = Auth(envpath=envpath, verbose=verbose)
        self.user = User(self.auth)
        self.uploader = Uploader(self.auth)
        self.downloader = Downloader(self.auth)
        self.file = File(self.auth)
        self.rb = Rb(self.auth)
