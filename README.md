# legalGym 宣传站

面向律师和合作伙伴的本地静态展示。C06 演示改编自工程咨询合同审查工作流，案卷、公司和业务记录全部为虚构数据。

- `site/index.html` 是宣传站入口，可直接在浏览器打开。部署时静态托管整个 `site` 目录。
- `site/mock/index.html` 是可查询的模拟资料室，包含企业名录、融资台账、报价和授权记录。
- `site/assets/c06-contract-redline.docx` 由模型提交的条款修订和批注导出。这个样例用于律师复核。
- 参与入口可生成并复制意向说明，供访客发给项目分享人。公开发布前可换成项目的正式联系入口。

## 接入案例视频

将 MP4 放入 `site/assets/c06-demo.mp4`，在 `site/index.html` 的 `<video id="case-video">` 上填写 `data-src="assets/c06-demo.mp4"`。视频载入后会在预留区域显示播放器。

## 重跑 C06

需要 Python、Playwright Chromium 和可运行的 `dsh`。先将 `DEEPSEEK_API_KEY` 设置在环境变量中，再执行：

```powershell
python run_case.py --run-dir .run/c06-retest
```

运行目录应尚未存在。如果安装的 dsh 不在标准 npm 路径，可加 `--dsh-entry <dsh 安装目录中的 lib/bin.js>`。运行提供本案读取、模拟浏览器、答卷提交三个专用工具，使用本地回环地址和临时 dsh 配置。浏览器动作会留下页面文字和真实截图。

使用安装了 python-docx 1.2 或以上的 Python 导出：

```powershell
python export_run.py .run/c06-retest
```

导出检查答卷确实经 dsh 提交，并要求引用的记录在浏览器轨迹中可查；它不作法律质量评分。`.run/` 保存本地原始记录，宣传站在视频下方回放导出的操作轨迹，并提供修改后的 Word 合同下载。

