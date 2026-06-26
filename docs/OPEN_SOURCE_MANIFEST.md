# QuantOS CN — 开源发布清单

## 仓库包含

| 类别 | 路径 |
|------|------|
| Web 门户 | `apps/portal-web/` |
| API 网关 | `gateway/` |
| 量化引擎 | `quant/` |
| 依赖 pins | `requirements/` |
| 启动脚本 | `scripts/`（bash + PowerShell） |
| 用户文档 | `docs/INSTALL.md`、`docs/USER_GUIDE.md` 等 |
| 截图 | `docs/assets/screenshots/` |
| 测试 | `tests/` |

## 不包含（`.gitignore`）

| 类别 | 路径 |
|------|------|
| 密钥 | `.env` |
| 虚拟环境 | `.venv-china-quant/` |
| 运行时数据 | `data/`（DuckDB、Paper、审计、日报） |
| Cursor 配置 | `.cursor/` |
| 历史验收 bulk | `docs/ai/` |

## 推送前检查

```bash
bash scripts/validate-open-source.sh
```

## 默认 API Key

开发：`demo-local-key-change-in-prod` — **生产前必须更换**。
