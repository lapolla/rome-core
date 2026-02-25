#include "CommandHooks.h"
#include <iostream>
#include "RE/C/Console.h"
#include "RE/A/Actor.h"
#include "RE/T/TESForm.h"

namespace ROME {

    /**
     * @brief Resolve a FormID string to a pointer.
     */
    static RE::Actor* ResolveActor(const std::string& actorId) {
        try {
            RE::FormID formId = std::stoul(actorId, nullptr, 16);
            auto* form = RE::TESForm::LookupByID(formId);
            if (form) {
                auto* actor = form->As<RE::Actor>();
                if (actor && actor->Is3DLoaded()) {
                    return actor;
                }
            }
        } catch (...) {}
        return nullptr;
    }

    void ExecuteRaw(const std::string& command) {
        // Imperial Strike: Execute directly via Console
        auto* console = RE::Console::GetSingleton();
        if (console) {
            RE::Console::ExecuteCommand(command.c_str());
            std::cout << "[ROME][HOOKS] Executed raw: " << command << std::endl;
        }
    }

    void ExecuteKill(const std::string& actorId) {
        // Imperial Strike: Resolve and Kill
        auto* actor = ResolveActor(actorId);
        if (actor) {
            actor->KillImmediate();
            std::cout << "[ROME][HOOKS] Executed kill on: " << actorId << std::endl;
        }
    }

} // namespace ROME
