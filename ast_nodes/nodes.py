# ============================================================
# NÓS DA ÁRVORE SINTÁTICA ABSTRATA (AST)
# ============================================================
#
# Visão geral:
#
#   O parser SLR(1) devolve uma árvore de DERIVAÇÃO (NoArvoreSintatica):
#   ela tem um nó para cada regra da gramática, inclusive as regras só
#   de precedência (Expr -> ExprOu -> ExprE -> ... -> Operando).
#
#   A AST é uma árvore ENXUTA, só com o que importa para as próximas
#   fases (análise semântica e geração de código):
#
#       x + 2 * y      vira      Binaria(+, x, Binaria(*, 2, y))
#
#   Cada classe abaixo corresponde a uma construção da gramática
#   simplificada de Go (parser/grammar.py).

 
 
# ============================================================
# 1. CLASSE BASE
# ============================================================
 
class No:
    """
    Classe base de todos os nós da AST.
 
    As subclasses sobrescrevem:
      - descricao(): texto curto do nó (usado em mostrar());
      - filhos():    lista de (rotulo, no) com os filhos do nó.
    """
 
    def __init__(self, linha=None, coluna=None):
        self.linha = linha
        self.coluna = coluna
 
    def descricao(self):
        """Texto que aparece depois do nome da classe em mostrar()."""
        return ""
 
    def filhos(self):
        """Devolve a lista de (rotulo, no) dos filhos. Padrão: nenhum."""
        return []
 
    def aceitar(self, visitante):
        """
        Padrão Visitor: chama visitante.visitar_<NomeDaClasse>(self).
        Se o visitante não souber tratar este nó, avisa com clareza.
        """
        nome_metodo = "visitar_" + type(self).__name__
        metodo = getattr(visitante, nome_metodo, None)
 
        if metodo is None:
            raise NotImplementedError(
                f"{type(visitante).__name__} não implementa {nome_metodo}()."
            )
 
        return metodo(self)
 
    def mostrar(self, nivel=0, rotulo=None):
        """Imprime a árvore com indentação."""
        espacos = "  " * nivel
        prefixo = f"{rotulo}: " if rotulo else ""
        texto = f"{espacos}{prefixo}{type(self).__name__}"
 
        descricao = self.descricao()
        if descricao:
            texto += f" {descricao}"
 
        # Depois da análise semântica, as expressões mostram o tipo: [int]
        if isinstance(self, Expressao) and self.tipo is not None:
            texto += f" [{self.tipo}]"
 
        print(texto)
 
        for rotulo_filho, filho in self.filhos():
            filho.mostrar(nivel + 1, rotulo_filho)
 
    def __repr__(self):
        return f"{type(self).__name__}({self.descricao()})"
 
 
def _com_rotulos(rotulo, lista):
    """Transforma uma lista de nós em [(rotulo, no), ...]."""
    return [(rotulo, item) for item in lista]
 
 
# ============================================================
# 2. PROGRAMA E DECLARAÇÕES GLOBAIS
# ============================================================
 
class Programa(No):
    """
    Raiz da árvore.
 
        package main
        import "fmt"
        ... declarações globais ...
    """
 
    def __init__(self, pacote, imports, declaracoes, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.pacote = pacote            # str. Exemplo: "main"
        self.imports = imports          # lista de Import
        self.declaracoes = declaracoes  # lista de DeclVar/DeclConst/DeclFuncao
 
    def descricao(self):
        return f"(pacote {self.pacote})"
 
    def filhos(self):
        return (
            _com_rotulos("import", self.imports)
            + _com_rotulos("declaracao", self.declaracoes)
        )
 
 
class Import(No):
    """
    Importação de pacote.
 
        import "fmt"          caminho="fmt"   apelido=None
        import f "fmt"        caminho="fmt"   apelido="f"
    """
 
    def __init__(self, caminho, apelido=None, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.caminho = caminho  # str, SEM as aspas
        self.apelido = apelido  # str ou None
 
    def descricao(self):
        if self.apelido:
            return f"{self.apelido} {self.caminho!r}"
        return repr(self.caminho)
 
 
class DeclVar(No):
    """
    Declaração de variáveis (global ou local).
 
        var x int              nomes=["x"]       tipo=int   valores=[]
        var a, b int = 1, 2    nomes=["a", "b"]  tipo=int   valores=[1, 2]
        var x = 5              nomes=["x"]       tipo=None  valores=[5]
 
    "tipo" é None quando o tipo deve ser inferido do valor.
    """
 
    def __init__(self, nomes, tipo, valores, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.nomes = nomes      # lista de str
        self.tipo = tipo        # Tipo ou None
        self.valores = valores  # lista de expressões (pode ser vazia)
 
        # Preenchido pela análise semântica: um Simbolo por nome
        # (None no lugar de "_").
        self.simbolos = []
 
    def descricao(self):
        return ", ".join(self.nomes)
 
    def filhos(self):
        filhos = []
        if self.tipo is not None:
            filhos.append(("tipo", self.tipo))
        return filhos + _com_rotulos("valor", self.valores)
 
 
class DeclConst(No):
    """
    Declaração de constantes.
 
        const pi = 3.14        nomes=["pi"]  tipo=None  valores=[3.14]
        const n int = 10       nomes=["n"]   tipo=int   valores=[10]
 
    Diferente de var, constante SEMPRE tem valor.
    """
 
    def __init__(self, nomes, tipo, valores, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.nomes = nomes
        self.tipo = tipo
        self.valores = valores
 
        # Preenchido pela análise semântica (um Simbolo por nome).
        self.simbolos = []
 
    def descricao(self):
        return ", ".join(self.nomes)
 
    def filhos(self):
        filhos = []
        if self.tipo is not None:
            filhos.append(("tipo", self.tipo))
        return filhos + _com_rotulos("valor", self.valores)
 
 
class Tipo(No):
    """
    Nome de um tipo: int, string, bool, float64...
 
    A gramática só aceita IDENTIFICADOR como tipo. Se o tipo existe
    mesmo, quem confere é a análise semântica.
    """
 
    def __init__(self, nome, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.nome = nome
 
    def descricao(self):
        return self.nome
 
 
class Parametro(No):
    """
    UM parâmetro de função (nome + tipo).
 
    Na gramática, "a, b int" é um Parametro só com vários nomes. Ao
    montar a AST, expandimos em dois nós: (a, int) e (b, int). Fica
    muito mais simples para a tabela de símbolos.
    """
 
    def __init__(self, nome, tipo, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.nome = nome
        self.tipo = tipo  # Tipo
 
        # Preenchido pela análise semântica.
        self.simbolo = None
 
    def descricao(self):
        return self.nome
 
    def filhos(self):
        return [("tipo", self.tipo)]
 
 
class DeclFuncao(No):
    """
    Declaração de função.
 
        func soma(a, b int) int { return a + b }
 
    "tipos_retorno" é uma lista:
        []              -> func f() { }
        [int]           -> func f() int { }
        [int, string]   -> func f() (int, string) { }
    """
 
    def __init__(self, nome, parametros, tipos_retorno, corpo,
                 linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.nome = nome                    # str
        self.parametros = parametros        # lista de Parametro
        self.tipos_retorno = tipos_retorno  # lista de Tipo
        self.corpo = corpo                  # Bloco
 
        # Preenchido pela análise semântica (Simbolo com a assinatura).
        self.simbolo = None
 
    def descricao(self):
        return self.nome
 
    def filhos(self):
        return (
            _com_rotulos("parametro", self.parametros)
            + _com_rotulos("retorno", self.tipos_retorno)
            + [("corpo", self.corpo)]
        )
 
 
# ============================================================
# 3. BLOCO E COMANDOS
# ============================================================
 
class Bloco(No):
    """Comandos entre chaves: { ... }. Cria um novo escopo."""
 
    def __init__(self, comandos, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.comandos = comandos  # lista de comandos
 
    def filhos(self):
        return _com_rotulos("comando", self.comandos)
 
 
class ComandoExpressao(No):
    """
    Comando que é só uma expressão. Exemplo: fmt.Println(x)
 
    A gramática aceita qualquer expressão aqui; a análise semântica
    deve conferir que é uma chamada de função.
    """
 
    def __init__(self, expressao, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.expressao = expressao
 
    def filhos(self):
        return [("expressao", self.expressao)]
 
 
class DeclaracaoCurta(No):
    """
    Declaração curta com ":=".
 
        x := 10            alvos=[x]     valores=[10]
        a, b := 1, 2       alvos=[a, b]  valores=[1, 2]
 
    "alvos" são Identificador. A gramática aceita qualquer expressão
    à esquerda; a análise semântica deve conferir que são só nomes.
    """
 
    def __init__(self, alvos, valores, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.alvos = alvos      # lista de expressões (Identificador)
        self.valores = valores  # lista de expressões
 
        # Preenchido pela análise semântica: para cada alvo, True se o
        # ":=" CRIOU a variável e False se só reaproveitou uma que já
        # existia no mesmo escopo (ou se é "_").
        self.novos = []
 
    def filhos(self):
        return (
            _com_rotulos("alvo", self.alvos)
            + _com_rotulos("valor", self.valores)
        )
 
 
class Atribuicao(No):
    """
    Atribuição simples ou composta.
 
        x = 5              operador="="
        x += 1             operador="+="
        a, b = b, a        operador="="
    """
 
    def __init__(self, alvos, operador, valores, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.alvos = alvos          # lista de expressões
        self.operador = operador    # str: "=", "+=", "<<=", "&^="...
        self.valores = valores      # lista de expressões
 
    def descricao(self):
        return self.operador
 
    def filhos(self):
        return (
            _com_rotulos("alvo", self.alvos)
            + _com_rotulos("valor", self.valores)
        )
 
 
class IncDec(No):
    """Incremento ou decremento: x++  ou  x--."""
 
    def __init__(self, alvo, operador, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.alvo = alvo            # expressão
        self.operador = operador    # "++" ou "--"
 
    def descricao(self):
        return self.operador
 
    def filhos(self):
        return [("alvo", self.alvo)]
 
 
class Return(No):
    """
    Retorno de função.
 
        return          valores=[]
        return x        valores=[x]
        return a, b     valores=[a, b]
    """
 
    def __init__(self, valores, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.valores = valores  # lista de expressões (pode ser vazia)
 
    def filhos(self):
        return _com_rotulos("valor", self.valores)
 
 
class Break(No):
    """Comando break (só vale dentro de um for)."""
 
 
class Continue(No):
    """Comando continue (só vale dentro de um for)."""
 
 
class If(No):
    """
    Comando if.
 
        if x > 0 { }
        if z := soma(a, b); z > 5 { } else { }
        if x > 0 { } else if x < 0 { } else { }
 
    - inicializacao: comando simples antes do ";" (ou None)
    - condicao:      expressão (deve ser booleana)
    - entao:         Bloco
    - senao:         Bloco (else), If (else if) ou None
    """
 
    def __init__(self, inicializacao, condicao, entao, senao=None,
                 linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.inicializacao = inicializacao
        self.condicao = condicao
        self.entao = entao
        self.senao = senao
 
    def filhos(self):
        filhos = []
        if self.inicializacao is not None:
            filhos.append(("inicializacao", self.inicializacao))
        filhos.append(("condicao", self.condicao))
        filhos.append(("entao", self.entao))
        if self.senao is not None:
            filhos.append(("senao", self.senao))
        return filhos
 
 
class For(No):
    """
    Comando for (as três formas da gramática).
 
        for { }                          tudo None  (laço infinito)
        for x < 10 { }                   só condicao
        for i := 0; i < 10; i++ { }      inicializacao, condicao e passo
 
    Qualquer uma das três partes pode ser None.
    """
 
    def __init__(self, inicializacao, condicao, passo, corpo,
                 linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.inicializacao = inicializacao  # comando simples ou None
        self.condicao = condicao            # expressão ou None
        self.passo = passo                  # comando simples ou None
        self.corpo = corpo                  # Bloco
 
    def filhos(self):
        filhos = []
        if self.inicializacao is not None:
            filhos.append(("inicializacao", self.inicializacao))
        if self.condicao is not None:
            filhos.append(("condicao", self.condicao))
        if self.passo is not None:
            filhos.append(("passo", self.passo))
        filhos.append(("corpo", self.corpo))
        return filhos
 
 
# ============================================================
# 4. EXPRESSÕES
# ============================================================
 
class Expressao(No):
    """
    Classe base das expressões.
 
    "tipo" começa como None e é preenchido pela análise semântica
    (ex.: "int", "float64", "string", "bool"). O gerador de código
    pode usar esse campo para escolher a instrução certa.
    """
 
    def __init__(self, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.tipo = None
 
 
class Identificador(Expressao):
    """Uso de um nome (variável, constante, função ou pacote)."""
 
    def __init__(self, nome, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.nome = nome
 
        # Preenchido pela análise semântica: o Simbolo a que o nome se
        # refere (já resolvendo escopos). O gerador de código usa isto
        # para achar o endereço da variável.
        self.simbolo = None
 
    def descricao(self):
        return self.nome
 
 
class LiteralInteiro(Expressao):
    """
    Número inteiro. Exemplos: 10   0xFF   0b101   1_000
 
    "valor" já vem convertido para int do Python; "texto" guarda o
    lexema original.
    """
 
    def __init__(self, valor, texto=None, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.valor = valor
        self.texto = texto if texto is not None else str(valor)
 
    def descricao(self):
        return self.texto
 
 
class LiteralReal(Expressao):
    """Número real. Exemplos: 3.14   .5   1e6   2.5e-3"""
 
    def __init__(self, valor, texto=None, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.valor = valor  # float
        self.texto = texto if texto is not None else str(valor)
 
    def descricao(self):
        return self.texto
 
 
class LiteralString(Expressao):
    """
    Texto entre aspas duplas.
 
    "valor" é o conteúdo SEM as aspas e com os escapes já
    interpretados (\\n vira quebra de linha de verdade).
    """
 
    def __init__(self, valor, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.valor = valor
 
    def descricao(self):
        return repr(self.valor)
 
 
class LiteralRune(Expressao):
    """
    Caractere entre aspas simples. Exemplo: 'a'
 
    Em Go, rune é um número inteiro (o código Unicode), então "valor"
    guarda o código (int) e "texto" o lexema original.
    """
 
    def __init__(self, valor, texto=None, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.valor = valor  # int
        self.texto = texto if texto is not None else chr(valor)
 
    def descricao(self):
        return self.texto
 
 
class Unaria(Expressao):
    """Operador na frente do operando: +x  -x  !x  ^x"""
 
    def __init__(self, operador, operando, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.operador = operador
        self.operando = operando
 
    def descricao(self):
        return self.operador
 
    def filhos(self):
        return [("operando", self.operando)]
 
 
class Binaria(Expressao):
    """
    Operador entre dois operandos: a + b   a && b   a <= b   a &^ b
 
    A precedência já foi resolvida pela gramática: aqui a árvore
    já tem o formato certo (a + b * c  ->  a + (b * c)).
    """
 
    def __init__(self, operador, esquerda, direita, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.operador = operador
        self.esquerda = esquerda
        self.direita = direita
 
    def descricao(self):
        return self.operador
 
    def filhos(self):
        return [("esquerda", self.esquerda), ("direita", self.direita)]
 
 
class Chamada(Expressao):
    """
    Chamada de função.
 
        soma(1, 2)          funcao=Identificador(soma)
        fmt.Println(x)      funcao=AcessoMembro(fmt, Println)
    """
 
    def __init__(self, funcao, argumentos, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.funcao = funcao            # expressão
        self.argumentos = argumentos    # lista de expressões
 
        # Preenchidos pela análise semântica:
        #   tipos        lista com os tipos devolvidos ([] se não devolve nada)
        #   tipo         "void", o tipo único, ou uma TUPLA de tipos
        #   eh_conversao True em int(x), float64(x), string(x)...
        #   builtin      "fmt.Println" etc. (None para funções do programa)
        self.tipos = []
        self.eh_conversao = False
        self.builtin = None
 
    def filhos(self):
        return (
            [("funcao", self.funcao)]
            + _com_rotulos("argumento", self.argumentos)
        )
 
 
class AcessoMembro(Expressao):
    """Acesso com ponto: fmt.Println  ->  objeto=fmt, membro="Println"."""
 
    def __init__(self, objeto, membro, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.objeto = objeto    # expressão
        self.membro = membro    # str
 
    def descricao(self):
        return f".{self.membro}"
 
    def filhos(self):
        return [("objeto", self.objeto)]
 
 
class Indexacao(Expressao):
    """
    Acesso com colchetes: v[i].
 
    A gramática já aceita, mas só terá utilidade quando a linguagem
    tiver arrays. Por enquanto, a análise semântica pode rejeitar.
    """
 
    def __init__(self, objeto, indice, linha=None, coluna=None):
        super().__init__(linha, coluna)
        self.objeto = objeto
        self.indice = indice
 
    def filhos(self):
        return [("objeto", self.objeto), ("indice", self.indice)]
 
 