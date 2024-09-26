# MIT License

# Copyright (c) 2021 Marcella Hastings, Brett Hemenway, Daniel Noble, Steve Zdancewic, Arianne Roselina Prananto

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


# *******************************************************************************
# * Note that this software contains scripts that download software created     *
# * by third parties, which must be used in accordance with their own licenses. *
# *******************************************************************************

# Taken from https://github.com/MPC-SoK/frameworks/blob/master/aby/source/geninput.py and modified.

# This file should live in the examples/tutorial directory.
import random, argparse, os, math, errno

def create_dirs(program):
    if program == "mult3-shared-arit" or program == "mult3-shared-bool" :
        program = "mult3"
    dirname = "{}/{}/data".format(args.output_dir, program)
    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname)
        except OSError as e:
            if e.errno != errno.EEXIST: raise


def gen_mult3_real_input():
    # 10 bit inputs for a max of 32 bit result
    BITS = 10
    f0 = open("{}/mult3/data/mult3.0.dat".format(args.output_dir),'w+')
    f1 = open("{}/mult3/data/mult3.1.dat".format(args.output_dir),'w+')
    f2 = open("{}/mult3/data/mult3.2.dat".format(args.output_dir),'w+')

    product = 1
    x = random.getrandbits(BITS)
    product *= x
    f0.write("%d" % x)
    x = random.getrandbits(BITS)
    product *= x
    f1.write("%d" % x)
    x = random.getrandbits(BITS)
    product *= x
    f2.write("%d" % x)

    f0.close()
    f1.close()
    f2.close()

    print("Expected result: %d" % product)


def gen_mult3_shared_arithmetic_input():
    # 10 bit inputs for a max of 32 bit result
    BITS = 10
    f0 = open("{}/mult3/data/mult3shared_arit.0.dat".format(args.output_dir),'w+')
    f1 = open("{}/mult3/data/mult3shared_arit.1.dat".format(args.output_dir),'w+')


    product = 1
    for _ in range(3):
        x = random.getrandbits(BITS)
        left = random.randrange(x)

        f0.write("%d\n"%(x-left))
        f1.write("%d\n"%left)

        product *= x

    f0.close()
    f1.close()

    print("Expected result: %d" % product)


def gen_mult3_shared_boolean_input():
    # 10 bit inputs for a max of 32 bit result
    BITS = 10
    f0 = open("{}/mult3/data/mult3shared_bool.0.dat".format(args.output_dir),'w+')
    f1 = open("{}/mult3/data/mult3shared_bool.1.dat".format(args.output_dir),'w+')
    

    product = 1
    for _ in range(3):
        x = random.getrandbits(BITS)
        left = random.randrange(x)

        f0.write("%d\n"%(x^left))
        f1.write("%d\n"%left)

        product *= x

    f0.close()
    f1.close()

    print("Expected result: %d" % product)


def gen_innerproduct_input(l):
    BITS = int((32 - int(math.log(10, 2))) / 2)

    xs = [random.getrandbits(BITS) for _ in range(l)]
    ys = [random.getrandbits(BITS) for _ in range(l)]
    result = sum([x * y for x, y in zip(xs, ys)])

    for i, arr in zip([0, 1], [xs, ys]):
        f = open("{}/innerproduct/data/innerproduct.{}.dat".format(args.output_dir, i), 'w+')
        for a in arr:
            f.write("%d\n" % a)

    print("Expected result: %d" % result)


def gen_crosstabs_input(l):
    BITS = int((32 - int(math.log(10, 2))) / 2)

    xs = [random.getrandbits(BITS) for _ in range(l)]
    ys = [random.getrandbits(BITS) for _ in range(l)]

    for i, arr in zip([0, 1], [xs, ys]):
        f = open("{}/crosstabs/data/crosstabs.{}.dat".format(args.output_dir, i), 'w+')
        for a in arr:
            f.write("%d\n" % a)

    print("Expected results :")
    for j in range(len(ys)):
        print("Bin (%d mod #bins) : %d\t" % (ys[j], xs[j]))
    print("And 0 for others")

def gen_crosstabs_shared_input(l, b):
    BITS = int((32 - int(math.log(10, 2))) / 2)

    xs = [random.getrandbits(BITS) for _ in range(l)]
    ys = [random.getrandbits(BITS) for _ in range(l)]

    f = []
    for i in [0, 1]:
        f.append(open("{}/crosstabs-shared/data/crosstabs.{}.dat".format(args.output_dir, i), 'w+'))

    for x in xs:
        left = random.randrange(x + 1)
        f[0].write("%d\n" % left)
        f[1].write("%d\n" % (x - left))
    for y in ys:
        left = random.randrange(y % b + 1)
        f[0].write("%d\n" % left)
        f[1].write("%d\n" % ((y % b) ^ left))

    print("Expected results :")
    for j in range(len(ys)):
        print("Bin (%d) : %d\t" % (ys[j] % b, xs[j]))
    print("And 0 for others")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='generates input for MOTION sample programs')

    parser.add_argument('-l', default=5, type=int,
                        help="array length (for innerproduct, crosstabs)")
    
    parser.add_argument('-b', default=10, type=int,
                        help="bin size (for crosstabs-shared)")

    programs = ["mult3", "mult3-shared-arit", "mult3-shared-bool", "innerproduct", "crosstabs", "crosstabs-shared"]
    parser.add_argument('-p', default="crosstabs", choices=programs,
                        help="program selection")

    parser.add_argument('--output-dir', default="/root/MOTION/data/", type=str,
                        help="output directory for generated input")

    args = parser.parse_args()

    create_dirs(args.p)

    if args.p == "mult3":
        gen_mult3_real_input()

    elif args.p == "mult3-shared-arit":
        gen_mult3_shared_arithmetic_input()

    elif args.p == "mult3-shared-bool":
        gen_mult3_shared_boolean_input()

    elif args.p == "innerproduct":
        gen_innerproduct_input(args.l)

    elif args.p == "crosstabs":
        gen_crosstabs_input(args.l)

    elif args.p == "crosstabs-shared":
        gen_crosstabs_shared_input(args.l, args.b)