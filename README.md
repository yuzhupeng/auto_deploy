# 自动化部署解决方案

基于现代工具链的自动化部署解决方案，结合低代码平台与后台代码的混合方案。

## 架构示意图

```
[文档需求] → [Dify大模型分析] → [Git操作] [python 调用大模型 和MCP协议 操作仓库代码]→ [Jenkins触发] → [消息通知]
                ↑        ↓              ↑           ↑
              [n8n] ← [版本控制]       [Mcp监控]
```

## 主要功能

- **需求文档自动解析**：通过 Dify 和大模型自动分析需求文档，生成代码修改方案
- **自动化代码操作**：自动执行 Git 操作，包括创建分支、应用修改、提交和推送
- **持续集成触发**：自动触发 Jenkins 构建并监控构建状态
- **多渠道通知**：支持 Slack、邮件和企业微信等多种通知渠道
- **全流程监控**：通过 MCP 协议实现全流程可视化监控

## 系统组件

- **Dify API 模块**：与 Dify 平台通信，实现需求解析
- **Git 操作模块**：执行 Git 相关操作，包括仓库克隆、分支管理和代码提交
- **LLM 接口模块**：调用大模型进行代码分析和生成
- **MCP 协议模块**：实现与 MCP 监控系统的通信
- **Jenkins 操作模块**：触发和监控 Jenkins 构建
- **通知模块**：发送部署状态通知到多个渠道

## 安装要求

- Python 3.8+
- Git
- 访问各服务的 API 凭证

## 安装步骤

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/auto-deploy.git
cd auto-deploy
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 配置服务凭证：

编辑 `config.py` 文件，填入各服务的 API 密钥和配置信息。

## 使用方法

### 命令行用法

```bash
python main.py --project 项目名称 --repo Git仓库URL [--job Jenkins作业] [--doc 需求文档路径] [--no-mcp]
```

参数说明：

- `--project`, `-p`: 项目名称（必填）
- `--repo`, `-r`: Git 仓库 URL（必填）
- `--job`, `-j`: Jenkins 作业名称（可选）
- `--doc`, `-d`: 需求文档文件路径（可选，如果不提供则从标准输入读取）
- `--no-mcp`: 禁用 MCP 监控（可选）

### 示例

```bash
# 从文件读取需求文档
python main.py --project my-app --repo https://github.com/username/my-app.git --job my-app-build --doc requirements.txt

# 从标准输入读取需求文档
python main.py --project my-app --repo https://github.com/username/my-app.git
```

## 分阶段实施

系统分为以下几个阶段实施：

1. **需求解析阶段**：使用 Dify 和大模型分析需求文档
2. **代码操作阶段**：执行 Git 操作和代码修改
3. **持续集成阶段**：触发 Jenkins 构建并监控结果
4. **消息通知阶段**：发送部署状态通知

## 安全增强方案

- 凭证管理：支持通过 HashiCorp Vault 等工具管理密钥
- 操作审计：记录所有关键操作，支持后续审计
- 权限控制：基于角色的访问控制

## 配置文件

系统配置示例：

```python
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

# Jenkins配置
JENKINS_URL = "https://jenkins.example.com"
JENKINS_USER = "jenkins_user"
JENKINS_TOKEN = "jenkins_token"

# MCP监控系统配置
MCP_API_URL = "https://mcp.example.com/api"
MCP_API_KEY = "your_mcp_api_key"
```

## 扩展能力

- **自动回滚机制**：在部署失败时自动执行回滚
- **多环境支持**：支持不同环境的独立配置
- **智能分析**：对部署结果进行智能分析和优化建议

## 许可证

MIT License
