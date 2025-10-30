import subprocess
import os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--method', type=str, default="RoundRole", help='Method to use')
parser.add_argument('--task_num', type=int, default=8, help='Number of tasks to run')
args = parser.parse_args()

method = args.method
task_num = args.task_num

USER_FOLDER="/root/MOTION/"
LOG_FOLDER=f"/root/MOTION/Log_B2A_{method}/"

os.system(f"cd {USER_FOLDER}; ./Eval/compile.sh")

task_assigns = []
if method == "RoundRole":
    # task_assigns = [(0,1), (0,1), (1,0), (1,0), (0,1), (0,1), (1,0), (1,0), (0,1), (0,1), (1,0), (1,0)]
    for i in range(task_num):
        if i % 2 == 0:
            task_assigns.append((0,1))
        else:
            task_assigns.append((1,0))
else:
    # task_assigns = [(0,1), (0,1), (0,1), (0,1), (0,1), (0,1), (0,1), (0,1) (0,1), (0,1), (0,1), (0,1)]
    for i in range(task_num):
        task_assigns.append((0,1))
    
hosts = ["h1", "h2"]
ips = ["10.0.0.11", "10.0.0.12"]
ports_start = 23000
task = "benchmark_primitive_operations"
net_interfaces=[hosts[0]+"-eth0", hosts[1]+"-eth0"]

cmds_on_h1 = ["cd /root/MOTION/;"]
cmds_on_h2 = ["cd /root/MOTION/;"]

for i, (role_h1, role_h2) in enumerate(task_assigns):
    port = ports_start + i

    # 根据任务角色确定 parties 顺序
    if role_h1 == 0 and role_h2 == 1:
        parties = f"0,{ips[0]},{port} 1,{ips[1]},{port}"
    elif role_h1 == 1 and role_h2 == 0:
        parties = f"0,{ips[1]},{port} 1,{ips[0]},{port}"
    else:
        raise ValueError(f"Invalid role pair for task {i}: {(role_h1, role_h2)}")

    log1 = f"{LOG_FOLDER}{task}-{i}-p{role_h1}.log"
    log2 = f"{LOG_FOLDER}{task}-{i}-p{role_h2}.log"

    cmd1 = (
        f"{USER_FOLDER}build/bin/{task} "
        f"--my-id {role_h1} --parties {parties} >> {log1} 2>&1 &"
    )
    cmd2 = (
        f"{USER_FOLDER}build/bin/{task} "
        f"--my-id {role_h2} --parties {parties} >> {log2} 2>&1 &"
    )

    cmds_on_h1.append(cmd1)
    cmds_on_h2.append(cmd2)

cmds_on_h1.append("wait;")
cmds_on_h2.append("wait;")

# 拼成单行命令
full_cmd_h1 = " ".join(cmds_on_h1)
full_cmd_h2 = " ".join(cmds_on_h2)

print("==> h1 command:\n", full_cmd_h1)
print("==> h2 command:\n", full_cmd_h2)


p1 = subprocess.Popen([
    "ssh", hosts[0],
    f"python {USER_FOLDER}scheduling/monitor_dis_run_profiler.py "
    f"--command \"{full_cmd_h1}\" "
    f"--record_folder {LOG_FOLDER} --keyword {task}-h1 --interface {net_interfaces[0]}"
])

p2 = subprocess.Popen([
    "ssh", hosts[1],
    f"python {USER_FOLDER}scheduling/monitor_dis_run_profiler.py "
    f"--command \"{full_cmd_h2}\" "
    f"--record_folder {LOG_FOLDER} --keyword {task}-h2 --interface {net_interfaces[1]}"
])

p1.wait()
p2.wait()