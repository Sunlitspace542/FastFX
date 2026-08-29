# Compatibility entry point for running FastFX from this repository.
# Use build_addon.ps1 to create the installable Blender add-on ZIP.
from fastfx import register, unregister


if __name__ == "__main__":
    register()
