from __future__ import annotations

import re


def validar_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def validar_cpf(cpf: str) -> bool:
    digits = re.sub(r"\D", "", cpf)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for pos in range(9, 11):
        soma = sum(int(digits[i]) * (pos + 1 - i) for i in range(pos))
        esperado = 0 if (soma * 10 % 11) >= 10 else (soma * 10 % 11)
        if int(digits[pos]) != esperado:
            return False
    return True


def validar_campos(campos: dict[str, str]) -> list[str]:
    return [nome for nome, valor in campos.items() if not str(valor).strip()]


def validar_senha(senha: str, minimo: int = 6) -> str | None:
    if len(senha) < minimo:
        return f"A senha deve ter ao menos {minimo} caracteres."
    return None


def formatar_cpf(cpf: str) -> str:
    digits = re.sub(r"\D", "", cpf)
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return cpf


def formatar_telefone(tel: str) -> str:
    digits = re.sub(r"\D", "", tel)
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2]} {digits[3:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return tel
