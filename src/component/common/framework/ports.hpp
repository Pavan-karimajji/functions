// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: DF
/// @file
/// @brief
///   ReqPort/ProPort templates: generic require/provide port wrappers.

#pragma once

namespace adas::df {

// Require-port: latest value received for one input, plus how the receiving
// function should judge it — age since receipt and whether it's usable at
// all. Staleness/validity *policy* lives in each function's exec(), not here
// (plan.md §5.3) — this struct only carries the data.
template <typename T>
struct ReqPort {
  T data{};
  double ageS = 0.0;
  bool valid = false;
};

// Provide-port: one function-level output plus whether this tick produced a
// new value worth publishing. The host publishes every ProPort with
// updated == true after each tick (plan.md §5.6).
template <typename T>
struct ProPort {
  T data{};
  bool updated = false;
};

}  // namespace adas::df
