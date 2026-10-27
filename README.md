# GsBrowserUse

给 GsCore 的 Agent 提供浏览器操作。工具不绑定具体引擎，配置里可以选 [Obscura](https://github.com/h4ckf0r0day/obscura) 或 [Lightpanda](https://github.com/lightpanda-io/browser)。

在网页控制台的插件配置里点「下载并安装」。按钮会先显示当前环境，例如 `windows-x86_64`、`linux-aarch64`、`macos-aarch64`，再下载这个环境对应的安装包。Windows 上 Obscura 是 zip 里的 exe，Linux 和 macOS 是 tar.gz。Lightpanda 是单个可执行文件，没有 Windows 安装包。

每个 `bot_id + user_id` 单独一个浏览器上下文。同时最多开配置里写的页数，默认 3。空闲超过配置的秒数后关掉页面；一个都不剩时退出浏览器进程。

Obscura 的 Linux 安装包需要 glibc 2.35+（Ubuntu 22.04 及以上）。Obscura 的 Windows 只有 x86_64。macOS 两种引擎都支持 Intel 和 Apple 芯片。

以后加功能，在内层包里新建 `gsbrowseruse_<功能>/`，目录中放 `__init__.py`。核心启动时会导入这个目录。

- `gsbrowseruse_config`：配置和环境探测
- `gsbrowseruse_install`：按引擎下载和安装
- `gsbrowseruse_browser`：进程、页面和会话
- `gsbrowseruse_agent`：代理工具和启动钩子
