"""
Jenkins操作模块 - 触发和管理Jenkins构建
"""

from config import JENKINS_URL, JENKINS_USER, JENKINS_TOKEN
import sys
import time
import logging
import json
import requests
from typing import Dict, List, Any, Optional, Union

# 添加项目根目录到路径
sys.path.append('..')

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class JenkinsClient:
    """Jenkins客户端，用于触发和管理Jenkins构建"""

    def __init__(self, url=JENKINS_URL, username=JENKINS_USER, token=JENKINS_TOKEN):
        """
        初始化Jenkins客户端

        Args:
            url (str): Jenkins服务器URL
            username (str): Jenkins用户名
            token (str): Jenkins API令牌
        """
        self.url = url.rstrip('/')
        self.username = username
        self.token = token
        self.auth = (username, token)
        self.crumb = self._get_crumb()

    def _get_crumb(self) -> Optional[Dict[str, str]]:
        """
        获取Jenkins CSRF crumb

        Returns:
            Optional[Dict[str, str]]: CSRF crumb信息
        """
        try:
            response = requests.get(
                f"{self.url}/crumbIssuer/api/json",
                auth=self.auth
            )

            if response.status_code == 200:
                data = response.json()
                return {data.get('crumbRequestField'): data.get('crumb')}
            else:
                logger.warning(
                    f"无法获取Jenkins CSRF crumb: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"获取Jenkins CSRF crumb时出错: {str(e)}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """
        获取请求头

        Returns:
            Dict[str, str]: 请求头
        """
        headers = {"Content-Type": "application/json"}
        if self.crumb:
            headers.update(self.crumb)
        return headers

    def get_job_info(self, job_name: str) -> Optional[Dict[str, Any]]:
        """
        获取Jenkins作业信息

        Args:
            job_name (str): 作业名称

        Returns:
            Optional[Dict[str, Any]]: 作业信息
        """
        try:
            url = f"{self.url}/job/{job_name}/api/json"
            response = requests.get(url, auth=self.auth)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"获取作业信息失败: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"获取作业信息时出错: {str(e)}")
            return None

    def build_job(self, job_name: str, parameters: Dict[str, Any] = None) -> Optional[int]:
        """
        触发Jenkins构建

        Args:
            job_name (str): 作业名称
            parameters (Dict[str, Any], optional): 构建参数

        Returns:
            Optional[int]: 构建编号
        """
        try:
            # 检查作业是否有参数化
            job_info = self.get_job_info(job_name)
            is_parameterized = False

            if job_info:
                for prop in job_info.get('property', []):
                    if 'ParametersDefinitionProperty' in prop.get('_class', ''):
                        is_parameterized = True
                        break

            # 构建URL
            if is_parameterized and parameters:
                url = f"{self.url}/job/{job_name}/buildWithParameters"
                response = requests.post(
                    url,
                    auth=self.auth,
                    headers=self._get_headers(),
                    params=parameters
                )
            else:
                url = f"{self.url}/job/{job_name}/build"
                response = requests.post(
                    url,
                    auth=self.auth,
                    headers=self._get_headers()
                )

            if response.status_code in [200, 201]:
                # 获取队列项ID
                queue_url = response.headers.get('Location')
                if queue_url:
                    build_number = self._get_build_number_from_queue(queue_url)
                    logger.info(f"已触发构建: {job_name} #{build_number}")
                    return build_number
                else:
                    logger.warning("无法获取构建队列URL")
                    return None
            else:
                logger.error(
                    f"触发构建失败: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"触发构建时出错: {str(e)}")
            return None

    def _get_build_number_from_queue(self, queue_url: str) -> Optional[int]:
        """
        从队列URL获取构建编号

        Args:
            queue_url (str): 队列项URL

        Returns:
            Optional[int]: 构建编号
        """
        try:
            max_attempts = 10
            attempts = 0

            while attempts < max_attempts:
                response = requests.get(
                    f"{queue_url}api/json",
                    auth=self.auth
                )

                if response.status_code == 200:
                    data = response.json()

                    # 检查队列项是否已转换为构建
                    if 'executable' in data and 'number' in data['executable']:
                        return data['executable']['number']

                    # 如果队列项被取消
                    if 'cancelled' in data and data['cancelled']:
                        logger.warning("构建被取消")
                        return None

                    # 如果没有转换为构建，等待后重试
                    time.sleep(2)
                    attempts += 1
                else:
                    logger.error(f"获取队列信息失败: {response.status_code}")
                    return None

            logger.warning(f"等待构建编号超时")
            return None

        except Exception as e:
            logger.error(f"获取构建编号时出错: {str(e)}")
            return None

    def get_build_info(self, job_name: str, build_number: int) -> Optional[Dict[str, Any]]:
        """
        获取构建信息

        Args:
            job_name (str): 作业名称
            build_number (int): 构建编号

        Returns:
            Optional[Dict[str, Any]]: 构建信息
        """
        try:
            url = f"{self.url}/job/{job_name}/{build_number}/api/json"
            response = requests.get(url, auth=self.auth)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"获取构建信息失败: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"获取构建信息时出错: {str(e)}")
            return None

    def get_build_status(self, job_name: str, build_number: int) -> Optional[str]:
        """
        获取构建状态

        Args:
            job_name (str): 作业名称
            build_number (int): 构建编号

        Returns:
            Optional[str]: 构建状态 (SUCCESS, FAILURE, ABORTED, IN_PROGRESS)
        """
        build_info = self.get_build_info(job_name, build_number)

        if not build_info:
            return None

        # 检查构建是否正在进行中
        if build_info.get('building', False):
            return "IN_PROGRESS"

        # 返回构建结果
        return build_info.get('result')

    def wait_for_build(self, job_name: str, build_number: int,
                       timeout: int = 600, check_interval: int = 10) -> Optional[str]:
        """
        等待构建完成

        Args:
            job_name (str): 作业名称
            build_number (int): 构建编号
            timeout (int): 超时时间(秒)
            check_interval (int): 检查间隔(秒)

        Returns:
            Optional[str]: 构建状态
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_build_status(job_name, build_number)

            # 如果构建完成，返回状态
            if status and status != "IN_PROGRESS":
                logger.info(f"构建 {job_name} #{build_number} 已完成: {status}")
                return status

            # 如果构建还在进行中，等待后重试
            logger.info(f"构建 {job_name} #{build_number} 进行中，等待中...")
            time.sleep(check_interval)

        logger.warning(f"等待构建超时: {job_name} #{build_number}")
        return None

    def get_build_log(self, job_name: str, build_number: int) -> Optional[str]:
        """
        获取构建日志

        Args:
            job_name (str): 作业名称
            build_number (int): 构建编号

        Returns:
            Optional[str]: 构建日志
        """
        try:
            url = f"{self.url}/job/{job_name}/{build_number}/consoleText"
            response = requests.get(url, auth=self.auth)

            if response.status_code == 200:
                return response.text
            else:
                logger.error(f"获取构建日志失败: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"获取构建日志时出错: {str(e)}")
            return None

    def abort_build(self, job_name: str, build_number: int) -> bool:
        """
        终止构建

        Args:
            job_name (str): 作业名称
            build_number (int): 构建编号

        Returns:
            bool: 操作是否成功
        """
        try:
            url = f"{self.url}/job/{job_name}/{build_number}/stop"
            response = requests.post(
                url,
                auth=self.auth,
                headers=self._get_headers()
            )

            if response.status_code in [200, 201, 302]:
                logger.info(f"已终止构建: {job_name} #{build_number}")
                return True
            else:
                logger.error(
                    f"终止构建失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"终止构建时出错: {str(e)}")
            return False


if __name__ == "__main__":
    # 测试用例
    client = JenkinsClient()

    # 获取作业信息
    job_name = "test-pipeline"
    job_info = client.get_job_info(job_name)

    if job_info:
        print(f"作业 {job_name} 信息:")
        print(f"描述: {job_info.get('description', '无描述')}")
        print(f"URL: {job_info.get('url', '无URL')}")

        # 触发构建
        parameters = {
            "ENV": "dev",
            "BRANCH": "main"
        }

        build_number = client.build_job(job_name, parameters)

        if build_number:
            print(f"已触发构建 #{build_number}")

            # 等待构建完成
            status = client.wait_for_build(job_name, build_number, timeout=300)

            if status:
                print(f"构建完成: {status}")

                # 获取构建日志
                log = client.get_build_log(job_name, build_number)
                if log:
                    print("构建日志:")
                    print(log[:500] + "..." if len(log) > 500 else log)
            else:
                print("等待构建超时")
        else:
            print("触发构建失败")
