#ifndef ROME_COMMAND_HOOKS_H
#define ROME_COMMAND_HOOKS_H

#include <string>

namespace ROME {

    /**
     * @brief Execute a raw console command.
     */
    void ExecuteRaw(const std::string& command);

    /**
     * @brief Execute a kill command on a specific actor.
     */
    void ExecuteKill(const std::string& actorId);

} // namespace ROME

#endif // ROME_COMMAND_HOOKS_H
