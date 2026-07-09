#pragma once

#include <cstddef>

// Maximum number of GenObjects any function's exec() processes per cycle.
//
// Mirrors the reference codebase's EM_N_OBJECTS pattern: a single shared
// fixed-size-array budget reused across every object-array type (GenObjects,
// radar objects, output objects), not one macro per array. There, the value
// is baked in per ECU/project variant by an AUTOSAR RTE code generator
// (EB tresos) reading ARXML; here, ADAS_MAX_GEN_OBJECTS (root CMakeLists.txt)
// plays the same role via a CMake cache variable instead of codegen - the
// #ifndef guard means any translation unit could still override it by
// defining the macro before including this header, same idiom the reference
// uses.
//
// Single global value for now, not per-project - no real per-project need
// has shown up yet (see docs/df_carla_bridge_blueprint.md, 2026-07-09,
// "trivial to make per-project via conf/build.yml later if needed").
#ifndef ADAS_MAX_GEN_OBJECTS
#define ADAS_MAX_GEN_OBJECTS 50
#endif

namespace adas::df {

constexpr std::size_t kMaxGenObjects = ADAS_MAX_GEN_OBJECTS;

}  // namespace adas::df
