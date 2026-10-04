"""Create local secrets once; never print them or overwrite an existing .env."""

import secrets
from pathlib import Path


def main() -> None:
    path = Path(".env")
    if path.exists():
        print(".env já existe; nenhuma alteração realizada.")
        return
    template = Path(".env.example").read_text(encoding="utf-8")
    for role in ("ADMIN", "ANALYTICS", "SEED"):
        template = template.replace(f"REPLACE_WITH_RANDOM_{role}_PASSWORD", secrets.token_hex(24))
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(template)
    print(".env criado com senhas distintas. Não publique nem compartilhe esse arquivo.")


if __name__ == "__main__":
    main()
