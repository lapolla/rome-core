#include "CommandDispatcher.h"
#include "CommandHooks.h"
#include <iostream>
#include "SKSE/SKSE.h"

namespace ROME {

    CommandDispatcher& CommandDispatcher::Get() {
        static CommandDispatcher instance;
        return instance;
    }

    CommandDispatcher::CommandDispatcher() : m_running(false) {}

    CommandDispatcher::~CommandDispatcher() {
        Stop();
    }

    void CommandDispatcher::Push(const Command& cmd) {
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            m_queue.push_back(cmd);
        }
        m_cv.notify_one();
    }

    void CommandDispatcher::Start() {
        if (!m_running) {
            m_running = true;
            m_worker = std::jthread(&CommandDispatcher::Process, this);
        }
    }

    void CommandDispatcher::Stop() {
        m_running = false;
        m_cv.notify_all();
        if (m_worker.joinable()) {
            m_worker.join();
        }
    }

    void CommandDispatcher::Process() {
        while (m_running) {
            Command cmd;
            {
                std::unique_lock<std::mutex> lock(m_mutex);
                m_cv.wait(lock, [this] { return !m_queue.empty() || !m_running; });

                if (!m_running && m_queue.empty()) {
                    break;
                }

                cmd = std::move(m_queue.front());
                m_queue.pop_front();
            }

            // Real Imperial Strike: Execute through SKSE Task Queue
            SKSE::GetTaskInterface()->AddTask([cmd]() {
                switch (cmd.type) {
                    case Command::Type::Raw:
                        ExecuteRaw(cmd.target);
                        break;
                    case Command::Type::Kill:
                        ExecuteKill(cmd.target);
                        break;
                    default:
                        break;
                }
            });
        }
    }

} // namespace ROME
