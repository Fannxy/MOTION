import pandas as pd
import re
import argparse

# log_file = ""
# res_file = ""

send_pattern_re = r'Sent: ([\d.]+) MiB in (\d+) messages'
recv_pattern_re = r'Received: ([\d.]+) MiB in (\d+) messages'
operation_re = r"Protocol (\w+) operation (\w+) bit size \d+ SIMD \d+"
circuit_pattern_re = r'Circuit Evaluation\s*([\d.]+) ms.*'

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--logfile', action='append', help='Path to the log file')
    parser.add_argument('--resfile', type=str, help='Path to the result file')
    parser.add_argument('--record-operation', action='store_true', help='Record operation')
    args = parser.parse_args()

    if args.record_operation:
        data = {
            "Sent": [],
            "Sent_mess": [],
            "Received": [],
            "Received_mess": [],
            "Protocol": [],
            "Operation": [],
            "Circuit_evaluation": []
        }
    else:
        data = {
            "Sent": [],
            "Sent_mess": [],
            "Received": [],
            "Received_mess": [],
            "Circuit_evaluation": []
        }
    
    log_files = args.logfile
    res_file = args.resfile
    
    for log_file in log_files:
        with open(log_file, 'r') as file:
            lines = file.readlines()
            for line in lines:
                operation = re.search(operation_re, line)
                send_pattern = re.search(send_pattern_re, line)
                recv_pattern = re.search(recv_pattern_re, line)
                circuit_pattern = re.search(circuit_pattern_re, line)
                # print(line)
                if send_pattern:
                    # print(line)
                    data["Sent"].append(float(send_pattern.group(1)))
                    data["Sent_mess"].append(int(send_pattern.group(2)))
                if recv_pattern:
                    # print(line)
                    data["Received"].append(float(recv_pattern.group(1)))
                    data["Received_mess"].append(int(recv_pattern.group(2)))
                if operation and args.record_operation:
                    # print(line)
                    data["Protocol"].append(operation.group(1))
                    data["Operation"].append(operation.group(2))
                if circuit_pattern:
                    data["Circuit_evaluation"].append(circuit_pattern.group(1))

    for(key, value) in data.items():
        print(key, len(value))
                
    df = pd.DataFrame(data)
    df.to_excel(res_file, index=False)