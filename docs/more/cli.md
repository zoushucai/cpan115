## 命令行工具


- 上传单个文件

```bash
cpan115 upload downloads\testpdf\3.pdf

```

- 上传整个文件夹（在目标处创建同名文件夹并显示总体进度）

```bash

cpan115 upload downloads

```


- 下载整个云端文件夹（并发模式）

```bash

cpan115 download 3294731262119378422 downloads_dl_bb 

```

## 帮助

```bash

cpan115 --help
cpan115 upload --help
cpan115 download--help
```


```text
download (down)  下载文件或文件夹（自动判断类型）
upload (up)      上传文件或文件夹到网盘（自动判断类型）
```