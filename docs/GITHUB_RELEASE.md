# GitHub 发布指南 — QuantOS CN

**状态（2026-06-26）：** 代码已推送到  
https://github.com/kenzhao0621-tech/netlify-demo/tree/fix/a-share-quant-reliability-paper-validation  
标签 `v4.1.0` 已推送。下一步请在 GitHub 将仓库重命名为 `quantos-cn`。

## 1. 重命名 GitHub 仓库（推荐）

在 GitHub 网页：

1. 打开 https://github.com/kenzhao0621-tech/netlify-demo/settings
2. **Repository name** 改为 `quantos-cn`
3. 保存

或在终端（需已 `gh auth login`）：

```bash
gh auth refresh -h github.com
gh repo rename quantos-cn --repo kenzhao0621-tech/netlify-demo
```

## 2. 更新本地 remote 并推送

```bash
cd /path/to/quantos-cn   # 原 netlify-demo 目录

git remote set-url origin https://github.com/kenzhao0621-tech/quantos-cn.git

git push -u origin fix/a-share-quant-reliability-paper-validation

# 合并到 main（可选）
git checkout main
git merge fix/a-share-quant-reliability-paper-validation
git push origin main
```

## 3. 打 Release 标签

```bash
git tag -a v4.1.0 -m "QuantOS CN v4.1 — live screener, learning loop, quantos-cn rebrand"
git push origin v4.1.0
```

在 GitHub **Releases** 用 [CHANGELOG.md](../CHANGELOG.md) 创建 Release 说明。

## 4. 仓库 About 设置

| 字段 | 建议 |
|------|------|
| Description | China A-share intelligent quant screener — multi-factor, live quotes, paper trading |
| Topics | `quantitative-finance` `a-share` `stock-screener` `fastapi` `duckdb` `paper-trading` |

## 5. 验证

```bash
git clone https://github.com/kenzhao0621-tech/quantos-cn.git
cd quantos-cn
make bootstrap && make app
# → http://127.0.0.1:8787/portal
```
