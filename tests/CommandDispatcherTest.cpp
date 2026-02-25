#include "CommandDispatcher.h"
#include <iostream>
#include <cassert>
#include <thread>
#include <chrono>

void TestPushPop() {
    using namespace ROME;
    auto& dispatcher = CommandDispatcher::Get();

    Command cmd1 { Command::Type::Raw, "player.additem f 100", "" };
    Command cmd2 { Command::Type::Kill, "00000014", "" };

    std::cout << "[TEST] Pushing commands..." << std::endl;
    dispatcher.Push(cmd1);
    dispatcher.Push(cmd2);

    std::cout << "[TEST] Starting dispatcher..." << std::endl;
    dispatcher.Start();

    // Let it process for a second
    std::this_thread::sleep_for(std::chrono::seconds(1));

    std::cout << "[TEST] Stopping dispatcher..." << std::endl;
    dispatcher.Stop();

    std::cout << "[TEST] SUCCESS: Dispatcher thread terminated normally." << std::endl;
}

int main() {
    try {
        TestPushPop();
        std::cout << "[TEST] All tests passed!" << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "[TEST] FAILED: " << e.what() << std::endl;
        return 1;
    }
}
