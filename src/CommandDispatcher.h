#ifndef ROME_COMMAND_DISPATCHER_H
#define ROME_COMMAND_DISPATCHER_H

#include <deque>
#include <mutex>
#include <condition_variable>
#include <thread>
#include <functional>
#include <string>

namespace ROME {

    /**
     * @brief Represents a command to be executed within the Skyrim engine.
     */
    struct Command {
        enum class Type {
            Raw,    // Console command
            Kill,   // Actor kill
            Follow, // Actor follow
            Face    // Actor face camera
        };

        Type type;
        std::string target; // Actor ID or raw command string
        std::string extra;  // Optional extra data (e.g., target ID for follow)
    };

    /**
     * @brief Singleton class for dispatching commands to the main Skyrim thread.
     */
    class CommandDispatcher {
    public:
        /**
         * @brief Access the singleton instance.
         */
        static CommandDispatcher& Get();

        // Delete copy/move constructors and assignment
        CommandDispatcher(const CommandDispatcher&) = delete;
        CommandDispatcher& operator=(const CommandDispatcher&) = delete;
        CommandDispatcher(CommandDispatcher&&) = delete;
        CommandDispatcher& operator=(CommandDispatcher&&) = delete;

        /**
         * @brief Push a new command into the queue.
         */
        void Push(const Command& cmd);

        /**
         * @brief Start the background processing thread.
         */
        void Start();

        /**
         * @brief Stop the background processing thread.
         */
        void Stop();

        /**
         * @brief Main loop for processing commands.
         */
        void Process();

    private:
        CommandDispatcher();
        ~CommandDispatcher();

        std::deque<Command> m_queue;
        std::mutex m_mutex;
        std::condition_variable m_cv;
        std::jthread m_worker;
        bool m_running;
    };

} // namespace ROME

#endif // ROME_COMMAND_DISPATCHER_H
