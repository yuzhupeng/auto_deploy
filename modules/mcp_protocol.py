"""
MCP协议模块 - 与MCP监控系统交互
"""

from config import MCP_API_URL, MCP_API_KEY
import json
import sys
import time
import logging
import requests
from typing import Dict, List, Any, Optional, Union

# 添加项目根目录到路径
sys.path.append('..')

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MCPClient:
    """MCP客户端，与MCP监控系统交互"""

    def __init__(self, api_url=MCP_API_URL, api_key=MCP_API_KEY):
        """
        初始化MCP客户端

        Args:
            api_url (str): MCP API地址
            api_key (str): MCP API密钥
        """
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.session_id = None
        self.start_time = None

    def create_session(self, project_name: str, pipeline_name: str,
                       description: str = "") -> str:
        """
        创建监控会话

        Args:
            project_name (str): 项目名称
            pipeline_name (str): 管道名称
            description (str): 会话描述

        Returns:
            str: 会话ID
        """
        try:
            endpoint = f"{self.api_url}/sessions"

            payload = {
                "project_name": project_name,
                "pipeline_name": pipeline_name,
                "description": description,
                "start_time": int(time.time())
            }

            response = requests.post(
                endpoint, json=payload, headers=self.headers)
            response.raise_for_status()
            response_data = response.json()

            if "session_id" in response_data:
                self.session_id = response_data["session_id"]
                self.start_time = payload["start_time"]
                logger.info(f"已创建MCP监控会话: {self.session_id}")
                return self.session_id
            else:
                logger.error(f"创建会话响应异常: {response_data}")
                return None

        except Exception as e:
            logger.error(f"创建MCP监控会话时出错: {str(e)}")
            return None

    def update_status(self, status: str, message: str = "",
                      data: Dict[str, Any] = None) -> bool:
        """
        更新会话状态

        Args:
            status (str): 状态码 (running, success, failed, warning)
            message (str): 状态消息
            data (Dict[str, Any]): 附加数据

        Returns:
            bool: 操作是否成功
        """
        if not self.session_id:
            logger.error("未创建会话，无法更新状态")
            return False

        try:
            endpoint = f"{self.api_url}/sessions/{self.session_id}/status"

            payload = {
                "status": status,
                "message": message,
                "timestamp": int(time.time())
            }

            if data:
                payload["data"] = data

            response = requests.post(
                endpoint, json=payload, headers=self.headers)
            response.raise_for_status()

            logger.info(f"已更新会话状态: {status}")
            return True

        except Exception as e:
            logger.error(f"更新会话状态时出错: {str(e)}")
            return False

    def add_stage(self, stage_name: str, status: str = "pending",
                  description: str = "") -> str:
        """
        添加部署阶段

        Args:
            stage_name (str): 阶段名称
            status (str): 阶段状态 (pending, running, success, failed)
            description (str): 阶段描述

        Returns:
            str: 阶段ID
        """
        if not self.session_id:
            logger.error("未创建会话，无法添加阶段")
            return None

        try:
            endpoint = f"{self.api_url}/sessions/{self.session_id}/stages"

            payload = {
                "name": stage_name,
                "status": status,
                "description": description,
                "start_time": int(time.time())
            }

            response = requests.post(
                endpoint, json=payload, headers=self.headers)
            response.raise_for_status()
            response_data = response.json()

            if "stage_id" in response_data:
                stage_id = response_data["stage_id"]
                logger.info(f"已添加部署阶段: {stage_name} (ID: {stage_id})")
                return stage_id
            else:
                logger.error(f"添加阶段响应异常: {response_data}")
                return None

        except Exception as e:
            logger.error(f"添加部署阶段时出错: {str(e)}")
            return None

    def update_stage(self, stage_id: str, status: str,
                     message: str = "", data: Dict[str, Any] = None) -> bool:
        """
        更新阶段状态

        Args:
            stage_id (str): 阶段ID
            status (str): 阶段状态 (pending, running, success, failed)
            message (str): 状态消息
            data (Dict[str, Any]): 附加数据

        Returns:
            bool: 操作是否成功
        """
        if not self.session_id:
            logger.error("未创建会话，无法更新阶段")
            return False

        try:
            endpoint = f"{self.api_url}/sessions/{self.session_id}/stages/{stage_id}"

            payload = {
                "status": status,
                "message": message
            }

            if status in ["success", "failed"]:
                payload["end_time"] = int(time.time())

            if data:
                payload["data"] = data

            response = requests.put(
                endpoint, json=payload, headers=self.headers)
            response.raise_for_status()

            logger.info(f"已更新阶段状态: {stage_id} -> {status}")
            return True

        except Exception as e:
            logger.error(f"更新阶段状态时出错: {str(e)}")
            return False

    def add_log(self, message: str, level: str = "info",
                stage_id: str = None, data: Dict[str, Any] = None) -> bool:
        """
        添加日志

        Args:
            message (str): 日志消息
            level (str): 日志级别 (debug, info, warning, error)
            stage_id (str): 关联的阶段ID
            data (Dict[str, Any]): 附加数据

        Returns:
            bool: 操作是否成功
        """
        if not self.session_id:
            logger.error("未创建会话，无法添加日志")
            return False

        try:
            endpoint = f"{self.api_url}/sessions/{self.session_id}/logs"

            payload = {
                "message": message,
                "level": level,
                "timestamp": int(time.time())
            }

            if stage_id:
                payload["stage_id"] = stage_id

            if data:
                payload["data"] = data

            response = requests.post(
                endpoint, json=payload, headers=self.headers)
            response.raise_for_status()

            return True

        except Exception as e:
            logger.error(f"添加日志时出错: {str(e)}")
            return False

    def close_session(self, status: str = "success",
                      summary: str = "") -> bool:
        """
        关闭监控会话

        Args:
            status (str): 最终状态 (success, failed)
            summary (str): 会话总结

        Returns:
            bool: 操作是否成功
        """
        if not self.session_id:
            logger.error("未创建会话，无法关闭")
            return False

        try:
            endpoint = f"{self.api_url}/sessions/{self.session_id}/close"

            payload = {
                "status": status,
                "summary": summary,
                "end_time": int(time.time())
            }

            if self.start_time:
                duration = payload["end_time"] - self.start_time
                payload["duration"] = duration

            response = requests.post(
                endpoint, json=payload, headers=self.headers)
            response.raise_for_status()

            logger.info(f"已关闭监控会话: {self.session_id}")
            return True

        except Exception as e:
            logger.error(f"关闭监控会话时出错: {str(e)}")
            return False

    def get_session_status(self) -> Dict[str, Any]:
        """
        获取会话状态

        Returns:
            Dict[str, Any]: 会话状态信息
        """
        if not self.session_id:
            logger.error("未创建会话，无法获取状态")
            return None

        try:
            endpoint = f"{self.api_url}/sessions/{self.session_id}"

            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"获取会话状态时出错: {str(e)}")
            return None


def notify_build_start(project_name="", build_id="", data=None):
    """
    通知构建开始

    Args:
        project_name (str): 项目名称
        build_id (str): 构建ID
        data (Dict[str, Any]): 构建数据

    Returns:
        bool: 操作是否成功
    """
    try:
        client = MCPClient()
        session_id = client.create_session(
            project_name=project_name or "未命名项目",
            pipeline_name=f"构建 #{build_id}" if build_id else "手动构建",
            description=f"自动化部署流程 ({time.strftime('%Y-%m-%d %H:%M:%S')})"
        )

        if not session_id:
            return False

        # 添加准备阶段
        stage_id = client.add_stage(
            "准备", status="running", description="初始化构建环境")

        # 记录构建数据
        if data:
            client.add_log("构建参数", data=data, stage_id=stage_id)

        # 更新阶段状态
        client.update_stage(stage_id, "success", "环境准备完成")

        # 更新会话状态
        client.update_status("running", "构建已开始")

        return True

    except Exception as e:
        logger.error(f"通知构建开始时出错: {str(e)}")
        return False


if __name__ == "__main__":
    # 测试用例
    client = MCPClient()

    # 创建会话
    session_id = client.create_session(
        project_name="测试项目",
        pipeline_name="自动部署流程",
        description="这是一个测试会话"
    )

    if session_id:
        # 添加阶段
        stage_id = client.add_stage("代码检出", status="running")

        # 添加日志
        client.add_log("正在克隆仓库...", stage_id=stage_id)

        # 模拟延迟
        time.sleep(2)

        # 更新阶段状态
        client.update_stage(stage_id, "success", "代码检出完成")

        # 添加新阶段
        build_stage = client.add_stage("构建", status="running")
        client.add_log("正在编译代码...", stage_id=build_stage)

        # 模拟延迟
        time.sleep(2)

        # 更新阶段状态
        client.update_stage(build_stage, "success", "构建完成")

        # 关闭会话
        client.close_session("success", "部署流程成功完成")
