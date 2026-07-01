from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

TipoCampo = Literal["texto", "inteiro", "decimal", "cpf", "telefone", "email", "data"]
NivelProblema = Literal["erro", "aviso"]

TRANSFORMACOES_DISPONIVEIS: dict[str, str] = {
    "trim":               "Remover espaços extras",
    "titulo":             "Capitalizar (Primeira Letra)",
    "maiusculo":          "MAIÚSCULAS",
    "minusculo":          "minúsculas",
    "remover_acentos":    "Remover acentos",
    "apenas_numeros":     "Apenas números",
    "formatar_cpf":       "Formatar CPF (000.000.000-00)",
    "formatar_telefone":  "Formatar telefone",
    "formatar_decimal_br":"Converter decimal BR (1.234,56 → 1234.56)",
}

TIPOS_CAMPO: dict[str, str] = {
    "texto":    "Texto",
    "inteiro":  "Número inteiro",
    "decimal":  "Número decimal",
    "cpf":      "CPF",
    "telefone": "Telefone",
    "email":    "E-mail",
    "data":     "Data",
}


@dataclass
class Coluna:
    nome_alvo: str
    nome_exibido: str
    tipo: TipoCampo = "texto"
    obrigatorio: bool = True
    transformacoes: list[str] = field(default_factory=lambda: ["trim"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "nome_alvo": self.nome_alvo,
            "nome_exibido": self.nome_exibido,
            "tipo": self.tipo,
            "obrigatorio": self.obrigatorio,
            "transformacoes": self.transformacoes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Coluna:
        return cls(**d)


@dataclass
class Template:
    nome: str
    descricao: str
    colunas: list[Coluna]
    builtin: bool = False

    def salvar(self, pasta: Path) -> Path:
        pasta.mkdir(parents=True, exist_ok=True)
        nome_arquivo = re.sub(r"[^\w\-]", "_", self.nome.lower()) + ".json"
        caminho = pasta / nome_arquivo
        data = {
            "nome": self.nome,
            "descricao": self.descricao,
            "colunas": [c.to_dict() for c in self.colunas],
        }
        caminho.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return caminho

    @classmethod
    def carregar(cls, caminho: Path) -> Template:
        data = json.loads(caminho.read_text(encoding="utf-8"))
        return cls(
            nome=data["nome"],
            descricao=data["descricao"],
            colunas=[Coluna.from_dict(c) for c in data.get("colunas", [])],
            builtin=False,
        )

    def clone(self, novo_nome: str) -> Template:
        return Template(
            nome=novo_nome,
            descricao=self.descricao,
            colunas=[Coluna(**c.to_dict()) for c in self.colunas],
            builtin=False,
        )


@dataclass
class Problema:
    linha: int
    coluna: str
    nivel: NivelProblema
    mensagem: str


@dataclass
class ResultadoOrganizacao:
    cabecalhos: list[str]
    dados: list[list[Any]]
    problemas: list[Problema]
    indices_duplicatas: list[int]
    total_original: int
    mapeamento_usado: dict[str, str]

    @property
    def total_erros(self) -> int:
        return sum(1 for p in self.problemas if p.nivel == "erro")

    @property
    def total_avisos(self) -> int:
        return sum(1 for p in self.problemas if p.nivel == "aviso")

    @property
    def linhas_com_erro(self) -> set[int]:
        return {p.linha for p in self.problemas if p.nivel == "erro"}

    @property
    def linhas_com_aviso(self) -> set[int]:
        return {p.linha for p in self.problemas if p.nivel == "aviso"}

    def problemas_da_linha(self, linha_real: int) -> list[Problema]:
        return [p for p in self.problemas if p.linha == linha_real]


def organizar(
    cabecalhos_fonte: list[str],
    dados_fonte: list[list[Any]],
    template: Template,
    mapeamento: dict[str, str],
    remover_duplicatas: bool = True,
) -> ResultadoOrganizacao:
    problemas: list[Problema] = []
    dados_limpos: list[list[Any]] = []
    idx_fonte = {col: i for i, col in enumerate(cabecalhos_fonte)}

    indices_dup: list[int] = []
    if remover_duplicatas:
        vistos: set[tuple[Any, ...]] = set()
        for i, linha in enumerate(dados_fonte):
            chave = tuple(str(v).strip().lower() for v in linha if v is not None)
            if chave in vistos:
                indices_dup.append(i)
            else:
                vistos.add(chave)

    colunas_efetivas = template.colunas if template.colunas else [
        Coluna(
            nome_alvo=_slugify(h),
            nome_exibido=h,
            tipo="texto",
            obrigatorio=False,
            transformacoes=["trim"],
        )
        for h in cabecalhos_fonte
    ]

    mapeamento_efetivo = mapeamento if template.colunas else {
        _slugify(h): h for h in cabecalhos_fonte
    }

    for row_idx, linha in enumerate(dados_fonte):
        if row_idx in indices_dup:
            continue

        linha_limpa: list[Any] = []
        linha_real = row_idx + 2

        for col in colunas_efetivas:
            nome_fonte = mapeamento_efetivo.get(col.nome_alvo, "")

            if not nome_fonte or nome_fonte not in idx_fonte:
                if col.obrigatorio:
                    problemas.append(Problema(
                        linha=linha_real, coluna=col.nome_exibido,
                        nivel="erro", mensagem="Coluna obrigatória não encontrada no arquivo",
                    ))
                linha_limpa.append(None)
                continue

            valor_raw = linha[idx_fonte[nome_fonte]]
            valor_str = str(valor_raw) if valor_raw is not None else ""
            valor_limpo = _aplicar_transformacoes(valor_str, col.transformacoes)

            if col.obrigatorio and not valor_limpo.strip():
                problemas.append(Problema(
                    linha=linha_real, coluna=col.nome_exibido,
                    nivel="erro", mensagem="Campo obrigatório vazio",
                ))

            valor_final, erro = _converter_tipo(valor_limpo, col.tipo)
            if erro:
                problemas.append(Problema(
                    linha=linha_real, coluna=col.nome_exibido,
                    nivel="aviso" if not col.obrigatorio else "erro",
                    mensagem=erro,
                ))

            linha_limpa.append(valor_final if valor_final is not None else valor_limpo)

        dados_limpos.append(linha_limpa)

    return ResultadoOrganizacao(
        cabecalhos=[c.nome_exibido for c in colunas_efetivas],
        dados=dados_limpos,
        problemas=problemas,
        indices_duplicatas=indices_dup,
        total_original=len(dados_fonte),
        mapeamento_usado=mapeamento_efetivo,
    )


def detectar_mapeamento_automatico(
    cabecalhos_fonte: list[str], colunas_template: list[Coluna]
) -> dict[str, str]:
    mapeamento: dict[str, str] = {}
    slugs_fonte = {_slugify(h): h for h in cabecalhos_fonte}

    for col in colunas_template:
        candidatos = [
            col.nome_alvo,
            col.nome_exibido,
            _slugify(col.nome_exibido),
            col.nome_alvo.replace("_", " "),
        ]
        for cand in candidatos:
            slug = _slugify(cand)
            if slug in slugs_fonte:
                mapeamento[col.nome_alvo] = slugs_fonte[slug]
                break

    return mapeamento


def _aplicar_transformacoes(valor: str, transformacoes: list[str]) -> str:
    for t in transformacoes:
        if t == "trim":
            valor = valor.strip()
        elif t == "titulo":
            valor = valor.title()
        elif t == "maiusculo":
            valor = valor.upper()
        elif t == "minusculo":
            valor = valor.lower()
        elif t == "remover_acentos":
            nfkd = unicodedata.normalize("NFD", valor)
            valor = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
        elif t == "apenas_numeros":
            valor = re.sub(r"\D", "", valor)
        elif t == "formatar_cpf":
            d = re.sub(r"\D", "", valor)
            if len(d) == 11:
                valor = f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
        elif t == "formatar_telefone":
            d = re.sub(r"\D", "", valor)
            if len(d) == 11:
                valor = f"({d[:2]}) {d[2]} {d[3:7]}-{d[7:]}"
            elif len(d) == 10:
                valor = f"({d[:2]}) {d[2:6]}-{d[6:]}"
        elif t == "formatar_decimal_br":
            valor = re.sub(r"\.(?=\d{3})", "", valor).replace(",", ".")
    return valor


def _converter_tipo(valor: str, tipo: TipoCampo) -> tuple[Any, str | None]:
    if not valor.strip():
        return None, None
    if tipo == "inteiro":
        try:
            return int(re.sub(r"[^\d\-]", "", valor) or "0"), None
        except ValueError:
            return None, f"'{valor}' não é um número inteiro válido"
    if tipo == "decimal":
        try:
            return float(valor.replace(".", "").replace(",", ".")), None
        except ValueError:
            return None, f"'{valor}' não é um número decimal válido"
    if tipo == "cpf":
        from utils.validacao import validar_cpf
        if valor and not validar_cpf(valor):
            return valor, f"CPF '{valor}' com dígito verificador inválido"
        return valor, None
    if tipo == "email":
        from utils.validacao import validar_email
        if valor and not validar_email(valor):
            return valor, f"E-mail '{valor}' com formato inválido"
        return valor, None
    return valor, None


def _slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", "", texto)
    return re.sub(r"\s+", "_", texto.strip())


def listar_templates_salvos(pasta: Path) -> list[Template]:
    if not pasta.exists():
        return []
    return [Template.carregar(f) for f in sorted(pasta.glob("*.json"))]


TEMPLATES_BUILTIN: list[Template] = [
    Template(
        nome="Produtos",
        descricao="Importação de produtos para o estoque — Código, Descrição, Valor, Estoque",
        builtin=True,
        colunas=[
            Coluna("cod_produto",    "Código",           "texto",   True,  ["trim", "maiusculo"]),
            Coluna("descricao",      "Descrição",         "texto",   True,  ["trim", "titulo"]),
            Coluna("valor_unitario", "Valor Unit. (R$)",  "decimal", True,  ["trim", "formatar_decimal_br"]),
            Coluna("qtde_estoque",   "Estoque",           "inteiro", True,  ["trim", "apenas_numeros"]),
            Coluna("estoque_minimo", "Estoque Mínimo",    "inteiro", False, ["trim", "apenas_numeros"]),
            Coluna("fornecedor",     "Fornecedor",        "texto",   False, ["trim", "titulo"]),
        ],
    ),
    Template(
        nome="Clientes",
        descricao="Importação de clientes — CPF, Nome, Endereço, Contato",
        builtin=True,
        colunas=[
            Coluna("cpf",      "CPF",      "cpf",    False, ["trim", "formatar_cpf"]),
            Coluna("nome",     "Nome",     "texto",  True,  ["trim", "titulo"]),
            Coluna("endereco", "Endereço", "texto",  False, ["trim", "titulo"]),
            Coluna("contato",  "Contato",  "texto",  False, ["trim", "formatar_telefone"]),
        ],
    ),
    Template(
        nome="Colaboradores",
        descricao="Importação de colaboradores — Usuário, Nome, CPF, E-mail, Cargo",
        builtin=True,
        colunas=[
            Coluna("usuario",  "Usuário",  "texto", True,  ["trim", "minusculo"]),
            Coluna("nome",     "Nome",     "texto", True,  ["trim", "titulo"]),
            Coluna("cpf",      "CPF",      "cpf",   False, ["trim", "formatar_cpf"]),
            Coluna("email",    "E-mail",   "email", False, ["trim", "minusculo"]),
            Coluna("telefone", "Telefone", "texto", False, ["trim", "formatar_telefone"]),
            Coluna("cargo",    "Cargo",    "texto", False, ["trim", "titulo"]),
        ],
    ),
    Template(
        nome="Limpeza Geral",
        descricao="Remove duplicatas e espaços extras de qualquer planilha, sem validação de tipos",
        builtin=True,
        colunas=[],
    ),
]
