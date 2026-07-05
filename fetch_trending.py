#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Trending Weekly Report - Email Sender
自动获取 GitHub Trending 并发送邮件（含中文翻译描述）
"""

import os
import re
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

# 语言颜色映射
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
    """将英文翻译成中文（使用免费 MyMemory API）"""
    if not text or not text.strip():
        return text
    
    # 已经包含中文则不翻译
    if re.search(r'[\u4e00-\u9fff]', text):
        return text.strip()
    
    try:
        # 使用 MyMemory 免费翻译 API
        url = "https://api.mymemory.translated.net/get"
        params = {
            'q': text,
            'langpair': 'en|zh-CN'
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        translated = data.get('responseData', {}).get('translatedText', '')
        
        # 检查翻译是否成功（MyMemory 有时会返回原文）
        if translated and translated != text and re.search(r'[\u4e00-\u9fff]', translated):
            return translated.strip()
        
        return text.strip()  # 翻译失败返回原文
        
    except Exception as e:
        print(f"⚠️ 翻译失败 ({text[:30]}...): {e}")
        return text.strip()


def fetch_github_trending() -> List[Dict]:
    """通过抓取 GitHub Trending 页面获取数据"""

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
                url = f"https://github.com{href}" if href.startswith('/') else href

                desc_tag = article.select_one('p')
                description = desc_tag.get_text().strip() if desc_tag else '无描述'

                lang_tag = article.select_one('[itemprop="programmingLanguage"]') or \
                           article.select_one('span[itemprop="programmingLanguage"]')
                language = lang_tag.get_text().strip() if lang_tag else '未知'

                stars_link = article.select_one('a[href*="stargazers"]')
                total_stars = 0
                if stars_link:
                    stars_text = stars_link.get_text().strip()
                    total_stars = parse_stars(stars_text)

                weekly_stars_el = article.select_one('.float-sm-right') or \
                                  article.select_one('[class*="float-right"] span')
                weekly_stars_text = ''
                weekly_stars = 0
                if weekly_stars_el:
                    weekly_stars_text = weekly_stars_el.get_text().strip()
                    nums = re.findall(r'[\d,]+', weekly_stars_text)
                    if nums:
                        weekly_stars = int(nums[0].replace(',', ''))

                forks_link = article.select_one('a[href*="forks"]')
                forks = 0
                if forks_link:
                    forks_text = forks_link.get_text().strip()
                    forks = parse_stars(forks_text)

                projects.append({
                    'name': full_name,
                    'url': url,
                    'description': description,
                    'language': language,
                    'total_stars': total_stars,
                    'weekly_stars': weekly_stars,
                    'forks': forks,
                    'weekly_stars_text': weekly_stars_text,
                })
            except Exception as e:
                continue

        print(f"✅ 成功解析 {len(projects)} 个项目")
        return projects

    except Exception as e:
        print(f"❌ 获取 GitHub Trending 失败: {e}")
        return []


def parse_stars(text: str) -> int:
    """将 '12.3k' / '1,234' 格式转为整数"""
    text = text.strip().lower().replace(',', '')
    if text.endswith('k'):
        return int(float(text[:-1]) * 1000)
    return int(re.sub(r'[^\d]', '', text)) if text.replace('.', '').isdigit() else 0


def generate_html_report(projects: List[Dict]) -> str:
    """生成 HTML 格式的报告（带中文翻译）"""
    now = datetime.now()
    date_str = now.strftime('%Y年%m月%d日')

    # 统计语言分布
    lang_count = {}
    for p in projects:
        lang = p['language']
        lang_count[lang] = lang_count.get(lang, 0) + 1
    top_languages = sorted(lang_count.items(), key=lambda x: x[1], reverse=True)[:5]

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

<div class="section-title">🏆 本周 TOP {min(len(projects), 15)} 热门项目</div>"""

    print("🔤 正在翻译项目描述...")
    for i, project in enumerate(projects[:15], 1):
        lang_color = LANGUAGE_COLORS.get(project.get('language', ''), LANGUAGE_COLORS['Unknown'])
        weekly_html = f'<span class="weekly-stars">🔥 +{project["weekly_stars"]:,} this week</span>' if project.get('weekly_stars') else ''

        # 翻译描述
        desc_en = project['description']
        desc_zh = translate_to_chinese(desc_en)

        if i <= 3:  # 只打印前3个翻译进度
            print(f"  [{i}/15] {project['name']}: {desc_zh[:40]}...")

        # 如果翻译结果和原文不同，显示双语；否则只显示原文
        if desc_zh and desc_zh != desc_en:
            desc_html = f'<div class="desc-original">📝 {desc_en}</div><div class="desc-zh">🇨🇳 {desc_zh}</div>'
        else:
            desc_html = f'<div class="desc-zh">{desc_en}</div>'

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
<p>💻 仓库: <a href="https://github.com/luoluo-up/github-trending-weekly">github-trending-weekly</a></p>
</div>
</body></html>"""

    return html


def send_email(html_content: str, recipient: str):
    """发送邮件"""
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

    print(f"✅ 成功获取 {len(projects)} 个项目")

    print("📝 生成 HTML 报告...")
    html_content = generate_html_report(projects)

    output_file = f"github-trending-{datetime.now().strftime('%Y-%m-%d')}.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"💾 报告已保存: {output_file}")

    recipient = os.environ.get('EMAIL_RECIPIENT', '601119280@qq.com')
    print(f"📧 正在发送邮件到 {recipient}...")
    send_email(html_content, recipient)

    print("🎉 完成！")


if __name__ == '__main__':
    main()
