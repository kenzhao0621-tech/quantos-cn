# macOS launchd 调度文件

本目录下的 `*.plist` 由量化调度器在**本地安装时自动生成**（含你的仓库绝对路径），**不提交 Git**。

生成方式示例：

```bash
.venv-china-quant/bin/python -m quant.daily_report_scheduler install
.venv-china-quant/bin/python -m quant.intraday_update_scheduler install
```

Windows 用户请使用任务计划程序，或手动运行 `scripts/run-daily-report-scheduled.sh` 等等价脚本。
