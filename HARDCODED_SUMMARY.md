# Hardcoded Values Audit Summary

## 1. Overview
- **Total hardcoded values found:** 115

## 2. Top 5 Worst Offenders
- `campaigns/gemini-ws-transport.yaml`: 12
- `arsenal/core_arsenal.json`: 8
- `dictator/tools_fs.py`: 4
- `dictator/legion_patches.json`: 4
- `legions/archive/zenith_orchestrator.py`: 4

## 3. Categories
- **Hardcoded Home Directory:** 101
- **Hardcoded /var/www path:** 11
- **Hardcoded NVM path:** 2
- **Localhost URL:** 1

## 4. Recommended Fix Priority
1. **High:** Externalize home directories (`/home/paul-kane/`) using environment variables (e.g., `os.environ.get('HOME')` or `Path.home()`).
2. **High:** Move absolute paths like `/var/www` to `.env` or application configuration files to support different deployment environments.
3. **Medium:** Abstract tool-specific paths (e.g., NVM path) and URLs (`localhost`) behind configuration or discovery mechanisms.
