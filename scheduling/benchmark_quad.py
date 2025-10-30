#!/usr/bin/env python3
import subprocess
import os
import argparse
import itertools


parser = argparse.ArgumentParser()
parser.add_argument('--method', type=str, default="RoundRole", help='Method to use')
parser.add_argument('--task_num', type=int, default=4, help='Number of 4-party tasks to run')
parser.add_argument('--size', type=int, default=33554432, help='input size')
parser.add_argument('--user-folder', type=str, default="/root/MOTION/", help='Base folder path')
args = parser.parse_args()

method = args.method
task_num = args.task_num

USER_FOLDER="/root/MOTION/"
LOG_FOLDER=f"/root/MOTION/Log_{method}_quad/"

os.makedirs(LOG_FOLDER, exist_ok=True)

task_assigns = []
if args.method == "RoundRole":
    # 轮换方式：id顺序循环分配 - suppose task_num = n! now
    if (task_num % 24) != 0:
        raise ValueError("RoundRole method currently requires task_num to be 24 (4!)")
    else:
        # task_assigns = list(itertools.permutations([0,1,2,3]))
        n_groups = task_num // 24
        base_perms = list(itertools.permutations([0, 1, 2, 3]))
        task_assigns = base_perms * n_groups
    # for i in range(args.task_num):
    #     # 例如 task0: (0,1,2,3), task1: (1,2,3,0), ...
    #     base = i % 4
    #     roles = [(base + j) % 4 for j in range(4)]
    #     task_assigns.append(roles)
else:
    # 默认固定映射：每个任务使用相同的角色分配
    for _ in range(args.task_num):
        task_assigns.append([0,1,2,3])

hosts = ["h1", "h2", "h3", "h4"]
ips = ["10.0.0.11", "10.0.0.12", "10.0.0.13", "10.0.0.14"]
ports_start = 23000
task = "quad"
net_interfaces=[hosts[i]+"-eth0" for i in range(len(hosts))]

print(f"==> Launching {args.task_num} tasks, method={args.method}")
for i, roles in enumerate(task_assigns):
    print(f"  Task {i}: role map = {roles}")

# === 构造每个任务的命令 ===
commands = {h:[f"cd {USER_FOLDER}; "] for h in hosts}
for i, roles in enumerate(task_assigns):
    port_base = ports_start + i * 100  # 每个任务端口隔开，防冲突
    # ips_str = ",".join(ips)
    # ips_ordered = [ips[r] for r in roles]
    ips_ordered = [None] * len(roles)
    for ip, role in zip(ips, roles):
        ips_ordered[role] = ip
    ips_str = ",".join(ips_ordered)

    hosts_ordered = [hosts[r] for r in roles]
    
    # with open(f"{LOG_FOLDER}debug.txt", "a") as f:
    #     print(f"==> Task {i}: roles {roles}, ips {ips_ordered}", file=f)

    for rid, (h, ip) in zip(roles, zip(hosts, ips)):
        log_file = f"{LOG_FOLDER}task{i}-p{rid}.log"
        cmd = (
            f"python {USER_FOLDER}scheduling/quad.py "
            f"--id {rid} "
            f"--ips {ips_str} "
            f"--port-base {port_base} "
            f"--seed 16 "
            f"--batch {int(args.size / task_num)} "
            f">> {log_file} 2>&1 &"
        )
        # commands.append((h, cmd))
        commands[h].append(cmd)

full_cmds = {}
for h, cmdlist in commands.items():
    cmdlist.append("wait;")
    full_cmds[h] = " ".join(cmdlist)
    # with open(f"{LOG_FOLDER}debug.txt", "a") as f:
    #     print(f"==> Command for {h}:\n{full_cmds[h]}\n", file=f)
    # print(f"\n==> Command for {h}:\n{full_cmds[h]}\n")

# exit(0)

procs = []
for i, h in enumerate(hosts):
    print(f"[+] Launching all tasks on {h} ...")
    # p = subprocess.Popen(["ssh", h, full_cmds[h]])
    p = subprocess.Popen(["ssh", h, f"python {USER_FOLDER}scheduling/monitor_dis_run_profiler.py", f"--command \"{full_cmds[h]}\" ", f"--record_folder {LOG_FOLDER} --keyword {task}-{h} --interface {net_interfaces[i]}"])
    procs.append(p)

# === 等待全部结束 ===
for p in procs:
    p.wait()

print("\n==> All tasks finished.")
print(f"Logs stored under: {LOG_FOLDER}")