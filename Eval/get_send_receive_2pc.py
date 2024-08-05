import pandas as pd
import re
import argparse

# log_file = ""
# res_file = ""

data = {
    "Protocol": [],
    "Operation": [],
    "Sent": [],
    "Received": [],
    "Sent_mess": [],
    "Received_mess": []
}

send_pattern_re = r'Sent: ([\d.]+) MiB in (\d+) messages'
recv_pattern_re = r'Received: ([\d.]+) MiB in (\d+) messages'
operation_re = r"Protocol (\w+) operation (\w+) bit size \d+ SIMD \d+"

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--logfile', type=str, help='Path to the log file')
    parser.add_argument('--resfile', type=str, help='Path to the result file')
    args = parser.parse_args()
    
    log_file = args.logfile
    res_file = args.resfile
    
    with open(log_file, 'r') as file:
        lines = file.readlines()
        for line in lines:
            operation = re.search(operation_re, line)
            send_pattern = re.search(send_pattern_re, line)
            recv_pattern = re.search(recv_pattern_re, line)
            # print(line)
            if send_pattern:
                # print(line)
                data["Sent"].append(float(send_pattern.group(1)))
                data["Sent_mess"].append(int(send_pattern.group(2)))
            if recv_pattern:
                # print(line)
                data["Received"].append(float(recv_pattern.group(1)))
                data["Received_mess"].append(int(recv_pattern.group(2)))
            if operation:
                # print(line)
                data["Protocol"].append(operation.group(1))
                data["Operation"].append(operation.group(2))
                
    for(key, value) in data.items():
        print(key, len(value))
                
    df = pd.DataFrame(data)
    df.to_excel(res_file, index=False)