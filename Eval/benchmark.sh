#!/bin/bash

USER_FOLDER=/root/MOTION/
LOG_FOLDER=/root/MOTION/Log/

${USER_FOLDER}build/bin/benchmark_primitive_operations --my-id 0 --parties 0,127.0.0.1,23000 1,127.0.0.1,23001 >> ${LOG_FOLDER}log-primitive &
${USER_FOLDER}build/bin/benchmark_primitive_operations --my-id 1 --parties 0,127.0.0.1,23000 1,127.0.0.1,23001 &
wait;


${USER_FOLDER}build/bin/benchmark_integers --my-id 0 --parties 0,127.0.0.1,23000 1,127.0.0.1,23001 >> ${LOG_FOLDER}log-benchmark_integers &
${USER_FOLDER}build/bin/benchmark_integers --my-id 1 --parties 0,127.0.0.1,23000 1,127.0.0.1,23001 &
wait;

python ${USER_FOLDER}Eval/get_send_receive_2pc.py --logfile ${LOG_FOLDER}log-primitive --resfile ${LOG_FOLDER}log-primitive-2pc.xlsx &
python ${USER_FOLDER}Eval/get_send_receive_2pc.py --logfile ${LOG_FOLDER}log-benchmark_integers --resfile ${LOG_FOLDER}log-benchmark_integers-2pc.xlsx &
wait;