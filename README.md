<div align="center">

# 个人仓库

**内容无意义。**

## 国内用户

```bash
git clone https://gitee.com/ialn8i/omj.git
```

Gitee 是 GitHub 的只读镜像，发布分支为 `myself`。

## 本地授权配置

授权服务地址和 Ed25519 公钥已经随代码发布，用户不需要自己创建配置文件。

首次使用：

- 前端调用 `POST /license/activate`，body 为 `{"key": "..."}`；
- 状态查询：`GET /license/status`。

可选：把卡密写进本机的 `config/license.json`，作为本地备份：

```json
{"key": "OAS-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX"}
```

该文件已被 `.gitignore` 忽略，不会进入仓库。

授权令牌的 claims 可以携带 `perms` 数组，例如：

```json
"perms": ["switch_account", "assist_battle"]
```

`AccountSwitch`（切换账号）需要 `switch_account`，`AssistBattle`（一键协战）需要
`assist_battle`。未开通时调度器会跳过该任务，并延后 1 小时重试。

> 仓库是公开的，授权校验只能作为轻量门槛；懂代码的用户可以自行修改或移除校验。
