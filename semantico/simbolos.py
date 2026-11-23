# ============================================================
# TABELA DE SÍMBOLOS E REGRAS DE TIPOS
# ============================================================
#
# Visão geral:
#PILHA DE ESCOPOS:
#
#       escopo 0  universo   int, float64, string, bool, rune, true, false
#       escopo 1  pacote     imports, funções e variáveis globais
#       escopo 2+ blocos     parâmetros, variáveis locais, if, for...
#
#   Buscar um nome começa no escopo mais interno e vai subindo; assim
#   uma variável local "esconde" uma global com o mesmo nome.
#
#   Este arquivo também guarda as REGRAS DE TIPOS (quem converte para
#   quem), porque são usadas pelo analisador semântico e, depois, pelo
#   gerador de código.
#
# CONSTANTES SEM TIPO ("untyped")
# -------------------------------
#   Em Go, o literal 2 não é "int": é uma constante inteira que vira
#   o tipo que o contexto pedir. Por isso isto funciona:
#
#       var f float64 = 2       // 2 vira float64
#       y := f * 2              // 2 vira float64
#       i := 2                  // sem contexto: vira int (tipo padrão)
#
#   Mas misturar variáveis de tipos diferentes dá erro:
#
#       i + f                   // int com float64: erro
#
#   Usamos três tipos internos para isso: "untyped int",
#   "untyped rune" e "untyped float". Ao fim da análise, todas as
#   expressões ficam com um tipo concreto.
#
#   Limitações (simplificações em relação ao Go):
#     - uma constante real só converte para float64 (em Go,
#       "var i int = 2.0" é válido; aqui dá erro);
#     - não se confere se o VALOR da constante cabe no tipo (overflow);
#     - só literais reais são conferidos em int(2.5) (erro de truncamento).
 
 
# ============================================================
# 1. TIPOS
# ============================================================
 
TIPO_INT = "int"
TIPO_FLOAT = "float64"
TIPO_STRING = "string"
TIPO_BOOL = "bool"
TIPO_RUNE = "rune"
 
TIPOS_BASICOS = [TIPO_INT, TIPO_FLOAT, TIPO_STRING, TIPO_BOOL, TIPO_RUNE]
 
TIPOS_NUMERICOS = {TIPO_INT, TIPO_FLOAT, TIPO_RUNE}
TIPOS_INTEIROS = {TIPO_INT, TIPO_RUNE}
 
# Tipos internos (nunca aparecem escritos no código Go)
UNTYPED_INT = "untyped int"
UNTYPED_RUNE = "untyped rune"
UNTYPED_FLOAT = "untyped float"
 
# "erro": a expressão já teve um erro. Operações com ela ficam em
# silêncio para não gerar uma cascata de mensagens repetidas.
TIPO_ERRO = "erro"
 
# "void": chamada de função que não devolve nada
TIPO_VOID = "void"
 
# Marcador interno (NÃO é um tipo da linguagem): devolvido ao analisar
# o alvo "_" de uma atribuição, para dizer "descarte o valor". Nenhum
# nó da AST recebe este valor em .tipo.
TIPO_BRANCO = "_"
 
TIPO_PADRAO = {
    UNTYPED_INT: TIPO_INT,
    UNTYPED_RUNE: TIPO_RUNE,
    UNTYPED_FLOAT: TIPO_FLOAT,
}
 
# Para qual tipo concreto cada constante sem tipo pode virar
CONVERSOES_UNTYPED = {
    UNTYPED_INT: {TIPO_INT, TIPO_FLOAT, TIPO_RUNE},
    UNTYPED_RUNE: {TIPO_INT, TIPO_FLOAT, TIPO_RUNE},
    UNTYPED_FLOAT: {TIPO_FLOAT},
}
 
# Quando duas constantes sem tipo se misturam, vence a "maior"
_RANK_UNTYPED = {UNTYPED_INT: 0, UNTYPED_RUNE: 1, UNTYPED_FLOAT: 2}
 
_NOMES_LEGIVEIS = {
    UNTYPED_INT: "constante inteira",
    UNTYPED_RUNE: "constante rune",
    UNTYPED_FLOAT: "constante real",
    TIPO_VOID: "nada",
}
 
 
def eh_untyped(tipo):
    return tipo in CONVERSOES_UNTYPED
 
 
def eh_numerico(tipo):
    return tipo in TIPOS_NUMERICOS or eh_untyped(tipo)
 
 
def eh_inteiro(tipo):
    return (
        tipo in TIPOS_INTEIROS
        or tipo == UNTYPED_INT
        or tipo == UNTYPED_RUNE
    )
 
 
def tipo_padrao(tipo):
    """Tipo concreto de uma constante sem tipo (int, float64, rune)."""
    return TIPO_PADRAO.get(tipo, tipo)
 
 
def pode_converter(untyped, alvo):
    """Uma constante sem tipo cabe neste tipo concreto?"""
    return alvo in CONVERSOES_UNTYPED.get(untyped, ())
 
 
def atribuivel(origem, alvo):
    """Um valor do tipo 'origem' pode ser guardado em um 'alvo'?"""
    return origem == alvo or (
        eh_untyped(origem) and pode_converter(origem, alvo)
    )
 
 
def unificar(a, b):
    """
    Tipo comum de dois operandos de uma operação, ou None se
    forem incompatíveis.
 
        int   com int            -> int
        int   com untyped int    -> int        (a constante vira int)
        float64 com untyped int  -> float64
        int   com float64        -> None
        untyped int com untyped float -> untyped float
    """
    if a == b:
        return a
 
    a_untyped = eh_untyped(a)
    b_untyped = eh_untyped(b)
 
    if a_untyped and b_untyped:
        return a if _RANK_UNTYPED[a] > _RANK_UNTYPED[b] else b
 
    if a_untyped and pode_converter(a, b):
        return b
 
    if b_untyped and pode_converter(b, a):
        return a
 
    return None
 
 
def nome_tipo(tipo):
    """Nome para mostrar nas mensagens de erro."""
    if isinstance(tipo, tuple):
        return "(" + ", ".join(nome_tipo(t) for t in tipo) + ")"
 
    return _NOMES_LEGIVEIS.get(tipo, tipo)
 
 
# ============================================================
# 2. SÍMBOLOS
# ============================================================
 
class Assinatura:
    """
    Tipo de uma função: parâmetros e retornos.
 
        func soma(a, b int) int    Assinatura(["int", "int"], ["int"])
 
    "variadico" vale None (número fixo de argumentos) ou "any": depois
    dos parâmetros fixos, aceita quantos argumentos quiser, de qualquer
    tipo (é o caso de fmt.Println).
    """
 
    def __init__(self, parametros, retornos, variadico=None):
        self.parametros = parametros
        self.retornos = retornos
        self.variadico = variadico
 
    def __str__(self):
        parametros = list(self.parametros)
 
        if self.variadico:
            parametros.append("...any")
 
        texto = f"func({', '.join(parametros)})"
 
        if len(self.retornos) == 1:
            texto += f" {self.retornos[0]}"
        elif self.retornos:
            texto += f" ({', '.join(self.retornos)})"
 
        return texto
 
 
class Simbolo:
    """
    Um nome declarado no programa.
 
    categoria:
        "var"     variável ou parâmetro      tipo = tipo da variável
        "const"   constante                  tipo = tipo (pode ser untyped)
        "func"    função                     assinatura = Assinatura
        "pacote"  pacote importado           tipo = caminho ("fmt")
        "tipo"    tipo básico (int, string...)
 
    Os campos "usado" e "global_" servem à análise semântica. O gerador
    de código pode acrescentar o que precisar (endereço, deslocamento...)
    diretamente no símbolo, por exemplo: simbolo.endereco = 3.
    """
 
    def __init__(self, nome, categoria, tipo=None, linha=None, coluna=None,
                 assinatura=None, global_=False):
        self.nome = nome
        self.categoria = categoria
        self.tipo = tipo
        self.linha = linha
        self.coluna = coluna
        self.assinatura = assinatura
        self.global_ = global_
        self.usado = False
 
    def __repr__(self):
        if self.categoria == "func":
            return f"Simbolo(func {self.nome} {self.assinatura})"
 
        return f"Simbolo({self.categoria} {self.nome}: {self.tipo})"
 
 
# ============================================================
# 3. TABELA DE SÍMBOLOS
# ============================================================
 
class TabelaSimbolos:
    """
    Pilha de escopos. Cada escopo é um dicionário nome -> Simbolo.
 
    A tabela já NASCE pronta para uso, com dois escopos:
        0  universo  int, float64, string, bool, rune, true, false
        1  pacote    (vazio: imports, funções e globais entram aqui)
    Os escopos de funções e blocos são abertos depois, com
    entrar_escopo(), e fechados com sair_escopo().
    """
 
    # Quantos escopos existem quando se está no nível do pacote
    PROFUNDIDADE_PACOTE = 2
 
    def __init__(self):
        self.escopos = []
 
        # Escopo 0: universo
        self.entrar_escopo()
 
        for nome in TIPOS_BASICOS:
            self.declarar(Simbolo(nome, "tipo"))
 
        for nome in ("true", "false"):
            constante = Simbolo(nome, "const", TIPO_BOOL)
            constante.usado = True
            self.declarar(constante)
 
        # Escopo 1: pacote
        self.entrar_escopo()
 
    @property
    def profundidade(self):
        return len(self.escopos)
 
    @property
    def no_escopo_do_pacote(self):
        """True quando o escopo atual é o do pacote (declarações globais)."""
        return self.profundidade == self.PROFUNDIDADE_PACOTE
 
    def entrar_escopo(self):
        self.escopos.append({})
 
    def sair_escopo(self):
        """
        Remove o escopo do topo e devolve seus símbolos (em ordem).
        Os escopos do universo e do pacote nunca podem ser removidos.
        """
        if self.profundidade <= self.PROFUNDIDADE_PACOTE:
            raise RuntimeError(
                "Não é possível sair do escopo do pacote ou do universo."
            )
 
        return list(self.escopos.pop().values())
 
    def declarar(self, simbolo):
        """
        Declara um símbolo no escopo atual.
 
        Devolve None se deu certo, ou o símbolo ANTERIOR se o nome já
        existia neste mesmo escopo (redeclaração).
        """
        atual = self.escopos[-1]
        anterior = atual.get(simbolo.nome)
 
        if anterior is not None:
            return anterior
 
        atual[simbolo.nome] = simbolo
        return None
 
    def buscar_local(self, nome):
        """Procura só no escopo atual."""
        return self.escopos[-1].get(nome)
 
    def buscar(self, nome):
        """Procura do escopo mais interno para o mais externo."""
        for escopo in reversed(self.escopos):
            if nome in escopo:
                return escopo[nome]
 
        return None
 