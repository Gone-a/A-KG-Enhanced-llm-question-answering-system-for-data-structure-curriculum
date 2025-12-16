# import os

# import subprocess
# def neo4j_restart():
#     neo_path = os.path.join(os.path.expandvars("$NEO4J_HOME"), "bin")

#     if os.path.exists(neo_path):
#         os.chdir(neo_path)
#         subprocess.run(["neo4j", "restart"])

import os
import contextlib
from pathlib import Path

#开启neo4j图知识库或Vue

import os
import contextlib
import subprocess
import threading
import time

class RunServe():
    def __init__(self):
        self.vue_process = None
        
    def start_vue_async(self, output_event=None):
        """
        异步启动Vue服务
        Args:
            output_event: threading.Event, 如果提供，将在显示"App running"之前等待该事件设定
        """
        def run_vue():
            original_dir = os.getcwd()
            try:
                # 尝试查找Vue目录
                vue_dir = os.path.join(original_dir, 'Vue')
                if not os.path.exists(vue_dir):
                     # 如果当前目录找不到，尝试上一级目录或绝对路径（假设在项目根目录）
                     project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                     vue_dir = os.path.join(project_root, 'Vue')
                
                if not os.path.exists(vue_dir):
                    print(f"错误：找不到Vue目录 (尝试路径: {vue_dir})")
                    return
                os.chdir(vue_dir)
                
                # 使用bufsize=1启用行缓冲，universal_newlines=True处理文本
                self.vue_process = subprocess.Popen(
                    ["npm", "run", "serve"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                
                # 实时读取输出，只显示关键信息
                app_running_shown = False
                buffer_lines = [] # 暂存需要延迟显示的行
                
                for line in self.vue_process.stdout:
                    if "App running at:" in line:
                        app_running_shown = True
                        if output_event:
                             # 如果有事件控制，先暂存，等待事件
                             buffer_lines.append("\n" + line.strip())
                        else:
                             print("\n" + line.strip())
                             
                    elif app_running_shown:
                        # 显示App running后的几行信息（通常是URL）
                        if output_event:
                            buffer_lines.append(line.strip())
                        else:
                            print(line.strip())
                            
                        if "Network:" in line: 
                             app_running_shown = False 
                             # 如果使用了事件，在这里等待并输出
                             if output_event:
                                 output_event.wait() # 等待后端准备就绪
                                 print("\n--- 前端服务已准备就绪 ---")
                                 for buffered_line in buffer_lines:
                                     print(buffered_line)
                                 print("--------------------------\n")
                                 buffer_lines = []
                    
                    # 可以根据需要过滤或显示其他日志
                    # if "error" in line.lower():
                    #     print(line.strip())
                        
                self.vue_process.wait()
            except Exception as e:
                print(f"Vue服务启动失败: {e}")
            finally:
                os.chdir(original_dir)
        
        vue_thread = threading.Thread(target=run_vue, daemon=True)
        vue_thread.start()
    
    def check_and_start_neo4j(self):
        """检查并启动Neo4j服务"""
        original_dir = os.getcwd()
        try:
            neo_home = os.environ.get("NEO4J_HOME")
            if not neo_home:
                # 尝试默认路径或其他推断方式，或者报错
                print("警告: NEO4J_HOME环境变量未设置，尝试使用默认路径...")
                # 这里可以添加默认路径逻辑，或者直接返回
                return

            bin_dir = os.path.join(neo_home, "bin")
            if not os.path.exists(bin_dir):
                 print(f"错误: Neo4j bin目录不存在: {bin_dir}")
                 return

            os.chdir(bin_dir)
            
            # 检查状态
            # 使用完整路径调用neo4j，避免相对路径问题
            neo4j_cmd = os.path.join(bin_dir, "neo4j")
            result = subprocess.run([neo4j_cmd, "status"], capture_output=True, text=True)
            if result.returncode != 0 or "not running" in result.stdout:
                print("Neo4j未运行，正在启动...")
                subprocess.run([neo4j_cmd, "start"])
            else:
                print("Neo4j已在运行")
                
        except Exception as e:
            print(f"Neo4j操作失败: {e}")
        finally:
            os.chdir(original_dir)

    @contextlib.contextmanager
    def run(self, str):
        """兼容旧代码的上下文管理器（建议逐步废弃）"""
        if str == 'neo4j':
            self.check_and_start_neo4j()
            yield
        elif str == 'Vue':  
            self.start_vue_async()
            yield
        else:
            raise ValueError('输入错误')

if __name__ == '__main__':
    with RunServe().run('neo4j'):
        pass
    with RunServe().run('Vue'):
        pass