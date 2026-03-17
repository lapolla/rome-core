# ROME Campaign YAML Schema

This document describes the YAML schema for defining ROME campaigns. A campaign consists of a name and a list of tasks, some of which can depend on others.

## Campaign Structure

A campaign YAML file should adhere to the following top-level structure:

```yaml
name: <string>
tasks:
  - id: <string>
    capability: <string>
    prompt: <string>
    input_files:
      - <string>
      - <string>
    depends_on:
      - <string>
      - <string>
  - # ... more tasks
```

## Field Definitions

### `name` (Required)
- **Type:** String
- **Description:** A unique name for the campaign. This name will be used for identification and logging.

### `tasks` (Required)
- **Type:** List of Task Objects
- **Description:** A list of individual tasks that constitute the campaign. Each task is an object with specific properties.

#### Task Object Fields

Each object in the `tasks` list must have the following fields:

##### `id` (Required)
- **Type:** String
- **Description:** A unique identifier for the task within the campaign. This ID is used for dependency tracking and referencing task results.

##### `capability` (Required)
- **Type:** String
- **Description:** The ROME capability that this task will execute (e.g., `SAFE_SHELL`, `GEMINI_CODE`, `GEMINI_PROMPT`).

##### `prompt` (Required)
- **Type:** String
- **Description:** The main prompt or argument string for the specified capability. This is the core instruction for the task.

##### `input_files` (Optional)
- **Type:** List of Strings
- **Description:** A list of file paths (relative to the ROME root or absolute) that are required as input for the task. Each string in the list should be a path to a file.

##### `depends_on` (Optional)
- **Type:** List of Strings
- **Description:** A list of `id`s of other tasks within the *same campaign* that must complete successfully before this task can start. This establishes the execution order and dependencies between tasks.
  - **Circular dependencies are not allowed and will result in an error.**
  - **All dependencies must refer to tasks defined within the same `tasks` list.**
