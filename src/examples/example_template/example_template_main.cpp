// MIT License
//
// Copyright (c) 2019 Oleksandr Tkachenko
// Cryptography and Privacy Engineering Group (ENCRYPTO)
// TU Darmstadt, Germany
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

#include <cmath>
#include <fstream>
#include <iostream>
#include <random>
#include <regex>

#include <fmt/format.h>
#include <boost/lexical_cast.hpp>
#include <boost/program_options.hpp>

#include "base/party.h"
#include "common/example_template.h"
#include "communication/communication_layer.h"
#include "communication/tcp_transport.h"

namespace po = boost::program_options;

bool CheckPartyArgumentSyntax(const std::string& p);

std::pair<po::variables_map, bool> ParseProgramOptions(int ac, char* av[]);

MOTION::PartyPtr CreateParty(const po::variables_map& vm);

int main(int ac, char* av[]) {
  auto [vm, help_flag] = ParseProgramOptions(ac, av);
  // if help flag is set - print allowed command line arguments and exit
  if (help_flag) return EXIT_SUCCESS;

  MOTION::PartyPtr party{CreateParty(vm)};

  EvaluateProtocol(party);
  return EXIT_SUCCESS;
}

const std::regex party_argument_re("(\\d+),(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}),(\\d{1,5})");

bool CheckPartyArgumentSyntax(const std::string& p) {
  // other party's id, IP address, and port
  return std::regex_match(p, party_argument_re);
}

std::tuple<std::size_t, std::string, std::uint16_t> ParsePartyArgument(const std::string& p) {
  std::smatch match;
  std::regex_match(p, match, party_argument_re);
  auto id = boost::lexical_cast<std::size_t>(match[1]);
  auto host = match[2];
  auto port = boost::lexical_cast<std::uint16_t>(match[3]);
  return {id, host, port};
}

// <variables map, help flag>
std::pair<po::variables_map, bool> ParseProgramOptions(int ac, char* av[]) {
  using namespace std::string_view_literals;
  constexpr std::string_view config_file_msg =
      "config file, other arguments will overwrite the parameters read from the config file"sv;
  bool print, help;
  boost::program_options::options_description desc("Allowed options");
  // clang-format off
  desc.add_options()
      ("help,h", po::bool_switch(&help)->default_value(false),"produce help message")
      ("disable-logging,l","disable logging to file")
      ("print-config,p", po::bool_switch(&print)->default_value(false), "print config")
      ("config-file,f", po::value<std::string>(), config_file_msg.data())
      ("my-id", po::value<std::size_t>(), "my party id")
      ("other-parties", po::value<std::vector<std::string>>()->multitoken(), "(other party id, IP, port, my role), e.g., --other-parties 1,127.0.0.1,7777");
  // clang-format on

  po::variables_map vm;

  po::store(po::parse_command_line(ac, av, desc), vm);
  po::notify(vm);

  // argument help or no arguments (at least a config file is expected)
  if (vm["help"].as<bool>() || ac == 1) {
    std::cout << desc << "\n";
    return std::make_pair<po::variables_map, bool>({}, true);
  }

  // read config file
  if (vm.count("config-file")) {
    std::ifstream ifs(vm["config-file"].as<std::string>().c_str());
    po::variables_map vm_config_file;
    po::store(po::parse_config_file(ifs, desc), vm);
    po::notify(vm);
  }

  // print parsed parameters
  if (vm.count("my-id")) {
    if (print) std::cout << "My id " << vm["my-id"].as<std::size_t>() << std::endl;
  } else
    throw std::runtime_error("My id is not set but required");

  if (vm.count("other-parties")) {
    const std::vector<std::string> other_parties{
        vm["other-parties"].as<std::vector<std::string>>()};
    std::string parties("Other parties: ");
    for (auto& p : other_parties) {
      if (CheckPartyArgumentSyntax(p)) {
        if (print) parties.append(" " + p);
      } else {
        throw std::runtime_error("Incorrect party argument syntax " + p);
      }
    }
    if (print) std::cout << parties << std::endl;
  } else
    throw std::runtime_error("Other parties' information is not set but required");

  return std::make_pair(vm, help);
}

MOTION::PartyPtr CreateParty(const po::variables_map& vm) {
  const auto parties_str{vm["other-parties"].as<const std::vector<std::string>>()};
  const auto num_parties{parties_str.size()};
  const auto my_id{vm["my-id"].as<std::size_t>()};
  if (my_id >= num_parties) {
    throw std::runtime_error(fmt::format(
        "My id needs to be in the range [0, #parties - 1], current my id is {} and #parties is {}",
        my_id, num_parties));
  }

  MOTION::Communication::tcp_parties_config parties_config(num_parties);

  for (const auto& party_str : parties_str) {
    const auto [party_id, host, port] = ParsePartyArgument(party_str);
    if (party_id >= num_parties) {
      throw std::runtime_error(
          fmt::format("Party's id needs to be in the range [0, #parties - 1], current id "
                      "is {} and #parties is {}",
                      party_id, num_parties));
    }
    parties_config.at(party_id) = std::make_pair(host, port);
  }
  MOTION::Communication::TCPSetupHelper helper(my_id, parties_config);
  auto comm_layer = std::make_unique<MOTION::Communication::CommunicationLayer>(my_id, helper.setup_connections());
  auto party = std::make_unique<MOTION::Party>(std::move(comm_layer));
  auto config = party->GetConfiguration();
  // disable logging if the corresponding flag was set
  const auto logging{!vm.count("disable-logging")};
  config->SetLoggingEnabled(logging);
  return party;
}
