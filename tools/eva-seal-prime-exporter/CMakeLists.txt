cmake_minimum_required(VERSION 3.13)
project(eva_seal_prime_exporter LANGUAGES CXX)

find_package(SEAL 3.6 REQUIRED)

add_executable(eva-seal-prime-exporter main.cpp)
target_compile_features(eva-seal-prime-exporter PRIVATE cxx_std_17)
target_link_libraries(eva-seal-prime-exporter PRIVATE SEAL::seal)
