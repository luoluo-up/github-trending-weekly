#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Trending Weekly Report - Email + Gitee Sync
自动获取 GitHub Trending → 调 Gemini API 生成中文解读 → 发邮件 + 推送到 Gitee Obsidian 仓库
"""

import os
import re
import json
import base64
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
try:
    from bs4 import BeautifulSoup
except ImportError:
    from html.parser import HTMLParser

TOP_N = 10  # TOP 10

# Gemini API（需要 GEMINI_API_KEY；模型可改 gemini-1.5-flash / gemini-2.0-flash 等）
GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
EXPLAIN_MODEL = "gemini-2.5-flash"

LANGUAGE_COLORS = {
    'Python': '#3572A5', 'JavaScript': '#f1e05a', 'TypeScript': '#2b7489',
    'Java': '#b07219', 'Go': '#00ADD8', 'Rust': '#dea584',
    'C++': '#f34b7d', 'C': '#555555', 'Ruby': '#701516',
    'Swift': '#F05138', 'Kotlin': '#A97BFF', 'Dart': '#00B4AB',
    'Shell': '#89e051', 'HTML': '#e34c26', 'CSS': '#563d7c',
    'Vue': '#41b883', 'R': '#198CE7', 'PHP': '#4F5D95',
    'Scala': '#c22d40', 'Elixir': '#6e4a7e', 'Haskell': '#5e5086',
    'Unknown': '#858585'
}


def translate_to_chinese(text: str) -> str:
    if not text or not text.strip():
        return text
    if re.search(r'[\u4e00-\u9fff]', text):
        return text.strip()
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {'q': text, 'langpair': 'en|zh-CN'}
        resp = requests.get(url, params=params, timeout=10).json()
        translated = resp.get('responseData', {}).get('translatedText', '')
        if translated and translated != text and re.search(r'[\u4e00-\u9fff]', translated):
            return translated.strip()
        return text.strip()
    except Exception as e:
        print(f"  ⚠️ 翻译失败 ({text[:30]}...): {e}")
        return text.strip()


def generate_explanation(project: Dict, api_key: str) -> str:
    """调用 Gemini API 生成项目中文解读；失败则返回空串（降级为仅翻译）"""
    if not api_key:
        return ""
    prompt = (
        "你是一个技术周报编辑。请用简洁专业的中文，为下面的 GitHub 热门开源项目写一段约 90-150 字的解读，"
        "包含：它是什么（一句话定位）、解决什么痛点、为什么本周受欢迎、适合谁用。"
        "不要使用标题，写成连贯的一段话，不要啰嗦。\n\n"
        f"项目名：{project['name']}\n"
        f"描述：{project['description']}\n"
        f"主要语言：{project['language']}\n"
        f"总 Stars：{project['total_stars']:,}\n"
        f"本周新增 Stars：{project['weekly_stars']:,}"
    )
    url = GEMINI_API_ENDPOINT.format(model=EXPLAIN_MODEL) + f"?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 400,
            "thinkingConfig": {"thinkingBudget": 0},  # 关闭思考，避免占用输出 token 导致解读被截断
        },
    }
    try:
        resp = requests.post(url, json=payload, timeout=45)
        if resp.status_code == 200:
            data = resp.json()
            cand = data.get("candidates", [{}])[0]
            if cand.get("finishReason") == "SAFETY":
                print("  ⚠️ Gemini 因安全策略拦截，跳过该解读")
                return ""
            return cand.get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        print(f"  ⚠️ Gemini 解读失败 ({resp.status_code}): {resp.text[:200]}")
        return ""
    except Exception as e:
        print(f"  ⚠️ Gemini 解读异常: {e}")
        return ""


def fetch_github_trending() -> List[Dict]:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cache-Control': 'no-cache',
    }
    projects = []
    try:
        print("📡 正在获取 GitHub Trending 页面...")
        url = "https://github.com/trending?since=weekly"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.select('article.Box-row')
        if not articles:
            articles = soup.select('.repo-list-item') or soup.select('li[class*="col-12"]')

        for article in articles:
            try:
                name_tag = article.select_one('h2 a') or article.select_one('h2 > a')
                if not name_tag:
                    continue
                name_parts = [s.strip() for s in name_tag.get_text().strip().split('/') if s.strip()]
                full_name = '/'.join(name_parts)
                href = name_tag.get('href', '')
                proj_url = f"https://github.com{href}" if href.startswith('/') else href

                desc_tag = article.select_one('p')
                description = desc_tag.get_text().strip() if desc_tag else '无描述'

                lang_tag = article.select_one('[itemprop="programmingLanguage"]') or \
                           article.select_one('span[itemprop="programmingLanguage"]')
                language = lang_tag.get_text().strip() if lang_tag else '未知'

                stars_link = article.select_one('a[href*="stargazers"]')
                total_stars = parse_stars(stars_link.get_text().strip()) if stars_link else 0

                weekly_stars_el = article.select_one('.float-sm-right') or \
                                  article.select_one('[class*="float-right"] span')
                weekly_stars = 0
                if weekly_stars_el:
                    nums = re.findall(r'[\d,]+', weekly_stars_el.get_text().strip())
                    if nums:
                        weekly_stars = int(nums[0].replace(',', ''))

                forks_link = article.select_one('a[href*="forks"]')
                forks = parse_stars(forks_link.get_text().strip()) if forks_link else 0

                projects.append({
                    'name': full_name, 'url': proj_url, 'description': description,
                    'language': language, 'total_stars': total_stars,
                    'weekly_stars': weekly_stars, 'forks': forks,
                    'explanation': '',
                })
            except Exception:
                continue
        print(f"✅ 成功解析 {len(projects)} 个项目")
        return projects
    except Exception as e:
        print(f"❌ 获取 GitHub Trending 失败: {e}")
        return []


def parse_stars(text: str) -> int:
    text = text.strip().lower().replace(',', '')
    if text.endswith('k'):
        return int(float(text[:-1]) * 1000)
    return int(re.sub(r'[^\d]', '', text)) if text.replace('.', '').isdigit() else 0


def generate_html_report(projects: List[Dict]) -> str:
    now = datetime.now()
    date_str = now.strftime('%Y年%m月%d日')
    lang_count = {}
    for p in projects:
        lang = p['language']
        lang_count[lang] = lang_count.get(lang, 0) + 1
    top_languages = sorted(lang_count.items(), key=lambda x: x[1], reverse=True)[:5]
    n = min(len(projects), TOP_N)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  line-height:1.6; color:#24292e; max-width:900px; margin:0 auto; padding:20px; background:#f6f8fa; }}
.header {{ background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:#fff;
  padding:30px; border-radius:10px; margin-bottom:30px; text-align:center; }}
.header h1 {{ margin:0; font-size:28px; }} .header p {{ margin:10px 0 0; opacity:.9; }}
.project {{ background:#fff; border:1px solid #e1e4e8; border-radius:8px; padding:20px;
  margin-bottom:15px; transition:all .3s; }}
.project:hover {{ box-shadow:0 4px 12px rgba(0,0,0,.1); transform:translateY(-2px); }}
.project-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:8px; }}
.project-name {{ font-size:18px; font-weight:600; color:#0366d6; text-decoration:none; }}
.project-name:hover {{ text-decoration:underline; }}
.stars-badge {{ display:flex; align-items:center; gap:15px; flex-wrap:wrap; }}
.total-stars {{ background:#f1f3f5; padding:5px 12px; border-radius:20px; font-size:14px; color:#586069; }}
.weekly-stars {{ background:#dafbe1; padding:5px 12px; border-radius:20px; font-size:14px; color:#1a7f37; }}
.desc-original {{ color:#586069; font-size:13px; margin:6px 0; line-height:1.5; }}
.desc-zh {{ color:#24292e; font-weight:500; font-size:14px; margin:6px 0 10px; line-height:1.5;
  padding-left:12px; border-left:3px solid #667eea; }}
.desc-explain {{ color:#1f6feb; font-size:13px; margin:8px 0 4px; line-height:1.6; background:#f6f8fa;
  padding:10px 12px; border-radius:6px; border-left:3px solid #1f6feb; }}
.project-meta {{ display:flex; gap:15px; font-size:14px; color:#586069; }}
.lang-dot {{ width:12px; height:12px; border-radius:50%; display:inline-block; vertical-align:middle; }}
.section-title {{ font-size:22px; font-weight:600; margin:30px 0 15px; color:#24292e; }}
.lang-bar {{ display:inline-flex; align-items:center; gap:8px; background:#fff; padding:8px 16px;
  border-radius:20px; border:1px solid #e1e4e8; font-size:14px; }}
.footer {{ text-align:center; margin-top:40px; padding:20px; color:#586069; font-size:14px; }}
.trend-section {{ background:#fff; border:1px solid #e1e4e8; border-radius:8px; padding:20px; margin-top:30px; }}
</style></head><body>

<div class="header"><h1>📊 GitHub Trending 周报</h1>
<p>{date_str} | 本周最热门的开源项目汇总</p></div>

<div class="section-title">🏆 本周 TOP {n} 热门项目</div>"""

    print("🔤 正在翻译项目描述...")
    for i, project in enumerate(projects[:TOP_N], 1):
        lang_color = LANGUAGE_COLORS.get(project.get('language', ''), LANGUAGE_COLORS['Unknown'])
        weekly_html = f'<span class="weekly-stars">🔥 +{project["weekly_stars"]:,} this week</span>' if project.get('weekly_stars') else ''
        desc_en = project['description']
        desc_zh = translate_to_chinese(desc_en)
        if i <= 3:
            print(f"  [{i}/{TOP_N}] {project['name']}: {desc_zh[:40]}...")
        if desc_zh and desc_zh != desc_en:
            desc_html = f'<div class="desc-original">📝 {desc_en}</div><div class="desc-zh">🇨🇳 {desc_zh}</div>'
        else:
            desc_html = f'<div class="desc-zh">{desc_en}</div>'
        explanation = project.get('explanation', '')
        explain_html = f'<div class="desc-explain">💡 {explanation}</div>' if explanation else ''
        html += f"""
<div class="project">
  <div class="project-header">
    <a href="{project['url']}" class="project-name">{i}. {project['name']}</a>
    <div class="stars-badge">
      <span class="total-stars">⭐ {project['total_stars']:,}</span>
      {weekly_html}
    </div>
  </div>
  {desc_html}
  {explain_html}
  <div class="project-meta">
    <span><span class="lang-dot" style="background:{lang_color}"></span> {project['language']}</span>
    <span>🍴 {project['forks']:,} forks</span>
  </div>
</div>"""
    print("✅ 翻译完成")

    html += f"""
<div class="trend-section">
  <div class="section-title">📈 本周趋势分析</div>
  <p><strong>🔥 热门语言：</strong> """
    html += ' '.join([f'<span class="lang-bar"><span class="lang-dot" style="background:{LANGUAGE_COLORS.get(l, "#888")}"></span>{l} ({c})</span>' for l, c in top_languages])
    html += """</p>
</div>

<div class="footer">
<p>📊 由 GitHub Actions 自动生成 | 数据来源: github.com/trending</p>
</div>
</body></html>"""
    return html


def generate_markdown_report(projects: List[Dict]) -> str:
    now = datetime.now()
    date_str = now.strftime('%Y年%m月%d日')
    lang_count = {}
    for p in projects:
        lang = p['language']
        lang_count[lang] = lang_count.get(lang, 0) + 1
    top_languages = sorted(lang_count.items(), key=lambda x: x[1], reverse=True)[:5]
    n = min(len(projects), TOP_N)

    md = f"""# 📊 GitHub Trending 周报 - {date_str}

> 本周最热门的开源项目汇总 | 数据来源: [github.com/trending](https://github.com/trending?since=weekly)

---

## 🏆 本周 TOP {n} 热门项目

"""
    print("🔤 正在翻译项目描述 (Markdown)...")
    for i, project in enumerate(projects[:TOP_N], 1):
        desc_en = project['description']
        desc_zh = translate_to_chinese(desc_en)
        weekly_str = f' 🔥 +{project["weekly_stars"]:,} this week' if project.get('weekly_stars') else ''
        md += f"""### {i}. [{project['name']}]({project['url']})

"""
        if desc_zh and desc_zh != desc_en:
            md += f"""> 📝 {desc_en}

> 🇨🇳 **{desc_zh}**

"""
        else:
            md += f"""> {desc_en}

"""
        explanation = project.get('explanation', '')
        explain_md = f"- 💡 **解读**: {explanation}\n" if explanation else ""
        md += f"""- 🔵 **语言**: {project['language']}
- ⭐ **总 Stars**: {project['total_stars']:,}{weekly_str}
- 🍴 **Forks**: {project['forks']:,}
{explain_md}
"""

    md += """---

## 📈 本周趋势分析

**🔥 热门语言：**

| 语言 | 项目数 |
|------|--------|
"""
    for lang, count in top_languages:
        md += f"| {lang} | {count} |\n"

    md += f"""

---

> 📊 由 GitHub Actions 自动生成 | {now.strftime('%Y-%m-%d %H:%M')} (UTC)

"""
    return md


def send_email(html_content: str, recipient: str):
    sender_email = os.environ.get('EMAIL_SENDER', '601119280@qq.com')
    sender_password = os.environ.get('EMAIL_PASSWORD')
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.qq.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '465'))
    date_str = datetime.now().strftime('%Y年%m月%d日')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'📊 GitHub Trending 周报 - {date_str}'
    msg['From'] = sender_email
    msg['To'] = recipient
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print(f"✅ 邮件发送成功: {recipient}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False


def main():
    print("🚀 开始生成 GitHub Trending 周报...")

    projects = fetch_github_trending()
    if not projects:
        print("❌ 未获取到任何数据，终止执行")
        exit(1)

    print(f"✅ 成功获取 {len(projects)} 个项目（将取 TOP {TOP_N}）")

    # 0.5 调用 Gemini API 生成项目解读（需要 GEMINI_API_KEY）
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    if gemini_key:
        print("🤖 调用 Gemini API 生成项目解读...")
        for idx, p in enumerate(projects[:TOP_N], 1):
            print(f"  [{idx}/{TOP_N}] 解读: {p['name']}")
            p['explanation'] = generate_explanation(p, gemini_key)
    else:
        print("⚠️ 未检测到 GEMINI_API_KEY，跳过 LLM 解读（仅保留翻译描述）")

    # 1. HTML 报告（邮件用）
    print("📝 生成 HTML 报告...")
    html_content = generate_html_report(projects)
    html_file = f"github-trending-{datetime.now().strftime('%Y-%m-%d')}.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"💾 HTML 报告已保存: {html_file}")

    # 2. Markdown 报告（Obsidian 用）
    print("📝 生成 Markdown 报告...")
    md_content = generate_markdown_report(projects)
    md_file = f"github-trending-{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"💾 Markdown 报告已保存: {md_file}")

    # 3. 发送邮件
    recipient = os.environ.get('EMAIL_RECIPIENT', '601119280@qq.com')
    print(f"📧 正在发送邮件到 {recipient}...")
    send_email(html_content, recipient)

    # 4. Markdown 文件已保存，由 workflow 的 git 步骤推送到 Gitee
    print("📂 Markdown 文件已生成，将由 GitHub Actions 推送到 Gitee Obsidian 仓库 (技术/技术周报/)")

    print("🎉 完成！")


if __name__ == '__main__':
    main()
