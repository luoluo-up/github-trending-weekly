#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Trending Weekly Report - Email Sender
自动获取 GitHub Trending 并发送邮件
"""

import os
import json
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict


def fetch_github_trending() -> List[Dict]:
    """获取 GitHub Trending 数据"""
    url = "https://api.github.com/search/repositories"
    
    # 搜索最近一周创建或更新的热门仓库
    one_week_ago = (datetime.now() - __import__('datetime').timedelta(days=7)).strftime('%Y-%m-%d')
    
    params = {
        'q': f'created:>{one_week_ago} OR pushed:>{one_week_ago}',
        'sort': 'stars',
        'order': 'desc',
        'per_page': 15
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        projects = []
        for item in data.get('items', []):
            projects.append({
                'name': item['full_name'],
                'url': item['html_url'],
                'description': item['description'] or '无描述',
                'language': item['language'] or '未知',
                'total_stars': item['stargazers_count'],
                'forks': item['forks_count'],
            })
        
        return projects
    except Exception as e:
        print(f"❌ 获取 GitHub Trending 失败: {e}")
        return []


def generate_html_report(projects: List[Dict]) -> str:
    """生成 HTML 格式的报告"""
    now = datetime.now()
    date_str = now.strftime('%Y年%m月%d日')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: #24292e;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f6f8fa;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
            }}
            .header p {{
                margin: 10px 0 0 0;
                opacity: 0.9;
            }}
            .project {{
                background: white;
                border: 1px solid #e1e4e8;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 15px;
                transition: all 0.3s;
            }}
            .project:hover {{
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                transform: translateY(-2px);
            }}
            .project-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }}
            .project-name {{
                font-size: 18px;
                font-weight: 600;
                color: #0366d6;
                text-decoration: none;
            }}
            .project-name:hover {{
                text-decoration: underline;
            }}
            .project-stars {{
                background: #f1f3f5;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 14px;
                color: #586069;
            }}
            .project-description {{
                color: #586069;
                margin: 10px 0;
            }}
            .project-meta {{
                display: flex;
                gap: 15px;
                font-size: 14px;
                color: #586069;
            }}
            .project-language {{
                display: flex;
                align-items: center;
                gap: 5px;
            }}
            .language-dot {{
                width: 12px;
                height: 12px;
                border-radius: 50%;
                background: #f1e05a;
            }}
            .footer {{
                text-align: center;
                margin-top: 40px;
                padding: 20px;
                color: #586069;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 GitHub Trending 周报</h1>
            <p>{date_str} | 本周最热门的开源项目汇总</p>
        </div>
    """
    
    for i, project in enumerate(projects, 1):
        html += f"""
        <div class="project">
            <div class="project-header">
                <a href="{project['url']}" class="project-name">
                    {i}. {project['name']}
                </a>
                <span class="project-stars">
                    ⭐ {project['total_stars']:,}
                </span>
            </div>
            <div class="project-description">
                {project['description']}
            </div>
            <div class="project-meta">
                <div class="project-language">
                    <span class="language-dot"></span>
                    <span>{project['language']}</span>
                </div>
                <div>
                    🍴 {project['forks']:,} forks
                </div>
            </div>
        </div>
        """
    
    html += """
        <div class="footer">
            <p>📊 由 GitHub Actions 自动生成 | 数据来源: GitHub API</p>
            <p>💡 想要自定义周报？访问 <a href="https://github.com">GitHub</a></p>
        </div>
    </body>
    </html>
    """
    
    return html


def send_email(html_content: str, recipient: str):
    """发送邮件"""
    # 从环境变量获取邮箱配置
    sender_email = os.environ.get('EMAIL_SENDER', '601119280@qq.com')
    sender_password = os.environ.get('EMAIL_PASSWORD')  # QQ邮箱授权码
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.qq.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '465'))
    
    now = datetime.now()
    date_str = now.strftime('%Y年%m月%d日')
    
    # 创建邮件
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'📊 GitHub Trending 周报 - {date_str}'
    msg['From'] = sender_email
    msg['To'] = recipient
    
    # HTML 内容
    html_part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(html_part)
    
    try:
        # 连接 SMTP 服务器并发送
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print(f"✅ 邮件发送成功: {recipient}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False


def main():
    """主函数"""
    print("🚀 开始生成 GitHub Trending 周报...")
    
    # 获取 Trending 数据
    print("📡 正在获取 GitHub Trending 数据...")
    projects = fetch_github_trending()
    
    if not projects:
        print("⚠️ 未获取到数据，使用测试数据")
        projects = [
            {
                'name': 'example/project',
                'url': 'https://github.com',
                'description': '示例项目',
                'language': 'Python',
                'total_stars': 1000,
                'forks': 100,
            }
        ]
    
    print(f"✅ 成功获取 {len(projects)} 个项目")
    
    # 生成 HTML 报告
    print("📝 生成 HTML 报告...")
    html_content = generate_html_report(projects)
    
    # 保存本地备份
    output_file = f"github-trending-{datetime.now().strftime('%Y-%m-%d')}.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"💾 报告已保存: {output_file}")
    
    # 发送邮件
    recipient = os.environ.get('EMAIL_RECIPIENT', '601119280@qq.com')
    print(f"📧 正在发送邮件到 {recipient}...")
    send_email(html_content, recipient)
    
    print("🎉 完成！")


if __name__ == '__main__':
    main()
