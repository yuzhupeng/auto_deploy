"""
Git操作模块 - 管理代码版本控制
"""

from config import GIT_USERNAME, GIT_TOKEN, DEFAULT_BRANCH
import os
import sys
import logging
import subprocess
from git import Repo, GitCommandError
import tempfile
import shutil

# 添加项目根目录到路径
sys.path.append('..')

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GitOperator:
    """Git仓库操作类"""

    def __init__(self, repo_url, username=GIT_USERNAME, token=GIT_TOKEN, work_dir=None):
        """
        初始化Git操作类

        Args:
            repo_url (str): Git仓库URL
            username (str): Git用户名
            token (str): Git访问令牌
            work_dir (str, optional): 工作目录路径，如果为None则创建临时目录
        """
        self.repo_url = repo_url
        self.username = username
        self.token = token
        self.repo = None
        self.is_temp_dir = work_dir is None

        # 处理认证的仓库URL
        if "http" in repo_url:
            # 将 https://github.com/user/repo.git 转换为 https://username:token@github.com/user/repo.git
            protocol, path = repo_url.split("://", 1)
            self.auth_repo_url = f"{protocol}://{username}:{token}@{path}"
        else:
            self.auth_repo_url = repo_url

        # 设置工作目录
        if work_dir:
            self.work_dir = work_dir
        else:
            self.work_dir = tempfile.mkdtemp(prefix="git_workspace_")
            logger.info(f"创建临时工作目录: {self.work_dir}")

    def __del__(self):
        """析构函数，清理临时目录"""
        if hasattr(self, 'is_temp_dir') and self.is_temp_dir and hasattr(self, 'work_dir'):
            try:
                shutil.rmtree(self.work_dir)
                logger.info(f"已清理临时工作目录: {self.work_dir}")
            except Exception as e:
                logger.error(f"清理临时目录时出错: {str(e)}")

    def clone(self, branch=DEFAULT_BRANCH):
        """
        克隆仓库到工作目录

        Args:
            branch (str): 要克隆的分支名称

        Returns:
            bool: 操作是否成功
        """
        try:
            logger.info(
                f"正在克隆仓库 {self.repo_url} 的 {branch} 分支到 {self.work_dir}")
            self.repo = Repo.clone_from(
                self.auth_repo_url, self.work_dir, branch=branch)
            return True
        except GitCommandError as e:
            logger.error(f"克隆仓库失败: {str(e)}")
            return False

    def create_branch(self, branch_name, base_branch=DEFAULT_BRANCH):
        """
        创建新分支

        Args:
            branch_name (str): 新分支名称
            base_branch (str): 基础分支名称

        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.repo:
                logger.error("仓库未克隆，无法创建分支")
                return False

            # 确保基础分支存在且为最新
            origin = self.repo.remotes.origin
            origin.fetch()

            # 检查分支是否已存在
            for ref in self.repo.refs:
                if ref.name == branch_name or ref.name == f"origin/{branch_name}":
                    logger.warning(f"分支 {branch_name} 已存在，将切换到该分支")
                    self.repo.git.checkout(branch_name)
                    return True

            # 创建并切换到新分支
            base = f"origin/{base_branch}"
            self.repo.git.checkout(base, b=branch_name)
            logger.info(f"已创建并切换到新分支: {branch_name}")
            return True

        except GitCommandError as e:
            logger.error(f"创建分支失败: {str(e)}")
            return False

    def apply_file_changes(self, file_changes):
        """
        应用文件修改

        Args:
            file_changes (dict): 文件修改字典，格式为 {"file_path": "file_content"}

        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.repo:
                logger.error("仓库未克隆，无法应用修改")
                return False

            for file_path, content in file_changes.items():
                full_path = os.path.join(self.work_dir, file_path)
                # 确保文件目录存在
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                # 写入文件内容
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                # 添加到git
                self.repo.git.add(file_path)

            logger.info(f"已应用 {len(file_changes)} 个文件的修改")
            return True

        except Exception as e:
            logger.error(f"应用文件修改失败: {str(e)}")
            return False

    def apply_patch(self, patch_content, file_path=None):
        """
        应用补丁

        Args:
            patch_content (str): 补丁内容
            file_path (str, optional): 补丁文件路径，如果为None则创建临时文件

        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.repo:
                logger.error("仓库未克隆，无法应用补丁")
                return False

            # 保存补丁内容到文件
            temp_patch = None
            if file_path:
                patch_file = file_path
            else:
                temp_patch = tempfile.NamedTemporaryFile(
                    delete=False, suffix='.patch')
                patch_file = temp_patch.name
                temp_patch.write(patch_content.encode('utf-8'))
                temp_patch.close()

            # 应用补丁
            try:
                self.repo.git.apply(patch_file)

                # 添加所有修改到暂存区
                self.repo.git.add(A=True)

                logger.info("补丁应用成功")
                return True
            finally:
                # 清理临时文件
                if temp_patch:
                    os.unlink(patch_file)

        except GitCommandError as e:
            logger.error(f"应用补丁失败: {str(e)}")
            return False

    def commit(self, message):
        """
        提交更改

        Args:
            message (str): 提交信息

        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.repo:
                logger.error("仓库未克隆，无法提交更改")
                return False

            # 检查是否有更改需要提交
            if not self.repo.is_dirty() and not self.repo.untracked_files:
                logger.warning("没有更改需要提交")
                return False

            # 添加所有更改
            self.repo.git.add(A=True)

            # 提交更改
            self.repo.git.commit(m=message)
            logger.info(f"已提交更改: {message}")
            return True

        except GitCommandError as e:
            logger.error(f"提交更改失败: {str(e)}")
            return False

    def push(self, branch=None, force=False):
        """
        推送更改到远程仓库

        Args:
            branch (str, optional): 分支名称，如果为None则使用当前分支
            force (bool): 是否强制推送

        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.repo:
                logger.error("仓库未克隆，无法推送更改")
                return False

            # 获取当前分支
            if not branch:
                branch = self.repo.active_branch.name

            # 推送更改
            if force:
                self.repo.git.push('origin', branch, force=True)
            else:
                self.repo.git.push('origin', branch)

            logger.info(f"已推送更改到远程分支: {branch}")
            return True

        except GitCommandError as e:
            logger.error(f"推送更改失败: {str(e)}")
            return False

    def create_pull_request(self, title, body, base_branch, head_branch):
        """
        创建拉取请求（需要额外的GitHub/GitLab API支持）

        这里给出一个伪实现，实际使用需要通过对应平台的API实现
        """
        logger.info(f"创建PR: {title} 从 {head_branch} 到 {base_branch}")
        logger.warning("此方法需要通过GitHub/GitLab API实现")
        # 实际实现需调用对应平台API
        return None

    def revert_last_commit(self):
        """
        回滚最后一次提交

        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.repo:
                logger.error("仓库未克隆，无法回滚提交")
                return False

            # 回滚最后一次提交
            self.repo.git.reset('--hard', 'HEAD~1')
            logger.info("已回滚最后一次提交")
            return True

        except GitCommandError as e:
            logger.error(f"回滚提交失败: {str(e)}")
            return False


def run_git_command(cmd, cwd=None):
    """
    运行Git命令

    Args:
        cmd (list): 命令列表
        cwd (str, optional): 工作目录

    Returns:
        str: 命令输出
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Git命令执行失败: {' '.join(cmd)}")
        logger.error(f"错误输出: {e.stderr}")
        raise


if __name__ == "__main__":
    # 测试用例
    test_repo_url = "https://github.com/username/test-repo.git"
    operator = GitOperator(test_repo_url)

    # 克隆仓库
    if operator.clone():
        # 创建特性分支
        operator.create_branch("feature/auto-test")

        # 修改文件
        file_changes = {
            "README.md": "# 测试仓库\n\n这是一个自动修改的测试。"
        }
        operator.apply_file_changes(file_changes)

        # 提交修改
        operator.commit("自动测试提交")

        # 推送修改
        operator.push()
