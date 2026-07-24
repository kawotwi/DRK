# Viam C++ Driver Patterns Reference

> Extracted from production module repos: viam-camera-realsense, viam-camera-orbbec,
> universal-robots, mlmodel-tflite, viam-mlmodelservice-triton, system-audio. April 2026.

---

## 1. Camera Driver Pattern (RealSense + Orbbec)

Both depth camera modules follow the same structural pattern: inherit from
`viam::sdk::Camera` and `viam::sdk::Reconfigurable`, manage hardware lifecycle
in constructor/destructor, stream frames in a background thread.

### Class declaration (from RealSense)

```cpp
class Realsense final : public viam::sdk::Camera,
                        public viam::sdk::Reconfigurable {
public:
    Realsense(viam::sdk::Dependencies deps,
              viam::sdk::ResourceConfig cfg,
              std::shared_ptr<RealsenseContext> ctx,
              std::shared_ptr<boost::synchronized_value<std::unordered_set<std::string>>> assigned_serials);
    ~Realsense();

    void reconfigure(const viam::sdk::Dependencies& deps,
                     const viam::sdk::ResourceConfig& cfg) override;

    // Camera interface:
    raw_image get_image(std::string mime_type, const viam::sdk::ProtoStruct& extra) override;
    image_collection get_images(std::vector<std::string> filter_source_names,
                                const viam::sdk::ProtoStruct& extra) override;
    point_cloud get_point_cloud(std::string mime_type, const viam::sdk::ProtoStruct& extra) override;
    properties get_properties() override;
    std::vector<viam::sdk::GeometryConfig> get_geometries(const viam::sdk::ProtoStruct& extra) override;
    ProtoStruct do_command(const ProtoStruct& command) override;

    static std::vector<std::string> validate(viam::sdk::ResourceConfig cfg);
    static inline viam::sdk::Model model{"viam", "camera", "realsense"};

private:
    boost::synchronized_value<RsResourceConfig> config_;
    std::shared_ptr<boost::synchronized_value<device::ViamRSDevice<>>> device_;
    std::shared_ptr<boost::synchronized_value<rs2::frameset>> latest_frameset_;
    // ...
};
```

### Key patterns

**Shared hardware context**: Both RealSense and Orbbec share a device context
across all instances of the module. The context is created once in `main()` and
passed to each resource constructor:

```cpp
// main.cpp (RealSense):
auto ctx = std::make_shared<boost::synchronized_value<rs2::context>>();
auto rs_ctx = std::make_shared<RealsenseContext<...>>(ctx);
auto assigned_serials = std::make_shared<boost::synchronized_value<std::unordered_set<std::string>>>();
auto module_service = std::make_shared<vsdk::ModuleService>(
    argc, argv, create_all_model_registrations(rs_ctx, assigned_serials));

// main.cpp (Orbbec):
auto ctx = std::make_shared<ob::Context>();
auto module_service = std::make_shared<vsdk::ModuleService>(
    argc, argv, create_all_model_registrations(ctx));
```

**Serial number management**: When multiple cameras of the same type are
connected, modules track which serial numbers are assigned to which instances.
RealSense uses `boost::synchronized_value<std::unordered_set<std::string>>`.

**Device hot-plug**: RealSense implements device-change callbacks via the
`RealsenseContext` which notifies all instances when devices connect/disconnect.

**Background frame capture**: Devices stream frames continuously via SDK
pipelines. The latest frameset is stored in a synchronized container and
returned on `get_images()` / `get_point_cloud()` calls.

**Frame age validation**: RealSense checks frame timestamps and throws if
frames are too old (stale data indicates a disconnected camera):

```cpp
static constexpr std::uint64_t MAX_FRAME_AGE_MS = 1e3;
time::throwIfTooOld(nowMs, frame.get_timestamp(), MAX_FRAME_AGE_MS,
                    "no recent color frame: check USB connection");
```

**gRPC message size limits**: Point clouds can be large. RealSense checks
against the 32MB gRPC limit:

```cpp
static constexpr size_t MAX_GRPC_MESSAGE_SIZE = 33554432;
if (data.size() > MAX_GRPC_MESSAGE_SIZE) {
    throw std::runtime_error("point cloud size exceeds gRPC message size limit");
}
```

### Config parsing pattern (from Orbbec)

```cpp
static std::unique_ptr<ObResourceConfig> configure(
    viam::sdk::Dependencies deps, viam::sdk::ResourceConfig cfg) {
    auto attrs = cfg.attributes();

    std::string serial;
    if (attrs.count("serial_number")) {
        serial = attrs["serial_number"].get_unchecked<std::string>();
    }

    std::optional<DeviceResolution> device_resolution;
    if (attrs.count("width_px")) {
        // ... parse resolution
    }

    return std::make_unique<ObResourceConfig>(serial, cfg.name(), device_resolution, device_format);
}
```

### Validation pattern (from RealSense)

```cpp
static std::vector<std::string> validate(viam::sdk::ResourceConfig cfg) {
    auto attrs = cfg.attributes();

    if (attrs.count("sensors")) {
        if (!attrs["sensors"].is_a<viam::sdk::ProtoList>()) {
            throw std::invalid_argument("sensors must be a list");
        }
        auto sensors_proto = attrs["sensors"].get_unchecked<viam::sdk::ProtoList>();
        // validate each element...
    }

    if (attrs.count("serial_number")) {
        if (!attrs["serial_number"].is_a<std::string>()) {
            throw std::invalid_argument("serial_number is not a string");
        }
    }

    return {};  // no implicit dependencies
}
```

### Multiple models from one class (from Orbbec)

Orbbec supports multiple camera models (Astra 2, Gemini 335Le) from the same
C++ class, using separate Model statics and validators:

```cpp
static viam::sdk::Model model_astra2;      // {"viam", "camera", "orbbec-astra2"}
static viam::sdk::Model model_gemini_335le; // {"viam", "camera", "orbbec-gemini-335le"}

static std::vector<std::string> validateAstra2(viam::sdk::ResourceConfig cfg);
static std::vector<std::string> validateGemini335Le(viam::sdk::ResourceConfig cfg);
```

Each is registered as a separate `ModelRegistration` with the same factory
but different validators.

### Discovery service pattern

Both camera modules also register a Discovery service for hardware detection:

```cpp
registrations.push_back(std::make_shared<vsdk::ModelRegistration>(
    vsdk::API::get<vsdk::Discovery>(),
    discovery::RealsenseDiscovery::model,
    [realsense_ctx](vsdk::Dependencies deps, vsdk::ResourceConfig config) {
        return std::make_unique<discovery::RealsenseDiscovery>(
            std::move(deps), std::move(config), realsense_ctx);
    }));
```

---

## 2. Arm Driver Pattern (Universal Robots)

The UR arm module is significantly more complex than camera modules due to
real-time control requirements, state machines, and kinematics.

### Class declaration

```cpp
class URArm final : public Arm, public Reconfigurable {
public:
    static constexpr double k_default_robot_control_freq_hz = 100.0;
    static constexpr double k_default_max_trajectory_duration_secs = 600.0;

    static const ModelFamily& model_family();
    static Model model(std::string model_name);
    static std::vector<std::shared_ptr<ModelRegistration>> create_model_registrations();

    URArm(Model model, const Dependencies& deps, const ResourceConfig& cfg);
    ~URArm() override;

    void reconfigure(const Dependencies& deps, const ResourceConfig& cfg) override;

    // Arm interface:
    std::vector<double> get_joint_positions(const ProtoStruct& extra) override;
    void move_to_joint_positions(const std::vector<double>& positions, const ProtoStruct& extra) override;
    void move_through_joint_positions(const std::vector<std::vector<double>>& positions,
                                      const MoveOptions& options, const ProtoStruct& extra) override;
    pose get_end_position(const ProtoStruct& extra) override;
    void move_to_position(const pose& p, const ProtoStruct&) override;
    bool is_moving() override;
    KinematicsData get_kinematics(const ProtoStruct& extra) override;
    std::map<std::string, mesh> get_3d_models(const ProtoStruct& extra) override;
    void stop(const ProtoStruct& extra) override;
    ProtoStruct do_command(const ProtoStruct& command) override;

    // Unimplemented -- RDK reconstructs from kinematics:
    std::vector<GeometryConfig> get_geometries(const ProtoStruct&) override {
        throw std::runtime_error("unimplemented");
    }

private:
    class state_;  // State machine (connected, controlled, disconnected, independent)
    const Model model_;
    std::shared_mutex config_mutex_;
    std::unique_ptr<state_> current_state_;
};
```

### Key patterns

**State machine**: The UR module uses a sophisticated state machine with
separate source files for each state:
- `ur_arm_state_disconnected.cpp` -- initial/error state
- `ur_arm_state_connected.cpp` -- connected but not controlling
- `ur_arm_state_controlled.cpp` -- actively sending trajectories
- `ur_arm_state_independent.cpp` -- arm moving under its own control
- `ur_arm_state_events.cpp` -- event handling

**Read/write locking**: Uses `std::shared_mutex` for the config:
- Read lock (`std::shared_lock<std::shared_mutex>`) for queries
  (`get_joint_positions`, `get_end_position`)
- Write lock (`std::unique_lock<std::shared_mutex>`) for config changes
  and shutdown

**Trajectory planning**: Integrates with the `trajex` library for
time-optimal trajectory generation:

```cpp
#include <viam/trajex/totg/tools/planner.hpp>
#include <viam/trajex/totg/totg.hpp>
```

**FFI for spatial math**: Uses Rust FFI for quaternion/orientation conversions:

```cpp
extern "C" void* quaternion_from_axis_angle(double x, double y, double z, double theta);
extern "C" void* orientation_vector_from_quaternion(void* q);
```

With RAII wrappers:

```cpp
using unique_quaternion = std::unique_ptr<void, decltype(&free_quaternion_memory)>;
```

**Config validation**: Thorough validation with descriptive errors:

```cpp
std::vector<std::string> validate_config_(const ResourceConfig& cfg) {
    if (!find_config_attribute<std::string>(cfg, "host")) {
        throw std::invalid_argument("attribute `host` is required");
    }
    parse_and_validate_joint_limits(cfg, "speed_degs_per_sec");
    parse_and_validate_joint_limits(cfg, "acceleration_degs_per_sec2");
    // ...
    return {};
}
```

**Multiple arm models**: Supports UR3e, UR5e, UR10e, etc. from one class with
a `ModelFamily`:

```cpp
static const ModelFamily& model_family() {
    static ModelFamily family{"viam", "arm"};
    return family;
}

static Model model(std::string model_name) {
    return Model(model_family(), std::move(model_name));
}
```

**Kinematics and 3D models**: Ships with URDF/SVA files and 3D model data
installed alongside the binary.

### CMake pattern (UR)

```cmake
# FetchContent for both SDK and hardware libraries
FetchContent_Declare(
    Universal_Robots_Client_Library
    GIT_REPOSITORY https://github.com/UniversalRobots/Universal_Robots_Client_Library
    GIT_TAG 2.9.0
    GIT_SHALLOW TRUE SYSTEM
)

FetchContent_Declare(
    viam-cpp-sdk
    GIT_REPOSITORY https://github.com/viamrobotics/viam-cpp-sdk
    GIT_TAG releases/v0.31.0
    GIT_SHALLOW TRUE SYSTEM
    FIND_PACKAGE_ARGS
)

# Library target + executable target
add_library(viam-ur)
target_link_libraries(viam-ur
    PUBLIC viam::trajex::totg::tools urcl viam-cpp-sdk::viamapi viam-cpp-sdk::viamsdk jsoncpp_lib
)

add_executable(universal-robots)
target_link_libraries(universal-robots PRIVATE viam-ur)
```

---

## 3. ML Model Service Pattern (TFLite + Triton)

### TFLite -- simple, single-model pattern

```cpp
class MLModelServiceTFLite final : public vsdk::MLModelService,
                                    public vsdk::Stoppable,
                                    public vsdk::Reconfigurable {
public:
    MLModelServiceTFLite(vsdk::Dependencies dependencies, vsdk::ResourceConfig configuration);
    ~MLModelServiceTFLite() final;

    void stop(const vsdk::ProtoStruct& extra) noexcept final;
    void reconfigure(const vsdk::Dependencies& dependencies,
                     const vsdk::ResourceConfig& configuration) final;
    std::shared_ptr<named_tensor_views> infer(const named_tensor_views& inputs,
                                              const vsdk::ProtoStruct& extra) final;
    struct metadata metadata(const vsdk::ProtoStruct& extra) final;

private:
    struct state_;   // holds interpreter, model, label data
    std::shared_mutex state_rwmutex_;
    std::unique_ptr<struct state_> state_;
};
```

**State encapsulation pattern**: All mutable state is held in a private
`state_` struct. `reconfigure()` creates a new state and swaps it in under
a write lock. `infer()` takes a read lock, enabling concurrent inference:

```cpp
void reconfigure(const vsdk::Dependencies& deps, const vsdk::ResourceConfig& cfg) final {
    auto new_state = configure_(std::move(deps), std::move(cfg));
    std::unique_lock lock(state_rwmutex_);
    state_ = std::move(new_state);
}

std::shared_ptr<named_tensor_views> infer(const named_tensor_views& inputs,
                                           const vsdk::ProtoStruct& extra) final {
    std::shared_lock lock(state_rwmutex_);
    check_stopped_inlock_();
    // run inference using state_->interpreter
}
```

**Tensor type dispatching**: Converts TFLite types to SDK tensor views:

```cpp
template <typename T>
vsdk::MLModelService::tensor_views tensor_views_from_tflite_tensor_t(
    const vsdk::MLModelService::tensor_info& info,
    const TfLiteTensor* const tflite_tensor) {
    const auto* tensor_data = reinterpret_cast<const T*>(TfLiteTensorData(tflite_tensor));
    std::vector<std::size_t> shape;
    for (const auto s : info.shape) {
        shape.push_back(static_cast<std::size_t>(s));
    }
    return MLModelServiceTFLite::MLModelService::make_tensor_view(
        tensor_data, tensor_size_t, std::move(shape));
}
```

**CMake** (simple):

```cmake
find_package(viam-cpp-sdk REQUIRED)
find_package(tensorflowlite REQUIRED)

add_library(tflite_cpu_service src/tflite_cpu.cpp)
target_link_libraries(tflite_cpu_service
    PUBLIC Threads::Threads viam-cpp-sdk::viamsdk
    PRIVATE tensorflow::tensorflowlite
)

add_executable(tflite_cpu src/main.cpp)
target_link_libraries(tflite_cpu PRIVATE tflite_cpu_service)
```

### Triton -- dlopen shim pattern

The Triton module uses a dynamic loading shim to avoid linking directly against
the NVIDIA Triton Server library at build time. All Triton API function pointers
are loaded at runtime:

```cpp
struct shim {
    decltype(TRITONSERVER_ServerNew)* ServerNew = nullptr;
    decltype(TRITONSERVER_ServerInferAsync)* ServerInferAsync = nullptr;
    // ... many more function pointers
};

shim the_shim;  // populated at runtime via dlopen
```

It wraps Triton C API lifecycle in RAII with `lifecycle_traits<T>` specializations
and a generic `call()` wrapper that converts Triton errors to C++ exceptions.

---

## 4. Simple Module Pattern (system-audio)

The audio module is the simplest pattern -- a good starting template.

### Class declaration (Microphone)

```cpp
class Microphone final : public viam::sdk::AudioIn,
                          public viam::sdk::Reconfigurable {
public:
    Microphone(viam::sdk::Dependencies deps, viam::sdk::ResourceConfig cfg,
               audio::portaudio::PortAudioInterface* pa = nullptr);
    ~Microphone();

    static std::vector<std::string> validate(viam::sdk::ResourceConfig cfg);

    viam::sdk::ProtoStruct do_command(const viam::sdk::ProtoStruct& command);
    void get_audio(std::string const& codec,
                   std::function<bool(audio_chunk&& chunk)> const& chunk_handler,
                   double const& duration_seconds,
                   int64_t const& previous_timestamp,
                   const viam::sdk::ProtoStruct& extra);
    viam::sdk::audio_properties get_properties(const viam::sdk::ProtoStruct& extra);
    std::vector<viam::sdk::GeometryConfig> get_geometries(const viam::sdk::ProtoStruct& extra);
    void reconfigure(const viam::sdk::Dependencies& deps, const viam::sdk::ResourceConfig& cfg);

    static vsdk::Model model;
private:
    std::mutex stream_ctx_mu_;
    PaStream* stream_;
    std::shared_ptr<audio::InputStreamContext> audio_context_;
};
```

### Main entry point

```cpp
int serve(int argc, char** argv) try {
    vsdk::Instance inst;
    audio::portaudio::startPortAudio();
    auto module_service = std::make_shared<vsdk::ModuleService>(
        argc, argv, create_all_model_registrations());
    module_service->serve();
    return EXIT_SUCCESS;
} catch (const std::exception& ex) {
    std::cerr << "ERROR: " << ex.what() << std::endl;
    return EXIT_FAILURE;
} catch (...) {
    std::cerr << "ERROR: An unknown exception was thrown" << std::endl;
    return EXIT_FAILURE;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "ERROR: insufficient arguments\n";
        return EXIT_FAILURE;
    }
    return serve(argc, argv);
}
```

### Multi-resource module

The audio module registers AudioIn (microphone), AudioOut (speaker), and
Discovery from the same binary:

```cpp
std::vector<std::shared_ptr<vsdk::ModelRegistration>> create_all_model_registrations() {
    std::vector<std::shared_ptr<vsdk::ModelRegistration>> registrations;

    registrations.push_back(std::make_shared<vsdk::ModelRegistration>(
        vsdk::API::get<vsdk::AudioIn>(), microphone::Microphone::model,
        [](vsdk::Dependencies deps, vsdk::ResourceConfig config) {
            return std::make_unique<microphone::Microphone>(std::move(deps), std::move(config));
        },
        microphone::Microphone::validate));

    registrations.push_back(std::make_shared<vsdk::ModelRegistration>(
        vsdk::API::get<vsdk::AudioOut>(), speaker::Speaker::model,
        [](vsdk::Dependencies deps, vsdk::ResourceConfig config) {
            return std::make_unique<speaker::Speaker>(std::move(deps), std::move(config));
        },
        speaker::Speaker::validate));

    registrations.push_back(std::make_shared<vsdk::ModelRegistration>(
        vsdk::API::get<vsdk::Discovery>(), discovery::AudioDiscovery::model,
        [](vsdk::Dependencies deps, vsdk::ResourceConfig config) {
            return std::make_unique<discovery::AudioDiscovery>(std::move(deps), std::move(config));
        }));

    return registrations;
}
```

### Dependency injection for testing

The audio module accepts an optional `PortAudioInterface*` parameter for
test injection:

```cpp
Microphone(viam::sdk::Dependencies deps, viam::sdk::ResourceConfig cfg,
           audio::portaudio::PortAudioInterface* pa = nullptr);
```

---

## 5. Reconfiguration Patterns

### Full state replacement (TFLite, UR)

Create a new state object and swap:

```cpp
void reconfigure(const Dependencies& deps, const ResourceConfig& cfg) override {
    auto new_state = configure_(deps, cfg);
    std::unique_lock lock(state_rwmutex_);
    state_ = std::move(new_state);
}
```

### In-place reconfiguration (RealSense)

For cameras where the device pipeline can be reused:

```cpp
void reconfigure(const Dependencies& deps, const ResourceConfig& cfg) override {
    device_funcs_.stopDevice(device_, this->logger_);
    config_ = configure(deps, cfg);
    device_funcs_.reconfigureDevice(device_, config_, this->logger_);
    device_funcs_.startDevice(serial, device_, latest_frameset_, ...);
}
```

---

## 6. Testing Patterns

### Unit tests alongside module code (UR)

```cmake
add_executable(universal-robots-test)
target_sources(universal-robots-test PRIVATE src/viam/ur/module/test.cpp)
target_link_libraries(universal-robots-test PRIVATE viam-ur)
add_test(NAME universal-robots COMMAND universal-robots-test)
```

### Separate test directory (RealSense, Audio)

```cmake
enable_testing()
add_subdirectory(test)
```

### Dependency injection for hardware abstraction

The audio module and RealSense both use injection to mock hardware:
- Audio: `PortAudioInterface*` parameter
- RealSense: `DeviceFunctions` struct with lambdas for device operations

---

## 7. Packaging and Deployment

### meta.json

Every module has a `meta.json` (or `meta.json.in` for CMake configure):

```json
{
  "module_id": "viam:camera-realsense",
  "visibility": "public",
  "url": "https://github.com/viam-modules/viam-camera-realsense",
  "description": "Intel RealSense depth camera module",
  "models": [
    { "api": "rdk:component:camera", "model": "viam:camera:realsense" }
  ]
}
```

### Conan build + deploy

Production modules use Conan for reproducible builds:

```bash
conan install . --output-folder=build --build=missing
cd build && cmake .. -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake
cmake --build .
```

### Install layout

Modules typically install to a flat directory with the binary and meta.json:

```cmake
install(TARGETS my-module DESTINATION .)
install(FILES meta.json DESTINATION .)
```

CPack can create a `.tar.gz` for upload to the Viam registry.

---

## 8. Cross-Cutting Concerns

### Error handling pattern (consistent across all modules)

```cpp
int serve(int argc, char** argv) try {
    vsdk::Instance inst;
    // ... setup and serve ...
    return EXIT_SUCCESS;
} catch (const std::exception& ex) {
    std::cerr << "ERROR: " << ex.what() << std::endl;
    return EXIT_FAILURE;
} catch (...) {
    std::cerr << "ERROR: An unknown exception was thrown" << std::endl;
    return EXIT_FAILURE;
}
```

### Namespace alias

```cpp
namespace vsdk = ::viam::sdk;
```

### Library initialization before SDK

When using external libraries that require initialization, do it before
creating the `ModuleService`:

```cpp
vsdk::Instance inst;
audio::portaudio::startPortAudio();  // init PortAudio
orbbec::startOrbbecSDK(*ctx);        // init Orbbec SDK
auto module_service = std::make_shared<vsdk::ModuleService>(...);
```

### RPATH for relocatable installs

```cmake
if (APPLE)
    list(PREPEND CMAKE_INSTALL_RPATH "@loader_path/../lib")
else()
    list(PREPEND CMAKE_INSTALL_RPATH "$ORIGIN/../lib")
endif()
```
