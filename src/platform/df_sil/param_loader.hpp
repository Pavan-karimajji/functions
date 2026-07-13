// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   ParamLoader: loads and sections a project's YAML config file.

#pragma once

#include <string>
#include <yaml-cpp/yaml.h>

#include "component/common/framework/df_params.hpp"

#if defined(_WIN32)
#if defined(DF_SIL_EXPORTS)
#define DF_SIL_API __declspec(dllexport)
#else
#define DF_SIL_API __declspec(dllimport)
#endif
#else
#define DF_SIL_API
#endif

namespace adas::df {

// Loads one YAML file shaped like projects/base/default.yaml (one top-level
// section per function name) and hands out each function's section. A missing file
// or missing section is not an error here — it degrades to an empty
// DfParams, so a function's init() falls back to its own hardcoded
// defaults. Lives here (not src/component/...) because it does disk I/O —
// see plan.md §5.7 Step 3's correction.
//
// Exported (dllexport/dllimport) because test_param_loader.cpp links it
// directly from a separate executable (df_tests) against
// df_sil's import lib — previously only reached indirectly through
// dfInit(), which is already extern "C" exported.
class DF_SIL_API ParamLoader {
public:
  explicit ParamLoader(const std::string& configPath);

  DfParams section(const std::string& functionName) const;

  // Whole file as one DfParams — for flat, non-per-function files like
  // projects/base/ego_params.yaml (as opposed to section(), which is for
  // files shaped like projects/base/default.yaml: one top-level section per
  // function).
  DfParams root() const;

private:
  YAML::Node root_;
};

}  // namespace adas::df
