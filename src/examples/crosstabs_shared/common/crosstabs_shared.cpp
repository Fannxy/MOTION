// MIT License
//
// Copyright (c) 2021 Arianne Roselina Prananto
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

#include "crosstabs_shared.h"

#include <fstream>
#include <span>
#include "protocols/arithmetic_gmw/arithmetic_gmw_wire.h"
#include "protocols/bmr/bmr_wire.h"
#include "protocols/boolean_gmw/boolean_gmw_wire.h"
#include "protocols/share_wrapper.h"
#include "secure_type/secure_unsigned_integer.h"
#include "statistics/analysis.h"
#include "statistics/run_time_statistics.h"
#include "utility/bit_vector.h"
#include "utility/config.h"

/**
 * Stores the attributes.
 */
struct Attributes {
  std::vector<std::uint32_t> cleartext_input;  // values for party_0 and categories for party_1.
  std::vector<encrypto::motion::SecureUnsignedInteger> id;
} party_0, party_1;

/**
 * Stores all the inputs needed for CrossTabsCircuit().
 */
struct CrossTabsContext {
  Attributes party_0, party_1;
  std::vector<encrypto::motion::SecureUnsignedInteger> shared_weight, shared_bin;
  std::vector<encrypto::motion::SecureUnsignedInteger> categories, results;
  encrypto::motion::ShareWrapper full_zero;
  std::uint32_t number_of_bins;
};

encrypto::motion::RunTimeStatistics EvaluateProtocol(
    encrypto::motion::PartyPointer& party, std::uint32_t number_of_bins,
    std::span<const std::uint32_t> input_command_line, const std::string& input_file_path,
    bool print_output) {
  /* Prepares some variables such as id (input index), results (zero vector as
   * initialization), and categories. categories contains the number from 0 until number_of_bins-1.
   * */
  std::vector<std::uint32_t> id;
  std::vector<encrypto::motion::SecureUnsignedInteger> shared_weight;
  std::vector<encrypto::motion::SecureUnsignedInteger> shared_bin;
  std::uint32_t zero = 0;
  auto party_id = party->GetConfiguration()->GetMyId();
  std::vector<encrypto::motion::SecureUnsignedInteger> results(number_of_bins),
      categories(number_of_bins);

  for (std::uint32_t i = 0; i < number_of_bins; i++) {
    results[i] = party->In<encrypto::motion::MpcProtocol::kArithmeticGmw>(zero, 0);
    categories[i] =
        party->In<encrypto::motion::MpcProtocol::kBooleanGmw>(encrypto::motion::ToInput(i), 0);
  }

  // Checks if there is no input from command line.
  if (input_command_line.empty()) {
    // Takes input from file, path is given in input_file_path.
    const auto [party_0_temp, party_1_temp, id_temp] =
        GetFileInput(party_id, input_file_path, number_of_bins);
    party_0.cleartext_input = party_0_temp;
    party_1.cleartext_input = party_1_temp;
    id = id_temp;
  } else {
    // Takes input as vector of integers from terminal.
    id.reserve(input_command_line.size());
    assert(input_command_line.size() % 2 == 0);
    for (std::uint32_t i = 0; i < input_command_line.size(); i++) {
      // Assigns real input to party and dummy input to the other party.
      if (i < input_command_line.size() / 2) {
        party_0.cleartext_input.push_back(input_command_line[i]);
        party_1.cleartext_input.push_back(input_command_line[i]);
      } else {
        party_0.cleartext_input.push_back(input_command_line[i] % number_of_bins);
        party_1.cleartext_input.push_back(input_command_line[i] % number_of_bins);
      }
      id.push_back(i);
    }
  }

  std::uint32_t input_len = party_0.cleartext_input.size();
  assert(input_len % 2 == 0);

  /* Assigns input to its party.
   * The same input will be used as a dummy input for the other party, but only the party with the
   * same id will really set the input.
   * */
  for (std::size_t i = 0; i < input_len / 2; i++) {
    if(party_id == 0) {
      shared_weight.push_back(
        party->SharedIn<encrypto::motion::MpcProtocol::kArithmeticGmw>(
        party_0.cleartext_input[i]));
      shared_bin.push_back(party->SharedIn<encrypto::motion::MpcProtocol::kBooleanGmw>(
        encrypto::motion::ToInput(party_0.cleartext_input[i + input_len / 2])));
    } else {
      shared_weight.push_back(
        party->SharedIn<encrypto::motion::MpcProtocol::kArithmeticGmw>(
        party_1.cleartext_input[i]));
      shared_bin.push_back(party->SharedIn<encrypto::motion::MpcProtocol::kBooleanGmw>(
        encrypto::motion::ToInput(party_1.cleartext_input[i + input_len / 2])));
    }
    party_0.id.push_back(
        party->In<encrypto::motion::MpcProtocol::kBooleanGmw>(encrypto::motion::ToInput(id[i]), 0));
    party_1.id.push_back(
        party->In<encrypto::motion::MpcProtocol::kBooleanGmw>(encrypto::motion::ToInput(id[i]), 1));
  }

  /* Creates a ShareWrapper initialized with zeros that will be used in CreateCrossTabsCircuit()
   * as a concatenation fill in.
   * */
  encrypto::motion::ShareWrapper full_zero = party->In<encrypto::motion::MpcProtocol::kBooleanGmw>(
      encrypto::motion::BitVector<>(1, false), 0);

  CrossTabsContext context = {party_0, party_1, shared_weight, shared_bin, categories, results, full_zero, number_of_bins};
  std::vector<encrypto::motion::SecureUnsignedInteger> output = CreateCrossTabsCircuit(context);

  // Constructs an output gate for each bin.
  for (std::size_t i = 0; i < output.size(); i++) output[i] = output[i].Out();

  party->Run();

  // Converts the outputs to integers.
  std::vector<std::uint32_t> result;
  for (auto each_output : output) result.push_back(each_output.As<std::uint32_t>());

  if (print_output) {
    for (std::size_t i = 0; i < number_of_bins; i++) {
      std::cout << "Bin " << i << ":\t" << result[i] << std::endl;
    }
  }

  party->Finish();

  const auto& statistics = party->GetBackend()->GetRunTimeStatistics();
  return statistics.front();
}

/**
 * Constructs the cross tabs of the given data in CrossTabsContext.
 * */
std::vector<encrypto::motion::SecureUnsignedInteger> CreateCrossTabsCircuit(
    CrossTabsContext context) {
  auto party_0_id = context.party_0.id, party_1_id = context.party_1.id;
  auto shared_weight = context.shared_weight, shared_bin = context.shared_bin;
  auto number_of_bins = context.number_of_bins;
  encrypto::motion::ShareWrapper id_match, bin_match;

  for (std::size_t i = 0; i < party_0_id.size(); i++) {
    for (std::size_t j = 0; j < party_1_id.size(); j++) {
      id_match = (party_0_id[i] == party_1_id[j]);  // Checks if the indices are the same.
      for (std::size_t k = 0; k < context.number_of_bins; k++) {
        // Checks if the bins numbers are the same.
        bin_match = (context.categories[k] == shared_bin[j]);

        // Checks if both binmatch and idmatch are 'true'.
        encrypto::motion::ShareWrapper keep = bin_match & id_match;

        // Concatenates keep so that it has the same length as party_0_values[i].
        std::vector<encrypto::motion::ShareWrapper> keep_concat;
        keep_concat.push_back(keep);
        for (std::size_t i = 0; i < 31; i++) keep_concat.push_back(context.full_zero);
        keep = encrypto::motion::ShareWrapper::Concatenate(keep_concat);

        // Assigns party_0_values[i] in keep only if keep is 'true'.
        keep = keep.Convert<encrypto::motion::MpcProtocol::kArithmeticGmw>();
        keep = keep * shared_weight[i].Get();

        // Adds keep to the result.
        context.results[k] = context.results[k] + encrypto::motion::SecureUnsignedInteger(keep);
      }
    }
  }
  return context.results;
}

/**
 * Takes inputs from file in path.
 */
std::tuple<std::vector<std::uint32_t>, std::vector<std::uint32_t>, std::vector<std::uint32_t>>
GetFileInput(std::size_t party_id, const std::string& path, std::uint32_t number_of_bins) {
  std::ifstream infile;
  std::vector<std::uint32_t> weight, bin, id;
  std::uint32_t n;

  infile.open(path);
  if (!infile.is_open()) throw std::runtime_error("Could not open CrossTabs file");

  while (infile >> n) {
    weight.push_back(n);
    bin.push_back(n);
  }
  infile.close();

  int len = weight.size();
  assert(len % 2 == 0);
  std::vector<std::uint32_t> party_0, party_1;
  for (std::uint32_t i = 0; i < len / 2; ++i) {
    party_0.push_back(weight[i]);
    party_1.push_back(weight[i]);
    id.push_back(i);
  }
  for (std::uint32_t i = len / 2; i < len; ++i) {
    party_0.push_back(bin[i]);
    party_1.push_back(bin[i]);
  }
  return {party_0, party_1, id};
}
