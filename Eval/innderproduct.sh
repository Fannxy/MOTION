#!/bin/bash

USER_FOLDER=/root/MOTION/

# all the four protocols are symmetric communicated.
${USER_FOLDER}build/bin/innerproduct --my-id 0 --parties 0,127.0.0.1,23000 1,127.0.0.1,23001 --input 1 3 5 7 9 --protocol BMR &
${USER_FOLDER}build/bin/innerproduct --my-id 1 --parties 0,127.0.0.1,23000 1,127.0.0.1,23001 --input 1 3 5 7 9 --protocol BMR &
wait;