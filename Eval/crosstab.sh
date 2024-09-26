#!/bin/bash

symmetric=0

data_size=5
bin_size=5

USER_FOLDER=/root/MOTION/
LOG_FOLDER=/root/MOTION/Log/
DATA_FOLDER=/root/MOTION/data/

IP_ADDR0=10.5.0.12
IP_ADDR1=10.5.0.13
PORT0=23000
PORT1=23001
PORT2=24000
PORT3=24001

lsof +D "${USER_FOLDER}/build/bin/" | awk 'NR>1 {print $2}' | xargs kill &
ssh motion1 "lsof +D ${USER_FOLDER}/build/bin/ | awk 'NR>1 {print \$2}' | xargs kill" &
wait;

python ${USER_FOLDER}/src/examples/tutorial/geninput.py -p crosstabs-shared -l ${data_size} -b ${bin_size} --output-dir ${DATA_FOLDER}

ssh motion1 "mkdir -p ${USER_FOLDER}/build/bin/; mkdir -p ${DATA_FOLDER}/crosstabs-shared/data/"
scp ${USER_FOLDER}/build/bin/crosstabs_shared motion1:${USER_FOLDER}/build/bin/
scp ${DATA_FOLDER}/crosstabs-shared/data/crosstabs.1.dat motion1:${DATA_FOLDER}/crosstabs-shared/data/

if [ $symmetric -eq 1 ]; then
    ${USER_FOLDER}build/bin/crosstabs_shared --my-id 0 --parties 0,${IP_ADDR0},${PORT0} 1,${IP_ADDR1},${PORT1} --input-file ${DATA_FOLDER}/crosstabs-shared/data/crosstabs.0.dat --bins ${bin_size} > ${LOG_FOLDER}log-crosstabs-shared${symmetric}-party0 &
    ssh motion1 "${USER_FOLDER}build/bin/crosstabs_shared --my-id 1 --parties 0,${IP_ADDR0},${PORT0} 1,${IP_ADDR1},${PORT1} --input-file ${DATA_FOLDER}/crosstabs-shared/data/crosstabs.1.dat --bins ${bin_size}" &
    ${USER_FOLDER}build/bin/crosstabs_shared --my-id 1 --parties 0,${IP_ADDR1},${PORT3} 1,${IP_ADDR0},${PORT2} --input-file ${DATA_FOLDER}/crosstabs-shared/data/crosstabs.0.dat --bins ${bin_size} > ${LOG_FOLDER}log-crosstabs-shared${symmetric}-party1 &
    ssh motion1 "${USER_FOLDER}build/bin/crosstabs_shared --my-id 0 --parties 0,${IP_ADDR1},${PORT3} 1,${IP_ADDR0},${PORT2} --input-file ${DATA_FOLDER}/crosstabs-shared/data/crosstabs.1.dat --bins ${bin_size}" &
    wait;
else
    ${USER_FOLDER}build/bin/crosstabs_shared --my-id 0 --parties 0,${IP_ADDR0},${PORT0} 1,${IP_ADDR1},${PORT1} --input-file ${DATA_FOLDER}/crosstabs-shared/data/crosstabs.0.dat --bins ${bin_size} > ${LOG_FOLDER}log-crosstabs-shared${symmetric}-party0 &
    ssh motion1 "${USER_FOLDER}build/bin/crosstabs_shared --my-id 1 --parties 0,${IP_ADDR0},${PORT0} 1,${IP_ADDR1},${PORT1} --input-file ${DATA_FOLDER}/crosstabs-shared/data/crosstabs.1.dat --bins ${bin_size}" &
    ${USER_FOLDER}build/bin/crosstabs_shared --my-id 0 --parties 0,${IP_ADDR0},${PORT2} 1,${IP_ADDR1},${PORT3} --input-file ${DATA_FOLDER}/crosstabs-shared/data/crosstabs.0.dat --bins ${bin_size} > ${LOG_FOLDER}log-crosstabs-shared${symmetric}-party1 &
    ssh motion1 "${USER_FOLDER}build/bin/crosstabs_shared --my-id 1 --parties 0,${IP_ADDR0},${PORT2} 1,${IP_ADDR1},${PORT3} --input-file ${DATA_FOLDER}/crosstabs-shared/data/crosstabs.1.dat --bins ${bin_size}" &
    wait;
fi

python ${USER_FOLDER}Eval/get_send_receive_2pc.py --logfile ${LOG_FOLDER}log-crosstabs-shared${symmetric}-party0 --logfile ${LOG_FOLDER}log-crosstabs-shared${symmetric}-party1 --resfile ${LOG_FOLDER}log-crosstabs-shared${symmetric}.xlsx &
wait;