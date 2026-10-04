"""Snapshot the resolved local environment; refresh deliberately after installation."""

from importlib.metadata import distributions
from pathlib import Path


def main() -> None:
    excluded = {"datapilot", "pip", "setuptools"}
    packages = {
        f"{distribution.metadata['Name']}=={distribution.version}"
        for distribution in distributions()
        if distribution.metadata["Name"].lower() not in excluded
    }
    header = (
        "# Resolved and tested on Python 3.12; includes development dependencies.\n"
        "# Regenerate intentionally: python -m scripts.lock_dependencies\n"
    )
    Path("requirements.lock").write_text(
        header + "\n".join(sorted(packages, key=str.lower)) + "\n", encoding="utf-8"
    )
    print("requirements.lock atualizado; contém somente nomes e versões de pacotes.")


if __name__ == "__main__":
    main()
