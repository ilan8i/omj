<div align="center">

# 个人仓库

**内容无意义。**

## 国内用户

```bash
git clone https://gitee.com/ialn8i/omj.git
```

Gitee 是发布源，只保留一个发布提交；完整提交历史见 GitHub。发布分支为 `myself`。

## 一键安装（Windows）

脚本自带 Python 3.10.11 运行环境，无需预先安装 Python 或 Git；首次安装需要联网下载运行时和依赖。

1. 从 Gitee 下载仓库压缩包并解压（不要直接在压缩软件里运行）；
2. 双击 `omj-install.bat`；
3. 脚本会把 OMJ 安装到 `%USERPROFILE%\OMJ`，自动下载 Python 3.10 运行时、安装依赖并启动网页端。

默认仓库为 `https://gitee.com/ialn8i/omj`，分支 `myself`。安装完成后可双击
`start-omj.bat` 启动。检测到 Git 时用 Git 更新，否则直接下载 Gitee 压缩包。

## 本地授权配置

授权服务地址和 Ed25519 公钥已经随代码发布，用户不需要自己创建配置文件。

首次使用：

- 前端调用 `POST /license/activate`，body 为 `{"key": "..."}`；
- 状态查询：`GET /license/status`。

可选：把卡密写进本机的 `config/license.json`，作为本地备份：

```json
{"key": "OMJ-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX"}
```

该文件已被 `.gitignore` 忽略，不会进入仓库。

授权令牌的 claims 可以携带 `perms` 数组，例如：

```json
"perms": ["switch_account", "assist_battle"]
```

`AccountSwitch`（切换账号）需要 `switch_account`，`AssistBattle`（一键协战）需要
`assist_battle`。未开通时调度器会跳过该任务，并延后 1 小时重试。

> 仓库是公开的，授权校验只能作为轻量门槛；懂代码的用户可以自行修改或移除校验。

## 私有构建（Cython）

把敏感模块编译成 `.pyd`，用于私有发行：

```bash
pip install -r requirements-build.txt
python dev_tools/cython_build.py
python dev_tools/package_private.py
```

编译范围：

```text
module/license/*.py（保留 __init__.py）
module/server/license_router.py
script.py
server.py
```

产物：

```text
dist/private/
dist/OMJ-private-<时间>.zip
```

说明：

- 需要在 Windows + MSVC 环境执行，推荐用 GitHub Actions 的 `build-private` 工作流；
- `script.py` / `server.py` 在发行目录里会替换成很薄的启动 stub，逻辑在 `.pyd` 中；
- `package_private.py` 生成的是**覆盖包**，不包含 `toolkit/` 运行时，需要叠加在已有 OMJ 安装目录上；
- 真正的源码私密前提是 **GitHub 仓库本身是私有的**；仓库公开时编译不能阻止别人直接看 `.py`；
- OMJ 是 GPL-3.0，对外分发时请自行确认合规。
