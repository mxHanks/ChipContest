// Native reader for metadata, complete hierarchy and required port initial values.
#include "fstapi.h"
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

static std::string quote(const std::string& value) {
    std::string result = "\"";
    for (const unsigned char ch : value) {
        if (ch == '\\' || ch == '"') { result += '\\'; result += ch; }
        else if (ch == '\n') result += "\\n";
        else if (ch == '\r') result += "\\r";
        else if (ch == '\t') result += "\\t";
        else if (ch < 32) throw std::runtime_error("control character in hierarchy");
        else result += ch;
    }
    return result + '"';
}

struct Initials {
    uint64_t first;
    std::set<fstHandle> wanted;
    std::set<fstHandle> seen;
};

static void callback(void* userdata, uint64_t time, fstHandle handle,
                     const unsigned char* value) {
    auto& state = *static_cast<Initials*>(userdata);
    if (time != state.first || !state.wanted.count(handle) || !state.seen.insert(handle).second)
        return;
    std::cout << "{\"type\":\"initial\",\"handle\":" << handle << ",\"time\":" << time
              << ",\"value\":" << quote(reinterpret_cast<const char*>(value)) << "}\n";
}

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("usage: fst_inventory FILE.fst");
        void* reader = fstReaderOpen(argv[1]);
        if (!reader) throw std::runtime_error("fstReaderOpen failed");
        const uint64_t first = fstReaderGetStartTime(reader);
        const uint64_t last = fstReaderGetEndTime(reader);
        std::cout << "{\"type\":\"metadata\",\"first\":" << first << ",\"last\":" << last
                  << ",\"timescale\":" << int(fstReaderGetTimescale(reader))
                  << ",\"timezero\":" << fstReaderGetTimezero(reader)
                  << ",\"variables\":" << fstReaderGetVarCount(reader)
                  << ",\"scopes\":" << fstReaderGetScopeCount(reader)
                  << ",\"max_handle\":" << fstReaderGetMaxHandle(reader)
                  << ",\"aliases\":" << fstReaderGetAliasCount(reader) << "}\n";
        std::vector<std::string> scopes;
        Initials state{first, {}, {}};
        const std::set<std::string> macroPins{"CLK", "CEN", "GWEN", "WEN", "A", "D", "Q", "EMA", "EMAW", "RET1N"};
        const std::set<std::string> cpuPins{"clk", "cs", "we", "wem", "addr", "din", "dout"};
        while (const auto* item = fstReaderIterateHier(reader)) {
            if (item->htyp == FST_HT_SCOPE) {
                scopes.emplace_back(item->u.scope.name);
                std::string path;
                for (const auto& name : scopes) { if (!path.empty()) path += '.'; path += name; }
                std::cout << "{\"type\":\"scope\",\"path\":" << quote(path)
                          << ",\"component\":" << quote(item->u.scope.component ? item->u.scope.component : "") << "}\n";
            } else if (item->htyp == FST_HT_UPSCOPE) {
                if (scopes.empty()) throw std::runtime_error("hierarchy upscope underflow");
                scopes.pop_back();
            } else if (item->htyp == FST_HT_VAR) {
                std::string path;
                for (const auto& name : scopes) { if (!path.empty()) path += '.'; path += name; }
                std::string name = item->u.var.name;
                const auto space = name.find(' ');
                const auto base = name.substr(0, space);
                const bool macro = !scopes.empty() && scopes.back() == "macro" && macroPins.count(base);
                const bool cpu = !scopes.empty() && scopes.back() == "u_sirv_sim_ram" && cpuPins.count(base);
                if (macro || cpu) state.wanted.insert(item->u.var.handle);
                std::cout << "{\"type\":\"signal\",\"scope\":" << quote(path)
                          << ",\"name\":" << quote(name) << ",\"width\":" << item->u.var.length
                          << ",\"handle\":" << item->u.var.handle << ",\"alias\":"
                          << (item->u.var.is_alias ? "true" : "false") << "}\n";
            }
        }
        if (!scopes.empty()) throw std::runtime_error("unclosed hierarchy scopes");
        fstReaderClrFacProcessMaskAll(reader);
        for (const auto handle : state.wanted) fstReaderSetFacProcessMask(reader, handle);
        fstReaderSetLimitTimeRange(reader, first, first);
        if (!fstReaderIterBlocks(reader, callback, &state, nullptr)) throw std::runtime_error("FST initial frame decode failed");
        if (state.seen != state.wanted) throw std::runtime_error("required port lacks initial FST value");
        if (fstReaderGetFseekFailed(reader)) throw std::runtime_error("FST seek failed");
        std::cout << "{\"type\":\"complete\",\"required_unique_handles\":" << state.wanted.size()
                  << ",\"initial_handles\":" << state.seen.size() << "}\n";
        fstReaderClose(reader);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
