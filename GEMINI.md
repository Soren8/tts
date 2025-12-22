# Gemini CLI Instructions

## Environment Management
- **Never run `uv` commands directly** (e.g., `uv add`, `uv run`, `uv sync`). 
- This project is often accessed via WSL while stored on a Windows drive. Running `uv` in WSL causes significant disk bloat in the WSL virtual drive and prevents efficient file linking (hardlinks) across the NTFS/ext4 boundary.
- Instead, identify the necessary `uv` command and **ask the user to run it** in their native Windows environment.
