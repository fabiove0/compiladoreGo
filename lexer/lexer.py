from lexer.token import Token
from lexer.errors import ErroLexico


class Lexer:

    # Palavras reservadas da linguagem Go
    PALAVRAS_RESERVADAS = {
        "break": "BREAK",
        "case": "CASE",
        "chan": "CHAN",
        "const": "CONST",
        "continue": "CONTINUE",
        "default": "DEFAULT",
        "defer": "DEFER",
        "else": "ELSE",
        "fallthrough": "FALLTHROUGH",
        "for": "FOR",
        "func": "FUNC",
        "go": "GO",
        "goto": "GOTO",
        "if": "IF",
        "import": "IMPORT",
        "interface": "INTERFACE",
        "map": "MAP",
        "package": "PACKAGE",
        "range": "RANGE",
        "return": "RETURN",
        "select": "SELECT",
        "struct": "STRUCT",
        "switch": "SWITCH",
        "type": "TYPE",
        "var": "VAR"
    }

    # Operadores
    OPERADORES = {
        # Operadores com dois caracteres
        "&&": "E_LOGICO",
        "||": "OU_LOGICO",
        "==": "IGUAL",
        "!=": "DIFERENTE",
        "<=": "MENOR_IGUAL",
        ">=": "MAIOR_IGUAL",
        ":=": "DECLARACAO_ATRIBUICAO",

        "+=": "SOMA_ATRIBUICAO",
        "-=": "SUBTRACAO_ATRIBUICAO",
        "*=": "MULTIPLICACAO_ATRIBUICAO",
        "/=": "DIVISAO_ATRIBUICAO",
        "%=": "MODULO_ATRIBUICAO",

        # Operadores bit a bit compostos
        "&=": "BIT_AND_ATRIBUICAO",
        "|=": "BIT_OR_ATRIBUICAO",
        "^=": "BIT_XOR_ATRIBUICAO",
        "<<=": "DESLOCAMENTO_ESQUERDA_ATRIBUICAO",
        ">>=": "DESLOCAMENTO_DIREITA_ATRIBUICAO",
        "&^=": "BIT_CLEAR_ATRIBUICAO",

        # Outros operadores compostos
        "<<": "DESLOCAMENTO_ESQUERDA",
        ">>": "DESLOCAMENTO_DIREITA",
        "&^": "BIT_CLEAR",
        "<-": "RECEBE",

        "++": "INCREMENTO",
        "--": "DECREMENTO",

        # Operadores com um caractere
        "+": "SOMA",
        "-": "SUBTRACAO",
        "*": "MULTIPLICACAO",
        "/": "DIVISAO",
        "%": "MODULO",
        "=": "ATRIBUICAO",
        "<": "MENOR",
        ">": "MAIOR",
        "!": "NAO_LOGICO",
        "&": "BIT_AND",
        "|": "BIT_OR",
        "^": "BIT_XOR",
        "~": "COMPLEMENTO",

        # Reticências
        "...": "RETICENCIAS"
    }

    # Delimitadores
    DELIMITADORES = {
        "(": "ABRE_PARENTESE",
        ")": "FECHA_PARENTESE",
        "{": "ABRE_CHAVE",
        "}": "FECHA_CHAVE",
        "[": "ABRE_COLCHETE",
        "]": "FECHA_COLCHETE",
        ",": "VIRGULA",
        ";": "PONTO_VIRGULA",
        ".": "PONTO",
        ":": "DOIS_PONTOS"
    }

    # Escapes básicos aceitos nas strings
    ESCAPES_VALIDOS = {
        "a", "b", "f", "n", "r", "t", "v", "\\", '"'
    }

    def __init__(self, codigo):

        self.codigo = codigo

        self.posicao = 0

        self.linha = 1
        self.coluna = 1

        self.tokens = []
        self.erros = []

    # Retorna o caractere atual
    def caractere_atual(self):

        if self.posicao >= len(self.codigo):
            return None

        return self.codigo[self.posicao]

    # Retorna um caractere à frente sem avançar
    def olhar_proximo(self):

        if self.posicao + 1 >= len(self.codigo):
            return None

        return self.codigo[self.posicao + 1]

    # Avança uma posição
    def avancar(self):

        if self.posicao >= len(self.codigo):
            return

        caractere = self.codigo[self.posicao]

        self.posicao += 1

        if caractere == "\n":
            self.linha += 1
            self.coluna = 1

        else:
            self.coluna += 1

    # Adiciona um token
    def adicionar_token(self, tipo, lexema, linha, coluna):

        token = Token(tipo, lexema, linha, coluna)

        self.tokens.append(token)

    # Adiciona um erro
    def adicionar_erro(self, mensagem, caractere, linha, coluna):

        erro = ErroLexico(
            mensagem,
            caractere,
            linha,
            coluna
        )

        self.erros.append(erro)

    # Verifica início de identificador
    def eh_inicio_identificador(self, caractere):

        return caractere == "_" or caractere.isalpha()

    # Verifica continuação de identificador
    def eh_parte_identificador(self, caractere):

        return (
            caractere == "_"
            or caractere.isalpha()
            or caractere.isdecimal()
        )

    # Reconhece identificadores e palavras reservadas
    def reconhecer_identificador(self):

        linha_inicial = self.linha
        coluna_inicial = self.coluna

        lexema = ""

        while (
            self.caractere_atual() is not None
            and self.eh_parte_identificador(self.caractere_atual())
        ):

            lexema += self.caractere_atual()

            self.avancar()

        if lexema in self.PALAVRAS_RESERVADAS:

            tipo = self.PALAVRAS_RESERVADAS[lexema]

        else:

            tipo = "IDENTIFICADOR"

        self.adicionar_token(
            tipo,
            lexema,
            linha_inicial,
            coluna_inicial
        )

    # Reconhece números inteiros e reais decimais
    def reconhecer_numero(self):

        linha_inicial = self.linha
        coluna_inicial = self.coluna

        # Verifica números com prefixo de base:
        # hexadecimal (0x), binário (0b) e octal (0o).
        if (
            self.caractere_atual() == "0"
            and self.olhar_proximo() in ("x", "X", "b", "B", "o", "O")
        ):

            inicio = self.posicao

            self.avancar()  # Consome o zero.

            prefixo = self.caractere_atual().lower()
            self.avancar()  # Consome x, b ou o.

            if prefixo == "x":
                digitos_validos = "0123456789abcdefABCDEF"
            elif prefixo == "b":
                digitos_validos = "01"
            else:
                digitos_validos = "01234567"

            inicio_digitos = self.posicao

            # Consome letras, números e "_" para identificar também
            # dígitos inválidos para a base escolhida.
            while (
                self.caractere_atual() is not None
                and (
                    self.caractere_atual().isalnum()
                    or self.caractere_atual() == "_"
                )
            ):
                self.avancar()

            digitos = self.codigo[inicio_digitos:self.posicao]
            lexema = self.codigo[inicio:self.posicao]

            valido = bool(digitos)

            for i, digito in enumerate(digitos):
                if digito == "_":
                    if (
                        i == 0
                        or i == len(digitos) - 1
                        or digitos[i - 1] not in digitos_validos
                        or digitos[i + 1] not in digitos_validos
                    ):
                        valido = False
                elif digito not in digitos_validos:
                    valido = False

            if not valido:
                self.adicionar_erro(
                    "Número inteiro com base ou dígitos inválidos.",
                    lexema,
                    linha_inicial,
                    coluna_inicial
                )

            self.adicionar_token(
                "NUMERO_INTEIRO",
                lexema,
                linha_inicial,
                coluna_inicial
            )

            return

        lexema = ""

        eh_real = False

        # Caso comece com ponto, como .5
        if self.caractere_atual() == ".":

            eh_real = True

            lexema += self.caractere_atual()
            self.avancar()

        # Lê os dígitos antes do ponto
        while (
            self.caractere_atual() is not None
            and self.caractere_atual().isdecimal()
        ):

            lexema += self.caractere_atual()
            self.avancar()

        # Verifica se existe parte decimal
        if (
            self.caractere_atual() == "."
            and not eh_real
        ):

            eh_real = True

            lexema += self.caractere_atual()
            self.avancar()

            while (
                self.caractere_atual() is not None
                and self.caractere_atual().isdecimal()
            ):

                lexema += self.caractere_atual()
                self.avancar()

        # Verifica se existe expoente: 1e6, 2.5e-3
        if self.caractere_atual() in ("e", "E"):

            eh_real = True

            lexema += self.caractere_atual()
            self.avancar()

            # O expoente pode ter sinal
            if self.caractere_atual() in ("+", "-"):

                lexema += self.caractere_atual()
                self.avancar()

            # O expoente precisa ter pelo menos um dígito
            if (
                self.caractere_atual() is None
                or not self.caractere_atual().isdecimal()
            ):

                self.adicionar_erro(
                    "Expoente numérico inválido.",
                    lexema[-1],
                    linha_inicial,
                    coluna_inicial
                )

            else:

                while (
                    self.caractere_atual() is not None
                    and self.caractere_atual().isdecimal()
                ):

                    lexema += self.caractere_atual()
                    self.avancar()

        if eh_real:
            tipo = "NUMERO_REAL"

        else:
            tipo = "NUMERO_INTEIRO"

        self.adicionar_token(
            tipo,
            lexema,
            linha_inicial,
            coluna_inicial
        )

    # Reconhece operadores
    def reconhecer_operador(self):

        linha_inicial = self.linha
        coluna_inicial = self.coluna

        # Tenta reconhecer os operadores maiores primeiro
        operadores_ordenados = sorted(
            self.OPERADORES.keys(),
            key=len,
            reverse=True
        )

        for operador in operadores_ordenados:

            tamanho = len(operador)

            trecho = self.codigo[
                self.posicao:self.posicao + tamanho
            ]

            if trecho == operador:

                tipo = self.OPERADORES[operador]

                self.adicionar_token(
                    tipo,
                    operador,
                    linha_inicial,
                    coluna_inicial
                )

                for i in range(tamanho):
                    self.avancar()

                return

    # Reconhece delimitadores
    def reconhecer_delimitador(self):

        caractere = self.caractere_atual()

        linha_inicial = self.linha
        coluna_inicial = self.coluna

        tipo = self.DELIMITADORES[caractere]

        self.adicionar_token(
            tipo,
            caractere,
            linha_inicial,
            coluna_inicial
        )

        self.avancar()

    # Reconhece comentários
    def reconhecer_comentario(self):

        linha_inicial = self.linha
        coluna_inicial = self.coluna

        # Guarda o segundo caractere para diferenciar // de /*
        segundo_caractere = self.olhar_proximo()

        # Avança os dois caracteres iniciais //
        # ou /*
        inicio_comentario = self.posicao
        self.avancar()
        self.avancar()

        # Comentário de linha
        if segundo_caractere == "/":

            while (
                self.caractere_atual() is not None
                and self.caractere_atual() != "\n"
            ):

                self.avancar()

            return

        # Comentário de bloco
        while self.caractere_atual() is not None:

            if (
                self.caractere_atual() == "*"
                and self.olhar_proximo() == "/"
            ):

                self.avancar()
                self.avancar()

                comentario = self.codigo[inicio_comentario:self.posicao]

                # Comentário de bloco com quebra de linha funciona
                # como uma quebra de linha para a inserção de ";".
                if "\n" in comentario:
                    self.inserir_ponto_virgula()

                return

            self.avancar()

        # Se chegou ao final, o comentário não foi fechado
        self.adicionar_erro(
            "Comentário de bloco não foi fechado.",
            "/*",
            linha_inicial,
            coluna_inicial
        )

    # Reconhece strings entre aspas duplas
    def reconhecer_string(self):

        linha_inicial = self.linha
        coluna_inicial = self.coluna

        lexema = ""

        # Consome a aspa inicial
        lexema += self.caractere_atual()
        self.avancar()

        string_valida = True
        fechou_string = False

        while self.caractere_atual() is not None:

            caractere = self.caractere_atual()

            # Aspas fechando a string
            if caractere == '"':

                lexema += caractere
                self.avancar()

                fechou_string = True
                break

            # String não pode conter quebra de linha
            if caractere == "\n":

                self.adicionar_erro(
                    "String não foi fechada.",
                    '"',
                    linha_inicial,
                    coluna_inicial
                )

                string_valida = False
                break

            # Verifica sequências de escape
            if caractere == "\\":

                self.avancar()

                proximo = self.caractere_atual()
                if proximo == "\n":
                    self.adicionar_erro(
                        "String não foi fechada.",
                        '"',
                        linha_inicial,
                        coluna_inicial
                    )
                    string_valida = False
                    break

                if (
                    proximo is None
                    or proximo not in self.ESCAPES_VALIDOS
                ):

                    self.adicionar_erro(
                        "Sequência de escape inválida.",
                        "\\" + (proximo if proximo is not None else ""),
                        self.linha,
                        self.coluna - 1
                    )

                    string_valida = False

                    if proximo is None:
                        break

                    lexema += "\\" + proximo
                    self.avancar()

                    continue

                lexema += "\\" + proximo
                self.avancar()

                continue

            lexema += caractere
            self.avancar()

        if not fechou_string and string_valida:

            self.adicionar_erro(
                "String não foi fechada.",
                '"',
                linha_inicial,
                coluna_inicial
            )

            string_valida = False

        if fechou_string:

            self.adicionar_token(
                "STRING",
                lexema,
                linha_inicial,
                coluna_inicial
            )

    # Reconhece literais Rune entre aspas simples
    def reconhecer_rune(self):

        linha_inicial = self.linha
        coluna_inicial = self.coluna
        inicio = self.posicao

        # Consome a aspa simples inicial
        self.avancar()

        rune_valido = True

        # Não pode haver uma string vazia nem quebra de linha.
        if (
            self.caractere_atual() is None
            or self.caractere_atual() in ("'", "\n")
        ):
            rune_valido = False

        # Verifica uma sequência de escape.
        elif self.caractere_atual() == "\\":
            self.avancar()

            proximo = self.caractere_atual()

            escapes_validos = {
                "a", "b", "f", "n", "r", "t", "v", "\\", "'"
            }

            if proximo in escapes_validos:
                self.avancar()

            # Escape octal de três dígitos, por exemplo '\\000'.
            elif proximo is not None and proximo in "01234567":
                for i in range(3):
                    if (
                        self.caractere_atual() is not None
                        and self.caractere_atual() in "01234567"
                    ):
                        self.avancar()
                    else:
                        rune_valido = False
                        break

            else:
                rune_valido = False

                if proximo is not None and proximo != "\n":
                    self.avancar()

        else:
            # Consome um caractere comum.
            self.avancar()

        # Verifica a aspa simples de fechamento.
        if self.caractere_atual() == "'":
            self.avancar()
        else:
            rune_valido = False

            # Recuperação simples: procura a aspa de fechamento
            # sem ultrapassar uma quebra de linha.
            while (
                self.caractere_atual() is not None
                and self.caractere_atual() not in ("\n", "'")
            ):
                self.avancar()

            if self.caractere_atual() == "'":
                self.avancar()

        lexema = self.codigo[inicio:self.posicao]

        if rune_valido:
            self.adicionar_token(
                "RUNE",
                lexema,
                linha_inicial,
                coluna_inicial
            )
        else:
            self.adicionar_erro(
                "Literal Rune inválido.",
                lexema,
                linha_inicial,
                coluna_inicial
            )

    # Verifica se o último token permite inserção automática de ";"
    def pode_inserir_ponto_virgula(self):

        if not self.tokens:
            return False

        ultimo_token = self.tokens[-1]

        tipos_que_encerram_linha = {
            "IDENTIFICADOR",
            "NUMERO_INTEIRO",
            "NUMERO_REAL",
            "STRING",
            "RUNE"
        }

        if ultimo_token.tipo in tipos_que_encerram_linha:
            return True

        palavras = {
            "BREAK",
            "CONTINUE",
            "FALLTHROUGH",
            "RETURN"
        }

        if ultimo_token.tipo in palavras:
            return True

        if ultimo_token.lexema in ("++", "--", ")", "]", "}"):
            return True

        return False

    # Insere ponto e vírgula automático quando necessário
    def inserir_ponto_virgula(self):

        if self.pode_inserir_ponto_virgula():
            self.adicionar_token(
                "PONTO_VIRGULA",
                ";",
                self.linha,
                self.coluna
            )

    # Executa a análise léxica
    def analisar(self):

        while self.caractere_atual() is not None:

            caractere = self.caractere_atual()

            # Ignora espaços e tabulações
            if caractere in (" ", "\t", "\r"):

                self.avancar()
                continue

            # Quebra de linha: verifica se precisa inserir ";"
            if caractere == "\n":

                self.inserir_ponto_virgula()

                self.avancar()
                continue

            # Comentários
            if (
                caractere == "/"
                and self.olhar_proximo() in ("/", "*")
            ):

                self.reconhecer_comentario()
                continue

            # Strings
            if caractere == '"':

                self.reconhecer_string()
                continue

            # Literais Rune
            if caractere == "'":

                self.reconhecer_rune()
                continue

            # Identificadores e palavras reservadas
            if self.eh_inicio_identificador(caractere):

                self.reconhecer_identificador()
                continue

            # Números inteiros e reais
            if caractere.isdecimal() or (
                caractere == "."
                and self.olhar_proximo() is not None
                and self.olhar_proximo().isdecimal()
            ):

                self.reconhecer_numero()
                continue

            # Operadores
            if any(
                self.codigo.startswith(operador, self.posicao)
                for operador in self.OPERADORES
            ):

                self.reconhecer_operador()
                continue

            # Delimitadores
            if caractere in self.DELIMITADORES:

                self.reconhecer_delimitador()
                continue

            # Caractere inválido
            linha_erro = self.linha
            coluna_erro = self.coluna

            self.adicionar_erro(
                "Caractere inválido.",
                caractere,
                linha_erro,
                coluna_erro
            )

            self.avancar()

        # Insere ponto e vírgula automático no fim do arquivo,
        # caso o último token permita essa inserção.
        self.inserir_ponto_virgula()

        # Token de fim de arquivo
        self.adicionar_token(
            "EOF",
            "",
            self.linha,
            self.coluna
        )

        return self.tokens, self.erros