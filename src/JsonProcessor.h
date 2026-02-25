#ifndef ROME_JSON_PROCESSOR_H
#define ROME_JSON_PROCESSOR_H

#include <string>
#include <vector>
#include "CommandDispatcher.h"

namespace ROME {

    /**
     * @brief Parse a JSON string and push commands into the dispatcher.
     */
    void ParseCommands(const std::string& jsonString);

} // namespace ROME

#endif // ROME_JSON_PROCESSOR_H
