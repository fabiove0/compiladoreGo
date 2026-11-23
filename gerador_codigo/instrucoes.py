# ============================================================
# INSTRUÇÕES DA MAQHIPO
# ============================================================
#
# Visão geral:
#
#   O gerador de código não escreve texto direto: ele monta uma LISTA
#   de objetos Instrucao (o array C da MaqHipo). Só no fim essa lista
#   vira texto, uma instrução por linha, no formato que a máquina
#   virtual lê:
#
#       INPP
#       ALME 1
#       CRCT 10
#       CRCT "texto com espacos"
#       ARMZ 0
#       PARA
#
#   O endereço de uma instrução é a posição dela na lista, começando
#   em 0 (igual ao que a máquina virtual faz ao carregar o arquivo).
 
import json
 
 
# ============================================================
# 1. INSTRUÇÕES CONHECIDAS
# ============================================================
 
# Instruções que NÃO recebem argumento
SEM_ARGUMENTO = {
    "INPP", "PARA",
    "SOMA", "SUBT", "MULT", "DIVI", "MODU", "INVE",
    "EBIT", "OUBIT", "XORB", "LIMP", "DESE", "DESD", "NBIT",
    "CONJ", "DISJ", "NEGA",
    "CPME", "CPMA", "CPIG", "CDES", "CPMI", "CMAI",
    "LEIT", "IMPR", "IMPB", "QUEB",
}
 
# Instruções que recebem exatamente 1 argumento
COM_ARGUMENTO = {
    "CRCT", "CRVL", "ARMZ", "CRVF", "ARMF",
    "ALME", "DESM",
    "DSVI", "DSVF",
    "ENPR", "CHPR", "RTPR",
    "CONV", "FMT",
}
 
# Enquanto um endereço de desvio ainda não é conhecido, o argumento
# fica com este valor. Se sobrar algum no final, é bug do gerador.
PENDENTE = "?"
 
 
# ============================================================
# 2. A INSTRUÇÃO
# ============================================================
 
class Instrucao:
    """
    Uma instrução da MaqHipo.
 
        Instrucao("CRCT", "10")      ->  CRCT 10
        Instrucao("SOMA")            ->  SOMA
 
    O argumento é sempre guardado como texto (ou None).
    """
 
    def __init__(self, operacao, argumento=None):
        # upper(): "soma" e "SOMA" viram a mesma instrução
        self.operacao = operacao.upper()
        self.argumento = None if argumento is None else str(argumento)
 
    def validar(self):
        """Confere se a instrução existe e se o argumento está certo."""
        if self.operacao in SEM_ARGUMENTO:
            if self.argumento is not None:
                raise ValueError(f"{self.operacao} não aceita argumento.")
 
        elif self.operacao in COM_ARGUMENTO:
            if self.argumento is None:
                raise ValueError(f"{self.operacao} exige um argumento.")
 
            if self.argumento == PENDENTE:
                raise ValueError(
                    f"{self.operacao} ficou com o endereço sem preencher."
                )
 
        else:
            raise ValueError(f"Instrução desconhecida: {self.operacao}.")
 
    def __str__(self):
        if self.argumento is None:
            return self.operacao
 
        return f"{self.operacao} {self.argumento}"
 
    __repr__ = __str__
 
 
# ============================================================
# 3. TEXTO
# ============================================================
 
def texto_de_string(texto):
    """
    Transforma um texto em um argumento de CRCT: com aspas e com
    escapes (\\n, \\", \\u00e9...). A máquina virtual desfaz isso
    com json.loads.
    """
    return json.dumps(texto, ensure_ascii=True)
 
 
def formatar_programa(instrucoes, com_enderecos=False):
    """
    Devolve o código objeto em texto, uma instrução por linha.
 
    com_enderecos=True acrescenta o endereço de cada instrução como
    comentário (  # 12 ). A máquina virtual ignora comentários, então
    o arquivo continua válido. Ajuda muito a conferir os desvios.
    """
    linhas = []
 
    for endereco, instrucao in enumerate(instrucoes):
        instrucao.validar()
 
        if com_enderecos:
            linhas.append(f"{str(instrucao):<24}# {endereco}")
        else:
            linhas.append(str(instrucao))
 
    return "\n".join(linhas) + "\n"
 
 
def salvar_programa(instrucoes, caminho, com_enderecos=False):
    """Escreve o código objeto no arquivo (por exemplo, programa.obj)."""
    texto = formatar_programa(instrucoes, com_enderecos)
 
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto)
 