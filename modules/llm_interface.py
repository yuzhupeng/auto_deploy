"""
大模型接口模块 - 调用大模型进行代码分析和生成
"""

from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL
import json
import sys
import requests
import logging
from typing import Dict, List, Any, Optional, Union

# 添加项目根目录到路径
sys.path.append('..')

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LLMInterface:
    """大模型接口封装类"""

    def __init__(self, api_key=LLM_API_KEY, api_url=LLM_API_URL, model=LLM_MODEL):
        """
        初始化大模型接口

        Args:
            api_key (str): API密钥
            api_url (str): API地址
            model (str): 模型名称
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def generate_completion(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.2,
                            stream: bool = False) -> Union[str, Dict[str, Any]]:
        """
        生成文本补全

        Args:
            prompt (str): 提示文本
            max_tokens (int): 最大生成令牌数
            temperature (float): 温度参数，控制随机性
            stream (bool): 是否使用流式响应

        Returns:
            Union[str, Dict[str, Any]]: 生成的文本或响应对象
        """
        try:
            endpoint = f"{self.api_url}/completions"

            payload = {
                "model": self.model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": stream
            }

            if stream:
                response = requests.post(
                    endpoint, json=payload, headers=self.headers, stream=True)
                response.raise_for_status()
                return self._handle_stream_response(response)
            else:
                response = requests.post(
                    endpoint, json=payload, headers=self.headers)
                response.raise_for_status()
                response_json = response.json()

                if "choices" in response_json and len(response_json["choices"]) > 0:
                    return response_json["choices"][0]["text"].strip()
                else:
                    logger.error(f"API响应格式异常: {response_json}")
                    return ""

        except Exception as e:
            logger.error(f"调用LLM API时出错: {str(e)}")
            return ""

    def _handle_stream_response(self, response):
        """
        处理流式响应

        Args:
            response: 响应对象

        Returns:
            str: 完整的生成文本
        """
        full_response = ""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]  # 去掉 'data: ' 前缀
                    if data == "[DONE]":
                        break
                    try:
                        json_data = json.loads(data)
                        if "choices" in json_data and len(json_data["choices"]) > 0:
                            chunk = json_data["choices"][0].get("text", "")
                            full_response += chunk
                            yield chunk
                    except json.JSONDecodeError:
                        logger.error(f"解析流式响应时出错: {data}")

        return full_response

    def analyze_code(self, code: str, task_description: str) -> Dict[str, Any]:
        """
        分析代码并提供修改建议

        Args:
            code (str): 要分析的代码
            task_description (str): 任务描述

        Returns:
            Dict[str, Any]: 分析结果
        """
        prompt = f"""
        请分析以下代码并根据任务描述提供修改建议:
        
        任务描述:
        {task_description}
        
        代码:
        ```
        {code}
        ```
        
        请提供:
        1. 需要修改的部分
        2. 修改建议 (diff格式)
        3. 修改理由
        
        以JSON格式输出，结构如下:
        {{
            "analysis": "代码分析结果",
            "changes": [
                {{
                    "line_start": 行号开始,
                    "line_end": 行号结束,
                    "original": "原始代码",
                    "modified": "修改后代码",
                    "reason": "修改理由"
                }}
            ],
            "diff": "完整diff格式修改"
        }}
        """

        response = self.generate_completion(prompt)

        try:
            # 尝试解析为JSON
            if response.startswith("```json"):
                response = response.split("```json", 1)[1]
            if response.endswith("```"):
                response = response.rsplit("```", 1)[0]

            return json.loads(response)
        except json.JSONDecodeError:
            logger.error("无法将响应解析为JSON")
            return {
                "analysis": response,
                "changes": [],
                "diff": ""
            }

    def generate_code(self, description: str, language: str = "python",
                      file_type: str = "script") -> Dict[str, Any]:
        """
        根据描述生成代码

        Args:
            description (str): 代码功能描述
            language (str): 编程语言
            file_type (str): 文件类型 (script, module, class)

        Returns:
            Dict[str, Any]: 生成结果
        """
        prompt = f"""
        请根据以下描述生成{language}代码:
        
        功能描述:
        {description}
        
        文件类型: {file_type}
        
        请确保代码:
        1. 功能完整
        2. 包含必要的注释
        3. 遵循{language}的最佳实践
        4. 包含异常处理
        
        以JSON格式输出，结构如下:
        {{
            "code": "生成的代码",
            "explanation": "代码功能说明",
            "instructions": "使用说明"
        }}
        """

        response = self.generate_completion(prompt)

        try:
            # 尝试解析为JSON
            if response.startswith("```json"):
                response = response.split("```json", 1)[1]
            if response.endswith("```"):
                response = response.rsplit("```", 1)[0]

            return json.loads(response)
        except json.JSONDecodeError:
            # 如果响应不是JSON格式，尝试提取代码部分
            code = ""
            if "```" in response:
                code_blocks = response.split("```")
                if len(code_blocks) > 1:
                    # 去掉语言标识符
                    code_content = code_blocks[1]
                    if code_content.startswith(language):
                        code_content = code_content[len(language):]
                    code = code_content.strip()

            if not code:
                code = response

            return {
                "code": code,
                "explanation": "生成的代码未以JSON格式返回",
                "instructions": "请参考代码注释了解使用方法"
            }


if __name__ == "__main__":
    # 测试用例
    llm = LLMInterface()

    # 测试代码分析
    test_code = """
    def calculate_total(items):
        total = 0
        for item in items:
            total += item['price']
        return total
    """

    test_description = "优化函数，添加对空列表的处理，并增加数量乘以价格的计算"

    result = llm.analyze_code(test_code, test_description)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试代码生成
    test_gen_description = "创建一个函数，用于从CSV文件中读取数据，并计算每列的平均值"

    gen_result = llm.generate_code(test_gen_description)
    print(json.dumps(gen_result, indent=2, ensure_ascii=False))
