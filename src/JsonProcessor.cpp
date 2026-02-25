#include "JsonProcessor.h"
#include <nlohmann/json.hpp>
#include "CommandDispatcher.h"
#include <iostream>

namespace ROME {

    void ParseCommands(const std::string& jsonString) {
        try {
            auto j = nlohmann::json::parse(jsonString);
            if (j.is_array()) {
                for (auto& element : j) {
                    Command cmd;
                    std::string type = element["type"].get<std::string>();
                    if (type == "raw") cmd.type = Command::Type::Raw;
                    else if (type == "kill") cmd.type = Command::Type::Kill;
                    else if (type == "follow") cmd.type = Command::Type::Follow;
                    else if (type == "face") cmd.type = Command::Type::Face;

                    cmd.target = element["target"].get<std::string>();
                    if (element.contains("extra")) {
                        cmd.extra = element["extra"].get<std::string>();
                    }

                    CommandDispatcher::Get().Push(cmd);
                }
            }
        } catch (const std::exception& e) {
            std::cerr << "[ROME][JSON] Error parsing commands: " << e.what() << std::endl;
        }
    }

} // namespace ROME
