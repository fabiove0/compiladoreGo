"""
GRAMÁTICA SIMPLIFICADA DE GO
============================

Este arquivo descreve QUAIS programas em Go o nosso analisador aceita.
Ele será usado para montar a tabela do parser SLR(1).

COMO LER
--------
Cada regra da gramática é escrita assim:

    Nome da regra:  lista de alternativas

Cada alternativa é uma tupla com os símbolos, em ordem. Exemplo:

    DeclPacote -> package IDENTIFICADOR ;

fica:

    "DeclPacote": [ ("package", "IDENTIFICADOR", ";") ]

Alternativa vazia (a regra pode "não ter nada") é a tupla vazia: ()

TIPOS DE SÍMBOLO
----------------
- NÃO TERMINAL: nome de uma regra desta gramática. Começa com letra
  maiúscula e tem letras minúsculas (ex.: Programa, ComandoIf, ListaExpr).
- TERMINAL: um token que vem do lexer. Pode ser:
    * palavra ou símbolo escrito igual ao código: "if", "+=", "(", ";"
    * nome de uma classe de token, em MAIÚSCULAS: IDENTIFICADOR,
      NUMERO_INTEIRO, NUMERO_REAL, STRING, RUNE

REGRAS DO PROJETO
-----------------
1. A gramática é SLR(1): a tabela gerada não tem conflitos.
2. O lexer coloca o ";" automaticamente no fim das linhas (como o Go faz).
   Por isso os comandos terminam em ";". O último ";" antes de "}" pode
   faltar: { x++ } também vale.
3. Para a tabela SLR não dar conflito, alguns comandos aceitam um pouco
   MAIS do que o Go aceita. Isso será conferido na análise semântica:
     - na esquerda de ":=" só podem ter identificadores
     - a condição do if/for tem que ser uma expressão booleana
     - um comando só de expressão tem que ser uma chamada de função
4. Os operadores seguem as 5 faixas de precedência do Go.
5. O lexer reconhece, mas esta gramática NÃO usa: switch, struct, map,
   interface, chan, type, go, defer, select, goto, range, "<-", "...",
   "~", ":", arrays, ponteiros, import/var/const com parênteses.
"""


# ============================================================
# 1. A GRAMÁTICA
# ============================================================

# Regra por onde a análise começa
SIMBOLO_INICIAL = "Programa"

PRODUCOES = {

    # ---------- Programa completo ----------
    # Um arquivo Go tem: package, depois imports, depois declarações.

    # Programa:  package main  +  imports  +  declarações globais
    "Programa": [
        ("DeclPacote", "ListaImports", "ListaDeclGlobais"),
    ],

    # Exemplo: package main
    "DeclPacote": [
        ("package", "IDENTIFICADOR", ";"),
    ],

    # Zero ou mais imports (lista vazia é permitida)
    "ListaImports": [
        ("ListaImports", "Import"),
        (),
    ],

    # Exemplos: import "fmt"      import f "fmt"
    "Import": [
        ("import", "STRING", ";"),
        ("import", "IDENTIFICADOR", "STRING", ";"),
    ],

    # Zero ou mais declarações globais (cada uma termina em ";")
    "ListaDeclGlobais": [
        ("ListaDeclGlobais", "DeclGlobal", ";"),
        (),
    ],

    # Fora das funções só podem existir: var, const e func
    "DeclGlobal": [
        ("DeclVar",),
        ("DeclConst",),
        ("DeclFuncao",),
    ],

    # ---------- Variáveis e constantes ----------

    # Exemplo: var x int
    "DeclVar": [
        ("var", "EspecVar"),
    ],

    # Exemplos: x int      x int = 5      x = 5      a, b = 1, 2
    "EspecVar": [
        ("ListaIds", "Tipo"),
        ("ListaIds", "Tipo", "=", "ListaExpr"),
        ("ListaIds", "=", "ListaExpr"),
    ],

    # Um ou mais nomes separados por vírgula. Exemplo: a, b, c
    "ListaIds": [
        ("ListaIds", ",", "IDENTIFICADOR"),
        ("IDENTIFICADOR",),
    ],

    # Exemplo: const pi = 3.14
    "DeclConst": [
        ("const", "EspecConst"),
    ],

    # Exemplos: pi = 3.14      n int = 10
    "EspecConst": [
        ("ListaIds", "=", "ListaExpr"),
        ("ListaIds", "Tipo", "=", "ListaExpr"),
    ],

    # ---------- Tipos ----------
    # int, string, bool, float64... chegam do lexer como IDENTIFICADOR.
    # Se o tipo existe mesmo, quem confere é a análise semântica.

    "Tipo": [
        ("IDENTIFICADOR",),
    ],

    # Um ou mais tipos separados por vírgula. Exemplo: int, string
    "ListaTipos": [
        ("ListaTipos", ",", "Tipo"),
        ("Tipo",),
    ],

    # ---------- Funções ----------

    # Exemplo: func soma(a, b int) int { return a + b }
    "DeclFuncao": [
        ("func", "IDENTIFICADOR", "(", "Parametros", ")", "TipoRetorno", "Bloco"),
    ],

    # O que a função devolve: nada, um tipo, ou vários tipos entre parênteses
    #   func f() { }        func f() int { }        func f() (int, int) { }
    "TipoRetorno": [
        (),
        ("Tipo",),
        ("(", "ListaTipos", ")"),
    ],

    # Parâmetros da função (pode não ter nenhum)
    "Parametros": [
        ("ListaParametros",),
        (),
    ],

    "ListaParametros": [
        ("ListaParametros", ",", "Parametro"),
        ("Parametro",),
    ],

    # Exemplos: a int      a, b int   (nomes agrupados com um tipo só)
    "Parametro": [
        ("ListaIds", "Tipo"),
    ],

    # ---------- Bloco e comandos ----------

    # Bloco = comandos entre chaves.
    # A 2ª alternativa permite que o último comando fique sem ";"
    # antes do "}" (ex.: { x++ }), como o Go permite.
    "Bloco": [
        ("{", "ListaComandos", "}"),
        ("{", "ListaComandos", "Comando", "}"),
    ],

    # Zero ou mais comandos, cada um terminando em ";"
    "ListaComandos": [
        ("ListaComandos", "Comando", ";"),
        (),
    ],

    # Tudo o que pode aparecer dentro de um bloco
    "Comando": [
        ("DeclVar",),
        ("DeclConst",),
        ("ComandoSimples",),
        ("ComandoReturn",),
        ("ComandoIf",),
        ("ComandoFor",),
        ("Bloco",),
        ("ComandoBreak",),
        ("ComandoContinue",),
    ],

    # Comando simples (1 linha):
    #   chamada ou expressão:   fmt.Println(x)
    #   declaração curta:       x := 10        a, b := 1, 2
    #   incremento:             x++            x--
    #   atribuição:             x = 5          x += 1
    # Obs.: na esquerda de ":=" usamos ListaExpr (e não ListaIds) para a
    # tabela SLR não dar conflito. Só identificadores são aceitos ali,
    # mas isso é conferido depois, na análise semântica.
    "ComandoSimples": [
        ("ListaExpr",),
        ("ListaExpr", ":=", "ListaExpr"),
        ("Expr", "++"),
        ("Expr", "--"),
        ("Atribuicao",),
    ],

    # Exemplos: x = 1      x += 2      x <<= 1      x &^= 3
    "Atribuicao": [
        ("ListaExpr", "=", "ListaExpr"),
        ("ListaExpr", "+=", "ListaExpr"),
        ("ListaExpr", "-=", "ListaExpr"),
        ("ListaExpr", "*=", "ListaExpr"),
        ("ListaExpr", "/=", "ListaExpr"),
        ("ListaExpr", "%=", "ListaExpr"),
        ("ListaExpr", "&=", "ListaExpr"),
        ("ListaExpr", "|=", "ListaExpr"),
        ("ListaExpr", "^=", "ListaExpr"),
        ("ListaExpr", "<<=", "ListaExpr"),
        ("ListaExpr", ">>=", "ListaExpr"),
        ("ListaExpr", "&^=", "ListaExpr"),
    ],

    # Exemplos: return      return x      return a, b
    "ComandoReturn": [
        ("return",),
        ("return", "ListaExpr"),
    ],

    "ComandoBreak": [
        ("break",),
    ],

    "ComandoContinue": [
        ("continue",),
    ],

    # ---------- if ----------

    # Exemplos:
    #   if x > 0 { }
    #   if x > 0 { } else { }
    #   if x > 0 { } else if x < 0 { } else { }
    "ComandoIf": [
        ("if", "CabecalhoIf", "Bloco"),
        ("if", "CabecalhoIf", "Bloco", "else", "Bloco"),
        ("if", "CabecalhoIf", "Bloco", "else", "ComandoIf"),
    ],

    # O que fica entre "if" e "{":
    #   só a condição:           x > 0
    #   comando + condição:      z := soma(a, b); z > 5
    # (se houver só um comando simples, ele é a condição)
    "CabecalhoIf": [
        ("ComandoSimples",),
        ("ComandoSimples", ";", "Expr"),
    ],

    # ---------- for ----------

    # Exemplos:
    #   for { }                          repete para sempre
    #   for x < 10 { }                   só com condição
    #   for i := 0; i < 10; i++ { }      for completo
    "ComandoFor": [
        ("for", "Bloco"),
        ("for", "ComandoSimples", "Bloco"),
        ("for", "CabecalhoFor", "Bloco"),
    ],

    # for completo:  início ; condição ; passo   (cada parte pode faltar)
    "CabecalhoFor": [
        ("ForInicio", ";", "ForCondicao", ";", "ForPasso"),
    ],

    # ForInicio e ForPasso são iguais, mas separados de propósito: se fosse
    # uma regra só, a tabela SLR daria conflito logo após a palavra "for".
    "ForInicio": [
        ("ComandoSimples",),
        (),
    ],

    "ForPasso": [
        ("ComandoSimples",),
        (),
    ],

    "ForCondicao": [
        ("Expr",),
        (),
    ],

    # ---------- Expressões ----------
    # Da MENOR para a MAIOR precedência (quem fica mais embaixo "gruda"
    # mais forte). Exemplo: em  a + b * c  o produto é feito primeiro.
    #   1) ||      2) &&      3) comparações      4) + - | ^
    #   5) * / % << >> & &^   depois os unários e os valores simples.

    # Uma ou mais expressões separadas por vírgula. Exemplo: 1, x + 2
    "ListaExpr": [
        ("ListaExpr", ",", "Expr"),
        ("Expr",),
    ],

    # Expressão completa = a faixa de menor precedência
    "Expr": [
        ("ExprOu",),
    ],

    # Faixa 1:  a || b
    "ExprOu": [
        ("ExprOu", "||", "ExprE"),
        ("ExprE",),
    ],

    # Faixa 2:  a && b
    "ExprE": [
        ("ExprE", "&&", "ExprComparacao"),
        ("ExprComparacao",),
    ],

    # Faixa 3:  a == b   a != b   a < b   a <= b   a > b   a >= b
    "ExprComparacao": [
        ("ExprComparacao", "==", "ExprSoma"),
        ("ExprComparacao", "!=", "ExprSoma"),
        ("ExprComparacao", "<", "ExprSoma"),
        ("ExprComparacao", "<=", "ExprSoma"),
        ("ExprComparacao", ">", "ExprSoma"),
        ("ExprComparacao", ">=", "ExprSoma"),
        ("ExprSoma",),
    ],

    # Faixa 4:  a + b   a - b   a | b   a ^ b
    "ExprSoma": [
        ("ExprSoma", "+", "ExprProduto"),
        ("ExprSoma", "-", "ExprProduto"),
        ("ExprSoma", "|", "ExprProduto"),
        ("ExprSoma", "^", "ExprProduto"),
        ("ExprProduto",),
    ],

    # Faixa 5:  a * b   a / b   a % b   a << b   a >> b   a & b   a &^ b
    "ExprProduto": [
        ("ExprProduto", "*", "ExprUnaria"),
        ("ExprProduto", "/", "ExprUnaria"),
        ("ExprProduto", "%", "ExprUnaria"),
        ("ExprProduto", "<<", "ExprUnaria"),
        ("ExprProduto", ">>", "ExprUnaria"),
        ("ExprProduto", "&", "ExprUnaria"),
        ("ExprProduto", "&^", "ExprUnaria"),
        ("ExprUnaria",),
    ],

    # Operador na frente:  +x   -x   !x   ^x
    # (em Go, o "não bit a bit" é ^x, e não ~x)
    "ExprUnaria": [
        ("+", "ExprUnaria"),
        ("-", "ExprUnaria"),
        ("!", "ExprUnaria"),
        ("^", "ExprUnaria"),
        ("ExprPrimaria",),
    ],

    # Um valor seguido, opcionalmente, de acessos e chamadas:
    #   fmt.Println     soma(1, 2)     a.b.c(1)(2)     v[i]
    # (v[i] só será útil quando a linguagem tiver arrays.)
    "ExprPrimaria": [
        ("Operando",),
        ("ExprPrimaria", ".", "IDENTIFICADOR"),
        ("ExprPrimaria", "(", "Argumentos", ")"),
        ("ExprPrimaria", "[", "Expr", "]"),
    ],

    # Os valores mais simples: nome, número, texto, caractere ou (expressão)
    "Operando": [
        ("IDENTIFICADOR",),
        ("NUMERO_INTEIRO",),
        ("NUMERO_REAL",),
        ("STRING",),
        ("RUNE",),
        ("(", "Expr", ")"),
    ],

    # O que vai dentro dos parênteses de uma chamada (pode ser nada)
    "Argumentos": [
        ("ListaExpr",),
        (),
    ],
}


# ============================================================
# 2. LIGAÇÃO COM O LEXER
# ============================================================
# O lexer entrega tokens com "tipo" e "lexema". Por exemplo:
#     tipo=PACKAGE           lexema="package"
#     tipo=SOMA_ATRIBUICAO   lexema="+="
#     tipo=IDENTIFICADOR     lexema="idade"
#
# A gramática usa:
#   - o LEXEMA para palavras, operadores e delimitadores ("package", "+=")
#   - o TIPO para identificadores e literais (IDENTIFICADOR, NUMERO_INTEIRO...)
#
# Para fazer essa escolha, o parser chama simbolo_do_token().

# Símbolo que marca o fim da entrada (token EOF do lexer)
FIM_DA_ENTRADA = "$"

# Tipos de token que a gramática usa pelo NOME do tipo
TIPOS_USADOS_PELO_NOME = {
    "IDENTIFICADOR",
    "NUMERO_INTEIRO",
    "NUMERO_REAL",
    "STRING",
    "RUNE",
}


def simbolo_do_token(token):
    """Diz qual símbolo da gramática corresponde a este token."""
    if token.tipo == "EOF":
        return FIM_DA_ENTRADA
    if token.tipo in TIPOS_USADOS_PELO_NOME:
        return token.tipo
    return token.lexema


# Todos os terminais que o lexer sabe produzir. Serve para achar erro de
# digitação: um símbolo fora desta lista quase sempre é um nome de regra
# escrito errado.
TERMINAIS_DO_LEXER = set("""
    break case chan const continue default defer else fallthrough for func
    go goto if import interface map package range return select struct
    switch type var

    && || == != <= >= := += -= *= /= %= &= |= ^= <<= >>= &^=
    << >> &^ <- ++ -- + - * / % = < > ! & | ^ ... ~

    ( ) { } [ ] , ; . :

    IDENTIFICADOR NUMERO_INTEIRO NUMERO_REAL STRING RUNE
""".split())


# ============================================================
# 3. CLASSE GRAMATICA
# ============================================================

class Gramatica:
    """Guarda a gramática e oferece funções para consultá-la e validá-la."""

    def __init__(self, producoes, simbolo_inicial):
        self.producoes = producoes
        self.simbolo_inicial = simbolo_inicial

        # Não terminais = nomes das regras (as chaves do dicionário)
        self.nao_terminais = set(producoes)

        # Terminais = símbolos usados nas regras que não são nome de regra
        self.terminais = self._achar_terminais()

        # Lista numerada com todas as produções, na ordem em que aparecem.
        # Cada item é (nome_da_regra, alternativa). O número de cada
        # produção será usado nas ações "reduce" da tabela SLR.
        self.lista_producoes = []
        for nome, alternativas in producoes.items():
            for alternativa in alternativas:
                self.lista_producoes.append((nome, alternativa))

    def _achar_terminais(self):
        terminais = set()
        for alternativas in self.producoes.values():
            for alternativa in alternativas:
                if not isinstance(alternativa, tuple):
                    continue  # alternativa mal escrita: validar() avisa
                for simbolo in alternativa:
                    if simbolo not in self.nao_terminais:
                        terminais.add(simbolo)
        return terminais

    def producoes_de(self, nao_terminal):
        """Devolve as alternativas de uma regra."""
        return self.producoes.get(nao_terminal, [])

    def gramatica_aumentada(self):
        """
        Cria uma cópia da gramática com uma regra nova no início:
            Programa' -> Programa
        O parser SLR precisa dela para saber quando aceitar a entrada.
        """
        novo_inicio = self.simbolo_inicial + "'"
        novas = {novo_inicio: [(self.simbolo_inicial,)]}
        for nome, alternativas in self.producoes.items():
            novas[nome] = list(alternativas)
        return Gramatica(novas, novo_inicio)

    def _regras_alcancaveis(self):
        """Regras que dá para chegar partindo do símbolo inicial."""
        alcancadas = {self.simbolo_inicial}
        a_visitar = [self.simbolo_inicial]
        while a_visitar:
            nome = a_visitar.pop()
            for alternativa in self.producoes.get(nome, []):
                if not isinstance(alternativa, tuple):
                    continue
                for simbolo in alternativa:
                    if simbolo in self.nao_terminais and simbolo not in alcancadas:
                        alcancadas.add(simbolo)
                        a_visitar.append(simbolo)
        return alcancadas

    def validar(self):
        """Procura erros de escrita na gramática. Devolve True se está tudo certo."""
        erros = []

        # 1) O símbolo inicial precisa ser uma regra
        if self.simbolo_inicial not in self.nao_terminais:
            erros.append("O símbolo inicial não existe na gramática.")

        # 2) Toda regra precisa ter alternativas, e cada uma deve ser tupla
        for nome, alternativas in self.producoes.items():
            if not alternativas:
                erros.append(f"A regra {nome} não tem alternativas.")
            for alternativa in alternativas:
                if not isinstance(alternativa, tuple):
                    erros.append(
                        f"Em {nome}: {alternativa!r} não é tupla "
                        "(esqueceu a vírgula no final?)."
                    )

        # 3) Todo terminal precisa existir no lexer
        for simbolo in sorted(self.terminais - TERMINAIS_DO_LEXER, key=str):
            erros.append(
                f"Símbolo desconhecido: {simbolo!r} "
                "(nome de regra escrito errado?)."
            )

        # 4) Toda regra precisa ser usada em algum lugar
        if self.simbolo_inicial in self.nao_terminais:
            for nome in sorted(self.nao_terminais - self._regras_alcancaveis()):
                erros.append(f"A regra {nome} nunca é usada.")

        if erros:
            print("\nERROS NA GRAMÁTICA:")
            for erro in erros:
                print(" -", erro)
            return False
        return True

    def mostrar_gramatica(self):
        print("\n========== GRAMÁTICA ==========\n")
        for nome, alternativa in self.lista_producoes:
            lado_direito = " ".join(alternativa) if alternativa else "ε"
            print(f"{nome} -> {lado_direito}")
        print()

    def mostrar_simbolos(self):
        print("\n========== SÍMBOLOS ==========\n")
        print("Símbolo inicial:", self.simbolo_inicial)
        print("\nNão terminais:", ", ".join(sorted(self.nao_terminais)))
        print("\nTerminais:", " ".join(sorted(self.terminais)))
        print()

gramatica = Gramatica(PRODUCOES, SIMBOLO_INICIAL)

