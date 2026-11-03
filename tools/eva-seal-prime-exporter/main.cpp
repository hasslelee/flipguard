#include <cstdint>
#include <exception>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

#include <seal/seal.h>

namespace {

std::uint64_t parseUnsigned(const char *text, const char *name) {
  std::size_t consumed = 0;
  const std::string value(text);
  const auto parsed = std::stoull(value, &consumed, 10);
  if (consumed != value.size()) {
    throw std::invalid_argument(std::string("invalid ") + name);
  }
  return parsed;
}

template <typename Value>
void printArray(const std::vector<Value> &values) {
  std::cout << '[';
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index != 0) {
      std::cout << ',';
    }
    std::cout << values[index];
  }
  std::cout << ']';
}

std::vector<std::uint64_t>
modulusValues(const std::vector<seal::Modulus> &moduli) {
  std::vector<std::uint64_t> values;
  values.reserve(moduli.size());
  for (const auto &modulus : moduli) {
    values.push_back(modulus.value());
  }
  return values;
}

} // namespace

int main(int argc, char **argv) {
  try {
    if (argc < 4) {
      throw std::invalid_argument(
          "usage: eva-seal-prime-exporter DEGREE BIT_SIZE BIT_SIZE [...]");
    }
    const auto degree = parseUnsigned(argv[1], "poly modulus degree");
    std::vector<int> bitSizes;
    bitSizes.reserve(static_cast<std::size_t>(argc - 2));
    for (int index = 2; index < argc; ++index) {
      const auto bitSize = parseUnsigned(argv[index], "prime bit size");
      if (bitSize > 60) {
        throw std::invalid_argument("SEAL prime bit size exceeds 60");
      }
      bitSizes.push_back(static_cast<int>(bitSize));
    }

    const auto keyModuli = seal::CoeffModulus::Create(degree, bitSizes);
    seal::EncryptionParameters parameters(seal::scheme_type::ckks);
    parameters.set_poly_modulus_degree(degree);
    parameters.set_coeff_modulus(keyModuli);
    const seal::SEALContext context(
        parameters, true, seal::sec_level_type::none);
    if (!context.parameters_set() || !context.using_keyswitching()) {
      throw std::runtime_error(
          "materialized SEAL context is invalid or has no key switching");
    }

    const auto &firstModuli =
        context.first_context_data()->parms().coeff_modulus();
    const auto keyValues = modulusValues(keyModuli);
    const auto firstValues = modulusValues(firstModuli);
    if (keyValues.size() != firstValues.size() + 1) {
      throw std::runtime_error(
          "SEAL key/ciphertext modulus split is not one special prime");
    }

    std::cout << "{\"schema_version\":"
                 "\"flipguard_eva_seal_prime_materialization_v1\",";
    std::cout << "\"poly_modulus_degree\":" << degree << ',';
    std::cout << "\"prime_bits\":";
    printArray(bitSizes);
    std::cout << ",\"key_context_coeff_modulus\":";
    printArray(keyValues);
    std::cout << ",\"first_context_coeff_modulus\":";
    printArray(firstValues);
    std::cout << ",\"special_modulus\":" << keyValues.back() << ',';
    std::cout << "\"using_keyswitching\":true}\n";
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "eva-seal-prime-exporter: " << error.what() << '\n';
    return 1;
  }
}
