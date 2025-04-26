"""
配置文件 - 包含所有外部服务API密钥和配置项
"""

# Dify API配置
DIFY_API_KEY = "your_dify_api_key"
DIFY_API_URL = "https://api.dify.ai/v1"

# 大模型API配置
LLM_API_KEY = "your_llm_api_key"
LLM_API_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4"

# Git配置
GIT_USERNAME = "your_git_username"
GIT_TOKEN = "your_git_token"
DEFAULT_BRANCH = "main"

# Jenkins配置
JENKINS_URL = "https://jenkins.example.com"
JENKINS_USER = "jenkins_user"
JENKINS_TOKEN = "jenkins_token"

# MCP监控系统配置
MCP_API_URL = "https://mcp.example.com/api"
MCP_API_KEY = "your_mcp_api_key"

# 消息通知配置
NOTIFICATION = {
    "slack": {
        "webhook": "https://hooks.slack.com/services/XXX/YYY/ZZZ"
    },
    "email": {
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "username": "notifications@example.com",
        "password": "email_password",
        "default_recipients": ["devops@example.com"]
    },
    "wecom": {
        "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXX"
    }
}

# 项目默认配置
DEFAULT_PROJECT_CONFIG = {
    "timeout": 3600,  # 超时时间（秒）
    "max_retries": 3,  # 最大重试次数
    "log_level": "INFO",
    "deploy_environments": ["dev", "test", "prod"]
}
