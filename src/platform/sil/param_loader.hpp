#pragma once

#include <string>
#include <yaml-cpp/yaml.h>

#include "component/common/framework/function_params.hpp"

namespace adas::functions {

// Loads one YAML file shaped like config/default.yaml (one top-level section
// per function name) and hands out each function's section. A missing file
// or missing section is not an error here — it degrades to an empty
// FunctionParams, so a function's init() falls back to its own hardcoded
// defaults. Lives here (not src/component/...) because it does disk I/O —
// see plan.md §5.7 Step 3's correction.
class ParamLoader {
public:
  explicit ParamLoader(const std::string& configPath);

  FunctionParams section(const std::string& functionName) const;

private:
  YAML::Node root_;
};

}  // namespace adas::functions
