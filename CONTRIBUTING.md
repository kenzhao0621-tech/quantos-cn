# Contributing to QuantOS CN

感谢关注本项目。开始前请阅读 [README.md](README.md) 与 [docs/USER_GUIDE.md](docs/USER_GUIDE.md)。

## Development setup

```bash
make bootstrap
make app
make doctor
```

## Pull requests

1. Fork 仓库并从 `main` 或当前功能分支创建 topic 分支  
2. `make bootstrap && make doctor` 确保环境就绪  
3. 改动附带测试（`make test-gateway` 或相关 `tests/test_*.py`）  
4. 使用 **Conventional Commits**：`feat:`、`fix:`、`docs:`、`test:`、`chore:`  
5. PR 描述说明：动机、测试方式、是否影响实盘门控  

**请勿提交：**

- `.env`、密钥、Token  
- `data/` 运行时状态（Paper 账本、券商配置含敏感信息）  
- 无人值守自动真实下单相关功能  

## Code areas

| Area | Path |
|------|------|
| Portal UI | `apps/portal-web/` |
| Gateway API | `gateway/api/` |
| Quant engine | `quant/` |
| Docs | `docs/` |

## Tests

```bash
make test-gateway
make test-core
make test-e2e
.venv-china-quant/bin/python scripts/run_product_acceptance.py
```

## 文档

- 用户可见改动请同步 `docs/USER_GUIDE.md`  
- 产品能力变更请更新 `docs/PRODUCT.md` 与 `CHANGELOG.md`  
- 架构级变更请更新 `docs/ARCHITECTURE.md`  
