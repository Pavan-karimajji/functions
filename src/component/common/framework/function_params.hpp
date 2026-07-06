#pragma once

#include <string>
#include <yaml-cpp/yaml.h>

namespace adas::functions {

// Thin wrapper around one function's YAML config section. Confines yaml-cpp
// to this one header instead of leaking YAML::Node into every function file
// (plan.md §5.8 item 1). In production (Step 5) constructed by
// ParamLoader::section() from a real file; here in tests, constructed
// directly via YAML::Load() on a string literal — either way a
// default-constructed/empty node is valid input, get() just always returns
// the caller's default in that case (missing section == missing key).
class FunctionParams {
public:
  FunctionParams() = default;
  explicit FunctionParams(YAML::Node section) : section_(std::move(section)) {}

  template <typename T>
  T get(const std::string& key, const T& defaultValue) const {
    if (!section_ || !section_[key]) {
      return defaultValue;
    }
    return section_[key].as<T>();
  }

private:
  YAML::Node section_;
};

}  // namespace adas::functions
