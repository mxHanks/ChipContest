// Native streaming FST -> structurally selected SAIF. No waveform rescaling.
// This exports digital activity; it is not a power or annotation-coverage tool.
#include "fstapi.h"
#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using Stats = std::array<uint64_t, 5>;  // T0,T1,TX,TZ,TC
static const std::string kSource = "TOP.tb_sysbus32_soc";
static const std::string kTarget = "xu_soc_sysbus32_ppa_top";
static std::string join(const std::vector<std::string>& parts, const std::string& separator) {
    std::string result;
    for (const auto& part : parts) { if (!result.empty()) result += separator; result += part; }
    return result;
}
static std::string quoted(const std::string& value) {
    std::string result = "\"";
    for (const auto ch : value) {
        if (ch == '\\' || ch == '"') result += '\\';
        if (static_cast<unsigned char>(ch) < 32) throw std::runtime_error("control in name");
        result += ch;
    }
    return result + '"';
}
static std::string atom(const std::string& value) {
    std::string result;
    for (const auto ch : value) {
        if (ch == '\\' || ch == '(' || ch == ')' || ch == '[' || ch == ']' || std::isspace(ch)) result += '\\';
        result += ch;
    }
    return result;
}
static int stateIndex(char state) {
    const auto index = std::string("01xz").find(char(std::tolower(state)));
    if (index == std::string::npos) throw std::runtime_error("non-digital FST value");
    return int(index);
}
struct Record {
    unsigned width;
    uint64_t last;
    std::string state;
    std::vector<Stats> bits;
    bool initialized = false;
};
struct Declaration {
    std::string source;
    std::vector<std::string> scopes;
    std::vector<std::string> names;
    std::string pin;
    fstHandle handle;
    bool macro;
};
struct State {
    uint64_t first, last;
    std::map<fstHandle, Record> records;
    std::string error;
    uint64_t callbacks = 0;
};
static void integrate(Record& record, uint64_t until) {
    if (until < record.last) throw std::runtime_error("FST per-handle time moved backwards");
    const auto delta = until - record.last;
    for (unsigned bit = 0; bit < record.width; ++bit)
        record.bits[bit][stateIndex(record.state[bit])] += delta;
    record.last = until;
}
static void callback(void* userdata, uint64_t time, fstHandle handle, const unsigned char* bytes) {
    auto& state = *static_cast<State*>(userdata);
    if (!state.error.empty()) return;
    try {
        auto& record = state.records.at(handle);
        if (time < state.first || time > state.last) throw std::runtime_error("callback outside FST range");
        ++state.callbacks;
        const std::string value(reinterpret_cast<const char*>(bytes));
        if (value.size() != record.width) throw std::runtime_error("FST value width differs");
        for (const char ch : value) stateIndex(ch);
        if (!record.initialized) {
            if (time != state.first) throw std::runtime_error("selected handle lacks initial full snapshot");
            record.initialized = true;
            record.state = value;
            std::transform(record.state.begin(), record.state.end(), record.state.begin(),
                           [](unsigned char ch) { return char(std::tolower(ch)); });
            return;
        }
        integrate(record, time);
        for (unsigned bit = 0; bit < record.width; ++bit) {
            const char next = char(std::tolower(value[bit]));
            const char old = record.state[bit];
            // First frame is initialization. Final timestamp is excluded.
            if (time > state.first && time < state.last && old != next &&
                (old == '0' || old == '1') && (next == '0' || next == '1'))
                ++record.bits[bit][4];
            record.state[bit] = next;
        }
    } catch (const std::exception& error) { state.error = error.what(); }
}
struct Tree {
    std::map<std::string, Tree> children;
    std::vector<std::pair<std::string, const Stats*>> nets;
};
static void emit(std::ofstream& output, const Tree& tree, int depth) {
    const std::string indent(depth * 2, ' ');
    if (!tree.nets.empty()) {
        output << indent << "(NET\n";
        for (const auto& net : tree.nets) {
            output << indent << "  (" << atom(net.first);
            for (unsigned i = 0; i < 5; ++i)
                output << " (" << std::array<const char*, 5>{"T0", "T1", "TX", "TZ", "TC"}[i]
                       << ' ' << net.second->at(i) << ')';
            output << ")\n";
        }
        output << indent << ")\n";
    }
    for (const auto& child : tree.children) {
        output << indent << "(INSTANCE " << atom(child.first) << '\n';
        emit(output, child.second, depth + 1);
        output << indent << ")\n";
    }
}
int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::runtime_error("usage: fst_to_saif IN.fst OUT.saif PORTS.jsonl");
        void* reader = fstReaderOpen(argv[1]);
        if (!reader) throw std::runtime_error("fstReaderOpen failed");
        State state{fstReaderGetStartTime(reader), fstReaderGetEndTime(reader), {}, "", 0};
        if (state.first >= state.last || fstReaderGetTimescale(reader) != -15 || fstReaderGetTimezero(reader) != 0)
            throw std::runtime_error("requires nonempty original 1fs/timezero0 FST");
        std::vector<std::string> scopes;
        std::vector<Declaration> declarations;
        std::set<std::string> selectedScopes, droppedScopes, paths;
        uint64_t droppedSignals = 0, omittedNondigital = 0, omittedMacroInternal = 0, macroPorts = 0;
        const std::set<std::string> macroPins{"CLK", "CEN", "GWEN", "WEN", "A", "D", "Q", "EMA", "EMAW", "RET1N"};
        while (const auto* item = fstReaderIterateHier(reader)) {
            if (item->htyp == FST_HT_SCOPE) scopes.emplace_back(item->u.scope.name);
            else if (item->htyp == FST_HT_UPSCOPE) {
                if (scopes.empty()) throw std::runtime_error("scope underflow");
                scopes.pop_back();
            } else if (item->htyp == FST_HT_VAR) {
                const auto source = join(scopes, ".");
                std::string branch;
                size_t offset = 0;
                if (source == kSource + ".dut" || source.rfind(kSource + ".dut.", 0) == 0) {
                    branch = "u_soc"; offset = 3;
                } else if (source == kSource + ".endpoint" || source.rfind(kSource + ".endpoint.", 0) == 0) {
                    branch = "u_shared"; offset = 3;
                } else { ++droppedSignals; droppedScopes.insert(source); continue; }
                std::string name = item->u.var.name;
                const auto space = name.find(' ');
                const auto pin = name.substr(0, space);
                const auto macroScope = std::find(scopes.begin(), scopes.end(), "macro");
                if (macroScope != scopes.end() &&
                    (macroScope + 1 != scopes.end() || !macroPins.count(pin))) {
                    ++omittedMacroInternal; continue;
                }
                const auto type = item->u.var.typ;
                if (type == FST_VT_VCD_REAL || type == FST_VT_VCD_REAL_PARAMETER ||
                    type == FST_VT_VCD_REALTIME || type == FST_VT_GEN_STRING ||
                    type == FST_VT_SV_SHORTREAL || type == FST_VT_VCD_EVENT) {
                    ++omittedNondigital; continue;
                }
                const unsigned width = item->u.var.length;
                if (!width || width > 65536) throw std::runtime_error("invalid selected digital width");
                std::vector<std::string> target{kTarget, branch};
                target.insert(target.end(), scopes.begin() + offset, scopes.end());
                selectedScopes.insert(join(target, "/"));
                std::vector<std::string> names;
                if (space == std::string::npos && width == 1) names.emplace_back(pin);
                else {
                    int left = int(width) - 1, right = 0;
                    if (space != std::string::npos) {
                        const auto range = name.substr(space + 1);
                        char tail = 0;
                        if (std::sscanf(range.c_str(), "[%d:%d]%c", &left, &right, &tail) != 2 ||
                            unsigned(std::abs(left - right) + 1) != width)
                            throw std::runtime_error("unsupported FST vector range: " + name);
                    }
                    for (int i = left;; i += left <= right ? 1 : -1) {
                        names.emplace_back(pin + '[' + std::to_string(i) + ']');
                        if (i == right) break;
                    }
                }
                for (const auto& bit : names)
                    if (!paths.insert(join(target, "/") + '/' + bit).second)
                        throw std::runtime_error("mapped path collision");
                const auto handle = item->u.var.handle;
                const auto inserted = state.records.emplace(handle, Record{width, state.first, std::string(width, 'x'), std::vector<Stats>(width), false});
                if (!inserted.second && inserted.first->second.width != width)
                    throw std::runtime_error("alias widths differ");
                const bool macro = !scopes.empty() && scopes.back() == "macro";
                if (macro) ++macroPorts;
                declarations.push_back(Declaration{source + '.' + pin, target, names, pin, handle, macro});
            }
        }
        if (!scopes.empty() || declarations.empty()) throw std::runtime_error("incomplete selected hierarchy");
        fstReaderClrFacProcessMaskAll(reader);
        for (const auto& entry : state.records) fstReaderSetFacProcessMask(reader, entry.first);
        fstReaderSetLimitTimeRange(reader, state.first, state.last);
        if (!fstReaderIterBlocks(reader, callback, &state, nullptr)) throw std::runtime_error("native FST decode failed");
        if (!state.error.empty()) throw std::runtime_error(state.error);
        if (fstReaderGetFseekFailed(reader)) throw std::runtime_error("FST seek failed");
        for (auto& entry : state.records) {
            auto& record = entry.second;
            if (!record.initialized) throw std::runtime_error("missing selected initialization");
            integrate(record, state.last);
            for (const auto& bit : record.bits)
                if (bit[0] + bit[1] + bit[2] + bit[3] != state.last - state.first)
                    throw std::runtime_error("dwell sum differs from full duration");
        }
        Tree tree;
        std::ofstream ports(argv[3]);
        ports.exceptions(std::ios::badbit | std::ios::failbit);
        for (const auto& declaration : declarations) {
            auto* node = &tree;
            for (const auto& scope : declaration.scopes) node = &node->children[scope];
            const auto& record = state.records.at(declaration.handle);
            for (unsigned bit = 0; bit < declaration.names.size(); ++bit)
                node->nets.emplace_back(declaration.names[bit], &record.bits[bit]);
            if (declaration.macro) {
                ports << "{\"source\":" << quoted(declaration.source) << ",\"target_scope\":" << quoted(join(declaration.scopes, "/"))
                      << ",\"pin\":" << quoted(declaration.pin) << ",\"handle\":" << declaration.handle << ",\"width\":" << record.width << ",\"stats\":[";
                for (unsigned bit = 0; bit < record.width; ++bit) {
                    if (bit) ports << ',';
                    ports << '[';
                    for (unsigned i = 0; i < 5; ++i) { if (i) ports << ','; ports << record.bits[bit][i]; }
                    ports << ']';
                }
                ports << "]}\n";
            }
        }
        std::ofstream output(argv[2]);
        output.exceptions(std::ios::badbit | std::ios::failbit);
        const auto currentTime = std::time(nullptr);
        char date[64];
        if (!std::strftime(date, sizeof(date), "%Y-%m-%dT%H:%M:%SZ", std::gmtime(&currentTime)))
            throw std::runtime_error("could not format UTC export date");
        output << "(SAIFILE\n  (SAIFVERSION \"2.0\")\n  (DIRECTION \"backward\")\n  (DESIGN)\n"
               << "  (DATE \"" << date << "\")\n"
               << "  (VENDOR \"xu\")\n  (PROGRAM_NAME \"compliant32 native FST digital activity\")\n  (VERSION \"1\")\n"
               << "  (DIVIDER /)\n  (TIMESCALE 1 fs)\n  (DURATION " << state.last - state.first << ")\n";
        emit(output, tree, 1);
        output << ")\n";
        output.close(); ports.close(); fstReaderClose(reader);
        std::cout << "{\"status\":\"CONVERTED_DIGITAL_NOT_POWER_READY\",\"first_fs\":" << state.first << ",\"last_fs\":" << state.last
                  << ",\"duration_fs\":" << state.last - state.first << ",\"digital_declarations\":" << declarations.size()
                  << ",\"digital_bits\":" << paths.size() << ",\"independent_handles\":" << state.records.size()
                  << ",\"selected_scopes\":" << selectedScopes.size() << ",\"dropped_tb_scopes\":" << droppedScopes.size()
                  << ",\"dropped_tb_declarations\":" << droppedSignals << ",\"omitted_nondigital_declarations\":" << omittedNondigital
                  << ",\"omitted_generic_macro_internal_declarations\":" << omittedMacroInternal
                  << ",\"macro_port_declarations\":" << macroPorts << ",\"native_callbacks\":" << state.callbacks << "}\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
