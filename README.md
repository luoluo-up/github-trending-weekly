# GitHub Trending 自动周报

自动获取 GitHub Trending 项目并发送邮件到你的邮箱 📧

## 🚀 快速开始

### 1. Fork 或创建新仓库

将本仓库复制到你的 GitHub 账号下

### 2. 配置邮箱 Secrets

在 GitHub 仓库设置中添加以下 Secrets：

1. 进入仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**，添加以下 5 个密钥：

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `EMAIL_SENDER` | 发送者邮箱 | `601119280@qq.com` |
| `EMAIL_PASSWORD` | QQ邮箱授权码 | `nmkqbnodlifmbfdi` |
| `EMAIL_RECIPIENT` | 接收者邮箱 | `601119280@qq.com` |
| `SMTP_SERVER` | SMTP服务器 | `smtp.qq.com` |
| `SMTP_PORT` | SMTP端口 | `465` |

### 3. 启用 GitHub Actions

1. 进入仓库 **Actions** 标签页
2. 启用工作流
3. 可以手动触发测试：点击 **Run workflow**

### 4. 自动运行

- ✅ 每周日早上 9:00 (北京时间) 自动运行
- ✅ 邮件会自动发送到你的邮箱
- ✅ 报告也会作为 Artifact 保存，可在 Actions 页面下载

## 📋 文件说明

- `fetch_trending.py` - 主脚本，获取 Trending 并发送邮件
- `.github/workflows/send-report.yml` - GitHub Actions 配置
- `requirements.txt` - Python 依赖（如有）

## 🛠️ 自定义

### 修改执行时间

编辑 `.github/workflows/send-report.yml` 中的 cron 表达式：

```yaml
schedule:
  - cron: '0 1 * * 0'  # 每周日 9:00 北京时间
```

Cron 格式：`分 时 日 月 周`

北京时间 = UTC+8，所以：
- 北京时间 9:00 = UTC 1:00
- 如果你想改成其他时间，用这个网站计算：https://crontab.guru/

### 修改邮件内容

编辑 `fetch_trending.py` 中的 `generate_html_report()` 函数

## 🔍 故障排查

### 邮件发送失败

1. 检查 QQ 邮箱授权码是否正确
2. 确认 SMTP 设置是否正确
3. 查看 GitHub Actions 运行日志

### 没有收到邮件

1. 检查垃圾邮件文件夹
2. 在 GitHub Actions 日志中查看是否发送成功
3. 手动触发一次工作流测试

## 📚 技术栈

- **Python 3.11** - 脚本语言
- **GitHub Actions** - 自动化平台
- **QQ 邮箱 SMTP** - 邮件发送
- **GitHub API** - 获取 Trending 数据

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT License

---

**由 WorkBuddy 自动生成** 🤖
