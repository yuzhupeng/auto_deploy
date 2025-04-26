"""
消息通知模块 - 发送部署状态通知
"""

from config import NOTIFICATION
import sys
import json
import time
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from string import Template
from typing import Dict, List, Any, Optional, Union

# 添加项目根目录到路径
sys.path.append('..')

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NotificationManager:
    """消息通知管理器"""

    def __init__(self, config=NOTIFICATION):
        """
        初始化通知管理器

        Args:
            config (Dict[str, Any]): 通知配置
        """
        self.config = config

    def send_notification(self, template_data: Dict[str, Any],
                          channels: List[str] = None) -> Dict[str, bool]:
        """
        发送通知到多个渠道

        Args:
            template_data (Dict[str, Any]): 模板数据
            channels (List[str], optional): 通知渠道列表

        Returns:
            Dict[str, bool]: 各渠道发送结果
        """
        if not channels:
            # 默认使用所有配置的渠道
            channels = [k for k in self.config.keys(
            ) if isinstance(self.config[k], dict)]

        results = {}

        for channel in channels:
            if channel in self.config:
                channel_config = self.config[channel]

                if channel == "slack":
                    results[channel] = self._send_slack(
                        channel_config, template_data)
                elif channel == "email":
                    results[channel] = self._send_email(
                        channel_config, template_data)
                elif channel == "wecom":
                    results[channel] = self._send_wecom(
                        channel_config, template_data)
                else:
                    logger.warning(f"未知的通知渠道: {channel}")
                    results[channel] = False
            else:
                logger.warning(f"未配置的通知渠道: {channel}")
                results[channel] = False

        return results

    def _send_slack(self, config: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """
        发送Slack通知

        Args:
            config (Dict[str, Any]): Slack配置
            data (Dict[str, Any]): 模板数据

        Returns:
            bool: 操作是否成功
        """
        try:
            webhook_url = config.get("webhook")
            if not webhook_url:
                logger.error("未配置Slack Webhook URL")
                return False

            # 获取模板
            template_str = config.get("template", "")
            if not template_str:
                # 默认模板
                template_str = """
                :rocket: *部署通知*
                *项目*: ${project_name}
                *环境*: ${environment}
                *状态*: ${status}
                *版本*: ${version}
                *时间*: ${timestamp}
                ${details}
                """

            # 填充模板
            template = Template(template_str)
            message = template.safe_substitute(data)

            # 发送请求
            payload = {
                "text": message
            }

            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code in [200, 201]:
                logger.info("Slack通知发送成功")
                return True
            else:
                logger.error(
                    f"Slack通知发送失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"发送Slack通知时出错: {str(e)}")
            return False

    def _send_email(self, config: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """
        发送邮件通知

        Args:
            config (Dict[str, Any]): 邮件配置
            data (Dict[str, Any]): 模板数据

        Returns:
            bool: 操作是否成功
        """
        try:
            smtp_server = config.get("smtp_server")
            smtp_port = config.get("smtp_port", 587)
            username = config.get("username")
            password = config.get("password")

            if not all([smtp_server, username, password]):
                logger.error("邮件配置不完整")
                return False

            # 获取收件人
            recipients = data.get(
                "recipients", config.get("default_recipients", []))
            if not recipients:
                logger.error("未指定收件人")
                return False

            # 获取邮件主题
            subject_template = config.get("subject", "部署通知 - ${project_name}")
            subject = Template(subject_template).safe_substitute(data)

            # 获取邮件正文模板
            body_template_str = config.get("template", "")
            if not body_template_str:
                # 默认HTML模板
                body_template_str = """
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body { font-family: Arial, sans-serif; }
                        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                        .header { background-color: #f8f9fa; padding: 10px; border-bottom: 1px solid #ddd; }
                        .content { padding: 20px 0; }
                        .footer { color: #6c757d; font-size: 12px; margin-top: 30px; }
                        .success { color: #28a745; }
                        .failure { color: #dc3545; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h2>部署通知</h2>
                        </div>
                        <div class="content">
                            <p><strong>项目:</strong> ${project_name}</p>
                            <p><strong>环境:</strong> ${environment}</p>
                            <p><strong>状态:</strong> <span class="${status == 'success' ? 'success' : 'failure'}">${status}</span></p>
                            <p><strong>版本:</strong> ${version}</p>
                            <p><strong>时间:</strong> ${timestamp}</p>
                            ${details ? '<div><strong>详情:</strong><pre>' + details + '</pre></div>' : ''}
                        </div>
                        <div class="footer">
                            <p>此邮件由自动部署系统发送，请勿回复。</p>
                        </div>
                    </div>
                </body>
                </html>
                """

            # 填充模板
            body_template = Template(body_template_str)
            body = body_template.safe_substitute(data)

            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = username
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = subject

            # 添加正文
            msg.attach(MIMEText(body, "html"))

            # 发送邮件
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.sendmail(username, recipients, msg.as_string())

            logger.info(f"邮件已发送至: {', '.join(recipients)}")
            return True

        except Exception as e:
            logger.error(f"发送邮件通知时出错: {str(e)}")
            return False

    def _send_wecom(self, config: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """
        发送企业微信通知

        Args:
            config (Dict[str, Any]): 企业微信配置
            data (Dict[str, Any]): 模板数据

        Returns:
            bool: 操作是否成功
        """
        try:
            webhook_url = config.get("webhook")
            if not webhook_url:
                logger.error("未配置企业微信Webhook URL")
                return False

            # 获取模板
            template_str = config.get("template", "")
            if not template_str:
                # 默认模板
                template_str = """
                【部署通知】
                项目：${project_name}
                环境：${environment}
                状态：${status}
                版本：${version}
                时间：${timestamp}
                ${details}
                """

            # 填充模板
            template = Template(template_str)
            message = template.safe_substitute(data)

            # 发送请求
            payload = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }

            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code in [200, 201]:
                response_data = response.json()
                if response_data.get("errcode") == 0:
                    logger.info("企业微信通知发送成功")
                    return True
                else:
                    logger.error(f"企业微信通知发送失败: {response_data.get('errmsg')}")
                    return False
            else:
                logger.error(
                    f"企业微信通知发送失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"发送企业微信通知时出错: {str(e)}")
            return False


def send_deployment_notification(project_name, environment, status, version=None,
                                 details=None, channels=None):
    """
    发送部署通知

    Args:
        project_name (str): 项目名称
        environment (str): 环境
        status (str): 状态
        version (str, optional): 版本
        details (str, optional): 详情
        channels (List[str], optional): 通知渠道

    Returns:
        Dict[str, bool]: 各渠道发送结果
    """
    # 准备模板数据
    template_data = {
        "project_name": project_name,
        "environment": environment,
        "status": status,
        "version": version or "未知",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "details": details or ""
    }

    # 发送通知
    manager = NotificationManager()
    return manager.send_notification(template_data, channels)


if __name__ == "__main__":
    # 测试用例
    template_data = {
        "project_name": "测试项目",
        "environment": "开发环境",
        "status": "success",
        "version": "v1.0.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "details": "部署过程顺利完成，无异常。\n构建时间: 2分钟\n部署时间: 1分钟"
    }

    manager = NotificationManager()
    results = manager.send_notification(
        template_data, ["slack", "email", "wecom"])

    for channel, success in results.items():
        print(f"{channel}: {'成功' if success else '失败'}")
