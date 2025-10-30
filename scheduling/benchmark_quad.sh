# port_base=5000
# USER_FOLDER=/root/MOTION/

# ssh h1 "python ${USER_FOLDER}scheduling/quad.py --id 0 --ips 10.0.0.11,10.0.0.12,10.0.0.13,10.0.0.14 --seed 16 --batch 1048576 " &
# ssh h2 "python ${USER_FOLDER}scheduling/quad.py --id 1 --ips 10.0.0.11,10.0.0.12,10.0.0.13,10.0.0.14 --seed 16 --batch 1048576 " &
# ssh h3 "python ${USER_FOLDER}scheduling/quad.py --id 2 --ips 10.0.0.11,10.0.0.12,10.0.0.13,10.0.0.14 --seed 16 --batch 1048576 " &
# ssh h4 "python ${USER_FOLDER}scheduling/quad.py --id 3 --ips 10.0.0.11,10.0.0.12,10.0.0.13,10.0.0.14 --seed 16 --batch 1048576 " &
# wait;

# size=1073741824
size=1416810830

rm -rf ../Log_RoundRole_quad;
python ./benchmark_quad.py --method "RoundRole" --task_num 96 --size ${size};
wait;

rm -rf ../Log_Baseline_quad;
python ./benchmark_quad.py --method "Baseline" --task_num 96 --size ${size};
wait;
