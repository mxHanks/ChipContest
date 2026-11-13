// Preserve every signal and event in selected absolute-time VCD intervals.
// Outside those intervals, emit only the complete preceding state. The original
// file is never modified. Input must be a digital/real VCD with a 1 fs timescale.
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

struct Window { uint64_t begin, end; };
static void require(bool ok, const std::string& why) {
  if (!ok) throw std::runtime_error(why);
}
static uint64_t number(const std::string& s) {
  require(!s.empty() && s.find_first_not_of("0123456789") == std::string::npos,
          "Invalid unsigned timestamp");
  size_t n = 0;
  uint64_t x = std::stoull(s, &n);
  require(n == s.size(), "Trailing timestamp text");
  return x;
}
int main(int argc, char** argv) {
  try {
    require(argc == 4, "Usage: extract INPUT.vcd WINDOWS.fs.tsv OUTPUT.vcd");
    std::ifstream input(argv[1], std::ios::binary), ranges(argv[2]);
    require(input.good() && ranges.good(), "Cannot open inputs");
    std::ifstream existing(argv[3]);
    require(!existing.good(), "Output already exists");
    std::vector<Window> windows;
    std::string line, a, b, extra;
    while (std::getline(ranges, line)) {
      if (line.empty()) continue;
      std::istringstream s(line);
      require(bool(s >> a >> b) && !(s >> extra), "Invalid window row");
      Window w{number(a), number(b)};
      require(w.begin > 0 && w.end > w.begin, "Empty or zero-origin window");
      if (!windows.empty())
        require(w.begin > windows.back().end + 1, "Overlapping windows");
      windows.push_back(w);
    }
    require(!windows.empty(), "No windows");
    std::ofstream output(argv[3], std::ios::binary);
    require(output.good(), "Cannot create output");
    std::unordered_map<std::string, unsigned> widths;
    std::unordered_map<std::string, std::string> state;
    std::vector<std::string> ids;
    std::string prefix;
    bool header_done = false;
    while (std::getline(input, line)) {
      require(line.find('\r') == std::string::npos, "CRLF input unsupported");
      output << line << '\n';
      if (prefix.size() < 65536) prefix += line;
      if (line.compare(0, 5, "$var ") == 0) {
        std::istringstream s(line);
        std::string tag, type, width, id, name;
        require(bool(s >> tag >> type >> width >> id >> name), "Invalid declaration");
        unsigned w = static_cast<unsigned>(number(width));
        require(w > 0, "Zero-width declaration");
        auto found = widths.find(id);
        require(found == widths.end() || found->second == w, "Alias width differs");
        if (found == widths.end()) { widths.emplace(id, w); ids.push_back(id); }
      }
      if (line.find("$enddefinitions") != std::string::npos) {
        require(line.find("$end") != std::string::npos &&
                line.find("$end", 1) != std::string::npos,
                "Multiline enddefinitions unsupported");
        header_done = true;
        break;
      }
    }
    std::string compact;
    for (char c : prefix) if (c != ' ' && c != '\t' && c != '\n') compact += c;
    require(header_done && compact.find("$timescale1fs$end") != std::string::npos,
            "Expected 1 fs timescale and complete header");
    require(!ids.empty(), "No signal declarations");
    std::sort(ids.begin(), ids.end());
    state.reserve(ids.size());
    size_t wi = 0;
    bool opened = false, seen_time = false, dumpvars = false, had_dumpvars = false;
    uint64_t now = 0, dump_time = 0, last_output_time = 0, kept = 0, changes = 0, timestamps = 0;
    auto emit_time = [&](uint64_t t) {
      require(t >= last_output_time, "Output timestamp regressed");
      output << '#' << t << '\n';
      last_output_time = t;
    };
    auto baseline = [&]() {
      require(state.size() == ids.size(), "Missing preceding values");
      emit_time(windows[wi].begin - 1);
      if (wi == 0) output << "$dumpvars\n";
      for (const auto& id : ids) output << state.at(id) << '\n';
      if (wi == 0) output << "$end\n";
      opened = true;
    };
    auto advance = [&](uint64_t t) {
      while (wi < windows.size() && t > windows[wi].end) {
        if (!opened) baseline();
        emit_time(windows[wi].end);
        ++wi;
        opened = false;
      }
      if (wi < windows.size() && t >= windows[wi].begin) {
        if (!opened) baseline();
        emit_time(t);
      }
    };
    while (std::getline(input, line)) {
      if (line.empty()) continue;
      require(line.find('\r') == std::string::npos, "CRLF input unsupported");
      if (line[0] == '#') {
        uint64_t t = number(line.substr(1));
        require(!seen_time || t >= now, "Input timestamp regressed");
        now = t; seen_time = true; ++timestamps;
        advance(t);
        continue;
      }
      if (line[0] == '$') {
        if (line == "$dumpvars") {
          require(now < windows.front().begin && !had_dumpvars && !dumpvars,
                  "Runtime dumpvars unsupported");
          dump_time = now;
          dumpvars = had_dumpvars = true;
        } else if (line == "$end") {
          require(dumpvars && now == dump_time, "Unexpected body directive end");
          dumpvars = false;
        } else throw std::runtime_error("Unsupported body directive: " + line.substr(0, 80));
        continue;
      }
      std::string id;
      if (std::string("01xXzZ").find(line[0]) != std::string::npos) {
        id = line.substr(1);
        require(id.find_first_of(" \t") == std::string::npos, "Malformed scalar");
      } else if (std::string("bBrRsS").find(line[0]) != std::string::npos) {
        std::istringstream s(line);
        std::string value;
        require(bool(s >> value >> id) && !(s >> extra), "Malformed vector/real/string");
      } else throw std::runtime_error("Unsupported value record");
      require(widths.find(id) != widths.end(), "Undeclared identifier");
      state[id] = line;
      ++changes;
      if (opened && wi < windows.size() && now >= windows[wi].begin && now <= windows[wi].end) {
        output << line << '\n';
        ++kept;
      }
    }
    require(input.eof() && !dumpvars && seen_time && now >= windows.back().end,
            "Incomplete source or missing final window");
    advance(now + 1);
    output.flush();
    require(wi == windows.size() && output.good(), "Incomplete output");
    std::cout << "WINDOW_VCD_EXTRACT_COMPLETE signals=" << ids.size()
              << " windows=" << windows.size() << " source_changes=" << changes
              << " copied_changes=" << kept << " timestamps=" << timestamps << '\n';
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "EXTRACT_FAILED " << e.what() << '\n';
    return 1;
  }
}
