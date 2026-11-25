<div align="center">

# 个人仓库

**内容无意义。**

## 本地授权配置

首次使用需要激活授权：

- 前端调用 `POST /license/activate`，body 为 `{"key": "..."}`；
- 或把密钥写入 `config/license.json`，内容为 `{"key": "..."}`（该文件已被 gitignore）；
- 状态查询：`GET /license/status`。

授权服务地址与 Ed25519 公钥在 `module/license/constants.py`，发布前必须替换占位值；
同时确认 `DEV_MODE = False`（发布构建不允许通过环境变量覆盖授权服务与公钥）。
