## 文件上传/下载(夹) 案例


**1. 获取用户信息**
```python

from cpan115 import Pan115OpenAPI

cpan = Pan115OpenAPI()
log = cpan.log
info = cpan.user.get_user_info()
log.info(f"用户信息: {info}")


```


**2.上传**

```python
# 上传文件夹
resp = cpan.uploader.upload_folder(folder_path="downloads")
log.info(f"文件夹上传结果: {resp}")


# 上传文件

resp = cpan.uploader.upload_file(file_name="downloads_dl/downloads/4.rar", target="0")
log.info(f"文件上传结果: {resp}")


# 上传文件(夹), 统一
resp = cpan.uploader.upload(path="downloads_dl/downloads/4.rar", target="0")
log.info(f"文件上传结果: {resp}")

```

**3.下载**

```python
# 下载文件夹
resp = cpan.downloader.download_folder(file_id=3294719661387546088, save_path="downloads_dl")
log.info(f"文件夹下载结果: {resp}")

# 下载文件(根据路径)
resp = cpan.downloader.download_by_path(path="/4.rar")
log.info(f"文件夹下载结果: {resp}")

```


```python
 # 通过ID下载文件, 整数：文件或文件夹ID
cpan.downloader.download_auto(123456)
# 通过路径下载文件, 字符串：云端文件的绝对路径
cpan.downloader.download_auto("/资料/报告.pdf")

```