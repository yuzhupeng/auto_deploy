"""
自动化部署系统主程序
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, List, Any, Optional

# 添加模块路径
from modules.dify_api import analyze_requirements, DifyClient
from modules.git_operations import GitOperator
from modules.llm_interface import LLMInterface
from modules.mcp_protocol import MCPClient, notify_build_start
from modules.jenkins_ops import JenkinsClient
from modules.notification import send_deployment_notification

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("auto_deploy.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutoDeployment:
    """自动化部署流程管理器"""

    def __init__(self, project_name, git_repo, jenkins_job=None, mcp_monitor=True):
        """
        初始化自动部署流程

        Args:
            project_name (str): 项目名称
            git_repo (str): Git仓库URL
            jenkins_job (str, optional): Jenkins作业名称
            mcp_monitor (bool): 是否启用MCP监控
        """
        self.project_name = project_name
        self.git_repo = git_repo
        self.jenkins_job = jenkins_job
        self.mcp_monitor = mcp_monitor

        # 初始化组件
        self.llm = LLMInterface()
        self.git = GitOperator(git_repo)

        # 初始化MCP客户端
        if mcp_monitor:
            self.mcp = MCPClient()
            self.session_id = self.mcp.create_session(
                project_name=project_name,
                pipeline_name="自动部署流程",
                description=f"项目 {project_name} 的自动化部署流程"
            )
        else:
            self.mcp = None
            self.session_id = None

        # 初始化Jenkins客户端
        if jenkins_job:
            self.jenkins = JenkinsClient()
        else:
            self.jenkins = None

        # 记录阶段和状态
        self.stages = {}
        self.current_stage = None
        self.start_time = time.time()

    def log(self, message, level="INFO", stage_id=None):
        """
        记录日志并同步到MCP

        Args:
            message (str): 日志消息
            level (str): 日志级别
            stage_id (str, optional): 阶段ID
        """
        if level == "INFO":
            logger.info(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
        elif level == "DEBUG":
            logger.debug(message)

        # 同步到MCP
        if self.mcp and self.session_id:
            self.mcp.add_log(message, level.lower(),
                             stage_id or self.current_stage)

    def start_stage(self, stage_name, description=""):
        """
        开始新阶段

        Args:
            stage_name (str): 阶段名称
            description (str): 阶段描述

        Returns:
            str: 阶段ID
        """
        self.log(f"开始阶段: {stage_name}")

        # 创建MCP阶段
        if self.mcp and self.session_id:
            stage_id = self.mcp.add_stage(stage_name, "running", description)
            self.stages[stage_name] = stage_id
            self.current_stage = stage_id
            return stage_id
        else:
            self.stages[stage_name] = stage_name
            self.current_stage = stage_name
            return stage_name

    def end_stage(self, stage_name, status="success", message=""):
        """
        结束阶段

        Args:
            stage_name (str): 阶段名称
            status (str): 阶段状态
            message (str): 状态消息
        """
        self.log(f"结束阶段: {stage_name} ({status})")

        # 更新MCP阶段
        if self.mcp and self.session_id:
            stage_id = self.stages.get(stage_name)
            if stage_id:
                self.mcp.update_stage(stage_id, status, message)

    def analyze_requirements_stage(self, doc_text):
        """
        需求解析阶段

        Args:
            doc_text (str): 需求文档内容

        Returns:
            Dict[str, Any]: 解析结果
        """
        stage_id = self.start_stage("需求解析", "分析需求文档生成代码修改方案")

        try:
            self.log("正在分析需求文档...")
            analysis_result = analyze_requirements(doc_text)

            if "error" in analysis_result:
                self.log(f"需求分析出错: {analysis_result['error']}", "ERROR")
                self.end_stage("需求解析", "failed",
                               f"需求分析失败: {analysis_result['error']}")
                return None

            self.log(
                f"需求分析完成，找到 {len(analysis_result.get('files_to_modify', []))} 个需要修改的文件")
            self.end_stage("需求解析", "success", "需求分析成功")
            return analysis_result

        except Exception as e:
            self.log(f"需求解析阶段出错: {str(e)}", "ERROR")
            self.end_stage("需求解析", "failed", f"需求解析失败: {str(e)}")
            return None

    def git_operations_stage(self, analysis_result):
        """
        Git操作阶段

        Args:
            analysis_result (Dict[str, Any]): 需求分析结果

        Returns:
            bool: 操作是否成功
        """
        stage_id = self.start_stage("Git操作", "执行代码版本控制操作")

        try:
            # 从分析结果中获取Git分支策略
            git_strategy = analysis_result.get("git_strategy", "使用feature分支")
            feature_branch = f"feature/auto-update-{int(time.time())}"

            self.log(f"Git策略: {git_strategy}")
            self.log(f"创建特性分支: {feature_branch}")

            # 克隆仓库
            self.log("正在克隆仓库...")
            if not self.git.clone():
                self.log("克隆仓库失败", "ERROR")
                self.end_stage("Git操作", "failed", "克隆仓库失败")
                return False

            # 创建特性分支
            self.log(f"正在创建分支: {feature_branch}")
            if not self.git.create_branch(feature_branch):
                self.log(f"创建分支 {feature_branch} 失败", "ERROR")
                self.end_stage("Git操作", "failed", f"创建分支 {feature_branch} 失败")
                return False

            # 应用文件修改
            file_changes = analysis_result.get("file_changes", {})
            if file_changes:
                self.log(f"应用 {len(file_changes)} 个文件修改...")
                if not self.git.apply_file_changes(file_changes):
                    self.log("应用文件修改失败", "ERROR")
                    self.end_stage("Git操作", "failed", "应用文件修改失败")
                    return False

            # 提交修改
            commit_message = f"自动更新: {analysis_result.get('summary', '代码自动更新')}"
            self.log(f"提交修改: {commit_message}")
            if not self.git.commit(commit_message):
                self.log("提交修改失败", "ERROR")
                self.end_stage("Git操作", "failed", "提交修改失败")
                return False

            # 推送分支
            self.log(f"推送分支: {feature_branch}")
            if not self.git.push(feature_branch):
                self.log(f"推送分支 {feature_branch} 失败", "ERROR")
                self.end_stage("Git操作", "failed", f"推送分支 {feature_branch} 失败")
                return False

            self.log("Git操作完成")
            self.end_stage("Git操作", "success", "Git操作成功完成")
            return True

        except Exception as e:
            self.log(f"Git操作阶段出错: {str(e)}", "ERROR")
            self.end_stage("Git操作", "failed", f"Git操作失败: {str(e)}")
            return False

    def jenkins_build_stage(self, analysis_result):
        """
        Jenkins构建阶段

        Args:
            analysis_result (Dict[str, Any]): 需求分析结果

        Returns:
            bool: 操作是否成功
        """
        if not self.jenkins or not self.jenkins_job:
            self.log("未配置Jenkins作业，跳过构建阶段", "WARNING")
            return True

        stage_id = self.start_stage("Jenkins构建", "触发Jenkins构建并等待结果")

        try:
            # 获取Jenkins构建参数
            jenkins_params = analysis_result.get("jenkins_params", {})

            # 添加默认参数
            if "BRANCH" not in jenkins_params:
                jenkins_params["BRANCH"] = f"feature/auto-update-{int(time.time())}"

            self.log(f"触发Jenkins作业: {self.jenkins_job}")
            self.log(f"构建参数: {jenkins_params}")

            # 通知MCP构建开始
            notify_build_start(self.project_name, jenkins_params.get(
                "BUILD_ID", "auto"), jenkins_params)

            # 触发构建
            build_number = self.jenkins.build_job(
                self.jenkins_job, jenkins_params)

            if not build_number:
                self.log("触发Jenkins构建失败", "ERROR")
                self.end_stage("Jenkins构建", "failed", "触发Jenkins构建失败")
                return False

            self.log(f"已触发构建 #{build_number}，等待构建完成...")

            # 等待构建完成
            build_status = self.jenkins.wait_for_build(
                self.jenkins_job, build_number)

            if not build_status:
                self.log("等待Jenkins构建超时", "WARNING")
                self.end_stage("Jenkins构建", "warning", "等待Jenkins构建超时")
                return True

            if build_status == "SUCCESS":
                self.log(f"构建成功完成: {self.jenkins_job} #{build_number}")
                self.end_stage("Jenkins构建", "success",
                               f"构建成功: #{build_number}")
                return True
            else:
                self.log(
                    f"构建失败: {self.jenkins_job} #{build_number} - {build_status}", "ERROR")

                # 获取构建日志
                build_log = self.jenkins.get_build_log(
                    self.jenkins_job, build_number)
                if build_log:
                    self.log(f"构建日志片段:\n{build_log[-1000:]}", "ERROR")

                self.end_stage("Jenkins构建", "failed", f"构建失败: {build_status}")
                return False

        except Exception as e:
            self.log(f"Jenkins构建阶段出错: {str(e)}", "ERROR")
            self.end_stage("Jenkins构建", "failed", f"Jenkins构建失败: {str(e)}")
            return False

    def notification_stage(self, status, details=None):
        """
        消息通知阶段

        Args:
            status (str): 部署状态
            details (str, optional): 详情

        Returns:
            bool: 操作是否成功
        """
        stage_id = self.start_stage("消息通知", "发送部署状态通知")

        try:
            # 生成通知详情
            if not details:
                duration = int(time.time() - self.start_time)
                minutes, seconds = divmod(duration, 60)

                details = f"""
                部署耗时: {minutes}分{seconds}秒
                状态: {'成功' if status == 'success' else '失败'}
                """

            # 确定环境
            environment = "开发环境"  # 可从配置或参数中获取

            # 发送通知
            self.log(f"发送部署状态通知: {status}")
            notification_results = send_deployment_notification(
                project_name=self.project_name,
                environment=environment,
                status=status,
                details=details
            )

            # 检查结果
            success_count = sum(
                1 for success in notification_results.values() if success)
            total_count = len(notification_results)

            if success_count == total_count:
                self.log(f"所有通知发送成功: {success_count}/{total_count}")
                self.end_stage("消息通知", "success", "所有通知发送成功")
                return True
            elif success_count > 0:
                self.log(f"部分通知发送成功: {success_count}/{total_count}", "WARNING")
                self.end_stage("消息通知", "warning",
                               f"部分通知发送成功 ({success_count}/{total_count})")
                return True
            else:
                self.log("所有通知发送失败", "ERROR")
                self.end_stage("消息通知", "failed", "所有通知发送失败")
                return False

        except Exception as e:
            self.log(f"消息通知阶段出错: {str(e)}", "ERROR")
            self.end_stage("消息通知", "failed", f"消息通知失败: {str(e)}")
            return False

    def close_session(self, status, summary=None):
        """
        关闭MCP会话

        Args:
            status (str): 部署状态
            summary (str, optional): 部署总结
        """
        if self.mcp and self.session_id:
            if not summary:
                duration = int(time.time() - self.start_time)
                minutes, seconds = divmod(duration, 60)

                if status == "success":
                    summary = f"自动部署成功完成，耗时{minutes}分{seconds}秒"
                else:
                    summary = f"自动部署失败，耗时{minutes}分{seconds}秒"

            self.log(f"关闭MCP会话: {status}")
            self.mcp.close_session(status, summary)

    def run(self, doc_text):
        """
        运行完整的自动部署流程

        Args:
            doc_text (str): 需求文档内容

        Returns:
            Dict[str, Any]: 部署结果
        """
        try:
            self.log(f"开始自动部署流程: {self.project_name}")

            # 更新MCP会话状态
            if self.mcp and self.session_id:
                self.mcp.update_status("running", "自动部署流程开始执行")

            # 1. 需求解析阶段
            analysis_result = self.analyze_requirements_stage(doc_text)
            if not analysis_result:
                self.close_session("failed", "需求解析阶段失败")
                return {"success": False, "stage": "需求解析", "error": "需求分析失败"}

            # 2. Git操作阶段
            git_success = self.git_operations_stage(analysis_result)
            if not git_success:
                self.close_session("failed", "Git操作阶段失败")
                return {"success": False, "stage": "Git操作", "error": "Git操作失败"}

            # 3. Jenkins构建阶段（可选）
            if self.jenkins and self.jenkins_job:
                jenkins_success = self.jenkins_build_stage(analysis_result)
                if not jenkins_success:
                    self.close_session("failed", "Jenkins构建阶段失败")
                    return {"success": False, "stage": "Jenkins构建", "error": "Jenkins构建失败"}

            # 4. 消息通知阶段
            notification_success = self.notification_stage("success")

            # 关闭MCP会话
            self.close_session("success", "自动部署流程成功完成")

            self.log(f"自动部署流程成功完成: {self.project_name}")
            return {
                "success": True,
                "analysis_result": analysis_result,
                "duration": int(time.time() - self.start_time)
            }

        except Exception as e:
            logger.exception("自动部署流程执行出错")

            # 关闭MCP会话
            self.close_session("failed", f"自动部署流程出错: {str(e)}")

            # 发送失败通知
            try:
                self.notification_stage("failure", f"自动部署流程出错: {str(e)}")
            except:
                pass

            return {"success": False, "error": str(e)}


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="自动化部署系统")

    parser.add_argument("--project", "-p", required=True, help="项目名称")
    parser.add_argument("--repo", "-r", required=True, help="Git仓库URL")
    parser.add_argument("--job", "-j", help="Jenkins作业名称")
    parser.add_argument("--doc", "-d", help="需求文档文件路径")
    parser.add_argument("--no-mcp", action="store_true", help="禁用MCP监控")

    args = parser.parse_args()

    # 读取需求文档
    if args.doc:
        try:
            with open(args.doc, 'r', encoding='utf-8') as f:
                doc_text = f.read()
        except Exception as e:
            logger.error(f"读取需求文档失败: {str(e)}")
            sys.exit(1)
    else:
        print("请输入需求文档内容 (按Ctrl+D结束输入):")
        try:
            doc_text = sys.stdin.read()
        except KeyboardInterrupt:
            print("\n已取消输入")
            sys.exit(0)

    # 创建并运行自动部署流程
    deployment = AutoDeployment(
        project_name=args.project,
        git_repo=args.repo,
        jenkins_job=args.job,
        mcp_monitor=not args.no_mcp
    )

    result = deployment.run(doc_text)

    # 输出结果
    if result["success"]:
        print(f"✅ 自动部署流程成功完成！耗时: {result['duration']}秒")
        sys.exit(0)
    else:
        print(
            f"❌ 自动部署流程失败: {result.get('stage', '未知阶段')} - {result.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
