// MIT License
//
// Copyright (c) 2020 Lennart Braun
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

#include "runtime_info.h"

#include <cassert>
#include <fstream>

#include <boost/process/child.hpp>
#include <boost/process/io.hpp>
#include <boost/process/pipe.hpp>

namespace encrypto::motion {

std::string GetCmdLine() {
  std::ifstream f("/proc/self/cmdline");
  assert(f);
  std::string cmdline;
  std::getline(f, cmdline, '\0');
  std::string line;
  while (std::getline(f, line, '\0')) {
    cmdline.append(" ");
    cmdline.append(line);
  }
  return cmdline;
}

std::size_t GetPid() {
  std::ifstream f("/proc/self/stat");
  assert(f);
  std::size_t pid;
  f >> pid;
  return pid;
}

std::string GetHostname() {
  std::ifstream f("/proc/sys/kernel/hostname");
  assert(f);
  std::string hostname;
  std::getline(f, hostname);
  return hostname;
}

std::string GetUsername() {
  namespace bp = boost::process;
  bp::ipstream output;
  bp::child child_process("whoami", bp::std_out > output);
  std::string username;
  std::getline(output, username);
  return username;
}

}  // namespace encrypto::motion
