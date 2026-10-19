"""Public diagnostic errors: stable codes, Chinese messages, no secret values."""
import json
import subprocess


def payload(exc):
    if isinstance(exc, json.JSONDecodeError):
        code, message = 'invalid_json', '配置或密钥文件不是有效 JSON，请重新检查文件；未导入任何内容。'
    elif isinstance(exc, FileExistsError):
        code, message = 'output_exists', '输出文件已存在，请换一个文件名。'
    elif isinstance(exc, FileNotFoundError):
        code, message = 'path_not_found', '所需文件或目录不存在，请检查安装、账号目录及密钥路径。'
    elif isinstance(exc, PermissionError):
        code, message = 'permission_denied', '没有访问所需文件或进程的权限，请检查目录权限和终端权限。'
    elif isinstance(exc, subprocess.TimeoutExpired):
        code, message = 'timeout', '检查命令超时，请检查独立运行环境后重试。'
    elif isinstance(exc, subprocess.CalledProcessError):
        code, message = 'installation_failed', '依赖安装未完成，请检查网络、代理和 Python 环境后重试 install。'
    elif isinstance(exc, ImportError):
        code, message = 'runtime_dependency', '独立运行环境缺少依赖，请运行 install 检查安装。'
    elif isinstance(exc, (KeyError, TypeError)):
        code, message = 'invalid_config', '配置结构不完整，请重新导入正确的账号配置。'
    elif isinstance(exc, ValueError):
        code, message = 'invalid_input', str(exc)
    elif isinstance(exc, RuntimeError):
        code, message = 'not_ready', str(exc)
    else:
        code, message = 'operation_failed', '操作未完成，请运行 doctor 并按诊断步骤排查。'
    return {'type': 'error', 'code': code, 'message': message}
