#!/bin/bash

USER_FOLDER=/root/MOTION/
LOG_FOLDER=/root/MOTION/Log/

host_list=(h1 h2)
id_list=(0 1)
node_id=(11 12)
port_list=(23000 23001)
target_task="benchmark_primitive_operations"

# start the two parties on two different machines.
command1="${USER_FOLDER}build/bin/${target_task} --my-id ${id_list[0]} --parties 0,10.0.0.${node_id[0]},${port_list[0]} 1,10.0.0.${node_id[1]},${port_list[1]} >> ${LOG_FOLDER}log-primitive &"
command2="${USER_FOLDER}build/bin/${target_task} --my-id ${id_list[1]} --parties 0,10.0.0.${node_id[0]},${port_list[0]} 1,10.0.0.${node_id[1]},${port_list[1]} &"

ssh ${host_list[0]} "bash -c 'cd ${USER_FOLDER} ; ${command1} '" &
ssh ${host_list[1]} "bash -c 'cd ${USER_FOLDER} ; ${command2} '"
wait;

# ${USER_FOLDER}build/bin/benchmark_primitive_operations --my-id 0 --parties 0,127.0.0.1,23000 1,127.0.0.1,23001 >> ${LOG_FOLDER}log-primitive &
# ${USER_FOLDER}build/bin/benchmark_primitive_operations --my-id 1 --parties 0,127.0.0.1,23000 1,127.0.0.1,23001 &
# wait;


# ${USER_FOLDER}build/bin/benchmark_integers --my-id 0 --parties 0,127.0.0.1,23000 1,127.0.0.1,23001 >> ${LOG_FOLDER}log-benchmark_integers &
# ${USER_FOLDER}build/bin/benchmark_integers --my-id 1 --parties 0,127.0.0.1,23000 1,127.0.0.1,23001 &
# wait;

# python ${USER_FOLDER}Eval/get_send_receive_2pc.py --logfile ${LOG_FOLDER}log-primitive --resfile ${LOG_FOLDER}log-primitive-2pc.xlsx --record-operation &
# wait;
# python ${USER_FOLDER}Eval/get_send_receive_2pc.py --logfile ${LOG_FOLDER}log-benchmark_integers --resfile ${LOG_FOLDER}log-benchmark_integers-2pc.xlsx --record-operation &
# wait;