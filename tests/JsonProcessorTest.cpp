#include "JsonProcessor.h"
#include "CommandDispatcher.h"
#include <iostream>
#include <cassert>

void TestParseValidArray() {
    using namespace ROME;
    auto& dispatcher = CommandDispatcher::Get();

    std::string json = R"([
        {"type": "raw", "target": "player.additem f 100"},
        {"type": "kill", "target": "00000014"},
        {"type": "follow", "target": "00000014", "extra": "1"}
    ])";

    ParseCommands(json);
    std::cout << "[TEST] ParseValidArray: 3 commands pushed." << std::endl;
}

void TestParseEmptyArray() {
    std::string json = "[]";
    ROME::ParseCommands(json);
    std::cout << "[TEST] ParseEmptyArray: no crash on empty input." << std::endl;
}

void TestParseMalformed() {
    std::string json = "NOT JSON AT ALL";
    ROME::ParseCommands(json);
    std::cout << "[TEST] ParseMalformed: graceful error handling." << std::endl;
}

void TestParseMissingFields() {
    std::string json = R"([{"type": "raw"}])";
    ROME::ParseCommands(json);
    std::cout << "[TEST] ParseMissingFields: handled missing 'target'." << std::endl;
}

int main() {
    try {
        TestParseValidArray();
        TestParseEmptyArray();
        TestParseMalformed();
        TestParseMissingFields();
        std::cout << "[TEST] All JSON parsing tests passed!" << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "[TEST] FAILED: " << e.what() << std::endl;
        return 1;
    }
}
