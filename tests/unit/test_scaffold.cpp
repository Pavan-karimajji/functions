#include <gtest/gtest.h>

// Proves the Step 2 build/test wiring end-to-end (Conan -> CMake presets ->
// gtest FetchContent -> ctest) before any real framework/function code exists.
// Safe to delete once Step 3/4 add real test suites.
TEST(BuildSkeletonTest, GtestHarnessWiringWorks) {
    SUCCEED();
}
