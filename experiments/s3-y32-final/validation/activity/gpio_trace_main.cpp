// Entire-model FST controlled explicitly in C++; no SV dump gating is used.
#include <verilated.h>
#include <verilated_fst_c.h>
#include "Vtb_sysbus32_soc.h"
#include "Vtb_sysbus32_soc___024root.h"
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
static constexpr uint64_t kHalfPeriodFs = 3333333;
static constexpr uint64_t kPeriodFs = 6666666;

static std::string argument(int argc, char** argv, const std::string& key,
                            const std::string& fallback) {
    for (int i = 1; i < argc; ++i) {
        const std::string value{argv[i]};
        if (value.rfind(key, 0) == 0) return value.substr(key.size());
    }
    return fallback;
}

int main(int argc, char** argv) {
    try {
        const auto traceDir = fs::path(argument(argc, argv, "+ACTIVITY_DIR=", "activity"));
        const int tasks = std::stoi(argument(argc, argv, "+TASKS=", "1"));
        const uint64_t diskLimit = std::stoull(argument(argc, argv, "+ACTIVITY_LIMIT=", "12884901888"));
        const bool gpioWindow=argument(argc,argv,"+ACTIVITY_WINDOW=","clear")=="gpio";
        if (tasks < 1 || tasks > 12) throw std::runtime_error("invalid activity tasks");
        fs::create_directories(traceDir);
        const auto context = std::make_unique<VerilatedContext>();
        context->threads(1);
        context->traceEverOn(true);
        context->commandArgs(argc, argv);
        const auto model = std::make_unique<Vtb_sysbus32_soc>(context.get(), "TOP");
        // All trace objects register before the first eval. --trace-depth is
        // absent; 99 is the documented trace-registration argument, and the
        // resulting declarations are independently inventoried afterwards.
        std::vector<std::unique_ptr<VerilatedFstC>> traces;
        for (int i = 0; i < tasks; ++i) {
            traces.emplace_back(std::make_unique<VerilatedFstC>());
            model->trace(traces.back().get(), 99);
        }
        std::ofstream windows(traceDir / "windows.jsonl");
        windows.exceptions(std::ios::badbit | std::ios::failbit);
        bool previousClk = false;
        int activeLayer = -1;
        int activeCall = -1;
        int completed = 0;
        uint64_t traceStart = 0;
        uint64_t dumpCount = 0;
        uint64_t iterations = 0;
        while (!context->gotFinish()) {
            model->eval();
            auto* const root = model->rootp;
            if (context->timeprecision() != -15)
                throw std::runtime_error("activity requires 1fs context precision");
            const uint64_t now = context->time();
            const bool clk = root->tb_sysbus32_soc__DOT__activity_hf_clk;
            const bool falling = previousClk && !clk;
            const int clearSeq = root->tb_sysbus32_soc__DOT__activity_clear_seq;
            const int endSeq = root->tb_sysbus32_soc__DOT__activity_end_seq;
            const uint64_t offeredFs=root->tb_sysbus32_soc__DOT__activity_gpio_first_fs;
            const bool armClear=!gpioWindow&&falling&&root->tb_sysbus32_soc__DOT__activity_arm;
            const bool armGpio=gpioWindow&&root->tb_sysbus32_soc__DOT__activity_capture_enabled&&
                root->tb_sysbus32_soc__DOT__activity_layer==completed&&offeredFs>0&&now==offeredFs;
            if (activeLayer < 0 && (armClear||armGpio)) {
                activeLayer = root->tb_sysbus32_soc__DOT__activity_layer;
                activeCall = root->tb_sysbus32_soc__DOT__activity_call;
                if (activeLayer != completed || activeLayer >= tasks)
                    throw std::runtime_error("trace task order differs");
                char basename[64];
                std::snprintf(basename, sizeof(basename), "layer_%02d.fst", activeLayer);
                const auto path = traceDir / basename;
                if (fs::exists(path)) throw std::runtime_error("trace output exists");
                traces[activeLayer]->open(path.c_str());
                if (!traces[activeLayer]->isOpen()) throw std::runtime_error("FST open failed");
                traceStart = now;
                dumpCount = 0;
                std::cout << "C32_ACTIVITY_BEGIN layer=" << activeLayer << " call=" << activeCall
                          << " first_fs=" << now << std::endl;
            }
            if (!gpioWindow && clearSeq > 0 && clearSeq != activeCall && endSeq != clearSeq)
                throw std::runtime_error("clear acceptance was not preceded by trace arm");
            if (activeLayer >= 0) {
                traces[activeLayer]->dump(now);  // immediately follows eval
                ++dumpCount;
                if (endSeq == activeCall && (gpioWindow||falling)) {
                    const uint64_t clearFs = root->tb_sysbus32_soc__DOT__activity_clear_fs;
                    const uint64_t lastFs = root->tb_sysbus32_soc__DOT__activity_last_y_fs;
                    const int clearCycle = root->tb_sysbus32_soc__DOT__activity_clear_cycle;
                    const int lastCycle = root->tb_sysbus32_soc__DOT__activity_last_y_cycle;
                    const uint64_t gpioFs = root->tb_sysbus32_soc__DOT__activity_gpio_first_fs;
                    const int gpioCycle = root->tb_sysbus32_soc__DOT__activity_gpio_first_cycle;
                    if (gpioFs <= clearFs || gpioFs >= lastFs || gpioCycle <= clearCycle || gpioCycle >= lastCycle)
                        throw std::runtime_error("GPIO first-data timestamp outside complete task");
                    const uint64_t cycles = uint64_t(lastCycle - clearCycle + 1);
                    if(gpioWindow){
                        if(traceStart!=gpioFs||now!=lastFs)throw std::runtime_error("actual GPIO/retired Y trace boundary differs");
                    } else if (clearFs != traceStart + kHalfPeriodFs || now != lastFs + kHalfPeriodFs ||
                        now - traceStart != cycles * kPeriodFs)
                        throw std::runtime_error("trace edge/full-cycle boundary differs");
                    traces[activeLayer]->close();
                    windows << "{\"trace_window\":\"" << (gpioWindow?"gpio":"clear") << "\",\"layer\":" << activeLayer << ",\"call\":" << activeCall
                            << ",\"trace_first_fs\":" << traceStart << ",\"clear_request_fs\":" << clearFs
                            << ",\"last_y_response_fs\":" << lastFs << ",\"trace_last_fs\":" << now
                            << ",\"clear_request_cycle\":" << clearCycle << ",\"last_y_response_cycle\":" << lastCycle
                            << ",\"inclusive_task_cycles\":" << cycles << ",\"duration_fs\":" << now - traceStart
                            << ",\"gpio_first_data_fs\":" << gpioFs << ",\"gpio_first_data_cycle\":" << gpioCycle
                            << ",\"gpio_first_data_to_last_y_response_fs\":" << lastFs - gpioFs
                            << ",\"gpio_first_data_inclusive_cycles\":" << lastCycle - gpioCycle + 1
                            << ",\"dump_points\":" << dumpCount << "}\n";
                    windows.flush();
                    std::cout << "C32_ACTIVITY_END layer=" << activeLayer << " call=" << activeCall
                              << " last_fs=" << now << " duration_fs=" << now - traceStart
                              << " cycles=" << cycles << std::endl;
                    ++completed;
                    activeLayer = -1;
                    activeCall = -1;
                }
            }
            if ((++iterations % 4096) == 0) {
                uint64_t bytes = 0;
                for (const auto& item : fs::directory_iterator(traceDir))
                    if (item.is_regular_file()) bytes += item.file_size();
                if (bytes > diskLimit || fs::space(traceDir).available < 536870912)
                    throw std::runtime_error("activity disk guard reached");
            }
            previousClk = clk;
            if (!model->eventsPending()) break;
            context->time(model->nextTimeSlot());
        }
        model->final();
        if (completed != tasks || activeLayer >= 0 || !context->gotFinish())
            throw std::runtime_error("incomplete activity run");
        std::cout << "C32_ACTIVITY_PASS tasks=" << completed << " timeprecision_fs=1" << std::endl;
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "C32_ACTIVITY_ERROR " << error.what() << std::endl;
        return 2;
    }
}
