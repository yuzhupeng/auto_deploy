"""
Dify API模块 - 调用Dify大模型进行需求解析
"""

from config import DIFY_API_KEY, DIFY_API_URL
import json
import requests
import logging
import sys

# 添加项目根目录到路径
sys.path.append('..')

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DifyClient:
    """Dify API客户端"""

    def __init__(self, api_key=DIFY_API_KEY, api_url=DIFY_API_URL):
        self.api_key = api_key
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def generate(self, prompt, conversation_id=None, stream=False):
        """向Dify发送请求并获取响应"""
        try:
            endpoint = f"{self.api_url}/completion-messages"

            payload = {
                "inputs": {},
                "query": prompt,
                "response_mode": "streaming" if stream else "blocking",
                "user": "auto-deploy-system"
            }

            if conversation_id:
                payload["conversation_id"] = conversation_id

            if stream:
                response = requests.post(
                    endpoint, json=payload, headers=self.headers, stream=True)
                response.raise_for_status()
                return self._handle_stream_response(response)
            else:
                response = requests.post(
                    endpoint, json=payload, headers=self.headers)
                response.raise_for_status()
                return self._handle_blocking_response(response.json())

        except Exception as e:
            logger.error(f"调用Dify API时出错: {str(e)}")
            raise

    def _handle_blocking_response(self, response_json):
        """处理非流式响应"""
        if "answer" in response_json:
            return response_json["answer"]
        else:
            logger.error(f"Dify响应格式异常: {response_json}")
            return None

    def _handle_stream_response(self, response):
        """处理流式响应"""
        full_response = ""
        for line in response.iter_lines():
            if line:
                try:
                    line_data = json.loads(line.decode(
                        'utf-8').replace('data: ', ''))
                    if 'answer' in line_data:
                        chunk = line_data.get('answer', '')
                        full_response += chunk
                        yield chunk
                except Exception as e:
                    logger.error(f"解析流式响应时出错: {str(e)}")
        return full_response


def analyze_requirements(doc_text):
    """
    根据需求文档分析并生成代码修改方案

    Args:
        doc_text (str): 需求文档文本内容

    Returns:
        dict: 包含修改方案的字典
    """
    client = DifyClient()

    prompt = f"""
    根据以下需求文档生成代码修改方案：
    {doc_text}
    
    输出格式要求：
    1. 需要修改的文件路径列表
    2. 每个文件的修改建议（diff格式）
    3. 关联的Git分支策略
    4. Jenkins构建参数建议
    
    以JSON格式输出，结构如下:
    {{
        "files_to_modify": ["path/to/file1", "path/to/file2"],
        "file_changes": {{
            "path/to/file1": "diff内容",
            "path/to/file2": "diff内容"
        }},
        "git_strategy": "分支策略描述",
        "jenkins_params": {{
            "param1": "value1",
            "param2": "value2"
        }}
    }}
    """

    try:
        response = client.generate(prompt)
        # 尝试解析JSON响应
        try:
            parsed_response = json.loads(response)
            return parsed_response
        except json.JSONDecodeError:
            # 如果无法解析为JSON，返回原始文本
            logger.warning("无法将Dify响应解析为JSON，返回原始文本")
            return {"raw_response": response}

    except Exception as e:
        logger.error(f"分析需求时出错: {str(e)}")
        return {"error": str(e)}


if __name__ == "__main__":
    # 测试用例
    test_doc = """
    需求：优化用户登录流程，增加验证码功能，并支持第三方登录
    功能点：
    1. 添加图形验证码
    2. 支持微信登录
    3. 登录失败三次后锁定账号10分钟
    """

    result = analyze_requirements(test_doc)
    print(json.dumps(result, indent=2, ensure_ascii=False))
