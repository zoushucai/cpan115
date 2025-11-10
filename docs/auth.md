
## Auth 类说明

### 1. 使用自己的密钥

在使用 115 授权时，必须在当前项目目录下（`.env`）或用户根目录下（`~/.env.115`）建立配置文件，并提供以下四个参数：

* `CLIENT_ID`
* `CLIENT_KEY`
* `CLIENT_SECRET`
* `REDIRECT_URI`

> 这四个参数需要在 115 开发者平台申请，申请通过后才能获得对应的值。



### 2. 使用第三方密钥（作者提供）

如果使用作者提供的第三方密钥，同样需要在项目目录（`.env`）或根目录（`~/.env.115`）建立配置文件，但只需填写以下三个参数且参数值固定(也可以不需要填写,软件内置下面三个参数)：

```env
CLIENT_ID=100197735
REDIRECT_URI=https://open.xiaocai.site
BACKEND_OAUTH_URL=https://open.xiaocai.site
```

> 注意：此方式无需 `CLIENT_SECRET`，适合快速使用或测试。




## OAuth类

::: cpan115.authtype.OAuth

## Auth类

::: cpan115.Auth