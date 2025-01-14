# suppose in ./MOTION/
root_folder=/root/MOTION

cd $root_folder

mkdir build && cd build
cmake ..
make -j 16

cd $root_folder

./Eval/benchmark.sh
wait;